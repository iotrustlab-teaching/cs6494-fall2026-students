from __future__ import annotations

import copy
import re
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any

from compiler import ControllerBuild


TICK_MS = 50
SOURCE_VOLTAGE = 120.0
SOURCE_RESISTANCE = 0.2
HEALTHY_RESISTANCE = 16.0
FAULT_RESISTANCE = 0.25
OVERCURRENT_AMPS = 80.0
TRIP_DELAY_MS = 500
SERVICE_TARGET_MS = 1000
CURRENT_LIMIT_DA = 400

DEVICE_MASKS = {"B0": 0x01, "S1": 0x02, "S2": 0x04, "S3": 0x08}
BRANCHES = ("S1", "S2", "S3")
SCENARIOS = {
    "s3_fault": {"label": "S3 maintenance fault", "oos": "S3", "required": ["S1", "S2"]},
    "s2_fault": {"label": "S2 maintenance fault", "oos": "S2", "required": ["S1", "S3"]},
}


@dataclass(frozen=True)
class Command:
    command_id: str
    action: str
    device: str
    authority: str
    generation: int
    submitted_unix_ms: int


class SubstationSimulator:
    def __init__(self, build: ControllerBuild, *, auto_start: bool = True, run_prefix: str = "live") -> None:
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._queue: deque[Command] = deque()
        self._events: deque[dict[str, Any]] = deque(maxlen=1000)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._test_thread: threading.Thread | None = None
        self._event_seq = 0
        self._run_counter = 0
        self._run_prefix = re.sub(r"[^a-zA-Z0-9-]+", "-", run_prefix).strip("-") or "live"
        self._build = build
        self._active_test: dict[str, Any] | None = None
        self._last_test: dict[str, Any] | None = None
        with self._lock:
            self._reset_locked("s3_fault", {})
        if auto_start:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run_loop, name="substation-sim", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread:
            thread.join(timeout=2)
        with self._lock:
            close = getattr(self._build, "close", None)
            if close:
                close()

    def activate_build(self, build: ControllerBuild) -> None:
        with self._lock:
            previous = self._build
            self._build = build
            close = getattr(previous, "close", None)
            if close:
                close()
            self._log_locked(
                "Controller build activated",
                f"Build {build.build_id} will evaluate subsequent close requests.",
                category="build",
                decision="NONE",
                reason="compile-clean build activated",
            )

    def reset(self, scenario: str = "s3_fault", initial_positions: dict[str, bool] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._active_test:
                raise RuntimeError("a regression run is active")
            self._reset_locked(scenario, initial_positions or {})
            return self._snapshot_locked()

    def _reset_locked(self, scenario: str, initial_positions: dict[str, bool]) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario: {scenario}")
        self._run_counter += 1
        self._generation = getattr(self, "_generation", 0) + 1
        self._run_id = f"{self._run_prefix}-{int(time.time())}-{self._run_counter:02d}"
        self._scenario_id = scenario
        self._sim_time_ms = 0
        self._positions = {device: bool(initial_positions.get(device, False)) for device in DEVICE_MASKS}
        self._trip_latched = False
        self._overcurrent_ms = 0
        self._service_ms = 0
        self._safety_violated = False
        self._unsafe_announced = False
        self._service_announced = False
        self._queue.clear()
        self._events.clear()
        self._last_test = None
        self._measurements = self._calculate_measurements_locked()
        self._log_locked(
            "Run reset",
            f"{SCENARIOS[scenario]['label']} loaded with generation {self._generation}.",
            category="reset",
            decision="NONE",
            reason="verified state reset",
        )

    def submit_command(self, action: str, device: str, authority: str = "manual") -> dict[str, Any]:
        action = action.upper().strip()
        device = device.upper().strip()
        authority = authority.strip().lower()
        if action not in {"OPEN", "CLOSE"}:
            raise ValueError("action must be OPEN or CLOSE")
        if device not in DEVICE_MASKS:
            raise ValueError("device must be B0, S1, S2, or S3")
        if authority not in {"manual", "fixed-test", "human-recovery"}:
            raise ValueError("unsupported authority")

        with self._lock:
            command = Command(
                command_id=f"cmd-{uuid.uuid4().hex[:10]}",
                action=action,
                device=device,
                authority=authority,
                generation=self._generation,
                submitted_unix_ms=int(time.time() * 1000),
            )
            self._queue.append(command)
            event = self._log_locked(
                "Request queued",
                f"{authority} submitted {action} {device} to the bounded command queue.",
                category="request",
                request=command,
                decision="PENDING",
                reason="awaiting the next 50 ms controller scan",
            )
            self._condition.notify_all()
            return {"commandId": command.command_id, "event": event}

    def snapshot(self, after_seq: int | None = None) -> dict[str, Any]:
        with self._lock:
            snapshot = self._snapshot_locked()
            if after_seq is not None:
                snapshot["events"] = [event for event in self._events if event["seq"] > after_seq]
            return snapshot

    def wait_for_events(self, after_seq: int, timeout_seconds: float = 15.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            while self._event_seq <= after_seq and not self._stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(timeout=remaining)
            return self.snapshot(after_seq=after_seq)

    def run_test(self, test_id: str) -> dict[str, Any]:
        if test_id not in {"upstream_counterexample", "legitimate_restore", "moved_fault"}:
            raise ValueError("unknown regression test")
        with self._lock:
            if self._active_test:
                raise RuntimeError("a regression run is already active")
            test_run_id = f"test-{uuid.uuid4().hex[:10]}"
            self._active_test = {
                "testRunId": test_run_id,
                "testId": test_id,
                "status": "running",
                "buildId": self._build.build_id,
                "startedUnixMs": int(time.time() * 1000),
            }
            self._test_thread = threading.Thread(
                target=self._run_test_worker,
                args=(test_id, test_run_id),
                name=f"substation-test-{test_id}",
                daemon=True,
            )
            self._test_thread.start()
            return copy.deepcopy(self._active_test)

    def step(self) -> None:
        with self._lock:
            if self._queue:
                self._process_command_locked(self._queue.popleft())
            self._sim_time_ms += TICK_MS
            self._advance_physics_locked()
            self._condition.notify_all()

    def _run_loop(self) -> None:
        next_tick = time.monotonic()
        while not self._stop.is_set():
            next_tick += TICK_MS / 1000.0
            self.step()
            delay = next_tick - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -0.5:
                next_tick = time.monotonic()

    def _process_command_locked(self, command: Command) -> None:
        if command.generation != self._generation:
            self._log_locked(
                "Stale request rejected",
                f"{command.action} {command.device} belongs to generation {command.generation}, not {self._generation}.",
                category="protocol",
                request=command,
                decision="DENY",
                reason="stale generation",
            )
            return

        if command.action == "OPEN":
            allowed = command.authority == "human-recovery" and command.device in BRANCHES and not self._positions["B0"]
            reason = (
                "authorized isolated-branch recovery opening"
                if allowed
                else "OPEN requires human-recovery authority, a branch target, and B0 open"
            )
            self._log_locked(
                "Recovery decision",
                f"The recovery guard {'permits' if allowed else 'rejects'} OPEN {command.device}.",
                category="decision",
                request=command,
                decision="ALLOW" if allowed else "DENY",
                reason=reason,
            )
            if allowed:
                self._positions[command.device] = False
                self._measurements = self._calculate_measurements_locked()
                self._log_locked(
                    "Position feedback",
                    f"{command.device} reports OPEN after the authorized recovery operation.",
                    category="position",
                    request=command,
                    decision="ALLOW",
                    reason="actual device model changed position",
                )
            return

        if self._positions[command.device]:
            self._log_locked(
                "Controller decision",
                f"{command.device} is already closed; the request is an idempotent no-op.",
                category="decision",
                request=command,
                decision="ALLOW",
                reason="target already closed",
            )
            return

        actual_mask = self._position_mask_locked()
        target_mask = DEVICE_MASKS[command.device]
        oos_mask = DEVICE_MASKS[self._scenario["oos"]]
        present_da = round(self._measurements["sourceA"] * 10)
        try:
            result = self._build.evaluate(
                close_requested=True,
                actual_positions=actual_mask,
                target_mask=target_mask,
                out_of_service_mask=oos_mask,
                trip_latched=self._trip_latched,
                present_current_da=present_da,
                current_limit_da=CURRENT_LIMIT_DA,
            )
            allowed = bool(result["allow"])
            reason = (
                f"compiled ST returned TRUE in {result['durationMs']} ms"
                if allowed
                else f"compiled ST returned FALSE in {result['durationMs']} ms"
            )
        except Exception as exc:
            allowed = False
            result = {
                "execution": self._build.manifest.get("execution", "controller-execution-error"),
                "durationMs": None,
            }
            reason = f"fail-closed controller execution error: {exc}"

        self._log_locked(
            "Controller decision",
            f"Compiled ST {'permits' if allowed else 'rejects'} CLOSE {command.device}.",
            category="decision",
            request=command,
            decision="ALLOW" if allowed else "DENY",
            reason=reason,
            controller_result=result,
        )
        if allowed:
            self._positions[command.device] = True
            self._measurements = self._calculate_measurements_locked()
            self._log_locked(
                "Position feedback",
                f"{command.device} reports CLOSED. Electrical state is recomputed from actual positions.",
                category="position",
                request=command,
                decision="ALLOW",
                reason="actual device model changed position",
            )

    def _advance_physics_locked(self) -> None:
        self._measurements = self._calculate_measurements_locked()
        oos = self._scenario["oos"]
        unsafe_now = self._measurements["branches"][oos] > 0.01
        if unsafe_now:
            self._safety_violated = True
            if not self._unsafe_announced:
                self._unsafe_announced = True
                self._log_locked(
                    "Unsafe energization",
                    f"{oos} is energized at {self._measurements['branches'][oos]:.1f} A.",
                    category="physics",
                    decision="NONE",
                    reason="physical oracle detected current in the prohibited section",
                )

        if self._measurements["sourceA"] > OVERCURRENT_AMPS and self._positions["B0"]:
            self._overcurrent_ms += TICK_MS
        else:
            self._overcurrent_ms = 0

        if self._overcurrent_ms >= TRIP_DELAY_MS and self._positions["B0"]:
            self._positions["B0"] = False
            self._trip_latched = True
            self._measurements = self._calculate_measurements_locked()
            self._log_locked(
                "Protection trip",
                f"B0 opened after source current exceeded {OVERCURRENT_AMPS:.0f} A for {TRIP_DELAY_MS} ms.",
                category="protection",
                decision="TRIP",
                reason="independent overcurrent protection",
            )

        required_served = all(self._measurements["branches"][device] > 0.01 for device in self._scenario["required"])
        service_now = required_served and not unsafe_now and not self._trip_latched
        if service_now:
            self._service_ms += TICK_MS
        else:
            self._service_ms = 0
            self._service_announced = False

        if self._service_ms >= SERVICE_TARGET_MS and not self._service_announced:
            self._service_announced = True
            self._log_locked(
                "Service sustained",
                f"Required healthy loads remained served for {SERVICE_TARGET_MS} ms.",
                category="service",
                decision="NONE",
                reason="independent service oracle",
            )

    def _calculate_measurements_locked(self) -> dict[str, Any]:
        branch_currents = {branch: 0.0 for branch in BRANCHES}
        if not self._positions.get("B0", False):
            return {"busV": 0.0, "sourceA": 0.0, "branches": branch_currents}

        conductance = 0.0
        resistances: dict[str, float] = {}
        for branch in BRANCHES:
            if self._positions.get(branch, False):
                resistance = FAULT_RESISTANCE if branch == self._scenario["oos"] else HEALTHY_RESISTANCE
                resistances[branch] = resistance
                conductance += 1.0 / resistance
        if conductance <= 0:
            return {"busV": SOURCE_VOLTAGE, "sourceA": 0.0, "branches": branch_currents}

        bus_voltage = SOURCE_VOLTAGE / (1.0 + SOURCE_RESISTANCE * conductance)
        for branch, resistance in resistances.items():
            branch_currents[branch] = bus_voltage / resistance
        source_current = sum(branch_currents.values())
        return {
            "busV": round(bus_voltage, 3),
            "sourceA": round(source_current, 3),
            "branches": {name: round(value, 3) for name, value in branch_currents.items()},
        }

    def _position_mask_locked(self) -> int:
        return sum(mask for device, mask in DEVICE_MASKS.items() if self._positions[device])

    @property
    def _scenario(self) -> dict[str, Any]:
        return SCENARIOS[self._scenario_id]

    def _mission_locked(self) -> dict[str, Any]:
        required_served = all(self._measurements["branches"][device] > 0.01 for device in self._scenario["required"])
        return {
            "safety": "fail" if self._safety_violated else "pass",
            "protection": "fail" if self._trip_latched else "pass",
            "requiredService": "pass" if required_served and not self._safety_violated else "pending",
            "serviceMs": self._service_ms,
            "serviceTargetMs": SERVICE_TARGET_MS,
        }

    def _log_locked(
        self,
        stage: str,
        description: str,
        *,
        category: str,
        decision: str,
        reason: str,
        request: Command | None = None,
        controller_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._event_seq += 1
        event = {
            "seq": self._event_seq,
            "eventId": f"evt-{self._event_seq:06d}",
            "runId": self._run_id,
            "generation": self._generation,
            "simTimeMs": self._sim_time_ms,
            "wallTimeUnixMs": int(time.time() * 1000),
            "stage": stage,
            "category": category,
            "description": description,
            "request": self._command_payload(request),
            "transport": self._build.manifest.get(
                "protocolMode", "browser command adapter (IEC-104 not active)"
            ),
            "decision": decision,
            "reason": reason,
            "controllerResult": controller_result,
            "buildId": self._build.build_id,
            "sourceSha256": self._build.source_sha256,
            "positions": copy.deepcopy(self._positions),
            "measurements": copy.deepcopy(self._measurements),
            "service": {branch: self._measurements["branches"][branch] > 0.01 for branch in BRANCHES},
            "trip": self._trip_latched,
            "oos": self._scenario["oos"],
            "mission": self._mission_locked(),
        }
        self._events.append(event)
        self._condition.notify_all()
        return copy.deepcopy(event)

    @staticmethod
    def _command_payload(command: Command | None) -> dict[str, Any] | None:
        if not command:
            return None
        return {
            "commandId": command.command_id,
            "action": command.action,
            "device": command.device,
            "authority": command.authority,
            "generation": command.generation,
            "submittedUnixMs": command.submitted_unix_ms,
        }

    def _snapshot_locked(self) -> dict[str, Any]:
        return {
            "mode": "LIVE SIMULATION",
            "controllerMode": self._build.manifest.get(
                "controllerMode", "MATIEC-COMPILED ST FUNCTION"
            ),
            "protocolMode": self._build.manifest.get(
                "protocolMode", "BROWSER ADAPTER; IEC-104 NOT ACTIVE"
            ),
            "runId": self._run_id,
            "generation": self._generation,
            "scenarioId": self._scenario_id,
            "scenario": self._scenario["label"],
            "requiredLoads": list(self._scenario["required"]),
            "simTimeMs": self._sim_time_ms,
            "tickMs": TICK_MS,
            "build": {
                "buildId": self._build.build_id,
                "sourceSha256": self._build.source_sha256,
                "execution": self._build.manifest.get("execution"),
                "preset": self._build.manifest.get("preset"),
            },
            "positions": copy.deepcopy(self._positions),
            "measurements": copy.deepcopy(self._measurements),
            "service": {branch: self._measurements["branches"][branch] > 0.01 for branch in BRANCHES},
            "trip": self._trip_latched,
            "oos": self._scenario["oos"],
            "mission": self._mission_locked(),
            "queueDepth": len(self._queue),
            "latestSeq": self._event_seq,
            "events": copy.deepcopy(list(self._events)),
            "activeTest": copy.deepcopy(self._active_test),
            "lastTest": copy.deepcopy(self._last_test),
        }

    def _run_test_worker(self, test_id: str, test_run_id: str) -> None:
        started = time.monotonic()
        try:
            if test_id == "upstream_counterexample":
                with self._lock:
                    self._reset_locked("s3_fault", {"S3": True})
                    self._active_test = {
                        "testRunId": test_run_id,
                        "testId": test_id,
                        "status": "running",
                        "buildId": self._build.build_id,
                    }
                self._sleep_ticks(2)
                self.submit_command("CLOSE", "B0", "fixed-test")
                self._sleep_ticks(14)
                with self._lock:
                    passed = not self._safety_violated and not self._trip_latched
                    detail = "unsafe upstream energization blocked" if passed else "faulted branch energized or protection tripped"
            elif test_id == "legitimate_restore":
                with self._lock:
                    self._reset_locked("s3_fault", {})
                    self._active_test = {
                        "testRunId": test_run_id,
                        "testId": test_id,
                        "status": "running",
                        "buildId": self._build.build_id,
                    }
                self._sleep_ticks(2)
                self.submit_command("CLOSE", "S1", "fixed-test")
                self._sleep_ticks(2)
                self.submit_command("CLOSE", "S2", "fixed-test")
                self._sleep_ticks(2)
                self.submit_command("CLOSE", "B0", "fixed-test")
                self._sleep_ticks(24)
                with self._lock:
                    passed = self._service_ms >= SERVICE_TARGET_MS and not self._safety_violated and not self._trip_latched
                    detail = "healthy service sustained" if passed else "required healthy service was not sustained"
            else:
                with self._lock:
                    self._reset_locked("s2_fault", {})
                    self._active_test = {
                        "testRunId": test_run_id,
                        "testId": test_id,
                        "status": "running",
                        "buildId": self._build.build_id,
                    }
                self._sleep_ticks(2)
                self.submit_command("CLOSE", "S1", "fixed-test")
                self._sleep_ticks(2)
                self.submit_command("CLOSE", "S3", "fixed-test")
                self._sleep_ticks(2)
                self.submit_command("CLOSE", "B0", "fixed-test")
                self._sleep_ticks(24)
                with self._lock:
                    passed = self._service_ms >= SERVICE_TARGET_MS and not self._safety_violated and not self._trip_latched
                    detail = "repair generalized to the S2 fault" if passed else "moved-fault service or safety property failed"

            with self._lock:
                result = {
                    "testRunId": test_run_id,
                    "testId": test_id,
                    "status": "passed" if passed else "failed",
                    "passed": passed,
                    "detail": detail,
                    "buildId": self._build.build_id,
                    "runId": self._run_id,
                    "durationMs": round((time.monotonic() - started) * 1000),
                    "completedUnixMs": int(time.time() * 1000),
                }
                self._last_test = result
                self._active_test = None
                self._log_locked(
                    "Regression result",
                    f"{test_id} {'PASSED' if passed else 'FAILED'}: {detail}.",
                    category="test",
                    decision="PASS" if passed else "FAIL",
                    reason="fixed regression oracle",
                )
        except Exception as exc:
            with self._lock:
                self._last_test = {
                    "testRunId": test_run_id,
                    "testId": test_id,
                    "status": "error",
                    "passed": False,
                    "detail": str(exc),
                    "buildId": self._build.build_id,
                    "runId": self._run_id,
                    "durationMs": round((time.monotonic() - started) * 1000),
                }
                self._active_test = None

    @staticmethod
    def _sleep_ticks(count: int) -> None:
        time.sleep((TICK_MS * count) / 1000.0)
