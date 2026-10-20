"""The Cloudflare CI/CD workflow contract preserves deployment safety boundaries."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(path: str) -> str:
    return (WORKFLOWS / path).read_text(encoding="utf-8")


class CicdWorkflowTests(unittest.TestCase):
    def test_reusable_workflows_are_supported_and_called(self) -> None:
        for name in ("reusable-ci.yml", "reusable-cloudflare-deploy.yml"):
            self.assertIn("workflow_call:", workflow(name))
        self.assertEqual(workflow("cicd.yml").count("uses: ./.github/workflows/reusable-cloudflare-deploy.yml"), 4)

    def test_preview_requires_trusted_pr_and_environment_gate(self) -> None:
        content = workflow("cicd.yml")
        self.assertEqual(content.count("head.repo.fork == false"), 1)
        self.assertIn("contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]')", content)
        self.assertIn("github-environment: preview", content)
        self.assertNotIn("secrets: inherit", content)

    def test_cloudflare_secrets_are_limited_to_cloudflare_jobs(self) -> None:
        adapter = workflow("reusable-cloudflare-deploy.yml")
        self.assertIn("CLOUDFLARE_API_TOKEN", adapter)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID", adapter)
        for forbidden in ("AWS_ROLE_TO_ASSUME", "configure-aws-credentials", "id-token: write", "cdk "):
            self.assertNotIn(forbidden, adapter)
            self.assertNotIn(forbidden, workflow("cicd.yml"))

    def test_deployment_adapter_validates_inputs_before_running_wrangler(self) -> None:
        adapter = workflow("reusable-cloudflare-deploy.yml")
        self.assertIn("environment:\n      name: ${{ inputs.github-environment }}", adapter)
        self.assertIn("Validate deployment inputs", adapter)
        self.assertLess(adapter.index("Validate deployment inputs"), adapter.index("Deploy application with Wrangler"))
        self.assertIn('[[ -d "$PROJECT_PATH" && -n "$DEPLOY_COMMAND" ]]', adapter)
        self.assertIn('[[ -n "$CLOUDFLARE_API_TOKEN" && -n "$CLOUDFLARE_ACCOUNT_ID" ]]', adapter)

    def test_disabled_deployments_do_not_require_cloudflare_secrets(self) -> None:
        adapter = workflow("reusable-cloudflare-deploy.yml")
        self.assertIn("if: inputs.enabled", adapter)
        self.assertIn("if: ${{ !inputs.enabled }}", adapter)
        self.assertFalse((WORKFLOWS / "cicd-preview-cleanup.yml").exists())

    def test_shared_environments_follow_the_branch_mapping(self) -> None:
        caller = workflow("cicd.yml")
        for branch, environment in (("main", "development"), ("stg", "staging"), ("prod", "production")):
            self.assertIn(f"refs/heads/{branch}", caller)
            self.assertIn(f"github-environment: {environment}", caller)
