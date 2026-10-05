from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UIContractTests(unittest.TestCase):
    def test_reference_build_requires_an_explicit_reveal(self) -> None:
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="reference-reveal"', html)
        self.assertIn('id="load-reference"', html)
        self.assertIn("if (preset.id !== REFERENCE_PRESET)", javascript)
        self.assertIn("window.confirm", javascript)

    def test_submission_builder_binds_claims_to_captured_evidence(self) -> None:
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        stylesheet = (ROOT / "static" / "app.css").read_text(encoding="utf-8")

        self.assertIn('id="hw3-builder"', html)
        self.assertIn('id="capture-repair"', html)
        self.assertIn('id="print-submission"', html)
        self.assertEqual(html.count('class="builder-step"'), 6)
        self.assertIn("localStorage.setItem(submissionStorageKey()", javascript)
        self.assertIn("record.buildId !== app.submission.repair.buildId", javascript)
        self.assertIn("window.print()", javascript)
        self.assertIn("#submission-report .report-appendix", stylesheet)


if __name__ == "__main__":
    unittest.main()
