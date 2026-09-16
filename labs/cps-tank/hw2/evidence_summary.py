#!/usr/bin/env python3
"""Print the compact, claim-oriented view of one HW2 evidence bundle."""

from __future__ import annotations

import argparse
import csv
import json
import pathlib

from hw2_lab import validate_bundle


def summarize(bundle: pathlib.Path) -> dict:
    metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
    validation = validate_bundle(bundle)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))

    result = json.loads((bundle / "property_results.json").read_text(encoding="utf-8"))
    ladder = json.loads((bundle / "oracle_ladder.json").read_text(encoding="utf-8"))
    is_modbus = metadata.get("transport") == "Modbus TCP"
    network_name = "modbus_trace.csv" if is_modbus else "network_trace.csv"
    with (bundle / network_name).open(newline="", encoding="utf-8") as handle:
        network_rows = list(csv.DictReader(handle))
    if is_modbus:
        with (bundle / "observations.csv").open(newline="", encoding="utf-8") as handle:
            overrides = [
                row for row in csv.DictReader(handle) if row["attack_active"] == "true"
            ]
    else:
        overrides = [
            row for row in network_rows if row["operation"] == "replace_whitelisted_value"
        ]
    first = result.get("first_violation")
    return {
        "case": metadata["case"],
        "property": result["expression"],
        "verdict": result["verdict"],
        "maximum_true_level_pct": result["maximum_observed_pct"],
        "first_violation_s": None if first is None else first["elapsed_s"],
        "reported_oracle": ladder["reported_state_below_high_high"]["verdict"],
        "physical_oracle": ladder["physical_state_below_high_high"]["verdict"],
        "modeled_network_operations": len(network_rows),
        "allowlisted_overrides": len(overrides),
        "network_evidence_kind": "pcap" if is_modbus else "semantic reconstruction",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=pathlib.Path)
    args = parser.parse_args()
    try:
        item = summarize(args.bundle)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"evidence error: {error}")
        return 2

    print(f"Case: {item['case']}")
    print(f"Property: {item['property']}")
    print(
        f"Verdict: {item['verdict']} "
        f"(max true level {item['maximum_true_level_pct']:.1f}%)"
    )
    if item["first_violation_s"] is not None:
        print(f"First violation: {item['first_violation_s']:.1f} s")
    print(
        "Oracle comparison: "
        f"reported={item['reported_oracle']}, physical={item['physical_oracle']}"
    )
    print(
        "Network view: "
        f"{item['network_evidence_kind']}; "
        f"{item['modeled_network_operations']} operations, "
        f"{item['allowlisted_overrides']} override rows"
    )
    print("\nMinimum evidence for the physical-property claim:")
    print("  timeline.csv + property_results.json")
    print(
        "Use network.pcap + modbus_trace.csv for interface traversal; "
        "use controller/process layers for consequence."
        if item["network_evidence_kind"] == "pcap"
        else "Use network_trace.csv only for the modeled operation/address chain."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
