"""Regression checks for pull request branch policy validation."""

import unittest

import pr_policy


class PullRequestPolicyTests(unittest.TestCase):
    def test_default_stg_patterns_allow_feature_and_fix_branches(self) -> None:
        patterns = pr_policy.allowed_stg_head_patterns(None)
        self.assertIsNone(pr_policy.validate("stg", "feature/login", "owner/repo", "owner/repo", patterns))
        self.assertIsNone(pr_policy.validate("stg", "fix/login", "owner/repo", "owner/repo", patterns))

    def test_stg_rejects_unconfigured_source_branch_patterns(self) -> None:
        error = pr_policy.validate(
            "stg", "release/1.0", "owner/repo", "owner/repo", ("feature/*", "fix/*")
        )
        self.assertIn("feature/*, fix/*", error or "")

    def test_stg_patterns_can_be_changed_without_code_changes(self) -> None:
        patterns = pr_policy.allowed_stg_head_patterns("feature/*,fix/*,release/*")
        self.assertIsNone(pr_policy.validate("stg", "release/1.0", "owner/repo", "owner/repo", patterns))

    def test_empty_stg_pattern_configuration_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one pattern"):
            pr_policy.allowed_stg_head_patterns(" , ")

    def test_prod_allows_only_stg_from_the_same_repository(self) -> None:
        self.assertIsNone(
            pr_policy.validate("prod", "stg", "owner/repo", "owner/repo", ("feature/*",))
        )

    def test_prod_rejects_other_branches_and_forks(self) -> None:
        for head_ref, head_repository in (("feature/login", "owner/repo"), ("stg", "fork/repo")):
            with self.subTest(head_ref=head_ref, head_repository=head_repository):
                error = pr_policy.validate("prod", head_ref, "owner/repo", head_repository, ("feature/*",))
                self.assertIn("同一リポジトリの stg", error or "")


if __name__ == "__main__":
    unittest.main()