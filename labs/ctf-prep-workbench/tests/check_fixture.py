#!/usr/bin/env python3
"""Check the frozen capture and its browser normalization without rewriting it."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_fixture import normalize_capture  # noqa: E402

traffic = json.loads((ROOT / "data/traffic.json").read_text())
assert traffic["events"] == normalize_capture(ROOT / "data/monday-synthetic.pcap")
assert (ROOT / "data/traffic.js").read_text() == "window.WORKBENCH_TRAFFIC = " + json.dumps(traffic, indent=2) + ";\n"
assert len(traffic["events"]) == 10
assert {event["source"] for event in traffic["events"]} == {"192.0.2.11", "192.0.2.20", "192.0.2.31"}
assert traffic["events"][4]["function"] == 6
assert traffic["events"][4]["address"] == 120
print("Fixture verified: PCAP, TShark normalization, browser data, and start write agree.")
