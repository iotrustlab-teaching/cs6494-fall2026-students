"""Starter GPS consistency check for the local HW5 flight.

The caller passes each new MAVLink GPS_RAW_INT message to ``update``.  This
class compares how far the reported GPS position moved with the distance and
direction implied by reported ground speed.  A large mismatch requests BRAKE.

This is intentionally a small starter, not a complete spoof detector.  Once a
step has occurred, a constant displaced GPS position can again agree with its
reported speed.  The automatic rejoin below can therefore be too trusting;
that is a useful limitation for students to investigate and revise.
"""

from __future__ import annotations

import math


EARTH_RADIUS_M = 6_371_000.0


class Watchdog:
    """Request BRAKE on a GPS position jump and AUTO after a quiet interval."""

    def __init__(self, jump_threshold_m: float = 7.0,
                 recovery_samples: int = 8) -> None:
        if jump_threshold_m <= 0 or recovery_samples < 1:
            raise ValueError("threshold and recovery sample count must be positive")
        self.jump_threshold_m = jump_threshold_m
        self.recovery_samples = recovery_samples
        self.previous: tuple[float, float, float] | None = None
        self.previous_gps_time: int | None = None
        self.braking = False
        self.quiet_samples = 0
        self.last_residual_m: float | None = None
        self.last_threshold_m: float | None = None

    def update(self, gps_msg, now_monotonic: float) -> str | None:
        """Consume one fresh GPS_RAW_INT sample; return BRAKE, AUTO, or None.

        ``now_monotonic`` is the receipt time in seconds.  The returned word is
        a *request*; the caller must check the flight controller's actual mode.
        """
        if getattr(gps_msg, "fix_type", 0) < 3:
            return None
        gps_time = int(getattr(gps_msg, "time_usec", 0) or 0)
        if gps_time and gps_time == self.previous_gps_time:
            return None
        latitude = float(gps_msg.lat) / 10_000_000.0
        longitude = float(gps_msg.lon) / 10_000_000.0
        if not (math.isfinite(latitude) and math.isfinite(longitude)
                and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            return None
        if self.previous is None:
            self.previous = (latitude, longitude, now_monotonic)
            self.previous_gps_time = gps_time or None
            return None

        old_lat, old_lon, old_time = self.previous
        dt = now_monotonic - old_time
        if dt <= 0.05:
            return None
        self.previous = (latitude, longitude, now_monotonic)
        self.previous_gps_time = gps_time or None
        if dt > 5.0:
            # A long gap is not a trustworthy velocity comparison.  In
            # particular, it must not clear an existing BRAKE decision.
            self.quiet_samples = 0
            return None

        speed_cm_s = int(getattr(gps_msg, "vel", 65535))
        course_cdeg = int(getattr(gps_msg, "cog", 65535))
        if not 0 <= speed_cm_s < 65535:
            return None
        speed_m_s = speed_cm_s / 100.0
        if speed_m_s >= 0.1 and not 0 <= course_cdeg < 36000:
            return None
        heading = math.radians(course_cdeg / 100.0) if speed_m_s >= 0.1 else 0.0

        north_m = math.radians(latitude - old_lat) * EARTH_RADIUS_M
        east_m = (math.radians(longitude - old_lon) * EARTH_RADIUS_M
                  * math.cos(math.radians((old_lat + latitude) / 2.0)))
        expected_north_m = math.cos(heading) * speed_m_s * dt
        expected_east_m = math.sin(heading) * speed_m_s * dt
        residual_m = math.hypot(north_m - expected_north_m,
                                east_m - expected_east_m)
        threshold_m = self.jump_threshold_m + 2.0 * dt
        self.last_residual_m = residual_m
        self.last_threshold_m = threshold_m

        if residual_m > threshold_m:
            self.quiet_samples = 0
            if not self.braking:
                self.braking = True
                return "BRAKE"
            return None

        if self.braking:
            self.quiet_samples += 1
            if self.quiet_samples >= self.recovery_samples:
                self.braking = False
                self.quiet_samples = 0
                return "AUTO"
        return None
