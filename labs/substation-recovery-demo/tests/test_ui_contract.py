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
        self.assertEqual(html.count('data-builder-page='), 7)
        self.assertIn('id="builder-back"', html)
        self.assertIn('id="builder-next"', html)
        self.assertIn('id="builder-review-page"', html)
        self.assertIn("localStorage.setItem(submissionStorageKey()", javascript)
        self.assertIn("api('/api/submission'", javascript)
        self.assertIn('id="save-submission-later"', html)
        self.assertIn("Another browser changed this draft", javascript)
        self.assertIn("Campus District Energy - Station 4", html)
        self.assertEqual(html.count('class="answer-contract"'), 6)
        self.assertIn('FDS-DA-___, p. ___', html)
        self.assertIn('run …; build …; event(s) …', html)
        self.assertIn('class="term-lookup"', html)
        self.assertIn('what <code>CloseInterlock</code> decides', html)
        self.assertIn('what <code>TripLatched</code> represents', html)
        self.assertIn("record.buildId !== app.submission.repair.buildId", javascript)
        self.assertIn("body.classList.add('submission-mode')", javascript)
        self.assertIn("step.classList.toggle('active', active)", javascript)
        self.assertIn("window.print()", javascript)
        self.assertIn("#submission-report .report-appendix", stylesheet)
        self.assertIn("body.submission-mode .workspace > :not(#hw3-builder)", stylesheet)

    def test_supplied_functional_spec_is_packaged_and_linked(self) -> None:
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        pdf = ROOT / "static" / "docs" / "riverbend_substation_fds_excerpt.pdf"

        self.assertIn('href="docs/riverbend_substation_fds_excerpt.pdf"', html)
        self.assertTrue(pdf.is_file())
        self.assertGreater(pdf.stat().st_size, 10_000)
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
