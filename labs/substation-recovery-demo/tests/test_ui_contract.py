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


if __name__ == "__main__":
    unittest.main()
