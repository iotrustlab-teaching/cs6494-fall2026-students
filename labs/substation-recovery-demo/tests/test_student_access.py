from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from access import AccessDenied, StudentAccessManager, append_roster, create_roster  # noqa: E402
from compiler import InterlockCompiler  # noqa: E402


class StudentAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.roster = self.root / "roster.json"
        self.invites = self.root / "invites.csv"
        create_roster(
            self.roster,
            self.invites,
            labels=["Team Alpha", "Team Beta"],
        )
        with self.invites.open(newline="", encoding="utf-8") as handle:
            self.codes = {row["label"]: row["access_code"] for row in csv.DictReader(handle)}
        self.compiler = InterlockCompiler()
        self.manager = StudentAccessManager(self.roster, self.compiler, self.root / "students")

    def tearDown(self) -> None:
        self.manager.close()
        self.tempdir.cleanup()

    def test_invalid_code_is_rejected(self) -> None:
        with self.assertRaises(AccessDenied):
            self.manager.login("SRL-NOT-A-REAL-CODE", "127.0.0.1")

    def test_student_circuits_are_isolated(self) -> None:
        _token_a, lab_a = self.manager.login(self.codes["Team Alpha"], "127.0.0.1")
        _token_b, lab_b = self.manager.login(self.codes["Team Beta"], "127.0.0.2")

        lab_a.simulator.submit_command("CLOSE", "S1", "manual")
        lab_a.simulator.step()

        self.assertTrue(lab_a.snapshot()["positions"]["S1"])
        self.assertFalse(lab_b.snapshot()["positions"]["S1"])
        self.assertNotEqual(lab_a.snapshot()["runId"], lab_b.snapshot()["runId"])

    def test_student_build_persists_without_changing_peer(self) -> None:
        _token_a, lab_a = self.manager.login(self.codes["Team Alpha"], "127.0.0.1")
        _token_b, lab_b = self.manager.login(self.codes["Team Beta"], "127.0.0.2")
        repaired = lab_a.compile_preset("repaired")
        self.assertEqual(lab_b.workspace_payload()["activePreset"], "vulnerable")

        self.manager.close()
        self.manager = StudentAccessManager(self.roster, self.compiler, self.root / "students")
        _new_token, restored = self.manager.login(self.codes["Team Alpha"], "127.0.0.3")

        self.assertEqual(restored.workspace_payload()["activeBuildId"], repaired.build_id)
        self.assertEqual(restored.workspace_payload()["activePreset"], "repaired")

    def test_session_token_resolves_only_its_student(self) -> None:
        token, lab = self.manager.login(self.codes["Team Alpha"], "127.0.0.1")
        self.assertEqual(self.manager.resolve(token).identity, lab.identity)
        self.assertIsNone(self.manager.resolve("unrelated-token"))
        self.manager.logout(token)
        self.assertIsNone(self.manager.resolve(token))

    def test_append_preserves_existing_invitations_and_adds_access(self) -> None:
        original_payload = json.loads(self.roster.read_text(encoding="utf-8"))
        with self.invites.open(newline="", encoding="utf-8") as handle:
            original_invitations = list(csv.DictReader(handle))

        added = append_roster(self.roster, self.invites, labels=["Team Gamma"])

        updated_payload = json.loads(self.roster.read_text(encoding="utf-8"))
        with self.invites.open(newline="", encoding="utf-8") as handle:
            updated_invitations = list(csv.DictReader(handle))
        self.assertEqual(updated_payload["students"][:2], original_payload["students"])
        self.assertEqual(updated_invitations[:2], original_invitations)
        self.assertEqual(added[0]["student_id"], "team-gamma")

        self.manager.close()
        self.manager = StudentAccessManager(self.roster, self.compiler, self.root / "students")
        _old_token, old_lab = self.manager.login(self.codes["Team Alpha"], "127.0.0.1")
        _new_token, new_lab = self.manager.login(added[0]["access_code"], "127.0.0.2")
        self.assertEqual(old_lab.identity.student_id, "team-alpha")
        self.assertEqual(new_lab.identity.student_id, "team-gamma")

    def test_append_rejects_mismatched_existing_invitation(self) -> None:
        before = self.roster.read_text(encoding="utf-8")
        with self.invites.open(newline="", encoding="utf-8") as handle:
            invitations = list(csv.DictReader(handle))
        invitations[0]["access_code"] = "SRL-NOT-THE-ORIGINAL"
        with self.invites.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["student_id", "label", "access_code"])
            writer.writeheader()
            writer.writerows(invitations)

        with self.assertRaisesRegex(ValueError, "does not match"):
            append_roster(self.roster, self.invites, labels=["Team Gamma"])
        self.assertEqual(self.roster.read_text(encoding="utf-8"), before)

    def test_duplicate_access_hash_is_rejected(self) -> None:
        payload = json.loads(self.roster.read_text(encoding="utf-8"))
        payload["students"][1]["codeHash"] = payload["students"][0]["codeHash"]
        self.roster.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "invalid or duplicate"):
            StudentAccessManager(self.roster, self.compiler, self.root / "other-students")


if __name__ == "__main__":
    unittest.main()
