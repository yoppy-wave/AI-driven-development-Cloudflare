"""The AI question workflow must preserve trusted, ordered issue conversations."""

import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ai-question.yml"


class AiQuestionWorkflowTests(unittest.TestCase):
    def test_comment_mentions_are_limited_to_trusted_issue_users(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("issue_comment:", content)
        self.assertIn("types: [created]", content)
        self.assertIn("github.event.issue.pull_request == null", content)
        self.assertIn("contains(github.event.comment.body, '@cline')", content)
        self.assertIn("github.event.comment.author_association", content)
        self.assertIn("github.event.comment.user.type != 'Bot'", content)
        self.assertIn("github.event.comment.user.login != 'github-actions[bot]'", content)

    def test_question_runs_queue_per_issue_and_keep_the_trigger_comment_id(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: ai-question-${{ github.event.issue.number }}", content)
        self.assertIn("cancel-in-progress: false", content)
        self.assertIn("queue: max", content)
        self.assertIn("gh api --paginate --slurp", content)
        self.assertIn("TRIGGER_COMMENT_ID: ${{ github.event.comment.id || '' }}", content)

    def test_label_trigger_remains_available(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("types: [labeled]", content)
        self.assertIn("github.event.label.name == 'ai-question'", content)


if __name__ == "__main__":
    unittest.main()