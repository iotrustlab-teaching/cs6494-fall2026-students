from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compiler import CompileError, InterlockCompiler, PRESETS
from openplc_program import (
    MODBUS_UNIT_ID,
    OPENPLC_IMAGE,
    OPENPLC_SCAN_MS,
    OPENPLC_UPSTREAM_REVISION,
    openplc_program_identity,
    register_manifest,
    render_openplc_program,
)


REQUEST_ADDRESS = 1024
DECISION_ADDRESS = 1031
REQUEST_WORDS = 7
DECISION_WORDS = 3
DEFAULT_DECISION_TIMEOUT_SECONDS = 1.0


def _atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _unit_kwargs(method: Any) -> dict[str, int]:
    parameters = inspect.signature(method).parameters
    if "device_id" in parameters:
        return {"device_id": MODBUS_UNIT_ID}
    if "slave" in parameters:
        return {"slave": MODBUS_UNIT_ID}
    return {}


def _response_ok(response: Any) -> bool:
    return response is not None and not response.isError()


class ModbusDecisionTransport:
    """Fixed OpenPLC request/decision transaction over the HW2 Modbus pattern."""

    def __init__(
        self,
        client: Any,
        *,
        timeout_seconds: float = DEFAULT_DECISION_TIMEOUT_SECONDS,
        reconnect_endpoint: tuple[str, int] | None = None,
    ) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.reconnect_endpoint = reconnect_endpoint
        self._lock = threading.Lock()
        self._sequence = secrets.randbelow(65534) + 1

    @classmethod
    def connect(cls, host: str, port: int) -> "ModbusDecisionTransport":
        client = cls._connect_client(host, port)
        return cls(client, reconnect_endpoint=(host, port))

    @staticmethod
    def _connect_client(host: str, port: int) -> Any:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError as exc:
            raise RuntimeError("OpenPLC mode requires pymodbus==3.8.6") from exc
        client = ModbusTcpClient(host, port=port, timeout=0.5)
        if not client.connect():
            raise ConnectionError(f"OpenPLC Modbus endpoint unavailable at {host}:{port}")
        return client

    def _reconnect(self) -> None:
        if not self.reconnect_endpoint:
            raise ConnectionError("OpenPLC Modbus transport cannot reconnect")
        self.close()
        host, port = self.reconnect_endpoint
        self.client = self._connect_client(host, port)

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close:
            close()

    def evaluate(
        self,
        *,
        close_requested: bool,
        actual_positions: int,
        target_mask: int,
        out_of_service_mask: int,
        trip_latched: bool,
        present_current_da: int,
        current_limit_da: int,
    ) -> dict[str, Any]:
        if not close_requested:
            return {
                "allow": False,
                "durationMs": 0.0,
                "execution": "openplc-v3-modbus-handshake",
                "requestSeq": None,
            }
        with self._lock:
            started = time.perf_counter()
            self._sequence = 1 if self._sequence >= 65535 else self._sequence + 1
            sequence = self._sequence
            request = [
                sequence,
                actual_positions & 0xFF,
                target_mask & 0xFF,
                out_of_service_mask & 0xFF,
                1 if trip_latched else 0,
                max(0, min(65535, present_current_da)),
                max(0, min(65535, current_limit_da)),
            ]
            for attempt in range(2):
                try:
                    return self._evaluate_request(sequence, request, started)
                except Exception:
                    if attempt or not self.reconnect_endpoint:
                        raise
                    self._reconnect()
            raise RuntimeError("OpenPLC decision transaction failed")

    def _evaluate_request(self, sequence: int, request: list[int], started: float) -> dict[str, Any]:
        response = self.client.write_registers(
            REQUEST_ADDRESS,
            request,
            **_unit_kwargs(self.client.write_registers),
        )
        if not _response_ok(response):
            raise RuntimeError("OpenPLC rejected the fixed request register write")

        deadline = time.monotonic() + self.timeout_seconds
        last_heartbeat: int | None = None
        while time.monotonic() < deadline:
            response = self.client.read_holding_registers(
                DECISION_ADDRESS,
                count=DECISION_WORDS,
                **_unit_kwargs(self.client.read_holding_registers),
            )
            if _response_ok(response) and len(response.registers) >= DECISION_WORDS:
                decision, decision_seq, heartbeat = [int(value) for value in response.registers[:3]]
                last_heartbeat = heartbeat
                if decision_seq == sequence:
                    if decision not in (0, 1):
                        raise RuntimeError("OpenPLC returned an invalid decision code")
                    return {
                        "allow": decision == 1,
                        "durationMs": round((time.perf_counter() - started) * 1000, 3),
                        "execution": "openplc-v3-modbus-handshake",
                        "requestSeq": sequence,
                        "decisionSeq": decision_seq,
                        "heartbeat": heartbeat,
                    }
            time.sleep(0.02)
        raise RuntimeError(
            f"OpenPLC decision timed out for request {sequence}; last heartbeat={last_heartbeat}"
        )


