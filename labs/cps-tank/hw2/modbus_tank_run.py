#!/usr/bin/env python3
"""Run the HW2 tank against the fixed OpenPLC/Modbus controller.

The process simulator owns physical truth.  It writes one reported REAL to the
course controller, waits for the actual Structured Text scan, reads the output
coil, and advances the process.  The command-line interface deliberately has
no host, port, address, value, or attack-window option.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.metadata
import inspect
import json
import os
import pathlib
import shutil
import signal
import struct
import subprocess
import sys
import time
from typing import Any, Callable

from pymodbus.client import ModbusTcpClient


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from cps_tank import HIGH_HIGH_LEVEL, Tank, apparent_state, physical_state  # noqa: E402
from property_oracle import evaluate_property  # noqa: E402


CONTROLLER_HOST = "10.42.0.20"
CONTROLLER_PORT = 502
CAPTURE_INTERFACE = "eth1"
UNIT_ID = 1
LEVEL_ADDRESS = 2048
LEVEL_WORDS = 2
VALVE_ADDRESS = 0
LOW_LEVEL_PCT = 45.0
HIGH_LEVEL_PCT = 55.0
ATTACK_START_S = 8.0
ATTACK_END_S = 16.0
SENSOR_BIAS_PCT = -50.0
SENSOR_FLOOR_PCT = 5.0
CASES = {"nominal", "sensor_spoof"}

PCAP_FIELDS = (
    "frame.time_relative",
    "ip.src",
    "tcp.srcport",
    "ip.dst",
    "tcp.dstport",
    "mbtcp.trans_id",
    "modbus.func_code",
    "modbus.reference_num",
    "modbus.word_cnt",
    "modbus.regval_uint16",
    "modbus.bitval",
)

FUNCTION_NAMES = {
    "1": "read_coils",
    "3": "read_holding_registers",
    "16": "write_multiple_registers",
}


def unit_kwargs(method: Callable[..., Any]) -> dict[str, int]:
    """Support the pymodbus 3.6 ``slave`` and 3.7+ ``device_id`` spellings."""

    parameters = inspect.signature(method).parameters
    if "device_id" in parameters:
        return {"device_id": UNIT_ID}
    if "slave" in parameters:
        return {"slave": UNIT_ID}
    return {}


def encode_real(value: float) -> list[int]:
    """Encode an OpenPLC %MD REAL as two high-word-first Modbus registers."""

    return list(struct.unpack(">HH", struct.pack(">f", float(value))))


def decode_real(words: list[int]) -> float:
    if len(words) != LEVEL_WORDS:
        raise ValueError(f"expected {LEVEL_WORDS} words, got {len(words)}")
    return struct.unpack(">f", struct.pack(">HH", *words))[0]


def response_ok(response: Any) -> bool:
    return response is not None and not response.isError()


class FixedOpenPLCClient:
    """Narrow client for the two objects in the disclosed representation map."""

    def __init__(self) -> None:
        self.client = ModbusTcpClient(
            CONTROLLER_HOST,
            port=CONTROLLER_PORT,
            timeout=3,
        )

    def connect(self, timeout_s: float = 30.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.client.connect():
                return
            time.sleep(0.5)
        raise ConnectionError(
            f"prepared OpenPLC controller unavailable at "
            f"{CONTROLLER_HOST}:{CONTROLLER_PORT}"
        )

    def close(self) -> None:
        self.client.close()

    def write_reported_level(self, value: float) -> list[int]:
        words = encode_real(value)
        response = self.client.write_registers(
            LEVEL_ADDRESS,
            words,
            **unit_kwargs(self.client.write_registers),
        )
        if not response_ok(response):
            raise RuntimeError("OpenPLC rejected the fixed reported-level write")
        return words

    def read_reported_level(self) -> tuple[list[int], float]:
        response = self.client.read_holding_registers(
            LEVEL_ADDRESS,
            count=LEVEL_WORDS,
            **unit_kwargs(self.client.read_holding_registers),
        )
        if not response_ok(response) or len(response.registers) < LEVEL_WORDS:
            raise RuntimeError("could not read the fixed reported-level register pair")
        words = list(response.registers[:LEVEL_WORDS])
        return words, decode_real(words)

    def read_valve(self) -> bool:
        response = self.client.read_coils(
            VALVE_ADDRESS,
            count=1,
            **unit_kwargs(self.client.read_coils),
        )
        if not response_ok(response) or not response.bits:
            raise RuntimeError("could not read the fixed inlet-valve coil")
        return bool(response.bits[0])


def initialize_controller(plc: Any, settle_s: float = 0.15) -> None:
    """Put the stateful ST controller in its disclosed CLOSED baseline."""

    plc.write_reported_level(HIGH_LEVEL_PCT + 1.0)
    if settle_s > 0:
        time.sleep(settle_s)
    if plc.read_valve():
        raise RuntimeError("OpenPLC controller initialization did not close the inlet")


def default_output(case: str) -> pathlib.Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return HERE / "runs" / f"modbus-{case}-{stamp}"


def write_csv(path: pathlib.Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(output: pathlib.Path) -> None:
    lines = []
    for path in sorted(output.iterdir()):
        if path.name == "manifest.sha256" or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    (output / "manifest.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def capture_command(output: pathlib.Path) -> list[str]:
    capture_wrapper = pathlib.Path("/usr/local/sbin/cs6494-hw2-capture")
    if not capture_wrapper.is_file():
        raise RuntimeError("prepared image is missing the fixed packet-capture wrapper")
    return [
        "sudo",
        "-n",
        str(capture_wrapper),
        str(output / "network.pcap"),
    ]


def start_capture(output: pathlib.Path) -> subprocess.Popen[str]:
    """Start the fixed course capture; no endpoint or filter is student supplied."""

    command = capture_command(output)
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    time.sleep(0.4)
    if process.poll() is not None:
        _, error = process.communicate()
        raise RuntimeError("could not start fixed packet capture: " + error.strip())
    return process


def stop_capture(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGINT)
        _, error = process.communicate(timeout=10)
    except ProcessLookupError:
        _, error = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        _, error = process.communicate(timeout=5)
        raise RuntimeError("fixed packet capture did not stop cleanly")
    if process.returncode not in (0, 130):
        raise RuntimeError("fixed packet capture failed: " + error.strip())


def tshark_command(output: pathlib.Path) -> list[str]:
    tshark = shutil.which("tshark")
    if tshark is None:
        raise RuntimeError("prepared image is missing tshark")
    command = [
        tshark,
        "-r",
        str(output / "network.pcap"),
        "-Y",
        "modbus",
        "-T",
        "fields",
        "-E",
        "separator=,",
        "-E",
        "quote=d",
        "-E",
        "occurrence=a",
        "-E",
        "aggregator=;",
    ]
    for field in PCAP_FIELDS:
        command.extend(["-e", field])
    return command


def project_pcap(output: pathlib.Path, *, expected_requests: int) -> None:
    """Derive the readable Modbus table from the captured packets themselves."""

    command = tshark_command(output)
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    decoded = list(csv.reader(result.stdout.splitlines()))
    if not decoded:
        raise RuntimeError("network.pcap contains no tshark-decoded Modbus packets")

    transactions: dict[str, tuple[str, str]] = {}
    rows: list[dict[str, str]] = []
    for values in decoded:
        values += [""] * (len(PCAP_FIELDS) - len(values))
        fields = dict(zip(PCAP_FIELDS, values))
        transaction = fields["mbtcp.trans_id"]
        function_code = fields["modbus.func_code"]
        address = fields["modbus.reference_num"]
        is_request = fields["ip.dst"] == CONTROLLER_HOST
        if is_request and transaction:
            transactions[transaction] = (function_code, address)
        paired_function, paired_address = transactions.get(
            transaction, (function_code, address)
        )
        function_code = function_code or paired_function
        address = address or paired_address
        raw = fields["modbus.regval_uint16"] or fields["modbus.bitval"]
        decoded_value = ""
        if raw and function_code in {"3", "16"}:
            try:
                words = [int(item) for item in raw.split(";")]
                if len(words) == LEVEL_WORDS:
                    decoded_value = f"{decode_real(words):.3f}"
            except ValueError:
                pass
        elif raw and function_code == "1":
            decoded_value = "OPEN" if raw.lower() in {"1", "true"} else "CLOSED"
        rows.append(
            {
                "time_s": fields["frame.time_relative"],
                "src": fields["ip.src"],
                "src_port": fields["tcp.srcport"],
                "dst": fields["ip.dst"],
                "dst_port": fields["tcp.dstport"],
                "transaction": transaction,
                "message": "request" if is_request else "response",
                "function_code": function_code,
                "operation": FUNCTION_NAMES.get(function_code, "unknown"),
                "address": address,
                "count": fields["modbus.word_cnt"],
                "raw_value": raw,
                "decoded_value": decoded_value,
                "provenance": "tshark projection of network.pcap",
            }
        )
    request_count = sum(row["message"] == "request" for row in rows)
    response_count = sum(row["message"] == "response" for row in rows)
    if request_count < expected_requests or response_count < expected_requests:
        raise RuntimeError(
            "network.pcap ended before all fixed Modbus operations were captured "
            f"(expected {expected_requests} request/response pairs, got "
            f"{request_count}/{response_count})"
        )
    write_csv(output / "modbus_trace.csv", list(rows[0]), rows)


def run_case(
    case: str,
    output: pathlib.Path,
    *,
    duration_s: int = 36,
    tick_s: float = 1.0,
    scan_settle_s: float = 0.15,
    pace: bool = True,
    client: Any | None = None,
    capture: bool = False,
) -> pathlib.Path:
    if case not in CASES:
        raise ValueError(f"unknown case {case!r}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)

    capture_process = start_capture(output) if capture else None
    plc = client if client is not None else FixedOpenPLCClient()
    owns_client = client is None
    try:
        plc.connect()
    except Exception:
        if capture_process is not None:
            stop_capture(capture_process)
        raise
    # The controller is stateful inside the hysteresis band.  Drive it once
    # above the high threshold so every run begins with the inlet closed,
    # independent of the prior run in the same realization.
    try:
        initialize_controller(plc, scan_settle_s if pace else 0.0)
    except RuntimeError:
        if capture_process is not None:
            stop_capture(capture_process)
        if owns_client:
            plc.close()
        raise
    tank = Tank(level=50.0)
    process_rows: list[dict[str, Any]] = []
    observation_rows: list[dict[str, Any]] = []
    controller_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    events = [
        "0.000 run_start case=" + case + " transport=modbus_tcp",
        "0.000 controller_state_initialized valve=CLOSED",
    ]
    prior_valve = False
    attack_logged = False
    violation_logged = False

    try:
        for second in range(duration_s + 1):
            cycle_start = time.monotonic()
            elapsed = float(second)
            true_level = tank.level
            honest_level = tank.sensor_reading()
            attack_active = (
                case == "sensor_spoof"
                and ATTACK_START_S <= elapsed < ATTACK_END_S
            )
            delivered_level = (
                max(SENSOR_FLOOR_PCT, honest_level + SENSOR_BIAS_PCT)
                if attack_active
                else honest_level
            )

            written_words = plc.write_reported_level(delivered_level)
            request_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "direction": "process_to_controller",
                    "function": "16_write_multiple_registers",
                    "object": "reported_level_pct",
                    "address": LEVEL_ADDRESS,
                    "count": LEVEL_WORDS,
                    "raw_words": " ".join(str(word) for word in written_words),
                    "decoded_value": f"{delivered_level:.3f}",
                }
            )
            if pace:
                time.sleep(scan_settle_s)

            observed_words, plc_observed = plc.read_reported_level()
            request_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "direction": "process_from_controller",
                    "function": "03_read_holding_registers",
                    "object": "reported_level_pct",
                    "address": LEVEL_ADDRESS,
                    "count": LEVEL_WORDS,
                    "raw_words": " ".join(str(word) for word in observed_words),
                    "decoded_value": f"{plc_observed:.3f}",
                }
            )
            valve_open = plc.read_valve()
            request_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "direction": "process_from_controller",
                    "function": "01_read_coils",
                    "object": "inlet_valve_open",
                    "address": VALVE_ADDRESS,
                    "count": 1,
                    "raw_words": "1" if valve_open else "0",
                    "decoded_value": "OPEN" if valve_open else "CLOSED",
                }
            )

            if plc_observed < LOW_LEVEL_PCT:
                relation = "below low threshold"
            elif plc_observed > HIGH_LEVEL_PCT:
                relation = "above high threshold"
            else:
                relation = "inside band; retained output"
            valve = "OPEN" if valve_open else "CLOSED"
            process_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "true_level_pct": f"{true_level:.3f}",
                    "physical_state": physical_state(true_level),
                }
            )
            observation_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "honest_level_pct": f"{honest_level:.3f}",
                    "modbus_reported_level_pct": f"{delivered_level:.3f}",
                    "plc_readback_level_pct": f"{plc_observed:.3f}",
                    "attack_active": str(attack_active).lower(),
                }
            )
            controller_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "plc_input_level_pct": f"{plc_observed:.3f}",
                    "st_relation": relation,
                    "valve_command": valve,
                }
            )
            timeline_rows.append(
                {
                    "elapsed_s": f"{elapsed:.3f}",
                    "true_level_pct": f"{true_level:.3f}",
                    "modbus_reported_level_pct": f"{delivered_level:.3f}",
                    "plc_readback_level_pct": f"{plc_observed:.3f}",
                    "valve_command": valve,
                    "attack_active": str(attack_active).lower(),
                    "physical_state": physical_state(true_level),
                    "apparent_state": apparent_state(plc_observed),
                }
            )
            if valve_open != prior_valve:
                action_rows.append(
                    {
                        "elapsed_s": f"{elapsed:.3f}",
                        "actuator": "inlet_valve",
                        "command": valve,
                        "evidence": "OpenPLC coil 0",
                    }
                )
                events.append(f"{elapsed:.3f} valve_command command={valve}")
            prior_valve = valve_open
            if attack_active and not attack_logged:
                events.append(
                    f"{elapsed:.3f} bounded_modbus_manipulation_start "
                    f"address={LEVEL_ADDRESS} bias_pct={SENSOR_BIAS_PCT:g}"
                )
                attack_logged = True
            if true_level >= HIGH_HIGH_LEVEL and not violation_logged:
                events.append(
                    f"{elapsed:.3f} property_violation true_level_pct={true_level:.3f}"
                )
                violation_logged = True

            tank.advance(valve, tick_s)
            if pace and second < duration_s:
                remaining = tick_s - (time.monotonic() - cycle_start)
                if remaining > 0:
                    time.sleep(remaining)
    finally:
        if owns_client:
            plc.close()
        if capture_process is not None:
            # Let tcpdump drain the final response from the interface before
            # requesting a clean stop and writing the pcap footer.
            time.sleep(0.25)
            stop_capture(capture_process)

    write_csv(output / "process.csv", list(process_rows[0]), process_rows)
    write_csv(output / "observations.csv", list(observation_rows[0]), observation_rows)
    write_csv(output / "controller.csv", list(controller_rows[0]), controller_rows)
    write_csv(output / "actions.csv", list(action_rows[0]), action_rows)
    write_csv(output / "timeline.csv", list(timeline_rows[0]), timeline_rows)
    write_csv(output / "requested_modbus_operations.csv", list(request_rows[0]), request_rows)
    (output / "events.log").write_text("\n".join(events) + "\n", encoding="utf-8")
    if capture:
        project_pcap(output, expected_requests=len(request_rows) + 2)

    property_result = evaluate_property(process_rows)
    (output / "property_results.json").write_text(
        json.dumps(property_result, indent=2) + "\n", encoding="utf-8"
    )
    reported_max = max(float(row["plc_readback_level_pct"]) for row in observation_rows)
    first_violation = property_result.get("first_violation")
    if first_violation is None:
        onset_detection = {
            "verdict": "NOT_APPLICABLE",
            "reason": "no physical violation occurred in the bounded run",
        }
    else:
        violation_index = next(
            index
            for index, row in enumerate(process_rows)
            if float(row["elapsed_s"]) == float(first_violation["elapsed_s"])
        )
        decision_index = max(0, violation_index - 1)
        decision_observation = observation_rows[decision_index]
        reported_at_decision = float(decision_observation["plc_readback_level_pct"])
        onset_detection = {
            "verdict": (
                "DETECTED" if reported_at_decision >= HIGH_HIGH_LEVEL else "MISSED"
            ),
            "first_physical_violation_s": float(first_violation["elapsed_s"]),
            "violation_causing_decision_s": float(
                decision_observation["elapsed_s"]
            ),
            "reported_level_at_decision_pct": reported_at_decision,
            "threshold_pct": HIGH_HIGH_LEVEL,
            "observes": (
                "the PLC readback used for the process step immediately before "
                "the first sampled physical violation"
            ),
        }
    oracle_ladder = {
        "network_capture_decoded": {
            "verdict": "PASS" if capture else "NOT_RUN",
            "evidence": "network.pcap -> modbus_trace.csv" if capture else None,
        },
        "modbus_requests_completed": {"verdict": "PASS"},
        "openplc_readback_matches_delivery": {
            "verdict": "PASS"
            if all(
                abs(
                    float(row["modbus_reported_level_pct"])
                    - float(row["plc_readback_level_pct"])
                )
                < 0.001
                for row in observation_rows
            )
            else "FAIL"
        },
        "reported_state_below_high_high": {
            "verdict": "PASS" if reported_max < HIGH_HIGH_LEVEL else "FAIL",
            "maximum_observed_pct": reported_max,
            "scope": "whole bounded run, including post-attack aftermath",
        },
        "physical_violation_onset_detection": onset_detection,
        "physical_state_below_high_high": property_result,
        "bounded_claim": "These verdicts describe this finite software-process run only.",
    }
    (output / "oracle_ladder.json").write_text(
        json.dumps(oracle_ladder, indent=2) + "\n", encoding="utf-8"
    )
    metadata = {
        "bundle_schema_version": "1.2.0-modbus-pilot",
        "case": case,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "controller_runtime": "OpenPLC executing representations/controller.st",
        "transport": "Modbus TCP",
        "fixed_endpoint": f"{CONTROLLER_HOST}:{CONTROLLER_PORT}",
        "mapping": {
            "reported_level_pct": {
                "iec": "%MD0",
                "object": "holding_register",
                "address": LEVEL_ADDRESS,
                "words": LEVEL_WORDS,
                "encoding": "IEEE-754 binary32, high word first",
            },
            "inlet_valve_open": {
                "iec": "%QX0.0",
                "object": "coil",
                "address": VALVE_ADDRESS,
            },
        },
        "capture_note": (
            "requested_modbus_operations.csv records client requests. "
            "network.pcap is the interface capture; modbus_trace.csv is generated from it with tshark."
        ),
        "controller_initialization": (
            "Before sample zero, the fixed runner writes 56.0% and confirms coil 0 is CLOSED "
            "so hysteresis state cannot leak across runs. Those operations are visible in the pcap."
        ),
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    if capture:
        def first_version(binary: str) -> str:
            result = subprocess.run(
                [shutil.which(binary) or binary, "--version"],
                capture_output=True, text=True, check=True,
            )
            return (result.stdout or result.stderr).splitlines()[0]

        toolchain = {
            "openplc_source_commit": "b5d41356dab4aeadca0dd7ca64ba542f870b595d",
            "pymodbus_version": importlib.metadata.version("pymodbus"),
            "tcpdump_version": first_version("tcpdump"),
            "tshark_version": first_version("tshark"),
            "capture_command": capture_command(output),
            "decode_command": tshark_command(output),
            "source_pcap": "network.pcap",
            "derived_table": "modbus_trace.csv",
            "limitations": (
                "The pcap establishes observed Modbus exchange on this isolated link; "
                "it does not establish physical tank truth or all possible behavior."
            ),
        }
        (output / "TOOLCHAIN.json").write_text(
            json.dumps(toolchain, indent=2) + "\n", encoding="utf-8"
        )
    write_manifest(output)
    print(
        f"{case}: {property_result['verdict']} - "
        f"max true level {property_result['maximum_observed_pct']:.1f}%"
    )
    print(f"evidence: {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=sorted(CASES))
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    try:
        run_case(
            args.case,
            args.output or default_output(args.case),
            capture=True,
        )
    except (
        ConnectionError,
        FileExistsError,
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
