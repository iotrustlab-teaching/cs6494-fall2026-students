#!/usr/bin/env python3
"""Run the HW2 tank cases and emit or validate a standard evidence bundle."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Dict, Iterable, List

HERE = pathlib.Path(__file__).resolve().parent
DEMO = HERE.parent / "cps_tank.py"


def load_demo():
    spec = importlib.util.spec_from_file_location("hw2_cps_tank", DEMO)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {DEMO}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(HERE))
from network_evidence import NETWORK_FIELDS, scan_records  # noqa: E402
from property_oracle import check_bundle  # noqa: E402


SCHEMA_VERSION = "1.1.0"
CASES = {
    "nominal": {"spoof_after": None, "sensor_bias": 0.0},
    "sensor_spoof": {"spoof_after": 8.0, "sensor_bias": -50.0},
}
SPOOF_MINIMUM_LEVEL = 5.0
REQUIRED = {
    "metadata.json",
    "process.csv",
    "observations.csv",
    "controller.csv",
    "actions.csv",
    "timeline.csv",
    "network_trace.csv",
    "messages.jsonl",
    "events.log",
    "property_results.json",
    "oracle_ladder.json",
    "README.txt",
    "manifest.sha256",
}
MODBUS_REQUIRED = {
    "metadata.json",
    "process.csv",
    "observations.csv",
    "controller.csv",
    "actions.csv",
    "timeline.csv",
    "requested_modbus_operations.csv",
    "network.pcap",
    "modbus_trace.csv",
    "events.log",
    "property_results.json",
    "oracle_ladder.json",
    "manifest.sha256",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_csv(path: pathlib.Path, fields: List[str], rows: Iterable[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def default_output(case: str) -> pathlib.Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return HERE / "runs" / f"{case}-{stamp}"


def run_case(
    case: str,
    output: pathlib.Path,
    duration: float = 36.0,
    tick: float = 1.0,
    initial_level: float = 50.0,
) -> pathlib.Path:
    """Execute a fresh deterministic model and package its observations."""

    if case not in CASES:
        raise ValueError(f"unknown case {case!r}; choose from {', '.join(CASES)}")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty bundle {output}")
    output.mkdir(parents=True, exist_ok=True)

    model = load_demo()
    config = CASES[case]
    tank = model.Tank(level=initial_level)
    controller = model.HysteresisController()
    process_rows: List[dict] = []
    observation_rows: List[dict] = []
    controller_rows: List[dict] = []
    action_rows: List[dict] = []
    timeline_rows: List[dict] = []
    network_rows: List[dict] = []
    messages: List[dict] = []
    events = ["0.000 run_start case=" + case]
    attack_logged = False
    violation_logged = False
    previous_valve = None
    transaction_id = 1
    elapsed = 0.0

    while elapsed <= duration + 1e-9:
        attack_active = (
            config["spoof_after"] is not None
            and elapsed >= float(config["spoof_after"])
        )
        honest_report = tank.sensor_reading()
        reported = tank.sensor_reading(float(config["sensor_bias"]) if attack_active else 0.0)
        if attack_active:
            reported = max(SPOOF_MINIMUM_LEVEL, reported)
        valve, reason = controller.decide(reported)
        physical = model.physical_state(tank.level)
        apparent = model.apparent_state(reported)
        source = "inline_network_override" if attack_active else "honest_sensor"

        process_rows.append(
            {
                "elapsed_s": f"{elapsed:.3f}",
                "true_level_pct": f"{tank.level:.3f}",
                "physical_state": physical,
                "inlet_rate_pct_s": f"{tank.inlet_rate:.3f}",
                "drain_rate_pct_s": f"{tank.drain_rate:.3f}",
            }
        )
        observation_rows.append(
            {
                "elapsed_s": f"{elapsed:.3f}",
                "reported_sensor_level_pct": f"{reported:.3f}",
                "controller_input_level_pct": f"{reported:.3f}",
                "observation_source": source,
                "attack_active": str(attack_active).lower(),
                "apparent_state": apparent,
            }
        )
        controller_rows.append(
            {
                "elapsed_s": f"{elapsed:.3f}",
                "controller_input_level_pct": f"{reported:.3f}",
                "valve_command": valve,
                "decision": reason,
            }
        )
        timeline_rows.append(
            {
                "elapsed_s": f"{elapsed:.3f}",
                "true_level_pct": f"{tank.level:.3f}",
                "reported_level_pct": f"{reported:.3f}",
                "controller_decision": reason,
                "valve_command": valve,
                "network_override": str(attack_active).lower(),
                "physical_state": physical,
                "apparent_state": apparent,
            }
        )
        scan = scan_records(
            elapsed,
            transaction_id,
            honest_report,
            reported,
            valve == "OPEN",
            attack_active,
        )
        network_rows.extend(scan)
        transaction_id += len(scan)
        if valve != previous_valve:
            action_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "actuator": "inlet_valve",
                    "command": valve,
                    "reason": reason,
                }
            )
            events.append(f"{elapsed:.3f} valve_command command={valve} reason={reason}")
            previous_valve = valve
        messages.extend(
            [
                {
                    "elapsed_s": elapsed,
                    "direction": "process_to_controller",
                    "payload": {"type": "observation", "sensor_level": reported},
                },
                {
                    "elapsed_s": elapsed,
                    "direction": "controller_to_process",
                    "payload": {"type": "command", "valve": valve},
                },
            ]
        )
        if attack_active and not attack_logged:
            events.append(
                f"{elapsed:.3f} perturbation_start sensor_bias_pct={config['sensor_bias']}"
            )
            attack_logged = True
        if tank.level >= model.HIGH_HIGH_LEVEL and not violation_logged:
            events.append(
                f"{elapsed:.3f} property_violation true_level_pct={tank.level:.3f}"
            )
            violation_logged = True

        tank.advance(valve, tick)
        elapsed += tick

    write_csv(
        output / "process.csv",
        [
            "elapsed_s",
            "true_level_pct",
            "physical_state",
            "inlet_rate_pct_s",
            "drain_rate_pct_s",
        ],
        process_rows,
    )
    write_csv(
        output / "observations.csv",
        [
            "elapsed_s",
            "reported_sensor_level_pct",
            "controller_input_level_pct",
            "observation_source",
            "attack_active",
            "apparent_state",
        ],
        observation_rows,
    )
    write_csv(
        output / "controller.csv",
        ["elapsed_s", "controller_input_level_pct", "valve_command", "decision"],
        controller_rows,
    )
    write_csv(
        output / "actions.csv",
        ["elapsed_s", "actuator", "command", "reason"],
        action_rows,
    )
    write_csv(
        output / "timeline.csv",
        [
            "elapsed_s",
            "true_level_pct",
            "reported_level_pct",
            "controller_decision",
            "valve_command",
            "network_override",
            "physical_state",
            "apparent_state",
        ],
        timeline_rows,
    )
    write_csv(output / "network_trace.csv", NETWORK_FIELDS, network_rows)
    (output / "messages.jsonl").write_text(
        "".join(json.dumps(message, separators=(",", ":")) + "\n" for message in messages),
        encoding="utf-8",
    )
    events.append(f"{duration:.3f} run_end samples={len(process_rows)}")
    (output / "events.log").write_text("\n".join(events) + "\n", encoding="utf-8")
    metadata = {
        "bundle_schema_version": SCHEMA_VERSION,
        "course": "CS 6494",
        "assignment_status": "HW2 student release",
        "case": case,
        "created_utc": utc_now(),
        "model": "labs/cps-tank/cps_tank.py",
        "parameters": {
            "duration_s": duration,
            "tick_s": tick,
            "initial_level_pct": initial_level,
            **config,
        },
        "clock": "deterministic elapsed simulation time; common across all CSV files",
        "layers": [
            "process",
            "observation",
            "controller",
            "actuator",
            "application_message",
            "network_representation",
        ],
        "controller_representations": {
            "python": "labs/cps-tank/cps_tank.py:HysteresisController",
            "c": "labs/cps-tank/hw2/representations/controller.c",
            "structured_text": "labs/cps-tank/hw2/representations/controller.st",
            "contract": "labs/cps-tank/hw2/representations/controller_contract.json",
        },
        "attack_plane": "process_data" if case == "sensor_spoof" else None,
        "network_capture": None,
        "network_capture_note": (
            "network_trace.csv is a deterministic semantic reconstruction of Modbus operations, not a pcap. "
            "Use the documented isolated two-node mode when packet evidence is required."
        ),
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    (output / "README.txt").write_text(BUNDLE_README, encoding="utf-8")
    result = check_bundle(output)
    reported_maximum = max(float(row["reported_sensor_level_pct"]) for row in observation_rows)
    oracle_ladder = {
        "execution_completed": {"verdict": "PASS", "observes": "runner completion"},
        "controller_responsive": {
            "verdict": "PASS" if len(controller_rows) == len(process_rows) else "FAIL",
            "observes": "one controller decision per process sample",
        },
        "reported_state_below_high_high": {
            "verdict": "PASS" if reported_maximum < model.HIGH_HIGH_LEVEL else "FAIL",
            "observes": "reported_sensor_level_pct",
            "maximum_observed_pct": reported_maximum,
        },
        "physical_state_below_high_high": {
            "verdict": result["verdict"],
            "observes": "true_level_pct",
            "maximum_observed_pct": result["maximum_observed_pct"],
        },
        "bounded_claim": "These verdicts describe this finite deterministic model run only.",
    }
    (output / "oracle_ladder.json").write_text(
        json.dumps(oracle_ladder, indent=2) + "\n", encoding="utf-8"
    )
    write_manifest(output)
    print(f"{case}: {result['verdict']} - max true level {result['maximum_observed_pct']:.1f}%")
    print(f"evidence: {output}")
    return output


BUNDLE_README = """CS 6494 HW2 EVIDENCE BUNDLE (schema 1.1.0)

