#!/usr/bin/env python3
"""Create/update and delete Workers Previews using the same branch-derived name."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def preview_name(branch: str) -> str:
    # Keep the previous branch normalization: each symbol becomes a hyphen.
    # No hash or PR number is appended.
    normalized = re.sub(r"[^A-Za-z0-9]", "-", branch).lower().strip("-")
    normalized = normalized[:30].rstrip("-")
    if not normalized:
        raise ValueError("preview branch normalizes to an empty name")
    return f"app-{normalized}"


def project_directory(root: Path, relative: str) -> Path:
    path = Path(relative)
    directory = (root / path).resolve()
    if not relative or path.is_absolute() or ".." in path.parts or not directory.is_relative_to(root.resolve()):
        raise ValueError("preview project must be inside the repository")
    for filename in ("package.json", "package-lock.json"):
        if not (directory / filename).is_file():
            raise ValueError(f"preview project requires {filename}")
    package = json.loads((directory / "package.json").read_text(encoding="utf-8"))
    wrangler = {**package.get("dependencies", {}), **package.get("devDependencies", {})}.get("wrangler")
    if not isinstance(wrangler, str) or not re.fullmatch(r"\d+\.\d+\.\d+", wrangler):
        raise ValueError("preview project must pin a Wrangler version supporting the preview command")
    if not any((directory / name).is_file() for name in ("wrangler.jsonc", "wrangler.json", "wrangler.toml")):
        raise ValueError("preview project requires a Wrangler configuration")
    return directory


def current_pr_matches(pr: dict, operation: str, repository: str, branch: str, sha: str) -> bool:
    head = pr.get("head", {})
    if (head.get("repo") or {}).get("full_name") != repository or head.get("ref") != branch:
        return False
    if operation == "delete":
        return pr.get("state") == "closed"
    return pr.get("state") == "open" and head.get("sha") == sha


def command(operation: str, branch: str) -> list[str]:
    if operation not in ("deploy", "delete"):
        raise ValueError("preview operation must be deploy or delete")
    args = ["npx", "--no-install", "wrangler", "preview"]
    if operation == "delete":
        args.append("delete")
    args.extend(["--name", preview_name(branch)])
    if operation == "delete":
        args.append("--skip-confirmation")
    return args


def run_preview(directory: Path, operation: str, branch: str, repository: str, number: str, sha: str) -> bool:
    args = command(operation, branch)
    if not re.fullmatch(r"[1-9]\d*", number):
        raise ValueError("PR number must be a positive integer")
    response = subprocess.check_output(
        ["gh", "api", f"repos/{repository}/pulls/{number}"], text=True,
    )
    if not current_pr_matches(json.loads(response), operation, repository, branch, sha):
        print("Preview operation skipped: PR state or revision has changed.")
        return False
    for name in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if not os.environ.get(name):
            raise ValueError(f"{name} is not configured")
    subprocess.run(args, cwd=directory, check=True)
    print(f"Preview {operation} completed: {preview_name(branch)}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate", "run"))
    args = parser.parse_args()
    operation, branch = os.environ["OPERATION"], os.environ["PREVIEW_BRANCH"]
    command(operation, branch)
    directory = project_directory(ROOT, os.environ["PROJECT_PATH"])
    if args.action == "run":
        run_preview(directory, operation, branch, os.environ["GH_REPO"], os.environ["PR_NUMBER"], os.environ["SOURCE_REF"])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
