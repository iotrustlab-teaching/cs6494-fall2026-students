"""One Python execution path for HW4 runs, RTAMT checks, search, and replay."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

import staliro
from staliro import models
from staliro.optimizers import DualAnnealing, UniformRandom
from staliro.specifications import rtamt

from model import DT, Parameters, State, sampled, simulate
from reference_spec import SAFETY_FORMULA, SERVICE_FORMULA, evaluate, signals

SCHEMA = "cs6494-hw4-docking-v1"
SEARCH_DEFAULT_BOUNDS = (0.6, 1.6)
SOURCE_FILES = ("model.py", "reference_spec.py")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def file_digest(name: str) -> str:
    return hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()


def load_policy(path: str | Path = "policy.json") -> dict[str, float]:
    data = json.loads(Path(path).read_text())
    if set(data) != {"brake_at_m"}:
        raise ValueError("policy.json must contain only brake_at_m")
    value = data["brake_at_m"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("brake_at_m must be a finite number")
    if not 0.3 <= value <= 1.5:
        raise ValueError("brake_at_m must be between 0.3 and 1.5 m")
    return {"brake_at_m": float(value)}


def run_case(*, cruise_speed_m_s: float = 1.2, braking_m_s2: float = 0.5,
             policy: dict[str, float] | None = None) -> dict[str, Any]:
    if policy is None:
        policy = load_policy()
    params = Parameters(cruise_speed_m_s, braking_m_s2, policy["brake_at_m"])
    states = simulate(params)  # a fresh reset to x=-3 m and v=0 for every call
    points = sampled(states)
    results = evaluate(points)  # invokes RTAMT for both fixed requirements
    trace = [asdict(p) for p in states]
    sample_trace = [asdict(p) for p in points]
    identity = {"model_sha256": file_digest("model.py"),
                "reference_sha256": file_digest("reference_spec.py")}
    scenario = {"cruise_speed_m_s": params.cruise_speed,
                "braking_m_s2": params.braking}
    record = {
        "schema": SCHEMA,
        "kind": "fresh_model_run",
        "model": "course-authored 1-D robot approach; no Gazebo, SITL, or hardware",
        "identity": identity,
        "runtime": {"psy_taliro": version("psy-taliro"), "rtamt": version("rtamt")},
        "scenario": scenario,
        "policy": {"brake_at_m": params.brake_at},
        "reset": {"position_m": -3.0, "velocity_m_s": 0.0},
        "integration_step_s": DT,
        "sample_times_s": list(range(8)),
        "formulae": {"service": SERVICE_FORMULA, "safety": SAFETY_FORMULA},
        "monitor": results,
        "trace": trace,
        "samples": sample_trace,
        "trace_sha256": digest(trace),
    }
    record["run_id"] = digest({"identity": identity, "scenario": scenario,
                                "policy": record["policy"], "trace_sha256": record["trace_sha256"]})[:16]
    return record


def select_run(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("kind") == "search":
        return record["selected_run"]
    if record.get("kind") == "fresh_model_run":
        return record
    raise ValueError("expected a saved fresh model run or search result")


def selected_case_from_comparison(record: dict[str, Any], strategy: str) -> dict[str, Any]:
    """Export the exact selected run embedded in a matched search comparison."""
    if record.get("schema") != SCHEMA or record.get("kind") != "search_comparison":
        raise ValueError("expected a saved search comparison")
    if strategy not in {"random", "guided"}:
        raise ValueError("strategy must be random or guided")
    result = record.get(strategy)
    if not isinstance(result, dict) or result.get("kind") != "search" or result.get("strategy") != strategy:
        raise ValueError(f"comparison has no valid {strategy} search result")
    evaluations = result.get("evaluations")
    if not isinstance(evaluations, list) or len(evaluations) != result.get("actual_evaluations"):
        raise ValueError("comparison evaluation count is inconsistent")
    matching = [item for item in evaluations if item.get("trial") == result.get("selected_trial")]
    if len(matching) != 1:
        raise ValueError("comparison selected trial is missing or duplicated")
    selected = select_run(result)
    item = matching[0]
    if (selected.get("run_id") != item.get("run_id") or
            selected.get("scenario", {}).get("braking_m_s2") != item.get("braking_m_s2") or
            selected.get("policy") != result.get("policy") or
            result.get("seed") != record.get("seed") or
            result.get("bounds") != record.get("bounds") or
            result.get("requested_budget") != record.get("requested_budget")):
        raise ValueError("selected run does not match the comparison history")
    checks = selected["monitor"]
    if (not math.isclose(float(item["safety_score_normalized"]),
                         float(checks["safety"]["robustness_normalized"]), abs_tol=1e-7) or
            item["safety_pass"] != checks["safety"]["pass"] or
            item["service_pass"] != checks["service"]["pass"] or
            item["service_margin_m"] != checks["service"]["margin_m"] or
            result.get("selected_trial") != min(
                evaluations, key=lambda entry: (entry["safety_score_normalized"],
                                                entry["safety_pass"]))["trial"] or
            result.get("violation_found") != any(not entry["safety_pass"] for entry in evaluations)):
        raise ValueError("comparison selected case or history is inconsistent")
    replay_record(selected)  # verify the embedded run against the current source
    return selected


def replay_record(record: dict[str, Any], *, tolerance: float = 1e-9) -> dict[str, Any]:
    original = select_run(record)
    if original.get("schema") != SCHEMA:
        raise ValueError("unsupported run schema")
    if original.get("identity") != {"model_sha256": file_digest("model.py"),
                                    "reference_sha256": file_digest("reference_spec.py")}:
        raise ValueError("model or fixed evaluator changed; this is not an exact replay")
    if digest(original["trace"]) != original.get("trace_sha256"):
        raise ValueError("saved trace hash does not match its contents")
    again = run_case(**original["scenario"], policy=original["policy"])
    if again["run_id"] != original.get("run_id"):
        raise ValueError("saved run identity disagrees with fresh execution")
    if again["samples"] != original.get("samples") or again["monitor"] != original.get("monitor"):
        raise ValueError("saved samples or monitor results disagree with fresh execution")
    if len(original["trace"]) != len(again["trace"]):
        raise ValueError("replay produced a different trace length")
    max_error = max(abs(float(a[field]) - float(b[field]))
                    for a, b in zip(original["trace"], again["trace"], strict=True)
                    for field in ("time", "position", "velocity", "distance",
                                  "observed_remaining", "commanded_speed"))
    if max_error > tolerance:
        raise ValueError(f"replay differs by {max_error:g}, above tolerance {tolerance:g}")
    return {"schema": SCHEMA, "kind": "verified_replay", "original_run_id": original["run_id"],
            "replayed_run_id": again["run_id"], "max_state_error": max_error,
            "tolerance": tolerance, "match": True, "replayed_run": again}


def retest_record(record: dict[str, Any], policy: dict[str, float]) -> dict[str, Any]:
    original = select_run(record)
    replay_record(original)  # reject edited source, scenario, trace, or verdict before comparing
    fresh = run_case(**original["scenario"], policy=policy)
    fresh["comparison_to_run_id"] = original["run_id"]
    return fresh


def compare_records(first_record: dict[str, Any], second_record: dict[str, Any]) -> dict[str, Any]:
    """Export a compact, verified comparison of two fresh model executions."""
    first, second = select_run(first_record), select_run(second_record)
    first_proof, second_proof = replay_record(first), replay_record(second)
    if first["identity"] != second["identity"] or first["formulae"] != second["formulae"]:
        raise ValueError("runs use different model or fixed evaluation definitions")

    def summary(run: dict[str, Any]) -> dict[str, Any]:
        return {"run_id": run["run_id"], "scenario": run["scenario"], "policy": run["policy"],
                "service_pass": run["monitor"]["service"]["pass"],
                "service_margin_m": run["monitor"]["service"]["margin_m"],
                "safety_pass": run["monitor"]["safety"]["pass"],
                "safety_score_normalized": run["monitor"]["safety"]["robustness_normalized"],
                "too_fast_samples_s": run["monitor"]["safety"]["too_fast_samples_s"]}

    changes = [f"{section}.{name}" for section in ("scenario", "policy")
               for name in first[section] if first[section][name] != second[section][name]]
    return {"schema": SCHEMA, "kind": "run_comparison",
            "same_fixed_model_and_evaluator": True,
            "changed_fields": changes,
            "first": summary(first), "second": summary(second),
            "delta_second_minus_first": {
                "service_margin_m": (second["monitor"]["service"]["margin_m"]
                                     - first["monitor"]["service"]["margin_m"]),
                "safety_score_normalized": (second["monitor"]["safety"]["robustness_normalized"]
                                            - first["monitor"]["safety"]["robustness_normalized"]),
            },
            "verified_replay_max_state_error": {
                "first": first_proof["max_state_error"],
                "second": second_proof["max_state_error"],
            }}


def search(*, strategy: str, seed: int, budget: int,
           policy: dict[str, float] | None = None,
           braking_bounds: tuple[float, float] = SEARCH_DEFAULT_BOUNDS) -> dict[str, Any]:
    if strategy not in {"random", "guided"}:
        raise ValueError("strategy must be random or guided")
    if not 4 <= budget <= 60:
        raise ValueError("budget must be 4–60 evaluations")
    low, high = braking_bounds
    if not (math.isfinite(low) and math.isfinite(high) and 0.2 <= low < high <= 2.5):
        raise ValueError("braking bounds must lie within 0.2–2.5 m/s²")
    if policy is None:
        policy = load_policy()

    objective_model_runs = 0

    @staliro.model
    def adapter(inputs: staliro.Inputs) -> models.Trace[dict[str, float]]:
        nonlocal objective_model_runs
        objective_model_runs += 1
        braking = float(inputs.static["braking"])
        params = Parameters(1.2, braking, policy["brake_at_m"])
        return signals(sampled(simulate(params)))

    optimizer = UniformRandom() if strategy == "random" else DualAnnealing()
    options = staliro.TestOptions(static_inputs={"braking": (low, high)}, runs=1,
                                  iterations=budget, seed=seed)
    experiment = staliro.staliro(adapter, rtamt.parse_discrete(SAFETY_FORMULA), optimizer, options)[0]
    evaluations = []
    for index, item in enumerate(experiment.evaluations, 1):
        braking = float(item.inputs.static["braking"])
        fresh = run_case(braking_m_s2=braking, policy=policy)
        score = float(item.cost)
        if not math.isfinite(score):
            raise ValueError("search returned a non-finite cost")
        if not math.isclose(score, fresh["monitor"]["safety"]["robustness_normalized"], abs_tol=1e-7):
            raise ValueError("search score disagrees with fresh-run RTAMT score")
        evaluations.append({"trial": index, "braking_m_s2": braking,
                            "safety_score_normalized": score,
                            "safety_pass": fresh["monitor"]["safety"]["pass"],
                            "service_pass": fresh["monitor"]["service"]["pass"],
                            "service_margin_m": fresh["monitor"]["service"]["margin_m"],
                            "run_id": fresh["run_id"]})
    if not evaluations:
        raise ValueError("search produced no evaluations")
    if objective_model_runs != len(evaluations):
        raise ValueError("optimizer history does not match objective model executions")
    # At a zero-score tie, retain a direct Boolean violation before a pass.
    selected = min(evaluations, key=lambda item: (item["safety_score_normalized"],
                                                   item["safety_pass"]))
    selected_run = run_case(braking_m_s2=selected["braking_m_s2"], policy=policy)
    return {"schema": SCHEMA, "kind": "search", "strategy": strategy,
            "library_optimizer": type(optimizer).__name__, "seed": seed,
            "requested_budget": budget, "actual_evaluations": len(evaluations),
            "objective_model_runs": objective_model_runs,
            "record_verification_runs": len(evaluations) + 1,
            "violation_found": any(not item["safety_pass"] for item in evaluations),
            "bounds": {"braking_m_s2": [low, high]}, "fixed_cruise_speed_m_s": 1.2,
            "policy": policy, "objective": "minimize RTAMT normalized speed-while-inside robustness",
            "objective_formula": SAFETY_FORMULA, "evaluations": evaluations,
            "selected_trial": selected["trial"], "selected_run": selected_run,
            "comparison_scope": "One seeded run per optimizer; no general performance claim"}


def write_record(path: str | Path, record: dict[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    return destination


def read_record(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value
