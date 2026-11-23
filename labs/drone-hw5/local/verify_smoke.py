"""Require real controller/plant receipts from all four practice flights."""

import json
from pathlib import Path


def latest(case: str) -> tuple[dict, list[dict]]:
    summaries = sorted(Path("runs").glob(f"*-{case}.summary.json"))
    if not summaries:
        raise AssertionError(f"No summary for {case}")
    summary_path = summaries[-1]
    summary = json.loads(summary_path.read_text())
    trace_path = Path(str(summary_path).replace(".summary.json", ".jsonl"))
    route_path = Path(str(summary_path).replace(".summary.json", ".route.svg"))
    assert trace_path.is_file() and trace_path.stat().st_size > 0, trace_path
    assert route_path.is_file() and "<svg" in route_path.read_text()[:500], route_path
    events = [json.loads(row) for row in trace_path.read_text().splitlines()]
    assert summary["case"] == case, summary
    return summary, events


cases = ["clean-starter", "attack-starter", "attack-student", "clean-student"]
receipts = {case: latest(case) for case in cases}
for case, (summary, events) in receipts.items():
    assert summary["watchdog"] == case.split("-")[1], summary
    assert summary["airborne_observed"], summary
    assert summary["finished_disarmed"], summary
    assert summary["mission_completed"], summary
    assert summary["final_mission_item_reached"], summary
    assert summary["truth_samples"] > 20, summary
    assert summary["max_gps_truth_separation_m"] is not None, summary
    assert any(row["kind"] == "flight_finished" for row in events), case

for suffix in ("starter", "student"):
    clean, clean_events = receipts[f"clean-{suffix}"]
    attack, attack_events = receipts[f"attack-{suffix}"]
    assert not any(row["kind"] == "attack_request" for row in clean_events), clean
    assert attack["max_gps_truth_separation_m"] > max(
        5, clean["max_gps_truth_separation_m"] + 5), (clean, attack)
    assert any(row["kind"] == "parameter_confirmed" and
               row["parameter"] == "SIM_GPS1_GLTCH_X" and
               abs(row["value"]) > 1e-6 for row in attack_events), attack


def attack_requests(events: list[dict]) -> list[tuple[float, float]]:
    return [(row["north_m"], row["east_m"]) for row in events
            if row["kind"] == "attack_request"]


starter_requests = attack_requests(receipts["attack-starter"][1])
student_requests = attack_requests(receipts["attack-student"][1])
for requests in (starter_requests, student_requests):
    # Sampling occurs on the simulator clock, so intermediate ramp values may
    # differ. Both flights must reach the same intended peak and return to zero.
    assert requests, requests
    assert any(abs(north - 20) < 1 and abs(east) < 1 for north, east in requests), requests
    assert abs(requests[-1][0]) < 1 and abs(requests[-1][1]) < 1, requests
print("Smoke evidence: all four AUTO missions completed; the same bounded GPS "
      "edit reached both attacked flights; starter and student watchdog cases "
      "produced labeled receipts. Inspect trace for actual route effect.")
