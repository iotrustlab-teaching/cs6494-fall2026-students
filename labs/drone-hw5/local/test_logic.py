"""Fast static checks; no Docker or flight controller is started."""

import math
import unittest
from types import SimpleNamespace

from attack import AttackPlan, degrees_from_meters
from runner import Flight, mission_items, near_practice_world, offset_from_home, route_deviation
from starter_watchdog import Watchdog


class PracticeLogicTest(unittest.TestCase):
    def test_attack_is_bounded_and_switches_on(self):
        attack = AttackPlan()
        self.assertEqual(attack.requested_offset(0), (0, 0))
        self.assertEqual(attack.requested_offset(26)[0], 20)
        with self.assertRaises(ValueError):
            AttackPlan(north_m=100)

    def test_metre_degree_round_trip(self):
        lat, lon = degrees_from_meters(10, 20, -35.363262)
        self.assertAlmostEqual(lat * 111_194.9, 10, places=5)
        self.assertAlmostEqual(lon * 111_194.9 * math.cos(math.radians(-35.363262)),
                               20, places=5)

    def test_mission_and_route_geometry(self):
        self.assertEqual(len(mission_items()), 6)
        self.assertAlmostEqual(route_deviation(-35.363262, 149.165237), 0)
        self.assertEqual(offset_from_home(-35.363262, 149.165237), (0, 0))
        self.assertTrue(near_practice_world(-35.363262, 149.165237))
        self.assertFalse(near_practice_world(0, 0))

    def test_starter_brakes_on_twenty_metres(self):
        watchdog = Watchdog()
        base = -35.363262
        def gps(t, north_m):
            lat = base + north_m / 111_194.9
            return SimpleNamespace(fix_type=3, time_usec=int(t * 1e6),
                                   lat=round(lat * 1e7),
                                   lon=round(149.165237 * 1e7), vel=0, cog=0)
        self.assertIsNone(watchdog.update(gps(1, 0), 1))
        self.assertIsNone(watchdog.update(gps(2, 0), 2))
        self.assertEqual(watchdog.update(gps(3, 20), 3), "BRAKE")

    def test_mission_receipt_requires_home_and_no_timeout(self):
        flight = Flight("clean-starter", 180)
        flight.airborne = True
        flight.latest_seq = len(mission_items()) - 1
        flight.latest_truth = (-35.363262, 149.165237)
        self.assertTrue(flight.summary()["mission_completed"])
        flight.latest_truth = (-35.362262, 149.165237)
        self.assertFalse(flight.summary()["mission_completed"])
        flight.latest_truth = (-35.363262, 149.165237)
        flight.timeout_recovery = True
        self.assertFalse(flight.summary()["mission_completed"])


if __name__ == "__main__":
    unittest.main()
