#!/usr/bin/env python3
"""Check runtime freshness separately from exact package/lock consistency."""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from importlib.metadata import version as installed_version
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from run_regression import discover, install_node, run

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / ".github/quality/version-policy.json"


class PolicyViolation(ValueError):
    pass


class ReleaseSourceError(RuntimeError):
    pass


def version(value: str) -> tuple[int, ...]:
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise PolicyViolation(f"expected a stable exact version, got {value!r}")
    return tuple(int(part) for part in value.removeprefix("v").split("."))


def in_series(value: str, series: str) -> bool:
    parts = tuple(int(part) for part in series.split("."))
    return version(value)[:len(parts)] == parts


def fetch_releases(url: str) -> list[dict]:
    try:
        headers = {"User-Agent": "repository-quality-gate"}
        if url.startswith("https://api.github.com/") and os.environ.get("GH_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            data = json.load(response)
        if not isinstance(data, list) or not data or not all(isinstance(row, dict) for row in data):
            raise ValueError("expected a nonempty release array")
        return data
    except (URLError, TimeoutError, OSError, ValueError) as error:
        raise ReleaseSourceError(f"could not read official release source {url}: {error}") from error


def required_runtime(kind: str, releases: list[dict], series: str, now: datetime, grace_hours: int) -> str:
    eligible: list[str] = []
    matched = False
    try:
        for release in releases:
            if kind == "python":
                if release.get("pre_release") or release.get("is_published") is not True:
                    continue
                candidate = release["name"].removeprefix("Python ")
                date = release["release_date"]
            else:
                if release.get("prerelease") or release.get("draft"):
                    continue
                candidate = release["tag_name"].removeprefix("v")
                date = release["published_at"]
            if not re.fullmatch(r"\d+\.\d+\.\d+", candidate) or not in_series(candidate, series):
                continue
            matched = True
            published = datetime.fromisoformat(date.replace("Z", "+00:00"))
            if published.tzinfo is None:
                raise ValueError("release timestamp must include a timezone")
            if now >= published + timedelta(hours=grace_hours):
                eligible.append(candidate)
    except (KeyError, AttributeError, TypeError, ValueError) as error:
        raise ReleaseSourceError(f"invalid {kind} release metadata: {error}") from error
    if not matched or not eligible:
        raise ReleaseSourceError(f"no mature stable {kind} {series} release in official response")
    return max(eligible, key=version)


def check_runtime(kind: str, actual: str, required: str, series: str) -> None:
    if not in_series(actual, series):
        raise PolicyViolation(f"{kind} {actual} is outside the selected {series} series")
    if version(actual) < version(required):
        raise PolicyViolation(f"{kind} {actual} is older than required {required}; release grace period expired")


def pins(path: Path) -> dict[str, str]:
    result = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+!-]+)", line)
        if match is None:
            raise PolicyViolation(f"{path}:{number}: fixed dependencies must use exact == pins")
        name, pinned = match.groups()
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in result:
            raise PolicyViolation(f"{path}:{number}: duplicate dependency {name}")
        result[name] = pinned
    return result


def check_python_lock(manifest: Path, lock: Path, installed: dict[str, str]) -> None:
    direct, locked = pins(manifest), pins(lock)
    for name, pinned in direct.items():
        if locked.get(name) != pinned:
            raise PolicyViolation(f"{name}: Python manifest/lock mismatch ({pinned})")
    for name, pinned in locked.items():
        if installed.get(name) != pinned:
            raise PolicyViolation(f"{name}: installed Python dependency does not match lock ({pinned})")


def check_node_lock(package: dict, lock: dict) -> None:
    if lock.get("lockfileVersion") not in (2, 3) or "" not in lock.get("packages", {}):
        raise PolicyViolation("npm lockfile v2/v3 with a root package is required")
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        declared = package.get(section, {})
        if declared != lock["packages"][""].get(section, {}):
            raise PolicyViolation(f"npm {section}: manifest/lock declarations differ")
        for name, pinned in declared.items():
            version(pinned)
            if lock["packages"].get(f"node_modules/{name}", {}).get("version") != pinned:
                raise PolicyViolation(f"{name}: resolved npm version does not match fixed {pinned}")


def main() -> None:
    policy = json.loads(POLICY.read_text())
    # Broad selectors must agree with the policy; freshness is checked on resolved binaries.
    container = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
    if container["build"]["args"]["PYTHON_VERSION"] != policy["runtimes"]["python"]["series"]:
        raise PolicyViolation("Dev Container Python selector differs from runtime policy")
    if container["features"]["ghcr.io/devcontainers/features/node:2"]["version"] != policy["runtimes"]["node"]["series"]:
        raise PolicyViolation("Dev Container Node selector differs from runtime policy")
    actual = {"python": ".".join(map(str, sys.version_info[:3])),
              "node": subprocess.check_output(["node", "--version"], text=True).strip().removeprefix("v")}
    now = datetime.now(timezone.utc)
    minimums = {}
    for kind, settings in policy["runtimes"].items():
        minimum = required_runtime(kind, fetch_releases(settings["source"]), settings["series"], now, policy["grace_hours"])
        check_runtime(kind, actual[kind], minimum, settings["series"])
        minimums[kind] = minimum
        print(f"{kind}: actual={actual[kind]}, minimum after grace={minimum}, series={settings['series']}")
    python_roots, node_roots = discover(ROOT)
    covered = set()
    for entry in policy["fixed"]["python"]:
        manifest, lock = ROOT / entry["manifest"], ROOT / entry["lock"]
        covered.add(manifest.parent.relative_to(ROOT))
        run([sys.executable, "-m", "pip", "install", "-r", str(lock)], ROOT)
        check_python_lock(manifest, lock, {name: installed_version(name) for name in pins(lock)})
    if set(python_roots) != covered:
        raise PolicyViolation("every discovered Python project needs a fixed manifest/lock policy entry")
    run([sys.executable, "-m", "pip", "check"], ROOT)
    for project in node_roots:
        directory = ROOT / project
        check_node_lock(json.loads((directory / "package.json").read_text()),
                        json.loads((directory / policy["fixed"]["node_lock"]).read_text()))
        install_node(ROOT, project, ignore_scripts=True)
        run(["npm", "ls", "--all"], directory)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for kind, minimum in minimums.items():
                output.write(f"required-{kind}={minimum}\n")


if __name__ == "__main__":
    try:
        main()
    except ReleaseSourceError as error:
        raise SystemExit(f"RELEASE_SOURCE_ERROR: {error}") from None
    except (PolicyViolation, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"VERSION_POLICY_ERROR: {error}") from None
