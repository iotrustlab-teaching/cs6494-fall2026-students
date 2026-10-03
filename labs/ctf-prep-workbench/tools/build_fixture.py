#!/usr/bin/env python3
"""Build a synthetic Modbus/TCP teaching capture and normalize it with TShark."""

import json
import shutil
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EPOCH = datetime(2026, 10, 2, 16, 0, tzinfo=timezone.utc).timestamp()
CLIENT = "192.0.2.11"
PLC = "192.0.2.20"
HISTORIAN = "192.0.2.31"
MAC = {
    CLIENT: bytes.fromhex("02 00 00 00 00 11"),
    PLC: bytes.fromhex("02 00 00 00 00 20"),
    HISTORIAN: bytes.fromhex("02 00 00 00 00 31"),
}


def checksum(data):
    if len(data) % 2:
        data += b"\0"
    words = struct.unpack("!%dH" % (len(data) // 2), data)
    total = sum(words)
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    return (~total) & 0xffff


def ip_bytes(address):
    return bytes(map(int, address.split(".")))


def mbap(transaction, pdu):
    return struct.pack("!HHHB", transaction, 0, len(pdu) + 1, 1) + pdu


def packet(src, dst, source_port, dest_port, sequence, acknowledgement, payload):
    src_ip, dst_ip = ip_bytes(src), ip_bytes(dst)
    tcp = struct.pack("!HHIIHHHH", source_port, dest_port, sequence, acknowledgement,
                      (5 << 12) | 0x18, 8192, 0, 0)
    pseudo = src_ip + dst_ip + struct.pack("!BBH", 0, 6, len(tcp) + len(payload))
    tcp = tcp[:16] + struct.pack("!H", checksum(pseudo + tcp + payload)) + tcp[18:]
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(tcp) + len(payload),
                     sequence & 0xffff, 0, 64, 6, 0, src_ip, dst_ip)
    ip = ip[:10] + struct.pack("!H", checksum(ip)) + ip[12:]
    return MAC[dst] + MAC[src] + b"\x08\x00" + ip + tcp + payload


def build_packets():
    read_run = b"\x03\x00\x64\x00\x01"  # holding register 100
    read_valve = b"\x03\x00\x65\x00\x01"  # reported valve state, register 101
    read_trip = b"\x03\x00\x66\x00\x01"  # reported trip state, register 102
    write_start = b"\x06\x00\x78\x00\x01"  # start-request register 120
    reads = [
        (0.00, CLIENT, PLC, 15011, 502, 1, read_run),
        (0.03, PLC, CLIENT, 502, 15011, 1, b"\x03\x02\x00\x00"),
        (0.40, HISTORIAN, PLC, 15031, 502, 2, read_valve),
        (0.43, PLC, HISTORIAN, 502, 15031, 2, b"\x03\x02\x00\x01"),
        (1.00, CLIENT, PLC, 15011, 502, 3, write_start),
        (1.03, PLC, CLIENT, 502, 15011, 3, write_start),
        (1.60, CLIENT, PLC, 15011, 502, 4, read_run),
        (1.63, PLC, CLIENT, 502, 15011, 4, b"\x03\x02\x00\x01"),
        (3.10, HISTORIAN, PLC, 15031, 502, 5, read_trip),
        (3.13, PLC, HISTORIAN, 502, 15031, 5, b"\x03\x02\x00\x01"),
    ]
    sequence = {(CLIENT, PLC): 1000, (PLC, CLIENT): 3000,
                (HISTORIAN, PLC): 5000, (PLC, HISTORIAN): 7000}
    frames = []
    for offset, src, dst, sport, dport, transaction, pdu in reads:
        payload = mbap(transaction, pdu)
        key = (src, dst)
        other = (dst, src)
        frame = packet(src, dst, sport, dport, sequence[key], sequence[other], payload)
        sequence[key] += len(payload)
        frames.append((EPOCH + offset, frame))
    return frames


def write_capture(frames, output):
    with output.open("wb") as capture:
        capture.write(struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1))
        for timestamp, frame in frames:
            seconds = int(timestamp)
            micros = round((timestamp - seconds) * 1_000_000)
            capture.write(struct.pack("<IIII", seconds, micros, len(frame), len(frame)))
            capture.write(frame)


def normalize_capture(capture):
    tshark = shutil.which("tshark") or "/Applications/Wireshark.app/Contents/MacOS/tshark"
    fields = ["frame.number", "frame.time_epoch", "eth.src", "eth.dst", "ip.src", "ip.dst", "tcp.srcport",
              "tcp.dstport", "modbus.func_code", "modbus.reference_num",
              "modbus.regval_uint16", "modbus.data"]
    command = [tshark, "-r", str(capture), "-T", "fields", "-E", "separator=\t",
               "-E", "occurrence=f"]
    for field in fields:
        command.extend(["-e", field])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    events = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        parts.extend([""] * (len(fields) - len(parts)))
        row = dict(zip(fields, parts))
        if not row["modbus.func_code"]:
            raise RuntimeError("TShark did not decode a Modbus function in packet " + row["frame.number"])
        events.append({
            "packet": int(row["frame.number"]),
            "seconds": round(float(row["frame.time_epoch"]) - EPOCH, 2),
            "evidence_source": "synthetic-pcap:tshark",
            "protocol": "Modbus/TCP",
            "operation": "write" if int(row["modbus.func_code"]) in (6, 16) else "read",
            "source": row["ip.src"],
            "destination": row["ip.dst"],
            "source_mac": row["eth.src"],
            "destination_mac": row["eth.dst"],
            "port": int(row["tcp.dstport"]),
            "function": int(row["modbus.func_code"]),
            "address": int(row["modbus.reference_num"]) if row["modbus.reference_num"] else None,
            "value": int(row["modbus.regval_uint16"]) if row["modbus.regval_uint16"] else None,
            "data": row["modbus.data"] or None,
            "direction": "request" if row["tcp.dstport"] == "502" else "response",
        })
    if len(events) != 10 or [event["function"] for event in events] != [3, 3, 3, 3, 6, 6, 3, 3, 3, 3]:
        raise RuntimeError("Unexpected Modbus decoding; inspect TShark output")
    if events[4]["address"] != 120:
        raise RuntimeError("Start request was not decoded at register 120")
    return events


def main():
    DATA.mkdir(exist_ok=True)
    capture = DATA / "monday-synthetic.pcap"
    write_capture(build_packets(), capture)
    traffic = {
        "provenance": "Constructed synthetic Modbus/TCP packets; decoded with TShark, not captured from a PLC.",
        "parser": "TShark Modbus dissector",
        "events": normalize_capture(capture),
    }
    content = json.dumps(traffic, indent=2) + "\n"
    (DATA / "traffic.json").write_text(content)
    (DATA / "traffic.js").write_text("window.WORKBENCH_TRAFFIC = " + content.rstrip() + ";\n")
    print("Built 10 synthetic packets; TShark decoded every Modbus function.")


if __name__ == "__main__":
    main()
