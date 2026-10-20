"""Regression checks for ai_coding helpers."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_coding


class AiCodingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.temp_path = Path(self.temp.name)
        self.environment = patch.dict(
            os.environ,
            {
                "RUNNER_TEMP": self.temp.name,
                "ISSUE_NUMBER": "42",
                "ISSUE_TITLE": "境界値を確認",
                "ISSUE_BODY": "0件の場合は？",
                "OPENAI_API_KEY": "test-secret-token",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def write_events(self, text: str) -> None:
        events = [
            {"type": "agent_event", "event": {"type": "content_end", "text": "途中経過"}},
            {"type": "agent_event", "event": {"type": "done", "reason": "completed", "text": text}},
            {"type": "run_result", "finishReason": "completed", "text": text},
        ]
        (self.temp_path / "ai-coding-events.ndjson").write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events),
            encoding="utf-8",
        )

    def test_extract_rejects_github_configuration_changes(self) -> None:
        self.write_events("変更内容: 実装しました。")
        with patch.object(
            ai_coding, "changed_paths", return_value=[Path(".github/workflows/ai-coding.yml")]
        ):
            with self.assertRaises(SystemExit):
                ai_coding.extract()
        self.assertFalse((self.temp_path / "ai-coding-pr-body.md").exists())

    def test_extract_rejects_token_in_summary(self) -> None:
        self.write_events("test-secret-token")
        with self.assertRaises(SystemExit):
            ai_coding.extract()
        self.assertFalse((self.temp_path / "ai-coding-pr-body.md").exists())

    def test_prepare_and_extract_create_reviewable_pr_body(self) -> None:
        ai_coding.prepare()
        prompt = (self.temp_path / "ai-coding-prompt.txt").read_text(encoding="utf-8")
        self.assertIn('"number": "42"', prompt)
        self.write_events("変更内容: 境界値を修正。\n確認: テスト成功。")
        with patch.object(ai_coding, "changed_paths", return_value=[]):
            ai_coding.extract()
        body = (self.temp_path / "ai-coding-pr-body.md").read_text(encoding="utf-8")
        self.assertIn("対象issue: #42", body)
        self.assertIn("確認: テスト成功。", body)


if __name__ == "__main__":
    unittest.main()