"""AST security checks accept ordinary logs and reject direct secret arguments."""

import unittest
import tempfile
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import check_security
from check_security import scan_source


class SecurityTests(unittest.TestCase):
    def test_safe_logs(self) -> None:
        for source in (
            'print("request completed", request_id)',
            'logger.info("token refreshed")',
            'logging.info("count=%s", token_count)',
            'print({"token": "[REDACTED]"})',
            'save(token)',
            'code = "print(password)"',
        ):
            with self.subTest(source=source):
                self.assertEqual(scan_source(source, "safe.py"), [])

    def test_sensitive_call_arguments(self) -> None:
        for source in (
            'print(password)', 'logger.info("value=%s", access_token)',
            'logging.error(user.password)', 'print(headers["Authorization"])',
            'logger.debug({"api_key": value})', 'print(f"token={value}")',
            'print(config.get("API_KEY"))', 'logger.info("x", extra={"secret": value})',
            'import logging as audit\naudit.warning(token)',
            'from logging import error as report\nreport(password)',
            'audit = logging.getLogger("audit")\naudit.info(token)',
            'print("Authorization: Bearer abc123")',
        ):
            with self.subTest(source=source):
                findings = scan_source(source, "unsafe.py")
                self.assertTrue(findings)
                self.assertIn("unsafe.py:", findings[0])
                self.assertIn("sensitive value", findings[0])
                self.assertNotIn("abc123", findings[0])

    def test_line_numbers_and_parse_errors(self) -> None:
        self.assertIn("unsafe.py:2:", scan_source('\nprint(password)', "unsafe.py")[0])
        self.assertIn("parse error", scan_source('print(', "bad.py")[0])

    def test_python_cli_gate_fails_for_a_dangerous_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "unsafe.py").write_text("print(password)\n")
            with patch.object(check_security, "ROOT", root), patch.object(check_security, "source_files", return_value=[Path("unsafe.py")]), patch.object(check_security.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
                with self.assertRaises(SystemExit) as exit_result:
                    check_security.main()
                self.assertEqual(exit_result.exception.code, 1)
