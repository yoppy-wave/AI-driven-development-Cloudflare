"""Independent PR quality workflows are the required merge checks."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


class QualityWorkflowTests(unittest.TestCase):
    def test_each_quality_gate_is_an_independent_pr_workflow(self) -> None:
        expected = {
            "lint.yml": "python .github/scripts/run_lint.py",
            "dependency-check.yml": "python .github/scripts/check_dependencies.py",
            "test.yml": "python .github/scripts/run_regression.py",
            "security-check.yml": "python .github/scripts/check_security.py",
        }
        for name, command in expected.items():
            content = workflow(name)
            self.assertIn("  pull_request:", content)
            self.assertIn("types: [opened, reopened, synchronize]", content)
            self.assertNotIn("  push:", content)
            self.assertIn(command, content)

    def test_rulesets_require_every_independent_quality_check(self) -> None:
        expected = {
            "Lint / lint",
            "Dependency check / dependency-check",
            "Test / test",
            "Security check / security-check",
            "Pull request policy / validate",
        }
        for environment in ("stg", "prod"):
            rules = json.loads((ROOT / f".github/rulesets/{environment}.json").read_text(encoding="utf-8"))
            checks = next(rule["parameters"]["required_status_checks"] for rule in rules["rules"] if rule["type"] == "required_status_checks")
            self.assertEqual({entry["context"] for entry in checks}, expected)

    def test_legacy_aggregate_workflows_are_removed(self) -> None:
        for name in ("cicd.yml", "reusable-ci.yml", "regression.yml"):
            self.assertFalse((WORKFLOWS / name).exists())