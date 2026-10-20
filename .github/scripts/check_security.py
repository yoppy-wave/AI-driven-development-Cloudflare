#!/usr/bin/env python3
"""Detect direct sensitive arguments to logging calls using Python's AST."""

import ast
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / ".github/quality/log-policy.json").read_text())
METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log", "trace"}


def sensitive(name: str) -> bool:
    if name in POLICY["safe_names"]:
        return False
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()
    compact = re.sub(r"[^a-z0-9]", "", words)
    return compact in POLICY["sensitive_words"] or bool(set(re.split(r"[^a-z0-9]+", words)) & set(POLICY["sensitive_words"])) or any(
        word in compact for word in ("apikey", "privatekey", "accesskey")
    )


def redacted(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in POLICY["redacted_values"]


def risky_argument(argument: ast.AST) -> bool:
    if redacted(argument):
        return False
    for node in ast.walk(argument):
        if isinstance(node, ast.Name) and sensitive(node.id):
            return True
        if isinstance(node, ast.Attribute) and sensitive(node.attr):
            return True
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and sensitive(node.slice.value):
            return True
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and sensitive(key.value) and not redacted(value):
                    return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
                key = node.args[0]
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and sensitive(key.value):
                    return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and not redacted(node):
            if re.search(r"\bBearer\s+\S+|\b(?:password|token|api[_-]?key|authorization)\s*[:=]\s*\S+", node.value, re.I):
                return True
        if isinstance(node, ast.JoinedStr):
            if any(isinstance(part, ast.Constant) and isinstance(part.value, str) and re.search(r"(?:password|token|api[_-]?key|authorization)\s*[:=]\s*$", part.value, re.I) for part in node.values):
                return True
    return False


def scan_source(source: str, filename: str) -> list[str]:
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return [f"{filename}:{error.lineno}: Python parse error"]
    logger_names = {"logging", "logger", "log"}
    direct_calls = {"print"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "logging":
                    logger_names.add(alias.asname or alias.name)
        if isinstance(node, ast.ImportFrom) and node.module == "logging":
            direct_calls.update(alias.asname or alias.name for alias in node.names if alias.name in METHODS)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "getLogger":
                logger_names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        sink = isinstance(node.func, ast.Name) and node.func.id in direct_calls
        if isinstance(node.func, ast.Attribute) and node.func.attr in METHODS:
            names = [part.id for part in ast.walk(node.func.value) if isinstance(part, ast.Name)]
            names += [part.attr for part in ast.walk(node.func.value) if isinstance(part, ast.Attribute)]
            sink = any(name in logger_names or name.lower().endswith("logger") for name in names)
        if sink and (any(risky_argument(arg) for arg in node.args) or any(
            risky_argument(item.value) or (item.arg is not None and sensitive(item.arg) and not redacted(item.value)) for item in node.keywords
        )):
            findings.append(f"{filename}:{node.lineno}: sensitive value passed directly to a logging call")
    return findings


def source_files(root: Path) -> list[Path]:
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
    return [Path(path) for path in paths if path and (root / path).is_file()]


def main() -> None:
    files = source_files(ROOT)
    findings = []
    for path in files:
        if path.suffix in (".py", ".pyi"):
            findings.extend(scan_source((ROOT / path).read_text(encoding="utf-8"), path.as_posix()))
    javascript = [path.as_posix() for path in files if path.suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")]
    result = subprocess.run(["node", str(ROOT / ".github/scripts/check_security.cjs")], cwd=ROOT, input=json.dumps(javascript), text=True, capture_output=True)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    for finding in findings:
        print(finding)
    if findings or result.returncode:
        raise SystemExit(1)
    print("Security: no direct sensitive logging arguments found.")


if __name__ == "__main__":
    main()
