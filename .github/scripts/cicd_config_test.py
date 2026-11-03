"""Tests for the Cloudflare CI/CD configuration contract."""

import json
import tempfile
import unittest
from pathlib import Path

import cicd_config


class CicdConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / ".github" / "cicd" / "application.json"

    def valid(self) -> dict[str, object]:
        return {"version": 1, "application": {"name": "app"}, "ci": {"enabled": True}, "cloudflare": {"enabled": False, "projectPath": "", "deployCommand": "", "hosting": {"provider": "workers", "projectName": "", "outputDirectory": ""}, "previewEnvironmentEnabled": False, "previewOrphanAuditEnabled": False, "previewWorkerName": "", "analysisArchiveEnabled": False}, "deployments": {"development": False, "staging": False, "production": False}}

    def write(self, config: dict[str, object], with_project: bool = False) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        if with_project:
            (self.root / "worker").mkdir()

    def write_pages_project(self) -> None:
        project = self.root / "worker"
        project.mkdir(exist_ok=True)
        (project / "package.json").write_text(json.dumps({"devDependencies": {"wrangler": "4.151.3"}}), encoding="utf-8")
        (project / "package-lock.json").write_text("{}", encoding="utf-8")
        (project / "public").mkdir(exist_ok=True)

    def test_disabled_cloudflare_is_valid_without_an_application_project(self) -> None:
        self.write(self.valid())
        self.assertEqual(cicd_config.load(self.config_path)["version"], 1)

    def test_preview_requires_cloudflare(self) -> None:
        config = self.valid()
        config["cloudflare"]["previewEnvironmentEnabled"] = True
        self.write(config)
        with self.assertRaisesRegex(ValueError, "requires cloudflare.enabled"):
            cicd_config.load(self.config_path)

    def test_preview_audit_requires_enabled_previews_and_worker_name(self) -> None:
        config = self.valid()
        config["cloudflare"]["previewOrphanAuditEnabled"] = True
        self.write(config)
        with self.assertRaisesRegex(ValueError, "previewEnvironmentEnabled"):
            cicd_config.load(self.config_path)

        config["cloudflare"].update({"enabled": True, "previewEnvironmentEnabled": True, "projectPath": "worker", "deployCommand": "npx wrangler deploy"})
        self.write(config, with_project=True)
        with self.assertRaisesRegex(ValueError, "previewWorkerName"):
            cicd_config.load(self.config_path)

    def test_analysis_archive_requires_cloudflare(self) -> None:
        config = self.valid()
        config["cloudflare"]["analysisArchiveEnabled"] = True
        self.write(config)
        with self.assertRaisesRegex(ValueError, "analysisArchiveEnabled requires"):
            cicd_config.load(self.config_path)

    def test_enabled_deployment_requires_cloudflare(self) -> None:
        config = self.valid()
        config["deployments"]["development"] = True
        self.write(config)
        with self.assertRaisesRegex(ValueError, "require cloudflare.enabled"):
            cicd_config.load(self.config_path)

    def test_enabled_cloudflare_requires_a_project_path_and_command(self) -> None:
        config = self.valid()
        config["cloudflare"]["enabled"] = True
        self.write(config)
        with self.assertRaisesRegex(ValueError, "projectPath"):
            cicd_config.load(self.config_path)

    def test_enabled_cloudflare_requires_a_deploy_command(self) -> None:
        config = self.valid()
        config["cloudflare"].update({"enabled": True, "projectPath": "worker"})
        self.write(config, with_project=True)
        with self.assertRaisesRegex(ValueError, "deployCommand"):
            cicd_config.load(self.config_path)

    def test_enabled_cloudflare_accepts_an_existing_relative_project_path(self) -> None:
        config = self.valid()
        config["cloudflare"].update({"enabled": True, "projectPath": "worker", "deployCommand": "npx wrangler deploy"})
        self.write(config, with_project=True)
        self.assertTrue(cicd_config.load(self.config_path)["cloudflare"]["enabled"])

    def test_application_name_uses_a_portable_identifier(self) -> None:
        config = self.valid()
        config["application"]["name"] = "Invalid_Name"
        self.write(config)
        with self.assertRaisesRegex(ValueError, "lowercase"):
            cicd_config.load(self.config_path)

    def test_preview_cannot_be_enabled_without_a_prepared_worker_project(self) -> None:
        config = self.valid()
        config["cloudflare"].update({
            "enabled": True, "projectPath": "worker", "deployCommand": "npx wrangler deploy",
            "previewEnvironmentEnabled": True,
        })
        self.write(config, with_project=True)
        with self.assertRaisesRegex(ValueError, "package.json"):
            cicd_config.load(self.config_path)

    def test_pages_requires_a_project_name_and_output_directory(self) -> None:
        config = self.valid()
        config["cloudflare"].update({"enabled": True, "projectPath": "worker", "hosting": {"provider": "pages", "projectName": "", "outputDirectory": ""}})
        self.write(config, with_project=True)
        with self.assertRaisesRegex(ValueError, "projectName"):
            cicd_config.load(self.config_path)

    def test_pages_accepts_a_locked_project_and_does_not_require_workers_deploy_command(self) -> None:
        config = self.valid()
        config["cloudflare"].update({"enabled": True, "projectPath": "worker", "hosting": {"provider": "pages", "projectName": "example-pages", "outputDirectory": "public"}})
        self.write(config, with_project=True)
        self.write_pages_project()
        values = cicd_config.values(cicd_config.load(self.config_path))
        self.assertEqual(values["cloudflare_hosting_provider"], "pages")
        self.assertEqual(values["cloudflare_pages_project_name"], "example-pages")

    def test_pages_cannot_enable_the_workers_orphan_audit(self) -> None:
        config = self.valid()
        config["cloudflare"].update({
            "enabled": True,
            "projectPath": "worker",
            "hosting": {"provider": "pages", "projectName": "example-pages", "outputDirectory": "public"},
            "previewEnvironmentEnabled": True,
            "previewOrphanAuditEnabled": True,
            "previewWorkerName": "worker",
        })
        self.write(config, with_project=True)
        self.write_pages_project()
        with self.assertRaisesRegex(ValueError, "provider workers"):
            cicd_config.load(self.config_path)