All CSV files use the same deterministic elapsed_s clock.

metadata.json
  Establishes the selected case, model path, parameters, schema, and capture
  limitations. It does not prove that the named code was unchanged.

process.csv
  true_level_pct is state owned by the software physical-process model. It
  establishes simulated physical truth for this execution, not a real tank.

observations.csv
  reported_sensor_level_pct is the observation presented to the controller;
  controller_input_level_pct records the value consumed. Equality between them
  establishes delivery within this model, not uncompromised sensing.

controller.csv
  Establishes the controller input, output command, and decision explanation at
  each step. It does not establish that a physical actuator obeyed the command.

actions.csv
  Establishes command transitions sent to the simulated inlet valve.

timeline.csv
  Joins the primary observation, decision, command, and physical-state fields
  for the default student view. The source files remain authoritative.

network_trace.csv
  Represents the Modbus reads/writes and the isolated inline value override at
  the process/data plane. It is not a pcap and contains no program download.

messages.jsonl
  Establishes the semantic process/controller messages generated by the run.
  It is not packet capture and proves no real network path.

events.log
  Establishes run, perturbation, command-transition, and first-violation timing.

property_results.json
  Evaluates a bounded finite-trace claim over process.csv. A PASS does not prove
  future, universal, or physical-system safety; a FAIL does not by itself prove
  why the violation occurred.