@dataclass(frozen=True)
class OpenPLCBuild:
    build_id: str
    source_sha256: str
    source: str
    manifest: dict[str, Any]
    transport: ModbusDecisionTransport

    def evaluate(self, **values: Any) -> dict[str, Any]:
        result = self.transport.evaluate(**values)
        result["buildId"] = self.build_id
        return result

    def close(self) -> None:
        self.transport.close()


class DockerOpenPLCRuntimePool:
    def __init__(
        self,
        root: Path,
        *,
        start_port: int = 15020,
        image: str = OPENPLC_IMAGE,
        docker_command: str = "docker",
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.start_port = start_port
        self.image = image
        self.docker_command = docker_command
        self.registry_path = self.root / "runtime-slots.json"
        self._lock = threading.RLock()

    def compiler_for(self, student_id: str) -> "OpenPLCStudentCompiler":
        with self._lock:
            registry = self._read_registry_locked()
            if student_id not in registry:
                registry[student_id] = len(registry)
                self._write_registry_locked(registry)
            slot = registry[student_id]
        return OpenPLCStudentCompiler(self, student_id, slot)

    def deploy(self, student_id: str, slot: int, build_id: str, program_path: Path) -> tuple[str, int]:
        self._require_docker()
        inspect_result = self._run(["image", "inspect", self.image], timeout=30, allow_failure=True)
        if inspect_result.returncode != 0:
            self._run(["pull", self.image], timeout=600)

        active_path = self.root / student_id / "active-runtime.json"
        active = self._read_json(active_path)
        if active and active.get("buildId") == build_id:
            container = str(active.get("container", ""))
            port = int(active.get("port", 0))
            if container and port and self._container_running(container):
                return container, port

        active_lane = str(active.get("lane", "b")) if active else "b"
        lane = "a" if active_lane == "b" else "b"
        port = self.start_port + (slot * 2) + (0 if lane == "a" else 1)
        base_name = re.sub(r"[^a-z0-9-]+", "-", student_id.lower()).strip("-")[:38]
        container = f"cs6494-substation-{base_name}-{lane}"
        student_root = self.root / student_id
        persistent = student_root / f"openplc-persistent-{lane}"
        persistent.mkdir(parents=True, exist_ok=True)

        self._run(["rm", "-f", container], timeout=30, allow_failure=True)
        command = [
            "run",
            "--detach",
            "--restart",
            "unless-stopped",
            "--name",
            container,
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            "512m",
            "--cpus",
            "1.0",
            "--publish",
            f"127.0.0.1:{port}:502",
            "--env",
            "OPENPLC_PROGRAM=/programs/program.st",
            "--env",
            "OPENPLC_MODBUS_PORT=502",
            "--env",
            f"OPENPLC_SCAN_CYCLE_MS={OPENPLC_SCAN_MS}",
            "--volume",
            f"{program_path.resolve()}:/programs/program.st:ro,Z",
            "--volume",
            f"{persistent.resolve()}:/docker_persistent:Z",
            self.image,
        ]
        self._run(command, timeout=120)
        try:
            self._wait_for_modbus(port, timeout_seconds=180)
        except Exception as exc:
            logs = self._run(["logs", container], timeout=20, allow_failure=True)
            self._run(["rm", "-f", container], timeout=30, allow_failure=True)
            detail = (logs.stdout + logs.stderr).strip()[-4000:]
            raise CompileError("OpenPLC candidate did not become ready", detail) from exc

        new_active = {
            "studentId": student_id,
            "buildId": build_id,
            "container": container,
            "port": port,
            "lane": lane,
            "image": self.image,
            "activatedAtUnixMs": int(time.time() * 1000),
        }
        _atomic_write(active_path, json.dumps(new_active, indent=2) + "\n")
        old_container = str(active.get("container", "")) if active else ""
        if old_container and old_container != container:
            self._run(["rm", "-f", old_container], timeout=30, allow_failure=True)
        return container, port

    def _container_running(self, container: str) -> bool:
        result = self._run(
            ["inspect", "--format", "{{.State.Running}}", container],
            timeout=20,
            allow_failure=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _require_docker(self) -> None:
        if shutil.which(self.docker_command) is None:
            raise RuntimeError("OpenPLC mode requires Docker on the Linux host")

    def _run(
        self,
        arguments: list[str],
        *,
        timeout: int,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [self.docker_command, *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0 and not allow_failure:
            detail = (result.stderr or result.stdout or "Docker command failed").strip()
            raise RuntimeError(detail[-4000:])
        return result

    @staticmethod
    def _wait_for_modbus(port: int, *, timeout_seconds: float) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            client = None
            try:
                client = ModbusDecisionTransport._connect_client("127.0.0.1", port)
                response = client.read_holding_registers(
                    DECISION_ADDRESS,
                    count=DECISION_WORDS,
                    **_unit_kwargs(client.read_holding_registers),
                )
                if _response_ok(response) and len(response.registers) >= DECISION_WORDS:
                    return
                last_error = RuntimeError("OpenPLC returned an incomplete readiness response")
            except Exception as exc:
                last_error = exc
            finally:
                if client is not None:
                    client.close()
            time.sleep(0.25)
        detail = f": {last_error}" if last_error else ""
        raise TimeoutError(f"OpenPLC did not answer Modbus on loopback port {port}{detail}")

    def _read_registry_locked(self) -> dict[str, int]:
        value = self._read_json(self.registry_path)
        slots = value.get("slots", {}) if value else {}
        return {str(student_id): int(slot) for student_id, slot in slots.items()}

    def _write_registry_locked(self, registry: dict[str, int]) -> None:
        _atomic_write(self.registry_path, json.dumps({"version": 1, "slots": registry}, indent=2) + "\n")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {}


class OpenPLCStudentCompiler:
    def __init__(self, pool: DockerOpenPLCRuntimePool, student_id: str, slot: int) -> None:
        self.pool = pool
        self.student_id = student_id
        self.slot = slot
        self.build_root = pool.root / student_id / "builds"
        self.build_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def preset_sources(self) -> dict[str, str]:
        return {name: path.read_text(encoding="utf-8") for name, path in PRESETS.items()}

    def compile_preset(self, name: str) -> OpenPLCBuild:
        sources = self.preset_sources()
        if name not in sources:
            raise CompileError(f"unknown preset: {name}")
        return self.compile(sources[name], preset=name)

    def compile(self, source: str, *, preset: str | None = None) -> OpenPLCBuild:
        source = source.replace("\r\n", "\n").strip() + "\n"
        program = render_openplc_program(source)
        source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
        build_id = f"openplc-{source_sha[:12]}"
        with self._lock:
            build_dir = self.build_root / build_id
            build_dir.mkdir(parents=True, exist_ok=True)
            source_path = build_dir / "CloseInterlock.st"
            program_path = build_dir / "program.st"
            source_path.write_text(source, encoding="utf-8")
            program_path.write_text(program, encoding="utf-8")
            identity = openplc_program_identity(source)
            manifest = {
                "buildId": build_id,
                "sourceSha256": source_sha,
                "preset": preset,
                "execution": "openplc-v3-modbus-handshake",
                "controllerMode": "OPENPLC V3 COMPILED ST RUNTIME",
                "protocolMode": "INTERNAL MODBUS HANDSHAKE; IEC-104 NOT ACTIVE",
                "compiledAtUnixMs": int(time.time() * 1000),
                **identity,
            }
            container, port = self.pool.deploy(self.student_id, self.slot, build_id, program_path)
            manifest.update({"container": container, "loopbackModbusPort": port})
            _atomic_write(build_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")
            transport = ModbusDecisionTransport.connect("127.0.0.1", port)
            return OpenPLCBuild(build_id, source_sha, source, manifest, transport)

    def load(self, build_id: str) -> OpenPLCBuild:
        if not re.fullmatch(r"openplc-[0-9a-f]{12}", build_id):
            raise CompileError("invalid OpenPLC build ID")
        build_dir = self.build_root / build_id
        source_path = build_dir / "CloseInterlock.st"
        program_path = build_dir / "program.st"
        manifest_path = build_dir / "manifest.json"
        if not source_path.is_file() or not program_path.is_file() or not manifest_path.is_file():
            raise CompileError("OpenPLC build not found")
        source = source_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        container, port = self.pool.deploy(self.student_id, self.slot, build_id, program_path)
        manifest.update({"container": container, "loopbackModbusPort": port})
        transport = ModbusDecisionTransport.connect("127.0.0.1", port)
        return OpenPLCBuild(build_id, manifest["sourceSha256"], source, manifest, transport)
