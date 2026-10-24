#!/usr/bin/env python3
"""Compare the Cloudflare Preview names reported by Wrangler with open PR branches."""

import json
import os
import subprocess
from pathlib import Path

from cloudflare_preview import preview_name


def summary(lines: list[str]) -> None:
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        Path(destination).write_text("\n".join(lines) + "\n", encoding="utf-8")


def pull_requests(repository: str) -> list[dict[str, object]]:
    response = subprocess.check_output(
        ["gh", "api", "--paginate", "--slurp", f"repos/{repository}/pulls?state=all&per_page=100"], text=True,
    )
    payload = json.loads(response)
    if not isinstance(payload, list) or any(not isinstance(page, list) for page in payload):
        raise ValueError("GitHub pull request response is invalid")
    return [pull for page in payload for pull in page if isinstance(pull, dict)]


def names(pulls: list[dict[str, object]], state: str) -> set[str]:
    result = set()
    for pull in pulls:
        if pull.get("state") != state:
            continue
        branch = pull.get("head", {}).get("ref") if isinstance(pull, dict) else None
        if not isinstance(branch, str):
            raise ValueError("GitHub pull request branch is invalid")
        result.add(preview_name(branch))
    return result


def preview_url_suffix(worker_name: str) -> str:
    response = subprocess.check_output(
        [
            "curl", "--fail-with-body", "--silent", "--show-error",
            "--header", f"Authorization: Bearer {os.environ['CLOUDFLARE_API_TOKEN']}",
            f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/workers/scripts/{worker_name}",
        ],
        text=True,
    )
    payload = json.loads(response)
    suffix = payload.get("result", {}).get("subdomain", {}).get("preview_url_suffix") if isinstance(payload, dict) else None
    if not isinstance(suffix, str) or not suffix:
        raise ValueError("Cloudflare Worker response did not include preview_url_suffix")
    return suffix.removeprefix("https://").removeprefix("http://").rstrip("/")


def existing_closed_previews(candidates: set[str], worker_name: str) -> set[str]:
    suffix = preview_url_suffix(worker_name)
    existing = set()
    for candidate in sorted(candidates):
        url = f"https://{candidate}-{worker_name}.{suffix}"
        status = subprocess.check_output(["curl", "--silent", "--output", "/dev/null", "--write-out", "%{http_code}", url], text=True)
        if status == "200":
            existing.add(candidate)
        elif status != "404":
            raise RuntimeError(f"Could not verify Preview candidate {candidate}: HTTP {status}")
    return existing


def main() -> None:
    pulls = pull_requests(os.environ["GH_REPO"])
    expected = names(pulls, "open")
    closed_candidates = names(pulls, "closed") - expected
    orphans = sorted(existing_closed_previews(closed_candidates, os.environ["PREVIEW_WORKER_NAME"]))
    lines = ["## Cloudflare Preview orphan audit", "", f"- Open PR previews expected: {len(expected)}", f"- Closed PR Preview candidates checked: {len(closed_candidates)}"]
    if not orphans:
        lines.append("- Result: no orphan Preview candidates found.")
        summary(lines)
        return
    lines.extend(["", "### Orphan candidates", *[f"- `{name}`" for name in orphans]])
    summary(lines)
    raise SystemExit(f"Found {len(orphans)} Cloudflare Preview orphan candidate(s).")


if __name__ == "__main__":
    main()