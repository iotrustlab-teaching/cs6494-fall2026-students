"""Student-editable, simulation-only GPS position bias plan.

The runner writes ArduPilot SITL's ``SIM_GPS1_GLTCH_X/Y`` parameters. This is a
local simulator control, not the network sensor arbiter used in CTF2. The plan
is bounded so a bad edit cannot request an arbitrarily large GPS displacement.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AttackPlan:
    start_s: float = 25.0
    hold_s: float = 20.0
    north_m: float = 20.0
    east_m: float = 0.0
    ramp_m_per_s: float = 25.0

    def __post_init__(self) -> None:
        fields = (self.start_s, self.hold_s, self.north_m,
                  self.east_m, self.ramp_m_per_s)
        if not all(math.isfinite(x) for x in fields):
            raise ValueError("attack values must be finite")
        if self.start_s < 0 or not 0 < self.hold_s <= 60:
            raise ValueError("attack timing must be within the exercise window")
        if math.hypot(self.north_m, self.east_m) > 25:
            raise ValueError("GPS offset must be at most 25 m")
        if not 0 < self.ramp_m_per_s <= 25:
            raise ValueError("GPS ramp must be at most 25 m/s in this practice sim")

    def requested_offset(self, elapsed_s: float) -> tuple[float, float]:
        """Return the bounded north/east offset requested at this flight time."""
        if elapsed_s < self.start_s:
            return 0.0, 0.0
        distance = math.hypot(self.north_m, self.east_m)
        if distance == 0:
            return 0.0, 0.0
        ramp = min(distance, (elapsed_s - self.start_s) * self.ramp_m_per_s)
        if elapsed_s > self.start_s + distance / self.ramp_m_per_s + self.hold_s:
            ramp = max(0.0, distance -
                       (elapsed_s - self.start_s - distance / self.ramp_m_per_s
                        - self.hold_s) * self.ramp_m_per_s)
        scale = ramp / distance
        return self.north_m * scale, self.east_m * scale


def degrees_from_meters(north_m: float, east_m: float,
                        latitude_deg: float) -> tuple[float, float]:
    """SITL GLTCH_X/Y expect latitude/longitude degrees, not metres."""
    metres_per_degree = 111_194.9
    cosine = math.cos(math.radians(latitude_deg))
    if abs(cosine) < 0.01:
        raise ValueError("longitude conversion is unstable near a pole")
    return north_m / metres_per_degree, east_m / (metres_per_degree * cosine)
