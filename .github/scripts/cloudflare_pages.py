#!/usr/bin/env python3
"""Deploy validated Cloudflare Pages Direct Uploads from GitHub Actions."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


def project_directory(root: Path, relative: str) -> Path:
    path = Path(relative)
    directory = (root / path).resolve()
    if not relative or path.is_absolute() or ".." in path.parts or not directory.is_relative_to(root.resolve()):
        raise ValueError("Pages project must be inside the repository")
    for filename in ("package.json", "package-lock.json"):
        if not (directory / filename).is_file():
            raise ValueError(f"Pages project requires {filename}")
    package = json.loads((directory / "package.json").read_text(encoding="utf-8"))
    wrangler = {**package.get("dependencies", {}), **package.get("devDependencies", {})}.get("wrangler")
    if not isinstance(wrangler, str) or not re.fullmatch(r"\d+\.\d+\.\d+", wrangler):
        raise ValueError("Pages project must pin a Wrangler version")
    return directory


def output_directory(project: Path, relative: str, require_exists: bool = False) -> Path:
    path = Path(relative)
    directory = (project / path).resolve()
    if not relative or path.is_absolute() or ".." in path.parts or not directory.is_relative_to(project.resolve()):
        raise ValueError("Pages output directory must be a relative path inside the project")
    if require_exists and not directory.is_dir():
        raise ValueError("Pages output directory does not exist after the build")
    return directory


def preview_branch(number: str) -> str:
    if not re.fullmatch(r"[1-9]\d*", number):
        raise ValueError("PR number must be a positive integer")
    return f"pr-{number}"


def command(project: Path, output: str, project_name: str, branch: str, commit_hash: str) -> list[str]:
    if not NAME_PATTERN.fullmatch(project_name):
        raise ValueError("Pages project name must contain lowercase letters, digits, and hyphens, and start with a letter")
    if not NAME_PATTERN.fullmatch(branch):
        raise ValueError("Pages deployment branch must contain lowercase letters, digits, and hyphens, and start with a letter")
    directory = output_directory(project, output, require_exists=True)
    if not re.fullmatch(r"[0-9a-f]{40}", commit_hash):
        raise ValueError("Pages deployment commit hash must be a full Git SHA")
    return [
        "npx", "--no-install", "wrangler", "pages", "deploy", str(directory),
        f"--project-name={project_name}", f"--branch={branch}", f"--commit-hash={commit_hash}",
    ]


def current_pr_matches(pr: dict, repository: str, branch: str, sha: str) -> bool:
    head = pr.get("head", {})
    return (
        pr.get("state") == "open"
        and (head.get("repo") or {}).get("full_name") == repository
        and head.get("ref") == branch
        and head.get("sha") == sha
    )


def preview_url(output: str) -> str | None:
    urls = re.findall(r"https://[^\s\]\"']+", output)
    return urls[-1] if urls else None


def preview_alias_url(project_name: str, number: str) -> str:
    return f"https://{preview_branch(number)}.{project_name}.pages.dev"


def safe_output(value: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            value = value.replace(secret, "***")
    return value


def run_wrangler(args: list[str], project: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, cwd=project, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as error:
        secrets = (os.environ.get("CLOUDFLARE_API_TOKEN", ""), os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""))
        if error.stdout:
            print(safe_output(error.stdout, secrets), end="")
        if error.stderr:
            print(safe_output(error.stderr, secrets), end="", file=sys.stderr)
        raise


def run_preview(project: Path, output: str, project_name: str, repository: str, number: str, branch: str, sha: str) -> bool:
    response = subprocess.check_output(["gh", "api", f"repos/{repository}/pulls/{number}"], text=True)
    if not current_pr_matches(json.loads(response), repository, branch, sha):
        print("Pages Preview skipped: PR state or revision has changed.")
        return False
    for name in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        if not os.environ.get(name):
            raise ValueError(f"{name} is not configured")
    completed = run_wrangler(command(project, output, project_name, preview_branch(number), sha), project)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = ["## Cloudflare Pages Preview", "", f"- Branch: `{preview_branch(number)}`", f"- Branch alias: {preview_alias_url(project_name, number)}"]
        lines.append(f"- Deployment URL: {preview_url(completed.stdout) or 'Wrangler output did not include an immutable Pages deployment URL.'}")
        Path(summary).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def cleanup_summary(number: str) -> None:
    branch = preview_branch(number)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    message = "Pages cannot reliably delete a branch's latest deployment, so its branch alias may remain accessible after this PR closes."
    if summary:
        Path(summary).write_text("\n".join(("## Cloudflare Pages Preview cleanup", "", f"- Branch: `{branch}`", "- Result: not deleted.", f"- {message}")) + "\n", encoding="utf-8")
    print(f"Pages Preview cleanup not performed: {message}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate", "deploy", "preview", "cleanup"))
    args = parser.parse_args()
    project = project_directory(ROOT, os.environ["PROJECT_PATH"])
    output = os.environ["PAGES_OUTPUT_DIRECTORY"]
    project_name = os.environ["PAGES_PROJECT_NAME"]
    if args.action == "validate":
        output_directory(project, output)
        if not NAME_PATTERN.fullmatch(project_name):
            raise ValueError("Pages project name must contain lowercase letters, digits, and hyphens, and start with a letter")
    elif args.action == "deploy":
        completed = run_wrangler(command(project, output, project_name, os.environ["DEPLOYMENT_BRANCH"], os.environ["SOURCE_REF"]), project)
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
    elif args.action == "preview":
        run_preview(project, output, project_name, os.environ["GH_REPO"], os.environ["PR_NUMBER"], os.environ["PREVIEW_BRANCH"], os.environ["SOURCE_REF"])
    else:
        cleanup_summary(os.environ["PR_NUMBER"])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None