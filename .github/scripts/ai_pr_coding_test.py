"""Regression checks for PR-comment Cline helpers."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_pr_coding


class AiPrCodingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {
            "RUNNER_TEMP": self.temp.name,
            "PR_NUMBER": "42",
            "PR_TITLE": "入力検証を追加",
            "PR_BODY": "PR本文",
            "COMMENT_ID": "123",
            "COMMENT_BODY": "@cline 検証を追加して",
            "OPENAI_API_KEY": "test-secret-token",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def events(self, text: str) -> None:
        (self.path / "ai-pr-coding-events.ndjson").write_text(
            json.dumps({"type": "run_result", "finishReason": "completed", "text": text}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_prepare_includes_the_pr_and_comment(self) -> None:
        ai_pr_coding.prepare()
        prompt = (self.path / "ai-pr-coding-prompt.txt").read_text(encoding="utf-8")
        self.assertIn('"number": "42"', prompt)
        self.assertIn("検証を追加して", prompt)

    def test_extract_requires_a_valid_commit_message(self) -> None:
        self.events("変更内容だけです")
        with self.assertRaises(SystemExit):
            ai_pr_coding.extract()

    def test_extract_writes_commit_message_and_report(self) -> None:
        self.events("COMMIT: 入力検証を追加する\n変更内容: 検証を追加しました。")
        with patch.object(ai_pr_coding.subprocess, "check_output", side_effect=[b"", b""]):
            ai_pr_coding.extract()
        self.assertEqual((self.path / "ai-pr-coding-commit-message.txt").read_text(encoding="utf-8"), "入力検証を追加する\n")
        self.assertIn("変更内容", (self.path / "ai-pr-coding-result.md").read_text(encoding="utf-8"))