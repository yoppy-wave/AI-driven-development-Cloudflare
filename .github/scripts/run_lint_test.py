"""Exercise Ruff's real CLI on safe and intentionally invalid source."""

import subprocess
import sys
import unittest


class LintTests(unittest.TestCase):
    def test_ruff_cli_exit_status(self) -> None:
        for source, expected in (("print('safe')\n", 0), ("print(undefined_name)\n", 1)):
            with self.subTest(source=source):
                result = subprocess.run([sys.executable, "-m", "ruff", "check", "--isolated", "--select", "F821", "-"], input=source, text=True, capture_output=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected:
                    self.assertIn("F821", result.stdout)
