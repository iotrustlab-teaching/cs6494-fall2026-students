#!/usr/bin/env python3
"""Student entry point for the course-authored robot docking HW4 workflow."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from staliro.models import Trace
from staliro.specifications import rtamt

from hw4_core import (SCHEMA, compare_records, load_policy, read_record, replay_record, retest_record,
                      run_case, search, selected_case_from_comparison, write_record)
from reference_spec import SERVICE_FORMULA


def student_formula_check(trace_file: Path | None = None) -> dict[str, object]:
    from student_spec import STUDENT_FORMULA

    fixtures = {
        "one brief visit is not a stay": [2.0, 1.1, 0.65, 0.35, 0.9, 1.2, 1.0, 0.8],
        "three consecutive inside samples": [2.0, 1.2, 0.8, 0.48, 0.42, 0.45, 0.3, 0.32],
        "never enters": [2.4, 2.0, 1.8, 1.4, 1.0, 0.8, 0.7, 0.6],
        "exactly on inclusive 0.5 m boundary": [2.0, 1.1, 0.7, 0.5, 0.5, 0.5, 0.5, 0.5],
    }
    if trace_file is not None:
        authored = json.loads(trace_file.read_text())
        if not isinstance(authored, dict) or set(authored) != {"distance_m"}:
            raise ValueError("authored fixture needs only a distance_m array")
        distances = authored["distance_m"]
        if (not isinstance(distances, list) or len(distances) != 8 or
                any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not math.isfinite(value) or value < 0 for value in distances)):
            raise ValueError("distance_m must contain eight finite, nonnegative metre values for seconds 0–7")
        fixtures["student-authored monitor fixture"] = distances
    student = rtamt.parse_discrete(STUDENT_FORMULA)
    reference = rtamt.parse_discrete(SERVICE_FORMULA)
    cases = []
    for name, distances in fixtures.items():
        trace = Trace({k: {"e": e} for k, e in enumerate(distances)})
        expected = float(reference.evaluate(trace).value)
        actual = float(student.evaluate(trace).value)
        if not (math.isfinite(expected) and math.isfinite(actual)):
            raise ValueError("formula returned a non-finite robustness value")
        cases.append({"fixture": name, "expected_margin_m": expected,
                      "student_margin_m": actual,
                      "reference_pass": expected >= -1e-9,
                      "student_pass": actual >= -1e-9,
                      "source": ("student_authored_monitor_fixture" if name == "student-authored monitor fixture"
                                 else "provided_monitor_fixture"),
                      "matches": math.isclose(expected, actual, abs_tol=1e-9)})
    return {"schema": SCHEMA, "kind": "student_formula_check",
            "student_formula": STUDENT_FORMULA, "reference_formula": SERVICE_FORMULA,
            "cases": cases, "all_match": all(c["matches"] for c in cases),
            "note": "Zero robustness at the inclusive boundary passes this predicate; do not generalize zero to strict predicates."}


def describe_run(record: dict[str, object]) -> None:
    scenario, policy, checks = record["scenario"], record["policy"], record["monitor"]
    service, safety = checks["service"], checks["safety"]
    print(f"Fresh model run {record['run_id']} · braking {scenario['braking_m_s2']:.3f} m/s² · "
          f"speed {scenario['cruise_speed_m_s']:.2f} m/s · brake point {policy['brake_at_m']:.2f} m")
    print(f"RTAMT service (reach and stay): {'PASS' if service['pass'] else 'FAIL'} · "
          f"margin {service['margin_m']:+.3f} m")
    safety_label = 'PASS' if safety['pass'] else 'FAIL'
    coverage = 'EXERCISED' if safety['exercised'] else 'NOT EXERCISED'
    print(f"RTAMT speed while inside: {safety_label} · antecedent {coverage} · normalized score "
          f"{safety['robustness_normalized']:+.3f} · too-fast samples "
          f"{safety['too_fast_samples_s']}")
    print("Sample times: 0–7 s at 1 s spacing; no interpolation. Model reset to x=-3 m, v=0.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="reset, execute, monitor, and export a fresh run")
    run.add_argument("--speed", type=float, default=1.2, help="scenario cruise speed in m/s")
    run.add_argument("--braking", type=float, default=0.5, help="scenario maximum deceleration in m/s²")
    run.add_argument("--policy", type=Path, default=Path("policy.json"))
    run.add_argument("--out", type=Path, help="saved JSON path; default runs/run_<id>.json")

    check = commands.add_parser("check-spec", help="check student_spec.py against hand-checkable cases")
    check.add_argument("--trace-file", type=Path, help="optional student-authored monitor fixture JSON")
    check.add_argument("--out", type=Path, help="optional JSON report path")

    search_cmd = commands.add_parser("search", help="PSY-TaLiRo search of one bounded braking input")
    search_cmd.add_argument("--strategy", choices=["random", "guided"], required=True)
    search_cmd.add_argument("--seed", type=int, default=7)
    search_cmd.add_argument("--budget", type=int, default=12)
    search_cmd.add_argument("--min-braking", type=float, default=0.6)
    search_cmd.add_argument("--max-braking", type=float, default=1.6)
    search_cmd.add_argument("--policy", type=Path, default=Path("policy.json"))
    search_cmd.add_argument("--out", type=Path, help="saved JSON path")

    compare = commands.add_parser("compare-search", help="run both strategies with matched seed, bounds, and budget")
    compare.add_argument("--seed", type=int, default=7)
    compare.add_argument("--budget", type=int, default=12)
    compare.add_argument("--min-braking", type=float, default=0.6)
    compare.add_argument("--max-braking", type=float, default=1.6)
    compare.add_argument("--policy", type=Path, default=Path("policy.json"))
    compare.add_argument("--out", type=Path, default=Path("runs/search_comparison.json"))

    selected = commands.add_parser("select-case", help="export one exact selected run from a search comparison")
    selected.add_argument("comparison", type=Path, help="saved compare-search JSON")
    selected.add_argument("--strategy", choices=["random", "guided"], required=True)
    selected.add_argument("--out", type=Path, help="selected run JSON path")

    replay = commands.add_parser("replay", help="rerun the saved scenario and policy, then compare traces")
    replay.add_argument("case", type=Path, help="saved run or search JSON")
    replay.add_argument("--out", type=Path, help="optional replay proof JSON")

    retest = commands.add_parser("retest", help="run a saved scenario against the current edited policy")
    retest.add_argument("case", type=Path, help="saved run or search JSON")
    retest.add_argument("--policy", type=Path, default=Path("policy.json"))
    retest.add_argument("--out", type=Path, help="optional fresh comparison JSON")

    compare_runs = commands.add_parser("compare-runs", help="verify and summarize two saved model runs")
    compare_runs.add_argument("first", type=Path)
    compare_runs.add_argument("second", type=Path)
    compare_runs.add_argument("--out", type=Path, default=Path("runs/run_comparison.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            record = run_case(cruise_speed_m_s=args.speed, braking_m_s2=args.braking,
                              policy=load_policy(args.policy))
            path = args.out or Path("runs") / f"run_{record['run_id']}.json"
            write_record(path, record)
            describe_run(record)
            print(f"Saved: {path}")
        elif args.command == "check-spec":
            report = student_formula_check(args.trace_file)
            print(f"Student formula: {report['student_formula']}")
            for case in report["cases"]:
                mark = "MATCH" if case["matches"] else "DIFF"
                print(f"{mark:5} {case['fixture']}: student {case['student_margin_m']:+.3f} m; "
                      f"reference {case['expected_margin_m']:+.3f} m")
            if args.out:
                write_record(args.out, report)
                print(f"Saved: {args.out}")
            return 0 if report["all_match"] else 1
        elif args.command == "search":
            report = search(strategy=args.strategy, seed=args.seed, budget=args.budget,
                            policy=load_policy(args.policy),
                            braking_bounds=(args.min_braking, args.max_braking))
            path = args.out or Path("runs") / f"search_{args.strategy}_seed{args.seed}_budget{args.budget}.json"
            write_record(path, report)
            print(f"{report['library_optimizer']} · {report['actual_evaluations']} evaluations "
                  f"(requested {report['requested_budget']}) · seed {args.seed}")
            for item in report["evaluations"]:
                print(f"{item['trial']:2d} braking={item['braking_m_s2']:.3f} m/s² "
                      f"safety={item['safety_score_normalized']:+.3f} normalized "
                      f"({'FAIL' if not item['safety_pass'] else 'PASS'}) "
                      f"service={'PASS' if item['service_pass'] else 'FAIL'}")
            print(f"Selected trial {report['selected_trial']}; saved: {path}")
        elif args.command == "compare-search":
            policy = load_policy(args.policy)
            bounds = (args.min_braking, args.max_braking)
            random_result = search(strategy="random", seed=args.seed, budget=args.budget,
                                   policy=policy, braking_bounds=bounds)
            guided_result = search(strategy="guided", seed=args.seed, budget=args.budget,
                                   policy=policy, braking_bounds=bounds)
            report = {"schema": SCHEMA, "kind": "search_comparison", "seed": args.seed,
                      "bounds": {"braking_m_s2": list(bounds)}, "requested_budget": args.budget,
                      "random": random_result, "guided": guided_result,
                      "scope": "One matched-budget seeded comparison, not an optimizer benchmark"}
            write_record(args.out, report)
            for name, result in [("random", random_result), ("guided", guided_result)]:
                selected = result["selected_run"]
                print(f"{name}: {result['actual_evaluations']} evaluations, "
                      f"selected trial {result['selected_trial']}, "
                      f"speed rule {'PASS' if selected['monitor']['safety']['pass'] else 'FAIL'}, "
                      f"score {selected['monitor']['safety']['robustness_normalized']:+.3f}")
            print(f"Saved: {args.out}")
        elif args.command == "select-case":
            selected = selected_case_from_comparison(read_record(args.comparison), args.strategy)
            path = args.out or Path("runs") / f"selected_{args.strategy}_case.json"
            write_record(path, selected)
            print(f"Exported the exact {args.strategy} selected run {selected['run_id']} "
                  f"from {args.comparison}; saved: {path}")
        elif args.command == "replay":
            proof = replay_record(read_record(args.case))
            print(f"Replayed {proof['original_run_id']}: MATCH, maximum state difference "
                  f"{proof['max_state_error']:.3g} (tolerance {proof['tolerance']:.3g})")
            if args.out:
                write_record(args.out, proof)
                print(f"Saved: {args.out}")
        elif args.command == "retest":
            fresh = retest_record(read_record(args.case), load_policy(args.policy))
            path = args.out or Path("runs") / f"retest_{fresh['run_id']}.json"
            write_record(path, fresh)
            describe_run(fresh)
            print(f"Compared with run {fresh['comparison_to_run_id']}; saved: {path}")
        elif args.command == "compare-runs":
            report = compare_records(read_record(args.first), read_record(args.second))
            write_record(args.out, report)
            print(f"Verified {report['first']['run_id']} → {report['second']['run_id']}")
            print(f"Changed: {', '.join(report['changed_fields']) or 'nothing'}")
            print(f"Service margin: {report['first']['service_margin_m']:+.3f} → "
                  f"{report['second']['service_margin_m']:+.3f} m")
            print(f"Safety score: {report['first']['safety_score_normalized']:+.3f} → "
                  f"{report['second']['safety_score_normalized']:+.3f} normalized")
            print(f"Saved: {args.out}")
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
