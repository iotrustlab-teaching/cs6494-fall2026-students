from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler import CompileError, IEC2C, IEC_LIB, InterlockCompiler  # noqa: E402
from openplc_program import OPENPLC_IMAGE, REGISTER_MAP, render_openplc_program  # noqa: E402


class OpenPLCProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiler = InterlockCompiler()

    def test_all_presets_compile_as_complete_openplc_programs(self) -> None:
        for name, source in self.compiler.preset_sources().items():
            with self.subTest(preset=name), tempfile.TemporaryDirectory() as raw_directory:
                directory = Path(raw_directory)
                program = directory / "program.st"
                program.write_text(render_openplc_program(source), encoding="utf-8")
                result = subprocess.run(
                    [str(IEC2C), "-I", str(IEC_LIB), "-T", str(directory), "-f", "-l", "-p", str(program)],
                    capture_output=True,
                    text=True,
                    timeout=12,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue((directory / "LOCATED_VARIABLES.h").exists())

    def test_register_map_is_fixed_and_owner_separated(self) -> None:
        self.assertEqual([point.modbus_address for point in REGISTER_MAP], list(range(1024, 1034)))
        self.assertTrue(all(point.owner == "adapter" for point in REGISTER_MAP[:7]))
        self.assertTrue(all(point.owner == "controller" for point in REGISTER_MAP[7:]))
        self.assertIn("@sha256:", OPENPLC_IMAGE)

    def test_student_cannot_supply_a_program_or_located_variable(self) -> None:
        source = self.compiler.preset_sources()["repaired"] + "\nPROGRAM Bypass\nEND_PROGRAM\n"
        with self.assertRaises(CompileError):
            render_openplc_program(source)


if __name__ == "__main__":
    unittest.main()
