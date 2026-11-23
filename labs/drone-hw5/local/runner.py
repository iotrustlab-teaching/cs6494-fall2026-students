"""Run one isolated, public-source ArduPilot/Gazebo practice flight.

The only student-facing control surfaces are attack.py and student_watchdog.py.
This runner intentionally keeps simulator truth out of the watchdog interface.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
import time
from pathlib import Path

from pymavlink import mavutil

from attack import AttackPlan, degrees_from_meters
from render_trace import render as render_trace


HOME_LAT = -35.363262
HOME_LON = 149.165237
ALT_M = 12.0
RUNS = Path("/runs")
GPS_PARAM_NAMES = ("SIM_GPS1_GLTCH_X", "SIM_GPS1_GLTCH_Y")
AUTOPILOT_COMPONENT = mavutil.mavlink.MAV_COMP_ID_AUTOPILOT1


def point(north_m: float, east_m: float) -> tuple[int, int]:
    lat_delta, lon_delta = degrees_from_meters(north_m, east_m, HOME_LAT)
    return round((HOME_LAT + lat_delta) * 1e7), round((HOME_LON + lon_delta) * 1e7)


def mission_items() -> list[tuple[int, int, int, float]]:
    # The same compact AUTO route is used for all four cases.  Its 30 m
    # square is a generic practice world, not the CTF's campus mission.
    # ArduPilot reserves mission seq 0 for home.  The first executable
    # command is therefore TAKEOFF at seq 1.
    items = [
        (mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *point(0, 0), 0.0),
        (mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, *point(0, 0), ALT_M),
        (mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *point(0, 30), ALT_M),
        (mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *point(30, 30), ALT_M),
        (mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *point(30, 0), ALT_M),
        (mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH, *point(0, 0), 0.0),
    ]
    return items


def offset_from_home(latitude: float, longitude: float) -> tuple[float, float]:
    metres_per_degree = 111_194.9
    return ((latitude - HOME_LAT) * metres_per_degree,
            (longitude - HOME_LON) * metres_per_degree
            * math.cos(math.radians(HOME_LAT)))


def near_practice_world(latitude: float, longitude: float) -> bool:
    """Reject uninitialized telemetry such as simulator latitude 0/longitude 0."""
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return False
    north, east = offset_from_home(latitude, longitude)
    return math.hypot(north, east) < 1000


def distance_to_segment(point_xy, start_xy, end_xy) -> float:
    ax, ay = start_xy
    bx, by = end_xy
    px, py = point_xy
    denom = (bx - ax) ** 2 + (by - ay) ** 2
    fraction = 0.0 if denom == 0 else max(0.0, min(1.0,
        ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / denom))
    return math.hypot(px - (ax + fraction * (bx - ax)),
                      py - (ay + fraction * (by - ay)))


def route_deviation(latitude: float, longitude: float) -> float:
    location = offset_from_home(latitude, longitude)
    route = [(0, 0), (0, 30), (30, 30), (30, 0), (0, 0)]
    return min(distance_to_segment(location, a, b)
               for a, b in zip(route, route[1:]))


class Flight:
    def __init__(self, case: str, max_seconds: float) -> None:
        self.case = case
        self.max_seconds = max_seconds
        self.connection = None
        self.t0 = 0.0
        self.latest_mode = "UNKNOWN"
        self.armed = False
        self.latest_seq = -1
        self.latest_gps = None
        self.latest_truth = None
        self.latest_estimate = None
        self.current_boot_s = None
        self.parameter_values: dict[str, float] = {}
        self.param_pending: set[str] = set()
        self.events: list[dict] = []
        self.attack_enabled = case.startswith("attack-")
        self.attack = AttackPlan() if self.attack_enabled else None
        module = "student_watchdog" if case.endswith("student") else "starter_watchdog"
        self.watchdog = importlib.import_module(module).Watchdog()
        self.last_attack_update = 0.0
        self.last_attack_offset = (0.0, 0.0)
        self.seen_flight = False
        self.airborne = False
        self.mode_requests = 0
        self.mode_confirmations = 0
        self.max_truth_route_deviation_m = None
        self.max_gps_truth_separation_m = None
        self.truth_samples = 0

    def emit(self, kind: str, **fields: object) -> None:
        event = {"t_s": round(max(0.0, time.monotonic() - self.t0), 3)
                 if self.t0 else 0.0,
                 "kind": kind, **fields}
        self.events.append(event)
        if kind in {"error", "mode_request", "mode_confirmed", "attack_request",
                    "parameter_confirmed", "mission", "connected"}:
            print(json.dumps(event), flush=True)

    def connect(self) -> None:
        deadline = time.monotonic() + 90
        last_error = None
        while time.monotonic() < deadline:
            try:
                self.connection = mavutil.mavlink_connection(
                    "tcp:127.0.0.1:5760", autoreconnect=False,
                    source_system=250, source_component=1)
                heartbeat = self.connection.wait_heartbeat(timeout=5)
                if heartbeat:
                    self.t0 = time.monotonic()
                    self.latest_mode = mavutil.mode_string_v10(heartbeat)
                    self.emit("connected", system=self.connection.target_system,
                              component=AUTOPILOT_COMPONENT,
                              mode=self.latest_mode)
                    return
            except (ConnectionError, OSError, EOFError) as exc:
                last_error = repr(exc)
            time.sleep(2)
        raise RuntimeError(f"No SITL heartbeat within 90 s: {last_error}")

    def command(self, command: int, *params: float) -> None:
        conn = self.connection
        seven = tuple(params) + (0.0,) * (7 - len(params))
        conn.mav.command_long_send(conn.target_system, AUTOPILOT_COMPONENT,
                                   command, 0, *seven)

    def request_streams(self) -> None:
        for message_id, interval_us in (
            (mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT, 500_000),
            (mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, 200_000),
            (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 200_000),
            (mavutil.mavlink.MAVLINK_MSG_ID_SIMSTATE, 200_000),
            (mavutil.mavlink.MAVLINK_MSG_ID_MISSION_CURRENT, 500_000),
        ):
            self.command(mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                         message_id, interval_us)

    def read(self, timeout: float = 0.5, watch: bool = False) -> None:
        msg = self.connection.recv_match(blocking=True, timeout=timeout)
        if msg is None:
            return
        typ = msg.get_type()
        if typ == "BAD_DATA":
            return
        if typ == "HEARTBEAT":
            mode = mavutil.mode_string_v10(msg)
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if mode != self.latest_mode:
                self.latest_mode = mode
                self.mode_confirmations += 1
                self.emit("mode_confirmed", mode=mode)
            if armed != self.armed:
                self.armed = armed
                self.emit("armed_state", armed=armed)
                self.seen_flight |= armed
        elif typ == "MISSION_CURRENT":
            if msg.seq != self.latest_seq:
                self.latest_seq = msg.seq
                self.emit("mission", sequence=msg.seq)
        elif typ == "GPS_RAW_INT":
            if msg.fix_type < 3 or not near_practice_world(msg.lat / 1e7,
                                                           msg.lon / 1e7):
                self.emit("gps_unusable", fix_type=msg.fix_type)
                return
            self.latest_gps = msg
            if self.latest_truth is not None:
                north, east = offset_from_home(msg.lat / 1e7, msg.lon / 1e7)
                true_north, true_east = offset_from_home(*self.latest_truth)
                separation = math.hypot(north - true_north, east - true_east)
                self.max_gps_truth_separation_m = max(
                    self.max_gps_truth_separation_m or 0.0, separation)
            self.emit("gps", latitude_deg=msg.lat / 1e7,
                      longitude_deg=msg.lon / 1e7, fix_type=msg.fix_type,
                      speed_m_s=None if msg.vel == 65535 else msg.vel / 100)
            if watch and self.armed:
                self.check_watchdog(msg)
        elif typ == "SIMSTATE":
            if not near_practice_world(msg.lat / 1e7, msg.lng / 1e7):
                self.emit("truth_unusable")
                return
            # Diagnostic truth is recorded for comparison, never provided to
            # student_watchdog.Watchdog.update().
            self.latest_truth = (msg.lat / 1e7, msg.lng / 1e7)
            self.truth_samples += 1
            deviation = route_deviation(*self.latest_truth)
            self.max_truth_route_deviation_m = max(
                self.max_truth_route_deviation_m or 0.0, deviation)
            self.emit("truth", latitude_deg=self.latest_truth[0],
                      longitude_deg=self.latest_truth[1])
        elif typ == "GLOBAL_POSITION_INT":
            self.current_boot_s = msg.time_boot_ms / 1000.0
            if not near_practice_world(msg.lat / 1e7, msg.lon / 1e7):
                self.emit("estimate_unusable")
                return
            self.latest_estimate = (msg.lat / 1e7, msg.lon / 1e7)
            if self.armed and msg.relative_alt > 2000:
                self.airborne = True
            self.emit("estimate", latitude_deg=self.latest_estimate[0],
                      longitude_deg=self.latest_estimate[1],
                      relative_alt_m=msg.relative_alt / 1000)
        elif typ == "PARAM_VALUE":
            name = msg.param_id
            if isinstance(name, bytes):
                name = name.decode("ascii", "replace")
            name = str(name).rstrip("\0")
            if name in self.param_pending:
                self.parameter_values[name] = float(msg.param_value)
                self.param_pending.discard(name)
                self.emit("parameter_confirmed", parameter=name,
                          value=float(msg.param_value))
        elif typ == "STATUSTEXT":
            text = msg.text.decode("utf-8", "replace") if isinstance(msg.text, bytes) else str(msg.text)
            self.emit("status", text=text)
        elif typ == "COMMAND_ACK":
            self.emit("command_ack", command=int(msg.command), result=int(msg.result))

    def wait_for(self, predicate, seconds: float, label: str,
                 watch: bool = False) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            self.read(watch=watch)
        raise RuntimeError(f"Timed out waiting for {label}")

    def set_parameter(self, name: str, value: float, tolerance: float = 1e-6) -> None:
        conn = self.connection
        actual = None
        for attempt in range(1, 4):
            self.param_pending.add(name)
            conn.mav.param_set_send(conn.target_system, AUTOPILOT_COMPONENT,
                                    name.encode("ascii"), float(value),
                                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and name in self.param_pending:
                self.read(timeout=0.3, watch=self.armed)
            actual = self.parameter_values.get(name)
            if (name not in self.param_pending and actual is not None
                    and abs(actual - value) <= tolerance):
                return
            self.emit("parameter_retry", parameter=name, attempt=attempt,
                      requested=value, observed=actual)
            self.param_pending.add(name)
            conn.mav.param_request_read_send(conn.target_system,
                                             AUTOPILOT_COMPONENT,
                                             name.encode("ascii"), -1)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and name in self.param_pending:
                self.read(timeout=0.3, watch=self.armed)
            actual = self.parameter_values.get(name)
            if (name not in self.param_pending and actual is not None
                    and abs(actual - value) <= tolerance):
                return
        raise RuntimeError(f"Parameter {name} requested {value}, got {actual}")

    def upload_mission(self) -> None:
        conn = self.connection
        items = mission_items()
        conn.mav.mission_clear_all_send(conn.target_system, AUTOPILOT_COMPONENT)
        # The clear operation has its own ACK. Never count it as upload success.
        conn.recv_match(type="MISSION_ACK", blocking=True, timeout=3)
        conn.mav.mission_count_send(conn.target_system, AUTOPILOT_COMPONENT,
                                    len(items))
        pending = set(range(len(items)))
        deadline = time.monotonic() + 25
        accepted = False
        while time.monotonic() < deadline:
            msg = conn.recv_match(blocking=True, timeout=1)
            if msg is None:
                continue
            typ = msg.get_type()
            if typ in ("MISSION_REQUEST_INT", "MISSION_REQUEST"):
                seq = int(msg.seq)
                if not 0 <= seq < len(items):
                    raise RuntimeError(f"Mission requested invalid item {seq}")
                command, lat, lon, alt = items[seq]
                if typ == "MISSION_REQUEST_INT":
                    conn.mav.mission_item_int_send(
                        conn.target_system, AUTOPILOT_COMPONENT, seq,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        command, 0, 1, 0, 0, 0, 0, lat, lon, alt)
                else:
                    conn.mav.mission_item_send(
                        conn.target_system, AUTOPILOT_COMPONENT, seq,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                        command, 0, 1, 0, 0, 0, 0, lat / 1e7, lon / 1e7, alt)
                pending.discard(seq)
            elif typ == "MISSION_ACK":
                if pending:
                    # A stray ACK cannot prove the current mission was uploaded.
                    continue
                if msg.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                    raise RuntimeError(f"Mission rejected: MAV_MISSION_RESULT {msg.type}")
                accepted = True
                break
            elif typ == "STATUSTEXT":
                self.emit("status", text=str(msg.text))
        if not accepted or pending:
            raise RuntimeError(f"Mission upload incomplete; pending {sorted(pending)}")
        self.emit("mission_uploaded", count=len(items), route="30 m square, takeoff/RTL")

    def set_mode(self, mode: str) -> None:
        mapping = self.connection.mode_mapping()
        if mode not in mapping:
            raise RuntimeError(f"Flight mode {mode} unavailable; modes={mapping}")
        self.connection.set_mode(mapping[mode])
        self.mode_requests += 1
        self.emit("mode_request", mode=mode)

    def check_watchdog(self, gps_msg) -> None:
        # GPS time advances with the simulated flight, including when an
        # emulated x86 container runs slower than wall time on Apple Silicon.
        gps_s = gps_msg.time_usec / 1e6 if gps_msg.time_usec else time.monotonic()
        action = self.watchdog.update(gps_msg, gps_s)
        if action is None:
            return
        residual = getattr(self.watchdog, "last_residual_m", None)
        threshold = getattr(self.watchdog, "last_threshold_m", None)
        self.emit("watchdog_request", mode=action, residual_m=residual,
                  threshold_m=threshold)
        if action in ("BRAKE", "AUTO") and self.latest_mode != action:
            self.set_mode(action)

    def apply_attack(self, elapsed: float) -> None:
        if not self.attack:
            return
        if elapsed - self.last_attack_update < 0.9:
            return
        self.last_attack_update = elapsed
        offset = self.attack.requested_offset(elapsed)
        if math.hypot(offset[0] - self.last_attack_offset[0],
                      offset[1] - self.last_attack_offset[1]) < 0.3:
            return
        self.last_attack_offset = offset
        lat_deg, lon_deg = degrees_from_meters(*offset, HOME_LAT)
        self.emit("attack_request", north_m=round(offset[0], 3),
                  east_m=round(offset[1], 3), simulator_parameters=list(GPS_PARAM_NAMES))
        self.set_parameter(GPS_PARAM_NAMES[0], lat_deg, tolerance=1e-7)
        self.set_parameter(GPS_PARAM_NAMES[1], lon_deg, tolerance=1e-7)

    def run(self) -> dict:
        self.connect()
        try:
            self.request_streams()
            self.wait_for(lambda: self.latest_gps is not None and
                          self.latest_gps.fix_type >= 3 and
                          self.current_boot_s is not None,
                          150, "3D GPS fix and simulator clock")
            # Copter 4.7 renamed WPNAV_SPEED (cm/s) to WP_SPD (m/s).
            self.set_parameter("WP_SPD", 2.0, tolerance=0.01)
            self.set_parameter(GPS_PARAM_NAMES[0], 0.0)
            self.set_parameter(GPS_PARAM_NAMES[1], 0.0)
            self.upload_mission()
            self.set_mode("AUTO")
            self.wait_for(lambda: self.latest_mode == "AUTO", 10, "AUTO mode")
            self.command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
            self.emit("arm_request")
            self.wait_for(lambda: self.armed, 90, "arming")
            flight_start_wall = time.monotonic()
            flight_start_sim = self.current_boot_s
            while (self.current_boot_s - flight_start_sim < self.max_seconds
                   and time.monotonic() - flight_start_wall < self.max_seconds * 4):
                self.read(timeout=0.3, watch=True)
                elapsed = self.current_boot_s - flight_start_sim
                self.apply_attack(elapsed)
                if self.airborne and not self.armed:
                    self.emit("flight_finished", elapsed_s=round(elapsed, 3))
                    break
            else:
                self.emit("error", message="Flight timed out; RTL requested")
                self.set_mode("RTL")
                self.wait_for(lambda: not self.armed, 45, "RTL landing", watch=True)
            return self.summary()
        finally:
            if self.attack_enabled:
                for name in GPS_PARAM_NAMES:
                    try:
                        self.set_parameter(name, 0.0)
                    except Exception as exc:
                        self.emit("error", message=f"Could not clear {name}: {exc}")
            if self.armed:
                try:
                    self.set_mode("RTL")
                except Exception:
                    pass

    def summary(self) -> dict:
        gps = self.latest_gps
        return {
            "case": self.case,
            "real_simulator": "ArduPilot Copter SITL + Gazebo Harmonic",
            "mission": "30 m square AUTO route, takeoff, return-to-launch",
            "attack_surface": "SITL SIM_GPS1_GLTCH_X/Y parameter" if self.attack_enabled else "none",
            "watchdog": "student" if self.case.endswith("student") else "starter",
            "last_mode": self.latest_mode,
            "last_mission_seq": self.latest_seq,
            "finished_disarmed": self.airborne and not self.armed,
            "airborne_observed": self.airborne,
            "mission_completed": self.airborne and not self.armed and
                                 self.latest_seq >= len(mission_items()) - 1,
            "truth_samples": self.truth_samples,
            "max_truth_route_deviation_m": self.max_truth_route_deviation_m,
            "max_gps_truth_separation_m": self.max_gps_truth_separation_m,
            "gps_fix_type": gps.fix_type if gps else None,
            "gps_final": (gps.lat / 1e7, gps.lon / 1e7) if gps else None,
            "simulator_truth_final": self.latest_truth,
            "mode_requests": self.mode_requests,
            "mode_confirmations": self.mode_confirmations,
            "event_count": len(self.events),
            "warning": "An accepted simulator parameter is not proof of route deviation or defense success; inspect the trace.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True,
                        choices=("clean-starter", "attack-starter",
                                 "attack-student", "clean-student"))
    parser.add_argument("--max-seconds", type=float, default=180)
    args = parser.parse_args()
    if not 30 <= args.max_seconds <= 300:
        parser.error("--max-seconds must be between 30 and 300")
    RUNS.mkdir(parents=True, exist_ok=True)
    flight = Flight(args.case, args.max_seconds)
    stem = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{args.case}"
    try:
        summary = flight.run()
        code = 0 if summary["finished_disarmed"] else 1
    except Exception as exc:
        flight.emit("error", message=repr(exc))
        summary = flight.summary()
        summary["error"] = repr(exc)
        code = 1
    (RUNS / f"{stem}.jsonl").write_text("".join(json.dumps(event) + "\n"
                                           for event in flight.events))
    (RUNS / f"{stem}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    svg_path = RUNS / f"{stem}.route.svg"
    if any(event["kind"] in {"gps", "truth", "estimate"}
           for event in flight.events):
        svg_path.write_text(render_trace(flight.events,
                            f"HW5 {args.case} flight", f"{stem}.jsonl"))
    print(json.dumps({"trace": str(RUNS / f"{stem}.jsonl"),
                      "route_plot": str(svg_path) if svg_path.exists() else None,
                      **summary}, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
