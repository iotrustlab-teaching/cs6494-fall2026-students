#!/usr/bin/env python3
"""Print a small Modbus operation table decoded from a real pcap with tshark."""

from __future__ import annotations

import argparse
import csv
import io
import pathlib
import shutil
import struct
import subprocess


FIELDS = (
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

CONTROLLER_HOST = "10.42.0.20"
OPERATIONS = {
    "1": ("read coils", "inlet_valve_open"),
    "3": ("read holding registers", "reported_level_pct"),
    "16": ("write multiple registers", "reported_level_pct"),
}


def decode_real(raw: str) -> str:
    try:
        words = [int(item) for item in raw.split(";")]
        if len(words) != 2:
            return ""
        value = struct.unpack(">f", struct.pack(">HH", *words))[0]
        return f"{value:.3f}%"
    except (ValueError, struct.error):
        return ""


def decode(pcap: pathlib.Path) -> str:
    tshark = shutil.which("tshark")
    if tshark is None:
        raise RuntimeError("prepared image is missing tshark")
    if not pcap.is_file():
        raise FileNotFoundError(pcap)
    command = [
        tshark,
        "-r",
        str(pcap),
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
    for field in FIELDS:
        command.extend(["-e", field])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    decoded = list(csv.reader(result.stdout.splitlines()))
    if not decoded:
        raise RuntimeError("pcap contains no tshark-decoded Modbus packets")
    transactions: dict[str, tuple[str, str]] = {}
    output = io.StringIO()
    fields = [
        "time_s",
        "src",
        "dst",
        "message",
        "function",
        "address",
        "object",
        "value",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for values in decoded:
        values += [""] * (len(FIELDS) - len(values))
        packet = dict(zip(FIELDS, values))
        transaction = packet["mbtcp.trans_id"]
        function = packet["modbus.func_code"]
        address = packet["modbus.reference_num"]
        is_request = packet["ip.dst"] == CONTROLLER_HOST
        if is_request and transaction:
            transactions[transaction] = (function, address)
        function, address = transactions.get(transaction, (function, address))
        operation, object_name = OPERATIONS.get(function, (f"function {function}", "unknown"))
        raw_words = packet["modbus.regval_uint16"]
        bit = packet["modbus.bitval"]
        value = decode_real(raw_words) if raw_words else ""
        if bit:
            value = "OPEN" if bit.lower() in {"1", "true"} else "CLOSED"
        writer.writerow(
            {
                "time_s": packet["frame.time_relative"],
                "src": packet["ip.src"],
                "dst": packet["ip.dst"],
                "message": "request" if is_request else "response",
                "function": f"FC{int(function):02d} {operation}" if function else "",
                "address": address,
                "object": object_name,
                "value": value or raw_words,
            }
        )
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=pathlib.Path, help="bundle containing network.pcap")
    args = parser.parse_args()
    try:
        print(decode(args.run / "network.pcap"), end="")
    except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
