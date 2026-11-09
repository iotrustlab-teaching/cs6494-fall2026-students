#!/usr/bin/env python3
"""Small, deterministic 1-D ground-robot simulation for the STL class demo.

This is a course-authored dynamics/controller model, not Gazebo, PX4, or hardware.
The controller drives toward a docking point, then commands zero velocity when
the reported remaining distance reaches a specified braking point. Momentum
can carry the robot through the region before it stops.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


DT = 0.05
HORIZON = 7
TARGET_RADIUS = 0.5
MAX_ACCELERATION = 1.2


@dataclass(frozen=True)
class Parameters:
    cruise_speed: float = 1.2  # meters / second
    braking: float = 0.5  # maximum deceleration, meters / second^2
    brake_at: float = 0.8  # meters before the dock

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0.3 <= self.cruise_speed <= 1.8:
            raise ValueError("cruise_speed must be between 0.3 and 1.8 m/s")
        if not 0.2 <= self.braking <= 2.5:
            raise ValueError("braking must be between 0.2 and 2.5 m/s²")
        if not 0.3 <= self.brake_at <= 1.5:
            raise ValueError("brake_at must be between 0.3 and 1.5 m")


@dataclass(frozen=True)
class State:
    time: float
    position: float  # dock is x = 0, start at x = -3
    velocity: float
    distance: float
    observed_remaining: float  # ideal controller-visible sensor, meters ahead of dock
    commanded_speed: float  # controller output for the next integration step, m/s


def controller_command(observed_remaining: float, params: Parameters) -> float:
    """Use only controller-visible distance and the policy threshold."""
    return params.cruise_speed if observed_remaining > params.brake_at else 0.0


def simulate(params: Parameters) -> list[State]:
    """Integrate a controller/kinematics loop at 20 Hz for seven seconds."""
    params.validate()
    position, velocity = -3.0, 0.0
    observation = max(0.0, -position)
    states = [State(0.0, position, velocity, abs(position), observation,
                    controller_command(observation, params))]
    steps = round(HORIZON / DT)
    for i in range(1, steps + 1):
        delta = states[-1].commanded_speed - velocity
        delta = min(MAX_ACCELERATION * DT, max(-params.braking * DT, delta))
        velocity += delta
        position += velocity * DT
        t = round(i * DT, 8)
        observation = max(0.0, -position)
        states.append(State(t, position, velocity, abs(position), observation,
                            controller_command(observation, params)))
    return states


def sampled(states: list[State]) -> list[State]:
    result = [states[round(second / DT)] for second in range(HORIZON + 1)]
    if [round(state.time, 8) for state in result] != list(range(HORIZON + 1)):
        raise ValueError("simulation did not yield exactly the required sample times")
    return result


def monitor(samples: list[State]) -> dict[str, object]:
    """Evaluate sampled reach, dwell, and speed-while-inside properties."""
    if len(samples) != HORIZON + 1:
        raise ValueError("eight samples from t=0 through t=7 are required")
    for expected, sample in enumerate(samples):
        if not (math.isfinite(sample.time) and math.isfinite(sample.distance) and math.isfinite(sample.velocity)):
            raise ValueError("sample times, distances, and speeds must be finite")
        if not math.isclose(sample.time, expected, abs_tol=1e-9):
            raise ValueError("samples must occur at t=0,1,...,7 seconds")
        if sample.distance < 0:
            raise ValueError("distance must not be negative")
    margins = [TARGET_RADIUS - point.distance for point in samples]
    window_margins = [min(margins[start : start + 3]) for start in range(6)]
    reach_margin = max(margins[:6])
    dwell_margin = max(window_margins)
    reach_witness = next((k for k, v in enumerate(margins[:6]) if v >= 0), None)
    dwell_witness = next((k for k, v in enumerate(window_margins) if v >= 0), None)
    fast_entry_samples = [k for k, point in enumerate(samples[:6])
                          if point.distance <= TARGET_RADIUS and abs(point.velocity) > 0.2]
    inside_samples = [k for k, point in enumerate(samples[:6])
                      if point.distance <= TARGET_RADIUS]
    return {
        "reach": reach_margin >= 0,
        "reach_margin": round(reach_margin, 6),
        "reach_witness": reach_witness,
        "dwell": dwell_margin >= 0,
        "dwell_margin": round(dwell_margin, 6),
        "dwell_witness_start": dwell_witness,
        "window_margins": [round(v, 6) for v in window_margins],
        "slow_entry": not fast_entry_samples,
        "inside_samples": inside_samples,
        "fast_entry_samples": fast_entry_samples,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed", type=float, default=1.2, help="cruise speed in m/s")
    parser.add_argument("--braking", type=float, default=0.5, help="maximum deceleration in m/s²")
    parser.add_argument("--brake-at", type=float, default=0.8, help="controller stop-command threshold in m")
    parser.add_argument("--csv", type=Path, help="optional CSV output for the eight sampled states")
    parser.add_argument("--json", action="store_true", help="emit machine-readable run record")
    args = parser.parse_args(argv)
    try:
        params = Parameters(args.speed, args.braking, args.brake_at)
        points = sampled(simulate(params))
        verdict = monitor(points)
    except ValueError as error:
        parser.error(str(error))
    if args.csv:
        with args.csv.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["time_s", "position_m", "velocity_m_s", "distance_m"])
            writer.writeheader()
            for point in points:
                writer.writerow({"time_s": point.time, "position_m": point.position,
                                 "velocity_m_s": point.velocity, "distance_m": point.distance})
    record = {"model": "course-authored 1-D docking controller and kinematics",
              "integration_dt_s": DT, "sample_times_s": list(range(HORIZON + 1)),
              "parameters": asdict(params), "samples": [asdict(point) for point in points],
              "monitor": verdict}
    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print("Course-authored 1-D ground-robot simulation (not Gazebo/PX4/hardware)")
        print(f"speed={params.cruise_speed:.2f} m/s  braking={params.braking:.2f} m/s²  brake_at={params.brake_at:.2f} m")
        print("time (s):     " + "  ".join(str(n) for n in range(HORIZON + 1)))
        print("distance (m): " + "  ".join(f"{p.distance:.2f}" for p in points))
        print("speed (m/s):  " + "  ".join(f"{abs(p.velocity):.2f}" for p in points))
        print(f"reach once: {'PASS' if verdict['reach'] else 'FAIL'}  margin={verdict['reach_margin']:+.3f} m")
        print(f"reach + stay: {'PASS' if verdict['dwell'] else 'FAIL'}  margin={verdict['dwell_margin']:+.3f} m")
        stay_start = verdict['dwell_witness_start']
        print("first passing stay starts: " + (f"{stay_start} s" if stay_start is not None else "none"))
        speed_status = ('NOT EXERCISED (no in-region sample)' if not verdict['inside_samples']
                        else 'PASS' if verdict['slow_entry'] else 'FAIL')
        print(f"speed while inside region: {speed_status}  fast samples={verdict['fast_entry_samples']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
