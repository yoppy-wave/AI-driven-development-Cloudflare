"""The independent Cloudflare workflows preserve deployment safety boundaries."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(path: str) -> str:
    return (WORKFLOWS / path).read_text(encoding="utf-8")


class CicdWorkflowTests(unittest.TestCase):
    def test_reusable_workflows_are_supported_and_called(self) -> None:
        for name in ("reusable-cloudflare-deploy.yml", "reusable-cloudflare-preview.yml"):
            self.assertIn("workflow_call:", workflow(name))
        self.assertIn("uses: ./.github/workflows/reusable-cloudflare-preview.yml", workflow("preview.yml"))
        for name in ("deploy-staging.yml", "deploy-production.yml"):
            self.assertIn("uses: ./.github/workflows/reusable-cloudflare-deploy.yml", workflow(name))

    def test_preview_is_independent_of_quality_gates_and_cleanup_shares_its_queue(self) -> None:
        preview = workflow("preview.yml")
        cleanup = workflow("preview-cleanup.yml")
        self.assertIn("types: [opened, reopened, synchronize]", preview)
        self.assertNotIn("needs: ci", preview)
        for content in (preview, cleanup):
            self.assertIn("group: preview-${{ github.event.pull_request.number", content)
            self.assertIn("cancel-in-progress: false", content)
            self.assertIn("queue: max", content)
        self.assertIn("types: [closed]", cleanup)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", cleanup)
        self.assertNotIn("ref: ${{ github.event.pull_request.head.sha }}", cleanup)

    def test_deployment_and_archive_are_branch_specific_and_fail_closed(self) -> None:
        self.assertIn("branches: [stg]", workflow("deploy-staging.yml"))
        self.assertIn("github-environment: staging", workflow("deploy-staging.yml"))
        self.assertIn("branches: [prod]", workflow("deploy-production.yml"))
        self.assertIn("github-environment: production", workflow("deploy-production.yml"))
        archive = workflow("publish-analysis-archive.yml")
        self.assertIn("branches: [prod]", archive)
        self.assertIn("environment: production", archive)
        self.assertIn("analysis_archive_enabled", archive)
        self.assertIn("R2_ANALYSIS_ARCHIVE_BUCKET", archive)

    def test_preview_orphan_audit_is_weekly_and_disabled_by_default(self) -> None:
        audit = workflow("preview-orphan-audit.yml")
        self.assertIn('cron: "0 9 * * 1"', audit)
        self.assertIn("preview_orphan_audit_enabled", audit)
        self.assertIn("environment: preview", audit)
        self.assertIn("Orphan candidates", (ROOT / ".github/scripts/preview_orphan_audit.py").read_text(encoding="utf-8"))