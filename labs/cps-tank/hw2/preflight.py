#!/usr/bin/env python3
"""Check that the prepared HW2 environment is ready for student work."""

from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import platform
import shutil
import socket
import subprocess
import sys
import tempfile


HERE = pathlib.Path(__file__).resolve().parent
REQUIRED_FILES = (
    "analyze.sh",
    "run_nominal.sh",
    "run_spoof.sh",
    "run_modbus_nominal.sh",
    "run_modbus_spoof.sh",
    "search.sh",
    "show_evidence.sh",
    "show_network.sh",
    "reset.sh",
    "modbus_reset.py",
    "representations/controller.c",
    "representations/controller.st",
    "REPRESENTATION_MAP.md",
)
SPHERE_ENVIRONMENT = (
    "HW2_INSTANCE_ID",
    "HW2_TEAM_ID",
    "HW2_EXPIRES_UTC",
    "HW2_TRANSPORT",
)

CONTROLLER_ENDPOINT = ("10.42.0.20", 502)


def inspect(require_sphere: bool = False) -> dict:
    checks = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    record(
        "Python 3.9+",
        sys.version_info >= (3, 9),
        platform.python_version(),
    )
    missing = [name for name in REQUIRED_FILES if not (HERE / name).is_file()]
    record(
        "lab files",
        not missing,
        "all present" if not missing else "missing: " + ", ".join(missing),
    )

    writable = True
    detail = "run directory is writable"
    try:
        runs = HERE / "runs"
        runs.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".preflight-", dir=runs):
            pass
    except OSError as error:
        writable = False
        detail = str(error)
    record("evidence output", writable, detail)

    sphere_values = {name: os.environ.get(name, "").strip() for name in SPHERE_ENVIRONMENT}
    sphere_present = all(sphere_values.values())
    if require_sphere:
        transport_ok = sphere_values["HW2_TRANSPORT"] == "modbus_tcp"
        record(
            "prepared SPHERE identity",
            sphere_present and transport_ok,
            (
                f"instance={sphere_values['HW2_INSTANCE_ID']}, "
                f"team={sphere_values['HW2_TEAM_ID']}, "
                f"expires={sphere_values['HW2_EXPIRES_UTC']}, "
                f"transport={sphere_values['HW2_TRANSPORT']}"
                if sphere_present and transport_ok
                else (
                    f"unsupported prepared transport: {sphere_values['HW2_TRANSPORT']}"
                    if sphere_present
                    else "prepared image did not provide "
                    + ", ".join(
                        name for name, value in sphere_values.items() if not value
                    )
                )
            ),
        )
        tools = [name for name in ("tcpdump", "tshark") if shutil.which(name) is None]
        pymodbus_present = importlib.util.find_spec("pymodbus") is not None
        record(
            "industrial network tools",
            not tools and pymodbus_present,
            (
                "pymodbus, tcpdump, and tshark present"
                if not tools and pymodbus_present
                else "missing: "
                + ", ".join(tools + ([] if pymodbus_present else ["pymodbus"]))
            ),
        )
        capture_ready = False
        capture_detail = "tcpdump privilege not checked"
        if not tools:
            try:
                probe = subprocess.run(
                    ["sudo", "-n", shutil.which("tcpdump") or "tcpdump", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                capture_ready = probe.returncode == 0
                capture_detail = (
                    "fixed capture can start without a password prompt"
                    if capture_ready
                    else "prepared capture privilege is missing"
                )
            except (OSError, subprocess.TimeoutExpired):
                capture_detail = "prepared capture privilege is unavailable"
        record("packet capture", capture_ready, capture_detail)
        controller_ready = False
        controller_detail = "OpenPLC endpoint unavailable"
        if sphere_present and transport_ok:
            try:
                with socket.create_connection(CONTROLLER_ENDPOINT, timeout=2):
                    controller_ready = True
                    controller_detail = "OpenPLC Modbus endpoint reachable at 10.42.0.20:502"
            except OSError as error:
                controller_detail = str(error)
        record("OpenPLC Modbus endpoint", controller_ready, controller_detail)
    else:
        record(
            "execution mode",
            True,
            (
                f"prepared SPHERE instance {sphere_values['HW2_INSTANCE_ID']}"
                if sphere_present
                else "local fallback (no SPHERE identity asserted)"
            ),
        )

    return {"ready": all(check["passed"] for check in checks), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-sphere",
        action="store_true",
        help="fail unless the prepared image supplies identity, expiry, and Modbus transport",
    )
    args = parser.parse_args()
    result = inspect(args.require_sphere)
    for check in result["checks"]:
        mark = "PASS" if check["passed"] else "FAIL"
        print(f"[{mark}] {check['name']}: {check['detail']}")
    if result["ready"]:
        print("\nReady. Next: ./analyze.sh")
        return 0
    print("\nNot ready. Give the failed lines to course staff.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
