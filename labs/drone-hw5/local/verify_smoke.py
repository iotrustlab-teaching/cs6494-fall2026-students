"""Require real controller/plant evidence from the first two smoke flights."""

import json
from pathlib import Path


def latest(case: str) -> tuple[dict, list[dict]]:
    summaries = sorted(Path("runs").glob(f"*-{case}.summary.json"))
    if not summaries:
        raise AssertionError(f"No summary for {case}")
    summary_path = summaries[-1]
    summary = json.loads(summary_path.read_text())
    trace_path = Path(str(summary_path).replace(".summary.json", ".jsonl"))
    events = [json.loads(row) for row in trace_path.read_text().splitlines()]
    return summary, events


clean, clean_events = latest("clean-starter")
attack, attack_events = latest("attack-starter")
assert clean["airborne_observed"], clean
assert clean["mission_completed"], clean
assert clean["truth_samples"] > 20, clean
assert attack["airborne_observed"], attack
assert attack["truth_samples"] > 20, attack
assert attack["max_gps_truth_separation_m"] is not None, attack
assert clean["max_gps_truth_separation_m"] is not None, clean
assert attack["max_gps_truth_separation_m"] > max(
    5, clean["max_gps_truth_separation_m"] + 5), (clean, attack)
assert any(row["kind"] == "attack_request" for row in attack_events)
assert any(row["kind"] == "parameter_confirmed" and
           row["parameter"] == "SIM_GPS1_GLTCH_X" and
           abs(row["value"]) > 1e-6 for row in attack_events)
print("Smoke evidence: clean AUTO mission completed; attacked GPS diverged "
      "from Gazebo truth after confirmed parameter edit.")
