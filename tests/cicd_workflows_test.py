"""The Cloudflare CI/CD workflow contract preserves deployment safety boundaries."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(path: str) -> str:
    return (WORKFLOWS / path).read_text(encoding="utf-8")


class CicdWorkflowTests(unittest.TestCase):
    def test_reusable_workflows_are_supported_and_called(self) -> None:
        for name in ("reusable-ci.yml", "reusable-cloudflare-deploy.yml", "reusable-cloudflare-preview.yml"):
            self.assertIn("workflow_call:", workflow(name))
        self.assertEqual(workflow("cicd.yml").count("uses: ./.github/workflows/reusable-cloudflare-deploy.yml"), 3)
        self.assertIn("uses: ./.github/workflows/reusable-cloudflare-preview.yml", workflow("cicd.yml"))

    def test_preview_requires_trusted_pr_and_environment_gate(self) -> None:
        content = workflow("cicd.yml")
        self.assertEqual(content.count("head.repo.fork == false"), 1)
        self.assertIn("contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]')", content)
        self.assertIn("environment: preview", workflow("reusable-cloudflare-preview.yml"))
        self.assertIn("preview-branch: ${{ github.event.pull_request.head.ref }}", content)
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
        self.assertIn("if: inputs.enabled", workflow("reusable-cloudflare-preview.yml"))
        self.assertIn("if: needs.configuration.outputs.enabled == 'true'", workflow("cicd-preview-cleanup.yml"))

    def test_cleanup_uses_trusted_source_and_shares_deploy_queue(self) -> None:
        cleanup = workflow("cicd-preview-cleanup.yml")
        self.assertIn("types: [closed]", cleanup)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", cleanup)
        self.assertIn("source-ref: ${{ needs.configuration.outputs.management-ref }}", cleanup)
        self.assertNotIn("ref: ${{ github.event.pull_request.head.sha }}", cleanup)
        self.assertIn("head.repo.full_name == github.repository", cleanup)
        for name in ("cicd.yml", "cicd-preview-cleanup.yml"):
            self.assertIn("group: preview-${{ github.event.pull_request.number", workflow(name))
            self.assertIn("cancel-in-progress: false", workflow(name))
            self.assertIn("queue: max", workflow(name))

    def test_preview_build_precedes_cloud_operation(self) -> None:
        content = workflow("reusable-cloudflare-preview.yml")
        self.assertLess(content.index("npm ci"), content.index("npm run build"))
        self.assertLess(content.index("npm run build"), content.index("cloudflare_preview.py run"))
        self.assertIn("if: inputs.operation == 'deploy'", content)
        self.assertNotIn("deploy-command", content)

    def test_shared_environments_follow_the_branch_mapping(self) -> None:
        caller = workflow("cicd.yml")
        for branch, environment in (("main", "development"), ("stg", "staging"), ("prod", "production")):
            self.assertIn(f"refs/heads/{branch}", caller)
            self.assertIn(f"github-environment: {environment}", caller)
