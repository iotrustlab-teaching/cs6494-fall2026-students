from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
TOOLCHAIN_ROOT = PROJECT_ROOT / "toolchain"
IEC2C = TOOLCHAIN_ROOT / "iec2c"
IEC_LIB = TOOLCHAIN_ROOT / "lib"
BUILD_ROOT = PROJECT_ROOT / "runtime" / "builds"
ST_ROOT = PROJECT_ROOT / "st"

PRESETS = {
    "vulnerable": ST_ROOT / "vulnerable.st",
    "target_local": ST_ROOT / "target_local.st",
    "deny_all": ST_ROOT / "deny_all.st",
    "repaired": ST_ROOT / "repaired.st",
}

EXPECTED_INPUTS = {
    "CloseRequested": "BOOL",
    "ActualPositions": "BYTE",
    "TargetMask": "BYTE",
    "OutOfServiceMask": "BYTE",
    "TripLatched": "BOOL",
    "PresentCurrent_dA": "UINT",
    "CurrentLimit_dA": "UINT",
}

FORBIDDEN_TOKENS = {
    "PROGRAM",
    "CONFIGURATION",
    "RESOURCE",
    "TASK",
    "VAR_GLOBAL",
    "VAR_EXTERNAL",
    "AT",
    "REFERENCE",
    "REF_TO",
    "POINTER",
    "WHILE",
    "REPEAT",
    "FOR",
    "JMP",
}


class CompileError(RuntimeError):
    def __init__(self, message: str, diagnostics: str = "") -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class PresetLibrary:
    def preset_sources(self) -> dict[str, str]:
        return {name: path.read_text(encoding="utf-8") for name, path in PRESETS.items()}


@dataclass(frozen=True)
class ControllerBuild:
    build_id: str
    source_sha256: str
    source: str
    executable: Path
    manifest: dict[str, Any]

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
        timeout_seconds: float = 0.25,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            result = subprocess.run(
                [
                    str(self.executable),
                    "1" if close_requested else "0",
                    str(actual_positions & 0xFF),
                    str(target_mask & 0xFF),
                    str(out_of_service_mask & 0xFF),
                    "1" if trip_latched else "0",
                    str(max(0, min(65535, present_current_da))),
                    str(max(0, min(65535, current_limit_da))),
                ],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("compiled controller timed out") from exc

        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "no diagnostics").strip()
            raise RuntimeError(f"compiled controller failed: {detail[:500]}")

        output = result.stdout.strip()
        if output not in {"0", "1"}:
            raise RuntimeError(f"compiled controller returned invalid output: {output[:100]}")

        return {
            "allow": output == "1",
            "durationMs": duration_ms,
            "execution": "matiec-compiled-native-function",
            "buildId": self.build_id,
        }


