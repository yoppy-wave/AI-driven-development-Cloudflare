#!/usr/bin/env python3
"""Resolve branch-based preview stacks and validate CloudFormation ownership."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANAGED_BY = "ai-driven-development"


def preview_stack_name(branch: str) -> str:
    # This exact implementation is also imported by the CDK Stack definition.
    return run(["node", str(ROOT / "lib" / "preview-stack-name.cjs"), branch]).strip()


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "command failed")
    return result.stdout


def aws(region: str, *arguments: str) -> str:
    return run(["aws", *arguments, "--region", region, "--output", "json"])


def validate_identity(region: str, role_arn: str) -> tuple[str, str]:
    if not re.fullmatch(r"[a-z]{2}-[a-z]+-[0-9]+", region):
        raise ValueError("region must be an AWS region identifier")
    role = re.fullmatch(r"arn:(aws(?:-us-gov|-cn)?):iam::([0-9]{12}):role/.+", role_arn)
    if role is None:
        raise ValueError("AWS_ROLE_TO_ASSUME must identify the expected AWS account")
    partition, account = role.groups()
    identity = json.loads(aws(region, "sts", "get-caller-identity"))
    if identity.get("Account") != account:
        raise ValueError("authenticated AWS account does not match the configured role")
    return partition, account


def describe_stack(region: str, stack_name: str) -> dict[str, Any] | None:
    try:
        response = aws(region, "cloudformation", "describe-stacks", "--stack-name", stack_name)
    except RuntimeError as error:
        if "(ValidationError)" in str(error) and f"Stack with id {stack_name} does not exist" in str(error):
            return None
        raise
    stacks = json.loads(response)["Stacks"]
    if len(stacks) != 1:
        raise ValueError("expected exactly one CloudFormation stack")
    return stacks[0]


def validate_stack(stack: dict[str, Any], name: str, region: str, partition: str, account: str, pr: int) -> str:
    if name in {"app-development", "app-staging", "app-production"}:
        raise ValueError("shared stacks cannot be managed as previews")
    if stack.get("StackName") != name:
        raise ValueError("CloudFormation stack name does not match")
    stack_id = stack.get("StackId", "")
    if not stack_id.startswith(f"arn:{partition}:cloudformation:{region}:{account}:stack/{name}/"):
        raise ValueError("CloudFormation stack account or region does not match")
    tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
    if tags.get("app:managed-by") != MANAGED_BY or tags.get("app:preview-pr") != str(pr):
        raise ValueError("preview stack is unmanaged or belongs to another PR")
    return stack_id


def remains_closed(repository: str, pr: int, branch: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must be owner/name")
    current = json.loads(run(["gh", "api", f"repos/{repository}/pulls/{pr}"]))
    return current["state"] == "closed" and current["head"]["ref"] == branch


def manage(command: str, branch: str, pr: int, region: str, role_arn: str, repository: str = "") -> None:
    if command not in ("verify", "cleanup"):
        raise ValueError("unsupported preview operation")
    if pr < 1:
        raise ValueError("pull request number must be positive")
    name = preview_stack_name(branch)
    if command == "cleanup" and not remains_closed(repository, pr, branch):
        print("Preview cleanup skipped: PR is open or its branch changed.")
        return
    partition, account = validate_identity(region, role_arn)
    stack = describe_stack(region, name)
    if stack is None:
        print(f"{name}: stack does not exist; no action required.")
        return
    stack_id = validate_stack(stack, name, region, partition, account, pr)
    status = stack["StackStatus"]
    if command == "verify":
        if status.startswith("DELETE_"):
            raise ValueError("preview stack is being deleted or deletion failed; retry after cleanup")
        print(f"{name}: ownership verified in {account}/{region} ({status}).")
        return
    if status == "DELETE_COMPLETE":
        return
    if status != "DELETE_IN_PROGRESS":
        # Recheck after CloudFormation inspection and any Environment approval wait.
        if not remains_closed(repository, pr, branch):
            print("Preview cleanup skipped: PR reopened or its branch changed.")
            return
        aws(region, "cloudformation", "delete-stack", "--stack-name", stack_id)
    # Use the validated immutable ID, so a recreated stack with the same name is never selected.
    aws(region, "cloudformation", "wait", "stack-delete-complete", "--stack-name", stack_id)
    print(f"{name}: deletion completed in {account}/{region}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("stack-name", "verify", "cleanup"))
    parser.add_argument("--branch", required=True)
    parser.add_argument("--pull-request", type=int)
    parser.add_argument("--region", default="")
    parser.add_argument("--repository", default="")
    args = parser.parse_args()
    if args.command == "stack-name":
        print(preview_stack_name(args.branch))
    else:
        if args.pull_request is None:
            parser.error("--pull-request is required for verify/cleanup")
        manage(args.command, args.branch, args.pull_request, args.region, os.environ.get("AWS_ROLE_TO_ASSUME", ""), args.repository)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, KeyError) as error:
        raise SystemExit(str(error)) from None
