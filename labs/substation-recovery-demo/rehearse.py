from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Any

from compiler import CompileError, InterlockCompiler
from simulator import SERVICE_TARGET_MS, SubstationSimulator


ROOT = Path(__file__).resolve().parent
EVIDENCE_DIR = ROOT / "runtime" / "evidence"


def command(sim: SubstationSimulator, action: str, device: str, authority: str = "fixed-test") -> None:
    sim.submit_command(action, device, authority)
    sim.step()


def capture(sim: SubstationSimulator, case_id: str, property_passed: bool, expectation: str) -> dict[str, Any]:
    state = sim.snapshot()
    return {
        "caseId": case_id,
        "propertyPassed": property_passed,
        "expectation": expectation,
        "runId": state["runId"],
        "generation": state["generation"],
        "build": state["build"],
        "scenario": state["scenario"],
        "oos": state["oos"],
        "positions": state["positions"],
        "measurements": state["measurements"],
        "mission": state["mission"],
        "trip": state["trip"],
        "events": state["events"],
    }


def upstream_case(build_name: str, build: Any) -> dict[str, Any]:
    sim = SubstationSimulator(build, auto_start=False)
    sim.reset("s3_fault", {"S3": True})
    command(sim, "CLOSE", "B0")
    for _ in range(13):
        sim.step()
    state = sim.snapshot()
    passed = state["mission"]["safety"] == "pass" and not state["trip"]
    return capture(sim, f"{build_name}-upstream-counterexample", passed, "unsafe upstream energization must be blocked")


def restoration_case(build_name: str, build: Any, scenario: str = "s3_fault") -> dict[str, Any]:
    sim = SubstationSimulator(build, auto_start=False)
    sim.reset(scenario, {})
    healthy = ["S1", "S3"] if scenario == "s2_fault" else ["S1", "S2"]
    for branch in healthy:
        command(sim, "CLOSE", branch)
    command(sim, "CLOSE", "B0")
    for _ in range((SERVICE_TARGET_MS // 50) - 1):
        sim.step()
    state = sim.snapshot()
    passed = (
        state["mission"]["safety"] == "pass"
        and state["mission"]["protection"] == "pass"
        and state["mission"]["requiredService"] == "pass"
        and state["mission"]["serviceMs"] >= SERVICE_TARGET_MS
    )
    suffix = "moved-fault" if scenario == "s2_fault" else "restoration"
    return capture(sim, f"{build_name}-{suffix}", passed, "required healthy service must be sustained safely")


def main() -> None:
    compiler = InterlockCompiler()
    builds = {name: compiler.compile_preset(name) for name in ("vulnerable", "target_local", "deny_all", "repaired")}
    cases = [
        upstream_case("vulnerable", builds["vulnerable"]),
        upstream_case("target-local", builds["target_local"]),
        restoration_case("deny-all", builds["deny_all"]),
        upstream_case("repaired", builds["repaired"]),
        restoration_case("repaired", builds["repaired"]),
        restoration_case("repaired", builds["repaired"], "s2_fault"),
    ]

    broken = compiler.preset_sources()["repaired"].replace(
        "END_FUNCTION", "CloseInterlock := ;\nEND_FUNCTION"
    )
    compile_error: dict[str, Any]
    try:
        compiler.compile(broken)
        compile_error = {"handled": False, "diagnostics": "invalid source unexpectedly compiled"}
    except CompileError as exc:
        compile_error = {"handled": True, "error": str(exc), "diagnostics": exc.diagnostics}

    expected = {
        "vulnerable-upstream-counterexample": False,
        "target-local-upstream-counterexample": False,
        "deny-all-restoration": False,
        "repaired-upstream-counterexample": True,
        "repaired-restoration": True,
        "repaired-moved-fault": True,
    }
    all_expected = all(case["propertyPassed"] == expected[case["caseId"]] for case in cases) and compile_error["handled"]
    payload = {
        "evidenceMode": "LIVE LOCAL CAPTURE",
        "controllerMode": "MATIEC-COMPILED ST FUNCTION",
        "protocolMode": "BROWSER ADAPTER; IEC-104 NOT ACTIVE",
        "capturedAtUnixMs": int(time.time() * 1000),
        "host": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "allExpectedOutcomesObserved": all_expected,
        "builds": {name: build.manifest for name, build in builds.items()},
        "cases": cases,
        "compileErrorCase": compile_error,
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    destination = EVIDENCE_DIR / "latest-rehearsal.json"
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    for case in cases:
        observed = "PASS" if case["propertyPassed"] else "FAIL"
        expected_label = "PASS" if expected[case["caseId"]] else "FAIL"
        print(f"{case['caseId']}: observed {observed}, expected {expected_label}")
    print(f"compile-error-handled: {compile_error['handled']}")
    print(f"all-expected-outcomes-observed: {all_expected}")
    print(destination)
    if not all_expected:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
