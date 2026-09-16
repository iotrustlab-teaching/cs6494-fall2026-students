#!/usr/bin/env python3
"""Generate a small CFG and dependency view from the teaching controller."""

from __future__ import annotations

import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

DOT = """digraph controller {
  rankdir=TB;
  node [shape=box];
  input [label="reported_level_pct"];
  low [shape=diamond,label="reported < LOW?"];
  high [shape=diamond,label="reported > HIGH?"];
  open [label="inlet_valve_open = true"];
  close [label="inlet_valve_open = false"];
  hold [label="retain prior valve state"];
  output [label="publish inlet_valve_open"];
  input -> low;
  low -> open [label="yes"];
  low -> high [label="no"];
  high -> close [label="yes"];
  high -> hold [label="no"];
  open -> output;
  close -> output;
  hold -> output;
}
"""

DEPENDENCY = {
    "external_observation": "reported_level_pct",
    "control_dependencies": ["reported_level_pct < LOW_LEVEL_PCT", "reported_level_pct > HIGH_LEVEL_PCT"],
    "retained_state": "inlet_valve_open",
    "actuator_decision": "inlet_valve_open",
    "assumption_to_question": "the reported observation faithfully represents the process state",
    "student_prompt": "Explain a path that can keep the inlet open even while true tank level rises.",
}


def generate(output: pathlib.Path) -> pathlib.Path:
    source = (HERE / "representations" / "controller.c").read_text(encoding="utf-8")
    for token in ("reported_level_pct", "LOW_LEVEL_PCT", "HIGH_LEVEL_PCT", "inlet_valve_open"):
        if token not in source:
            raise ValueError(f"controller.c no longer contains required token {token}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "controller_cfg.dot").write_text(DOT, encoding="utf-8")
    (output / "dependency_map.json").write_text(json.dumps(DEPENDENCY, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=HERE / "runs" / "analysis")
    args = parser.parse_args()
    print(generate(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
