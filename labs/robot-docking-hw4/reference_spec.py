"""Fixed HW4 evaluator. Student formula practice lives in student_spec.py."""

from __future__ import annotations

import math

from staliro.models import Trace
from staliro.specifications import rtamt

from model import HORIZON, State, monitor

SERVICE_FORMULA = "eventually[0,5] (always[0,2] (e <= 0.5))"
SAFETY_FORMULA = "always[0,5] ((outside_norm > 0) or (slow_norm >= 0))"
SERVICE_LIMIT_M = 0.5
SLOW_LIMIT_M_S = 0.2
DISTANCE_SCALE_M = 0.5
SPEED_SCALE_M_S = 0.2


def signals(points: list[State]) -> Trace[dict[str, float]]:
    """Build an eight-point, one-second RTAMT trace from reference states."""
    if len(points) != HORIZON + 1:
        raise ValueError("STL needs samples at every integer second from 0 through 7")
    for k, point in enumerate(points):
        if not math.isclose(point.time, k, abs_tol=1e-9):
            raise ValueError("STL sample times must be 0, 1, ..., 7 seconds")
        if not all(math.isfinite(x) for x in (point.position, point.velocity, point.distance)):
            raise ValueError("STL inputs must be finite")
    return Trace({k: {
        "e": p.distance,
        "outside_norm": (p.distance - SERVICE_LIMIT_M) / DISTANCE_SCALE_M,
        "slow_norm": (SLOW_LIMIT_M_S - abs(p.velocity)) / SPEED_SCALE_M_S,
    } for k, p in enumerate(points)})


def evaluate(points: list[State]) -> dict[str, object]:
    """Run real RTAMT discrete monitoring and retain exact Boolean boundary checks."""
    trace = signals(points)
    direct = monitor(points)
    service_margin = float(rtamt.parse_discrete(SERVICE_FORMULA).evaluate(trace).value)
    safety_score = float(rtamt.parse_discrete(SAFETY_FORMULA).evaluate(trace).value)
    if not (math.isfinite(service_margin) and math.isfinite(safety_score)):
        raise ValueError("RTAMT returned a non-finite robustness score")
    if not math.isclose(service_margin, float(direct["dwell_margin"]), abs_tol=1e-5):
        raise ValueError("RTAMT service margin disagrees with direct sample arithmetic")
    if safety_score < -1e-8 and bool(direct["slow_entry"]):
        raise ValueError("RTAMT safety sign disagrees with the sampled Boolean check")
    if safety_score > 1e-8 and not bool(direct["slow_entry"]):
        raise ValueError("RTAMT safety sign disagrees with the sampled Boolean check")
    return {
        "semantics": "discrete RTAMT at 1 s; no interpolation; integration at 0.05 s",
        "service": {
            "formula": SERVICE_FORMULA,
            "pass": bool(direct["dwell"]),
            "margin_m": service_margin,
            "first_window_start_s": direct["dwell_witness_start"],
            "requires_samples_through_s": 7,
        },
        "safety": {
            "formula": SAFETY_FORMULA,
            "pass": bool(direct["slow_entry"]),
            "exercised": bool(direct["inside_samples"]),
            "robustness_normalized": safety_score,
            "normalization": {"outside_distance_m": DISTANCE_SCALE_M,
                              "slow_speed_m_s": SPEED_SCALE_M_S},
            "inside_samples_s": direct["inside_samples"],
            "too_fast_samples_s": direct["fast_entry_samples"],
            "zero_score_note": "At zero robustness, inspect strict/inclusive predicates; Boolean result is authoritative.",
        },
    }
