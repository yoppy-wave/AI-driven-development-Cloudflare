#!/usr/bin/env python3
"""Archive tracked source at prod and upload it to the configured R2 bucket."""

import os
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    archive = Path(os.environ["RUNNER_TEMP"]) / "analysis-archive.zip"
    project = root / os.environ["PROJECT_PATH"]
    repository = os.environ["GITHUB_REPOSITORY"]
    bucket = os.environ["R2_ANALYSIS_ARCHIVE_BUCKET"]
    if not bucket:
        raise SystemExit("R2_ANALYSIS_ARCHIVE_BUCKET is not configured.")
    owner, name = repository.split("/", 1)
    key = f"analysis-archives/{owner}/{name}.zip"
    subprocess.run(["git", "archive", "--format=zip", "--output", str(archive), "HEAD"], cwd=root, check=True)
    subprocess.run(
        ["npx", "--no-install", "wrangler", "r2", "object", "put", f"{bucket}/{key}", "--file", str(archive), "--content-type", "application/zip"],
        cwd=project,
        check=True,
    )
    Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(
        f"## Analysis archive published\n\n- Bucket: `{bucket}`\n- Key: `{key}`\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()