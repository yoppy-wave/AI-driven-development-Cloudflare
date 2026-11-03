"""Pages Direct Upload helpers must generate safe, provider-specific commands."""

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import cloudflare_pages as pages


class CloudflarePagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "app"
        self.project.mkdir()
        (self.project / "package.json").write_text(json.dumps({"devDependencies": {"wrangler": "4.151.3"}}))
        (self.project / "package-lock.json").write_text("{}")
        (self.project / "public").mkdir()

    def test_pr_number_creates_an_isolated_pages_preview_branch(self) -> None:
        self.assertEqual(pages.preview_branch("123"), "pr-123")
        self.assertEqual(pages.preview_alias_url("example-pages", "123"), "https://pr-123.example-pages.pages.dev")
        with self.assertRaises(ValueError):
            pages.preview_branch("0")

    def test_pages_command_uses_only_validated_pages_arguments(self) -> None:
        self.assertEqual(pages.command(self.project, "public", "example-pages", "pr-123", "a" * 40), [
            "npx", "--no-install", "wrangler", "pages", "deploy", str(self.project / "public"),
            "--project-name=example-pages", "--branch=pr-123", f"--commit-hash={'a' * 40}",
        ])
        with self.assertRaisesRegex(ValueError, "output directory"):
            pages.command(self.project, "../outside", "example-pages", "pr-123", "a" * 40)
        with self.assertRaisesRegex(ValueError, "branch"):
            pages.command(self.project, "public", "example-pages", "prod; rm -rf /", "a" * 40)

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ACCOUNT_ID": "account"})
    @patch.object(pages.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "Success! https://abc.example.pages.dev", ""))
    @patch.object(pages.subprocess, "check_output")
    def test_pages_preview_checks_the_current_pr_before_deploying(self, get_pr, run) -> None:
        get_pr.return_value = json.dumps({"state": "open", "head": {"sha": "a" * 40, "ref": "feature/login", "repo": {"full_name": "owner/repo"}}})
        self.assertTrue(pages.run_preview(self.project, "public", "example-pages", "owner/repo", "12", "feature/login", "a" * 40))
        self.assertIn("--branch=pr-12", run.call_args.args[0])

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret-token", "CLOUDFLARE_ACCOUNT_ID": "secret-account"})
    @patch.object(pages.subprocess, "run")
    def test_wrangler_failure_masks_cloudflare_secrets_before_reporting_output(self, run) -> None:
        run.side_effect = subprocess.CalledProcessError(1, ["wrangler"], output="token=secret-token", stderr="account=secret-account")
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), self.assertRaises(subprocess.CalledProcessError):
            pages.run_wrangler(["wrangler"], self.project)
        self.assertEqual(stdout.getvalue(), "token=***")
        self.assertEqual(stderr.getvalue(), "account=***")

    def test_pages_cleanup_does_not_claim_the_preview_was_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": f"{temporary}/summary"}):
            pages.cleanup_summary("12")
            summary = Path(temporary, "summary").read_text()
        self.assertIn("not deleted", summary)
        self.assertIn("may remain accessible", summary)