#!/usr/bin/env python3
"""A deliberately small, inspectable HW2 property checker.

The default property is about simulated physical truth, not the reported
sensor value: the tank must remain below the high-high threshold throughout
the run.  Students can read or adapt ``evaluate_property`` without learning a
temporal-logic package first.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List


PROPERTY_ID = "P1_TRUE_LEVEL_BELOW_HIGH_HIGH"


def evaluate_property(rows: List[Dict[str, str]], limit: float = 90.0) -> dict:
    """Evaluate ``always(true_level_pct < limit)`` over a process trace."""

    if not rows:
        raise ValueError("process trace contains no samples")
    samples = [
        (float(row["elapsed_s"]), float(row["true_level_pct"])) for row in rows
    ]
    violations = [(elapsed, level) for elapsed, level in samples if level >= limit]
    first = violations[0] if violations else None
    return {
        "property_id": PROPERTY_ID,
        "expression": f"always(true_level_pct < {limit:g})",
        "verdict": "FAIL" if violations else "PASS",
        "evaluated_samples": len(samples),
        "threshold_pct": limit,
        "maximum_observed_pct": max(level for _, level in samples),
        "violation_count": len(violations),
        "first_violation": (
            {"elapsed_s": first[0], "true_level_pct": first[1]} if first else None
        ),
        "evidence_source": "process.csv:true_level_pct",
        "establishes": (
            "Whether the simulated physical-state trace violated the stated "
            "high-high bound during this finite run."
        ),
        "does_not_establish": (
            "Safety outside the recorded interval, safety of a physical plant, "
            "or the cause of any violation."
        ),
    }


def check_bundle(bundle: Path, limit: float = 90.0, write: bool = True) -> dict:
    process_path = bundle / "process.csv"
    with process_path.open(newline="", encoding="utf-8") as handle:
        result = evaluate_property(list(csv.DictReader(handle)), limit)
    if write:
        (bundle / "property_results.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="run bundle directory")
    parser.add_argument("--max-level", type=float, default=90.0)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    try:
        result = check_bundle(args.bundle, args.max_level, not args.no_write)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
