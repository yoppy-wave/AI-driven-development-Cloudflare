"""Preview lifecycle tests without contacting GitHub or Cloudflare."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cloudflare_preview as preview


class PreviewTests(unittest.TestCase):
    def pr(self, state="open", sha="current", branch="feature/login", repository="owner/repo"):
        return {"state": state, "head": {"sha": sha, "ref": branch, "repo": {"full_name": repository}}}

    def test_branch_names_preserve_previous_readable_convention_without_hash(self):
        for branch, expected in (
            ("feature/login", "app-feature-login"),
            ("fix/Login_UI", "app-fix-login-ui"),
            ("feature/a.b", "app-feature-a-b"),
            ("feature/a__b", "app-feature-a--b"),
            ("x" * 60, "app-" + "x" * 30),
        ):
            with self.subTest(branch=branch):
                self.assertEqual(preview.preview_name(branch), expected)
        with self.assertRaises(ValueError):
            preview.preview_name("///")

    def test_symbol_collisions_are_not_disambiguated(self):
        self.assertEqual(preview.preview_name("feature/login"), preview.preview_name("feature_login"))

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ACCOUNT_ID": "test"})
    @patch.object(preview.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "{}", ""))
    @patch.object(preview.subprocess, "check_output")
    def test_create_update_and_close_delete_the_same_preview(self, get_pr, run):
        get_pr.side_effect = [
            json.dumps(self.pr()), json.dumps(self.pr(sha="next")),
            json.dumps(self.pr(state="closed", sha="next")),
        ]
        for operation, sha in (("deploy", "current"), ("deploy", "next"), ("delete", "management-sha")):
            self.assertTrue(preview.run_preview(Path("."), operation, "feature/login", "owner/repo", "12", sha))
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(calls[0], ["npx", "--no-install", "wrangler", "preview", "--name", "app-feature-login", "--json"])
        self.assertEqual(calls[2], ["npx", "--no-install", "wrangler", "preview", "delete", "--name", "app-feature-login", "--skip-confirmation"])

    @patch.object(preview.subprocess, "run")
    @patch.object(preview.subprocess, "check_output")
    def test_stale_deploy_and_reopened_cleanup_do_not_contact_cloudflare(self, get_pr, run):
        cases = [
            ("deploy", self.pr(state="closed")),
            ("deploy", self.pr(sha="newer")),
            ("delete", self.pr(state="open")),
            ("delete", self.pr(state="closed", repository="fork/repo")),
            ("delete", self.pr(state="closed", branch="feature/other")),
        ]
        for operation, pr in cases:
            get_pr.return_value = json.dumps(pr)
            self.assertFalse(preview.run_preview(Path("."), operation, "feature/login", "owner/repo", "12", "current"))
        run.assert_not_called()

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ACCOUNT_ID": "test"})
    @patch.object(preview.subprocess, "check_output")
    @patch.object(preview.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["wrangler"]))
    def test_cloudflare_failures_are_not_reported_as_success(self, run, get_pr):
        get_pr.return_value = json.dumps(self.pr(state="closed"))
        with self.assertRaises(subprocess.CalledProcessError):
            preview.run_preview(Path("."), "delete", "feature/login", "owner/repo", "12", "current")

    def test_invalid_operation_cannot_turn_into_another_wrangler_command(self):
        with self.assertRaises(ValueError):
            preview.command("deploy --env production", "feature/login")

    def test_project_requires_locked_wrangler_and_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "worker"
            project.mkdir()
            with self.assertRaises(ValueError):
                preview.project_directory(root, "../outside")
            with self.assertRaises(ValueError):
                preview.project_directory(root, "worker")
            (project / "package.json").write_text(json.dumps({"devDependencies": {"wrangler": "4.100.0"}}))
            (project / "package-lock.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "configuration"):
                preview.project_directory(root, "worker")
            (project / "wrangler.jsonc").write_text("{}")
            self.assertEqual(preview.project_directory(root, "worker"), project.resolve())
