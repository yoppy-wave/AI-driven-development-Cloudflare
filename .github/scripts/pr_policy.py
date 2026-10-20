#!/usr/bin/env python3
"""Validate pull request source branches for protected branch flows."""

import fnmatch
import os


DEFAULT_STG_HEAD_PATTERNS = ("feature/*", "fix/*")


def allowed_stg_head_patterns(value: str | None) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_STG_HEAD_PATTERNS
    patterns = tuple(pattern.strip() for pattern in value.split(",") if pattern.strip())
    if not patterns:
        raise ValueError("ALLOWED_STG_HEAD_PATTERNS must contain at least one pattern")
    return patterns


def validate(
    base_ref: str,
    head_ref: str,
    base_repository: str,
    head_repository: str,
    stg_patterns: tuple[str, ...],
) -> str | None:
    if base_ref == "prod":
        if head_repository != base_repository or head_ref != "stg":
            return "prod への PR は同一リポジトリの stg ブランチから作成してください。"
        return None
    if base_ref == "stg" and not any(fnmatch.fnmatchcase(head_ref, pattern) for pattern in stg_patterns):
        patterns = ", ".join(stg_patterns)
        return f"stg への PR 元ブランチは次のパターンに一致させてください: {patterns}"
    return None


def main() -> None:
    patterns = allowed_stg_head_patterns(os.environ.get("ALLOWED_STG_HEAD_PATTERNS"))
    error = validate(
        os.environ["BASE_REF"],
        os.environ["HEAD_REF"],
        os.environ["BASE_REPOSITORY"],
        os.environ["HEAD_REPOSITORY"],
        patterns,
    )
    if error:
        raise SystemExit(error)


if __name__ == "__main__":
    main()