class InterlockCompiler:
    def __init__(self) -> None:
        self._compile_lock = threading.RLock()
        BUILD_ROOT.mkdir(parents=True, exist_ok=True)
        configured_iec2c = os.environ.get("MATIEC_IEC2C")
        if configured_iec2c:
            self.iec2c = Path(configured_iec2c).expanduser().resolve()
        elif IEC2C.exists():
            self.iec2c = IEC2C
        else:
            system_iec2c = shutil.which("iec2c")
            self.iec2c = Path(system_iec2c) if system_iec2c else IEC2C
        if not self.iec2c.is_file() or not os.access(self.iec2c, os.X_OK):
            raise RuntimeError(
                "matiec iec2c is unavailable; set MATIEC_IEC2C to an executable compiler"
            )

        configured_cc = os.environ.get("CC")
        self.native_cc = configured_cc or shutil.which("cc") or shutil.which("clang")
        if not self.native_cc:
            raise RuntimeError("a C compiler is required; set CC or install cc/clang")

    def preset_sources(self) -> dict[str, str]:
        return PresetLibrary().preset_sources()

    def compile_preset(self, name: str) -> ControllerBuild:
        if name not in PRESETS:
            raise CompileError(f"unknown preset: {name}")
        return self.compile(PRESETS[name].read_text(encoding="utf-8"), preset=name)

    def compile(self, source: str, *, preset: str | None = None) -> ControllerBuild:
        source = source.replace("\r\n", "\n").strip() + "\n"
        self._validate_source(source)
        with self._compile_lock:
            return self._compile_locked(source, preset=preset)

    def _compile_locked(self, source: str, *, preset: str | None = None) -> ControllerBuild:
        source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
        build_id = f"st-{source_sha[:12]}"
        final_dir = BUILD_ROOT / build_id
        manifest_path = final_dir / "manifest.json"
        executable = final_dir / "controller"

        if manifest_path.exists() and executable.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return ControllerBuild(build_id, source_sha, source, executable, manifest)

        with tempfile.TemporaryDirectory(prefix=f".{build_id}-", dir=BUILD_ROOT) as raw_tmp:
            tmp = Path(raw_tmp)
            source_path = tmp / "CloseInterlock.st"
            source_path.write_text(source, encoding="utf-8")

            compile_cmd = [
                str(self.iec2c),
                "-I",
                str(IEC_LIB),
                "-T",
                str(tmp),
                "-f",
                "-l",
                "-p",
                "-r",
                "-R",
                "-a",
                str(source_path),
            ]
            try:
                generated = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=12,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise CompileError("matiec compilation timed out") from exc

            diagnostics = (generated.stdout + "\n" + generated.stderr).strip()
            if generated.returncode != 0 or not (tmp / "POUS.c").exists():
                raise CompileError("Structured Text compilation failed", diagnostics[-5000:])

            runner_source = self._runner_source()
            runner_path = tmp / "runner.c"
            runner_path.write_text(runner_source, encoding="utf-8")
            native = subprocess.run(
                [self.native_cc, "-std=c11", "-O2", str(runner_path), "-o", str(tmp / "controller")],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
                cwd=tmp,
            )
            native_diagnostics = (native.stdout + "\n" + native.stderr).strip()
            if native.returncode != 0:
                raise CompileError("native build failed", native_diagnostics[-5000:])

            os.chmod(tmp / "controller", 0o755)
            generated_sha = hashlib.sha256((tmp / "POUS.c").read_bytes()).hexdigest()
            manifest = {
                "buildId": build_id,
                "sourceSha256": source_sha,
                "generatedCSha256": generated_sha,
                "preset": preset,
                "compiler": "matiec iec2c",
                "compilerExecutable": str(self.iec2c),
                "nativeCompiler": self.native_cc,
                "execution": "matiec-compiled-native-function",
                "controllerMode": "MATIEC-COMPILED ST FUNCTION",
                "protocolMode": "BROWSER ADAPTER; IEC-104 NOT ACTIVE",
                "compiledAtUnixMs": int(time.time() * 1000),
                "compileDiagnostics": diagnostics,
                "nativeDiagnostics": native_diagnostics,
                "inputContract": EXPECTED_INPUTS,
            }
            (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(tmp, final_dir)

        return ControllerBuild(build_id, source_sha, source, executable, manifest)

    @staticmethod
    def load(build_id: str) -> ControllerBuild:
        if not re.fullmatch(r"st-[0-9a-f]{12}", build_id):
            raise CompileError("invalid build ID")
        directory = BUILD_ROOT / build_id
        manifest_path = directory / "manifest.json"
        source_path = directory / "CloseInterlock.st"
        executable = directory / "controller"
        if not (manifest_path.exists() and source_path.exists() and executable.exists()):
            raise CompileError("build not found")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = source_path.read_text(encoding="utf-8")
        return ControllerBuild(build_id, manifest["sourceSha256"], source, executable, manifest)

    @staticmethod
    def _validate_source(source: str) -> None:
        if len(source.encode("utf-8")) > 20_000:
            raise CompileError("source exceeds the 20 KB exercise limit")
        upper = re.sub(r"\(\*.*?\*\)", " ", source.upper(), flags=re.DOTALL)
        if len(re.findall(r"\bFUNCTION\b", upper)) != 1 or len(re.findall(r"\bEND_FUNCTION\b", upper)) != 1:
            raise CompileError("submit exactly one FUNCTION / END_FUNCTION block")
        if not re.search(r"\bFUNCTION\s+CLOSEINTERLOCK\s*:\s*BOOL\b", upper):
            raise CompileError("the function must be named CloseInterlock and return BOOL")
        for token in FORBIDDEN_TOKENS:
            if re.search(rf"\b{re.escape(token)}\b", upper):
                raise CompileError(f"{token} is outside the student edit boundary")
        for name, data_type in EXPECTED_INPUTS.items():
            if not re.search(rf"\b{re.escape(name.upper())}\s*:\s*{data_type}\s*;", upper):
                raise CompileError(f"missing required input declaration: {name} : {data_type}")
        declarations = re.findall(r"\b[A-Z][A-Z0-9_]*\s*:\s*([A-Z][A-Z0-9_]*)\s*(?::=\s*[^;]+)?;", upper)
        unsupported = sorted({item for item in declarations if item not in {"BOOL", "BYTE", "UINT"}})
        if unsupported:
            raise CompileError(f"unsupported data type in exercise sandbox: {', '.join(unsupported)}")

    @staticmethod
    def _runner_source() -> str:
        return r'''#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint8_t BOOL;
typedef uint8_t BYTE;
typedef uint16_t UINT;

#define TRUE 1
#define FALSE 0
#define __BOOL_LITERAL(value) ((BOOL)(value))

#include "POUS.c"

int main(int argc, char **argv) {
  if (argc != 8) return 2;
  BOOL eno = 0;
  BOOL result = CLOSEINTERLOCK(
      1,
      &eno,
      (BOOL)strtoul(argv[1], NULL, 10),
      (BYTE)strtoul(argv[2], NULL, 10),
      (BYTE)strtoul(argv[3], NULL, 10),
      (BYTE)strtoul(argv[4], NULL, 10),
      (BOOL)strtoul(argv[5], NULL, 10),
      (UINT)strtoul(argv[6], NULL, 10),
      (UINT)strtoul(argv[7], NULL, 10));
  printf("%d\n", result ? 1 : 0);
  return 0;
}
'''
