"""Regression checks for run_regression helpers."""

import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import run_regression


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[2]
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, path: str, content: str = "") -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_empty_repository_has_no_application_projects(self) -> None:
        self.assertEqual(run_regression.discover(self.root), ([], []))

    def test_python_project_requires_tests(self) -> None:
        self.write("backend/pyproject.toml", "[project]\nname = 'backend'\nversion = '0.1'\n")
        self.write("backend/src/backend.py", "def calculate(): return 1")
        with self.assertRaisesRegex(RuntimeError, r"has no \*_test\.py tests"):
            run_regression.discover(self.root)
        self.write("backend/src/backend_test.py", "def test_calculate(): assert True")
        self.assertEqual(run_regression.discover(self.root)[0], [Path("backend")])

    def test_unregistered_python_source_fails(self) -> None:
        self.write("app/feature.py", "def feature(): return True")
        with self.assertRaisesRegex(RuntimeError, "no project manifest"):
            run_regression.discover(self.root)

    def test_node_project_requires_test_script(self) -> None:
        self.write("web/package.json", '{"scripts":{"build":"tsc"}}')
        with self.assertRaisesRegex(RuntimeError, "no test script"):
            run_regression.discover(self.root)
        self.write("web/package.json", '{"scripts":{"test":" "}}')
        with self.assertRaisesRegex(RuntimeError, "no test script"):
            run_regression.discover(self.root)
        self.write("web/package.json", '{"scripts":{"test":"vitest run"}}')
        self.write("web/src/app.ts", "export const app = true")
        self.assertEqual(run_regression.discover(self.root)[1], [Path("web")])

    def test_nested_node_package_uses_root_workspace(self) -> None:
        self.write("package.json", '{"scripts":{"test":"npm -ws test"}}')
        self.write("packages/web/package.json", '{"scripts":{"test":"vitest run"}}')
        self.write("packages/web/src/app.ts", "export const app = true")
        self.assertEqual(run_regression.discover(self.root)[1], [Path(".")])

    def test_failed_test_command_propagates_failure(self) -> None:
        with patch.object(run_regression.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pytest")):
            with self.assertRaises(subprocess.CalledProcessError):
                run_regression.run(["pytest"], self.root)

    def test_intentionally_failing_pytest_returns_failure(self) -> None:
        self.write("failure_test.py", "def test_failure():\n    assert False\n")
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", str(self.root / "failure_test.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("1 failed", result.stdout)

    def test_node_test_gate_excludes_lint_and_deduplicates_typecheck_build(self) -> None:
        self.write("package.json", '{"scripts":{"test":"jest", "lint":"eslint .", "typecheck":"tsc --noEmit", "build":"tsc --noEmit", "synth":"cdk synth"}}')
        with patch.object(run_regression, "install_node", return_value=["npm"]), patch.object(run_regression, "run") as run:
            run_regression.node_project(self.root, Path("."))
        self.assertEqual([call.args[0] for call in run.call_args_list], [["npm", "run", "test"], ["npm", "run", "typecheck"], ["npm", "run", "synth"]])


if __name__ == "__main__":
    unittest.main()
