#!/usr/bin/env python3
"""Lint all discovered projects; a missing Node lint script is a failed gate."""

import json
import subprocess
import sys
from pathlib import Path

from run_regression import discover, install_node, install_python, run


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    python_roots, node_roots = discover(root)
    for project in python_roots:
        install_python(root, project)
    if python_roots:
        run([sys.executable, "-m", "ruff", "check", "."], root)
    for project in node_roots:
        package = json.loads((root / project / "package.json").read_text())
        if not package.get("scripts", {}).get("lint"):
            raise RuntimeError(f"Node project {project} needs a lint script")
        manager = install_node(root, project)
        run([*manager, "run", "lint"], root / project)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