oracle_ladder.json
  Separates execution, responsiveness, reported-state, and physical-state
  verdicts. A green software-level verdict does not imply process safety.

manifest.sha256
  Detects later changes to bundle files. It does not authenticate their origin.
"""


def write_manifest(bundle: pathlib.Path) -> None:
    lines = []
    for path in sorted(bundle.iterdir()):
        if path.name == "manifest.sha256" or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (bundle / "manifest.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_bundle(bundle: pathlib.Path) -> dict:
    if not bundle.is_dir():
        return {"valid": False, "errors": [f"not a bundle directory: {bundle}"]}
    present = {path.name for path in bundle.iterdir() if path.is_file()}
    metadata_path = bundle / "metadata.json"
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata_path.is_file()
        else {}
    )
    is_modbus = metadata.get("transport") == "Modbus TCP"
    required = MODBUS_REQUIRED if is_modbus else REQUIRED
    missing = sorted(required - present)
    errors = [f"missing {name}" for name in missing]
    if missing:
        return {"valid": False, "errors": errors}
    if not is_modbus and metadata.get("bundle_schema_version") != SCHEMA_VERSION:
        errors.append("unsupported bundle schema version")
    if is_modbus and not str(metadata.get("bundle_schema_version", "")).startswith(
        "1.2.0-modbus"
    ):
        errors.append("unsupported Modbus bundle schema version")
    columns = {
        "process.csv": {"elapsed_s", "true_level_pct", "physical_state"},
        "actions.csv": {"elapsed_s", "actuator", "command"},
        "timeline.csv": {"elapsed_s", "true_level_pct", "valve_command"},
    }
    if is_modbus:
        columns.update(
            {
                "observations.csv": {
                    "elapsed_s",
                    "modbus_reported_level_pct",
                    "plc_readback_level_pct",
                    "attack_active",
                },
                "controller.csv": {"elapsed_s", "plc_input_level_pct", "valve_command"},
                "requested_modbus_operations.csv": {
                    "elapsed_s",
                    "function",
                    "address",
                },
                "modbus_trace.csv": {
                    "time_s",
                    "src",
                    "dst",
                    "function_code",
                    "address",
                    "provenance",
                },
            }
        )
    else:
        columns.update(
            {
                "observations.csv": {"elapsed_s", "reported_sensor_level_pct", "attack_active"},
                "controller.csv": {"elapsed_s", "controller_input_level_pct", "valve_command"},
                "network_trace.csv": {"elapsed_s", "plane", "protocol", "operation", "address"},
            }
        )
    for filename, required_columns in columns.items():
        with (bundle / filename).open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not required_columns.issubset(set(reader.fieldnames or [])):
                errors.append(f"{filename} has unexpected columns")
            rows = list(reader)
            if not rows:
                errors.append(f"{filename} contains no data rows")
            if filename == "modbus_trace.csv" and any(
                row.get("provenance") != "tshark projection of network.pcap"
                for row in rows
            ):
                errors.append("modbus_trace.csv has invalid provenance")
    if is_modbus and (bundle / "network.pcap").stat().st_size == 0:
        errors.append("network.pcap is empty")
    expected = {}
    for line in (bundle / "manifest.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    for name, digest in expected.items():
        if not (bundle / name).is_file():
            errors.append(f"manifest target missing: {name}")
        elif hashlib.sha256((bundle / name).read_bytes()).hexdigest() != digest:
            errors.append(f"checksum mismatch: {name}")
    expected_targets = present - {"manifest.sha256"}
    if set(expected) != expected_targets:
        errors.append("manifest does not cover every bundle file")
    result = json.loads((bundle / "property_results.json").read_text(encoding="utf-8"))
    ladder = json.loads((bundle / "oracle_ladder.json").read_text(encoding="utf-8"))
    if ladder.get("physical_state_below_high_high", {}).get("verdict") != result.get("verdict"):
        errors.append("oracle ladder physical verdict disagrees with property result")
    return {
        "valid": not errors,
        "errors": errors,
        "case": metadata.get("case"),
        "property_verdict": result.get("verdict"),
    }


def reset(runtime_dir: pathlib.Path) -> None:
    """Remove only ephemeral files owned by this scaffold; evidence is retained."""

    allowed = {"session.json", "process.pid", "controller.pid"}
    if runtime_dir.exists():
        unexpected = [path.name for path in runtime_dir.iterdir() if path.name not in allowed]
        if unexpected:
            raise RuntimeError(
                "refusing reset because runtime directory contains unexpected files: "
                + ", ".join(sorted(unexpected))
            )
        for path in runtime_dir.iterdir():
            path.unlink()
        runtime_dir.rmdir()
    print("reset complete: the model is stateless; prior evidence bundles were retained")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("case", choices=sorted(CASES))
    run.add_argument("--out", type=pathlib.Path)
    run.add_argument("--duration", type=float, default=36.0)
    run.add_argument("--tick", type=float, default=1.0)
    validate = sub.add_parser("validate")
    validate.add_argument("bundle", type=pathlib.Path)
    reset_parser = sub.add_parser("reset")
    reset_parser.add_argument("--runtime-dir", type=pathlib.Path, default=HERE / ".runtime")
    args = parser.parse_args()

    try:
        if args.command == "run":
            run_case(args.case, args.out or default_output(args.case), args.duration, args.tick)
            return 0
        if args.command == "validate":
            result = validate_bundle(args.bundle)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 2
        reset(args.runtime_dir)
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"hw2 lab error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
