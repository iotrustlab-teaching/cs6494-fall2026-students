#!/usr/bin/env python3
"""Mechanically compare the Python, C, and teaching ST controller artifacts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Dict, Iterable, List, Tuple

HERE = pathlib.Path(__file__).resolve().parent
REPRESENTATIONS = HERE / "representations"
sys.path.insert(0, str(HERE))

from controller_semantics import run_sequence  # noqa: E402


SEQUENCES: Dict[str, List[float]] = {
    "below_middle_above": [40.0, 50.0, 50.0, 60.0],
    "above_middle_below": [60.0, 50.0, 40.0],
    "boundaries": [44.999, 45.0, 55.0, 55.001],
    "long_hold": [40.0] + [50.0] * 12 + [60.0],
    "oscillation": [44.0, 46.0, 54.0, 56.0, 54.0, 44.0],
    "spoof_style": [50.0, 49.0, 48.0, 5.0, 5.0, 7.0, 56.0],
}


def load_tank_model():
    path = HERE.parent / "cps_tank.py"
    spec = importlib.util.spec_from_file_location("hw2_equivalence_tank", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_existing_python(values: Iterable[float]) -> List[bool]:
    controller = load_tank_model().HysteresisController()
    return [controller.decide(value)[0] == "OPEN" for value in values]


def parse_st_contract(path: pathlib.Path) -> Tuple[float, float]:
    source = path.read_text(encoding="utf-8")
    low_match = re.search(r"LOW_LEVEL_PCT\s*:\s*REAL\s*:=\s*([0-9.]+)", source)
    high_match = re.search(r"HIGH_LEVEL_PCT\s*:\s*REAL\s*:=\s*([0-9.]+)", source)
    required = [
        r"IF\s+reported_level_pct\s*<\s*LOW_LEVEL_PCT\s+THEN",
        r"inlet_valve_open\s*:=\s*TRUE",
        r"ELSIF\s+reported_level_pct\s*>\s*HIGH_LEVEL_PCT\s+THEN",
        r"inlet_valve_open\s*:=\s*FALSE",
        r"reported_level_pct\s+AT\s+%MD0",
        r"inlet_valve_open\s+AT\s+%QX0\.0",
    ]
    if not low_match or not high_match or any(
        re.search(pattern, source, re.IGNORECASE) is None for pattern in required
    ):
        raise ValueError(f"{path} is outside the supported teaching ST contract")
    return float(low_match.group(1)), float(high_match.group(1))


def run_st(values: Iterable[float], path: pathlib.Path) -> List[bool]:
    low, high = parse_st_contract(path)
    return run_sequence(values, low=low, high=high)


def run_c(values: Iterable[float]) -> List[bool]:
    source = REPRESENTATIONS / "controller.c"
    with tempfile.TemporaryDirectory(prefix="hw2-c-controller-") as temporary:
        binary = pathlib.Path(temporary) / "controller"
        subprocess.run(
            [
                "cc",
                "-std=c99",
                "-Wall",
                "-Wextra",
                "-DHW2_SEQUENCE_RUNNER",
                str(source),
                "-o",
                str(binary),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        completed = subprocess.run(
            [str(binary), *(str(value) for value in values)],
            check=True,
            capture_output=True,
            text=True,
        )
    return [line == "1" for line in completed.stdout.splitlines()]


def verify() -> dict:
    results = []
    for name, values in SEQUENCES.items():
        reference = run_sequence(values)
        implementations = {
            "reference": reference,
            "existing_python": run_existing_python(values),
            "c": run_c(values),
            "structured_text": run_st(values, REPRESENTATIONS / "controller.st"),
        }
        equivalent = all(output == reference for output in implementations.values())
        results.append(
            {
                "sequence": name,
                "inputs": values,
                "outputs": {key: [int(value) for value in output] for key, output in implementations.items()},
                "equivalent": equivalent,
            }
        )
    return {
        "equivalent": all(item["equivalent"] for item in results),
        "bounded_scope": "six disclosed stateful input sequences; not universal equivalence",
        "sequences": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()
    result = verify()
    rendered = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["equivalent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
