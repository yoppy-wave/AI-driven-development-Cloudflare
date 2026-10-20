"""Preview management tests use real shared naming and mocked AWS/GitHub calls."""

import copy
import json
import unittest
from unittest.mock import patch

import preview_cleanup as preview

REGION = "us-east-1"
ACCOUNT = "123456789012"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/preview"
BRANCH = "feature/Add_Login"
NAME = "app-feature-add-login"
STACK_ID = f"arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/{NAME}/unique-id"


class PreviewCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = {
            "StackName": NAME, "StackId": STACK_ID, "StackStatus": "UPDATE_COMPLETE",
            "Tags": [{"Key": "app:managed-by", "Value": preview.MANAGED_BY},
                     {"Key": "app:preview-pr", "Value": "42"}],
        }
        self.calls = []
        self.identity = ACCOUNT
        self.describe_error = None
        self.aws_mock = self.enterContext(patch.object(preview, "aws", side_effect=self.aws))
        self.closed = self.enterContext(patch.object(preview, "remains_closed", return_value=True))

    def aws(self, region, *arguments):
        self.calls.append((region, *arguments))
        self.assertEqual(region, REGION)
        if arguments == ("sts", "get-caller-identity"):
            return json.dumps({"Account": self.identity})
        if arguments[:2] == ("cloudformation", "describe-stacks"):
            self.assertEqual(arguments[3], NAME)
            if self.describe_error:
                raise RuntimeError(self.describe_error)
            return json.dumps({"Stacks": [copy.deepcopy(self.stack)]})
        return "{}"

    def manage(self, command="cleanup", branch=BRANCH, pr=42, region=REGION, role=ROLE):
        preview.manage(command, branch, pr, region, role, "owner/repo")

    def mutations(self):
        return [call for call in self.calls if call[1:3] == ("cloudformation", "delete-stack")]

    def waits(self):
        return [call for call in self.calls if call[1:4] == ("cloudformation", "wait", "stack-delete-complete")]

    def test_normalizes_branches_with_the_same_function_as_cdk(self):
        for branch, expected in [
            (BRANCH, NAME), ("fix/API_Error", "app-fix-api-error"),
            ("--A__B--", "app-a--b"),
            ("a" * 40, "app-" + "a" * 30),
            ("a" * 29 + "/rest", "app-" + "a" * 29),
            ("a" * 28 + "//rest", "app-" + "a" * 28),
            ("日本語/Feature", "app-feature"),
            ("a😀b", "app-a-b"),
        ]:
            with self.subTest(branch=branch):
                self.assertEqual(preview.preview_stack_name(branch), expected)

    def test_empty_and_shared_names_are_rejected_before_aws(self):
        for command in ("verify", "cleanup"):
            for branch in ("", "---", "日本語", "Development", "-staging-", "PRODUCTION", "development" + "-" * 30 + "x"):
                with self.subTest(command=command, branch=branch), self.assertRaises(RuntimeError):
                    self.manage(command, branch)
        self.aws_mock.assert_not_called()

    def test_same_branch_updates_and_cleanup_resolve_same_stack(self):
        self.manage("verify")
        self.manage("verify")
        self.manage("cleanup")
        describes = [call[4] for call in self.calls if call[1:3] == ("cloudformation", "describe-stacks")]
        self.assertEqual(describes, [NAME] * 3)
        self.assertEqual(self.mutations(), [(REGION, "cloudformation", "delete-stack", "--stack-name", STACK_ID)])
        self.assertEqual(self.waits(), [(REGION, "cloudformation", "wait", "stack-delete-complete", "--stack-name", STACK_ID)])

    def test_missing_stack_is_successful_for_create_and_cleanup(self):
        self.describe_error = f"An error occurred (ValidationError): Stack with id {NAME} does not exist"
        self.manage("verify")
        self.manage("cleanup")
        self.assertFalse(self.mutations())
        self.assertFalse(self.waits())

    def test_cloudformation_errors_are_not_mistaken_for_missing_stack(self):
        for error in ("AccessDenied: does not exist", "(ValidationError): something else"):
            self.describe_error = error
            with self.assertRaises(RuntimeError):
                self.manage()
        self.assertFalse(self.mutations())

    def test_different_pr_collision_prevents_both_update_and_deletion(self):
        for branch in (BRANCH, "FEATURE-add-login"):
            for command in ("verify", "cleanup"):
                with self.subTest(command=command, branch=branch), self.assertRaisesRegex(ValueError, "another PR"):
                    self.manage(command, branch, pr=99)
        self.assertFalse(self.mutations())
        self.assertFalse(self.waits())

    def test_truncation_collision_also_rejects_another_pr(self):
        first = "a" * 30 + "/first"
        second = "a" * 30 + "/second"
        name = preview.preview_stack_name(first)
        self.assertEqual(name, preview.preview_stack_name(second))
        self.stack["StackName"] = name
        self.stack["StackId"] = STACK_ID.replace(NAME, name)
        with patch.object(preview, "describe_stack", return_value=self.stack):
            for command in ("verify", "cleanup"):
                with self.assertRaisesRegex(ValueError, "another PR"):
                    self.manage(command, second, pr=99)
        self.assertFalse(self.mutations())

    def test_unmanaged_or_incorrect_tags_prevent_update_and_delete(self):
        for tags in ([], [{"Key": "app:preview-pr", "Value": "42"}],
                     [{"Key": "app:managed-by", "Value": "other"}, {"Key": "app:preview-pr", "Value": "42"}]):
            self.stack["Tags"] = tags
            for command in ("verify", "cleanup"):
                with self.subTest(tags=tags, command=command), self.assertRaisesRegex(ValueError, "unmanaged"):
                    self.manage(command)
        self.assertFalse(self.mutations())

    def test_delete_in_progress_validates_tags_and_only_waits(self):
        self.stack["StackStatus"] = "DELETE_IN_PROGRESS"
        self.manage()
        self.assertFalse(self.mutations())
        self.assertEqual(len(self.waits()), 1)
        self.stack["Tags"] = []
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            self.manage()
        self.assertEqual(len(self.waits()), 1)

    def test_verify_refuses_to_deploy_during_or_after_failed_deletion(self):
        for status in ("DELETE_IN_PROGRESS", "DELETE_FAILED", "DELETE_COMPLETE"):
            self.stack["StackStatus"] = status
            with self.assertRaisesRegex(ValueError, "deleted"):
                self.manage("verify")
        self.assertFalse(self.mutations())

    def test_delete_failed_can_be_retried_and_delete_complete_is_a_noop(self):
        self.stack["StackStatus"] = "DELETE_FAILED"
        self.manage()
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(len(self.waits()), 1)
        self.stack["StackStatus"] = "DELETE_COMPLETE"
        self.manage()
        self.assertEqual(len(self.mutations()), 1)
        self.assertEqual(len(self.waits()), 1)

    def test_reopened_pr_skips_aws_entirely(self):
        self.closed.return_value = False
        self.manage()
        self.aws_mock.assert_not_called()

    def test_pr_reopened_during_inspection_is_not_deleted(self):
        self.closed.side_effect = [True, False]
        self.manage()
        self.assertFalse(self.mutations())
        self.assertFalse(self.waits())

    def test_account_region_and_stack_identity_must_match(self):
        self.identity = "999999999999"
        with self.assertRaisesRegex(ValueError, "AWS account"):
            self.manage()
        self.identity = ACCOUNT
        for field, value in (
            ("StackName", "app-production"),
            ("StackId", STACK_ID.replace(REGION, "eu-west-1")),
            ("StackId", STACK_ID.replace(ACCOUNT, "999999999999")),
            ("StackId", STACK_ID.replace(NAME, "app-other")),
        ):
            original = self.stack[field]
            self.stack[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.manage()
            self.stack[field] = original
        self.assertFalse(self.mutations())

    def test_invalid_pr_region_and_role_fail_before_aws(self):
        for overrides in ({"pr": 0}, {"region": "bad"}, {"role": ""}, {"role": "arn:aws:iam::123:role/x"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.manage(**overrides)
        self.aws_mock.assert_not_called()

    def test_wait_and_delete_failures_propagate(self):
        original = self.aws
        for failing_command in ("delete-stack", "wait"):
            def fail(region, *arguments):
                if arguments[1] == failing_command:
                    raise RuntimeError("AWS failure")
                return original(region, *arguments)
            self.aws_mock.side_effect = fail
            with self.subTest(command=failing_command), self.assertRaisesRegex(RuntimeError, "AWS failure"):
                self.manage()

    def test_shared_stack_is_rejected_even_with_preview_tags(self):
        with self.assertRaisesRegex(ValueError, "shared"):
            preview.validate_stack(self.stack, "app-production", REGION, "aws", ACCOUNT, 42)


class PullRequestStateTests(unittest.TestCase):
    def test_closed_open_and_renamed_pr(self):
        for state, branch, expected in (("closed", BRANCH, True), ("open", BRANCH, False),
                                        ("closed", "renamed", False)):
            with patch.object(preview, "run", return_value=json.dumps({"state": state, "head": {"ref": branch}})) as run:
                self.assertEqual(preview.remains_closed("owner/repo", 42, BRANCH), expected)
                run.assert_called_once_with(["gh", "api", "repos/owner/repo/pulls/42"])

    def test_github_api_failure_is_not_treated_as_closed(self):
        with patch.object(preview, "run", side_effect=RuntimeError("GitHub unavailable")):
            with self.assertRaises(RuntimeError):
                preview.remains_closed("owner/repo", 42, BRANCH)
