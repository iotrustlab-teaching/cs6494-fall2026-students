from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler import CompileError, InterlockCompiler  # noqa: E402
from simulator import SERVICE_TARGET_MS, SubstationSimulator  # noqa: E402


class LiveLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiler = InterlockCompiler()
        cls.builds = {
            name: cls.compiler.compile_preset(name)
            for name in ("vulnerable", "target_local", "deny_all", "repaired")
        }
        for build in cls.builds.values():
            build.evaluate(
                close_requested=True,
                actual_positions=0,
                target_mask=2,
                out_of_service_mask=8,
                trip_latched=False,
                present_current_da=0,
                current_limit_da=400,
            )

    def simulator(self, build: str = "repaired") -> SubstationSimulator:
        return SubstationSimulator(self.builds[build], auto_start=False)

    @staticmethod
    def command(sim: SubstationSimulator, action: str, device: str, authority: str = "manual") -> None:
        sim.submit_command(action, device, authority)
        sim.step()

    def test_vulnerable_upstream_close_energizes_fault_and_trips(self) -> None:
        sim = self.simulator("vulnerable")
        sim.reset("s3_fault", {"S3": True})
        self.command(sim, "CLOSE", "B0")
        state = sim.snapshot()
        self.assertTrue(state["positions"]["B0"])
        self.assertGreater(state["measurements"]["branches"]["S3"], 200)
        self.assertEqual(state["mission"]["safety"], "fail")
        for _ in range(9):
            sim.step()
        state = sim.snapshot()
        self.assertTrue(state["trip"])
        self.assertFalse(state["positions"]["B0"])

    def test_target_local_patch_misses_upstream_close(self) -> None:
        sim = self.simulator("target_local")
        sim.reset("s3_fault", {"S3": True})
        self.command(sim, "CLOSE", "B0")
        state = sim.snapshot()
        self.assertTrue(state["positions"]["B0"])
        self.assertEqual(state["mission"]["safety"], "fail")

    def test_repaired_build_blocks_upstream_close(self) -> None:
        sim = self.simulator("repaired")
        sim.reset("s3_fault", {"S3": True})
        self.command(sim, "CLOSE", "B0")
        state = sim.snapshot()
        self.assertFalse(state["positions"]["B0"])
        self.assertEqual(state["mission"]["safety"], "pass")
        decision = [event for event in state["events"] if event["category"] == "decision"][-1]
        self.assertEqual(decision["decision"], "DENY")
        self.assertEqual(decision["controllerResult"]["execution"], "matiec-compiled-native-function")

    def test_authorized_recovery_then_legitimate_service(self) -> None:
        sim = self.simulator("repaired")
        sim.reset("s3_fault", {"S3": True})
        self.command(sim, "OPEN", "S3", "human-recovery")
        self.command(sim, "CLOSE", "S1")
        self.command(sim, "CLOSE", "S2")
        self.command(sim, "CLOSE", "B0")
        for _ in range((SERVICE_TARGET_MS // 50) - 1):
            sim.step()
        state = sim.snapshot()
        self.assertEqual(state["mission"]["safety"], "pass")
        self.assertEqual(state["mission"]["protection"], "pass")
        self.assertEqual(state["mission"]["requiredService"], "pass")
        self.assertGreaterEqual(state["mission"]["serviceMs"], SERVICE_TARGET_MS)
        self.assertAlmostEqual(state["measurements"]["busV"], 117.073, places=2)

    def test_open_without_recovery_authority_is_rejected(self) -> None:
        sim = self.simulator("repaired")
        sim.reset("s3_fault", {"S3": True})
        self.command(sim, "OPEN", "S3", "manual")
        self.assertTrue(sim.snapshot()["positions"]["S3"])

    def test_deny_all_cannot_restore_service(self) -> None:
        sim = self.simulator("deny_all")
        sim.reset("s3_fault", {})
        self.command(sim, "CLOSE", "S1")
        self.command(sim, "CLOSE", "S2")
        self.command(sim, "CLOSE", "B0")
        for _ in range(25):
            sim.step()
        state = sim.snapshot()
        self.assertEqual(state["mission"]["safety"], "pass")
        self.assertEqual(state["mission"]["requiredService"], "pending")
        self.assertEqual(state["mission"]["serviceMs"], 0)

    def test_repaired_build_generalizes_to_moved_fault(self) -> None:
        sim = self.simulator("repaired")
        sim.reset("s2_fault", {})
        self.command(sim, "CLOSE", "S1")
        self.command(sim, "CLOSE", "S3")
        self.command(sim, "CLOSE", "B0")
        for _ in range((SERVICE_TARGET_MS // 50) - 1):
            sim.step()
        state = sim.snapshot()
        self.assertEqual(state["oos"], "S2")
        self.assertEqual(state["mission"]["safety"], "pass")
        self.assertEqual(state["mission"]["requiredService"], "pass")
        self.assertGreaterEqual(state["mission"]["serviceMs"], SERVICE_TARGET_MS)

    def test_compile_error_does_not_create_a_build(self) -> None:
        broken = self.compiler.preset_sources()["repaired"].replace(
            "END_FUNCTION", "CloseInterlock := ;\nEND_FUNCTION"
        )
        with self.assertRaises(CompileError):
            self.compiler.compile(broken)

    def test_edit_boundary_rejects_programs(self) -> None:
        source = self.compiler.preset_sources()["repaired"] + "\nPROGRAM Escape\nEND_PROGRAM\n"
        with self.assertRaises(CompileError):
            self.compiler.compile(source)


if __name__ == "__main__":
    unittest.main()
