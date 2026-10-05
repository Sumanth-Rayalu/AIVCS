import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aivcs.ai.agent import run_ai_autonomous, run_ai_commit, validate_action_plan
from aivcs.ai.approval import (
    confirm_commit,
    confirm_dangerous_operation,
    confirm_pull,
    confirm_push,
)
from aivcs.ai.context import build_commit_context
from aivcs.ai.engine import generate_commit_message
from aivcs.commits import create_commit, history
from aivcs.repository import init_repository
from aivcs.staging import add


class TestAiApproval(unittest.TestCase):
    def test_confirm_commit_affirmative(self):
        for ans in ["", "y", "Y", "yes", "YES"]:
            self.assertTrue(confirm_commit(input_fn=lambda _: ans))

    def test_confirm_commit_negative(self):
        for ans in ["n", "no", "cancel", "anything"]:
            self.assertFalse(confirm_commit(input_fn=lambda _: ans))

    def test_confirm_commit_eof(self):
        def raise_eof(_):
            raise EOFError
        self.assertFalse(confirm_commit(input_fn=raise_eof))


class TestAiContext(unittest.TestCase):
    def test_empty_context(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            ctx = build_commit_context(root)
            self.assertEqual(ctx["staged_files"], [])
            self.assertEqual(ctx["staged_diff"], "")

    def test_context_with_staged_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / "sample.py").write_text("def hello(): pass\n", encoding="utf-8")
            add(root, ["sample.py"])

            ctx = build_commit_context(root)
            self.assertEqual(ctx["branch"], "main")
            self.assertEqual(len(ctx["staged_files"]), 1)
            self.assertEqual(ctx["staged_files"][0]["path"], "sample.py")
            self.assertIn("def hello(): pass", ctx["staged_files"][0]["content"])
            self.assertIn("+def hello(): pass", ctx["staged_diff"])

    def test_context_with_binary_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / "image.bin").write_bytes(b"\x00\x01\x02\x03")
            add(root, ["image.bin"])

            ctx = build_commit_context(root)
            self.assertEqual(len(ctx["staged_files"]), 1)
            self.assertEqual(ctx["staged_files"][0]["content"], "[binary file content omitted]")


class TestAiEngine(unittest.TestCase):
    @patch("aivcs.ai.engine._find_project_env", return_value=None)
    def test_missing_api_key_raises(self, _mock_find):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(RuntimeError) as ctx:
                    generate_commit_message({"staged_files": []}, root)
                self.assertIn("GEMINI_API_KEY is not set", str(ctx.exception))

    def test_load_from_project_env(self):
        with tempfile.TemporaryDirectory() as proj_td, tempfile.TemporaryDirectory() as repo_td:
            proj_root = Path(proj_td)
            repo_root = Path(repo_td)
            (proj_root / ".env").write_text("GEMINI_API_KEY=test-proj-key\nGEMINI_MODEL=gemini-3.8-flash\n", encoding="utf-8")
            
            with patch("aivcs.ai.engine._find_project_env", return_value=proj_root / ".env"):
                with patch.dict(os.environ, {}, clear=True):
                    from aivcs.ai.engine import _load_api_credentials
                    key, model = _load_api_credentials(repo_root)
                    self.assertEqual(key, "test-proj-key")
                    self.assertEqual(model, "gemini-3.8-flash")

    @patch("aivcs.ai.engine._create_client")
    def test_generate_commit_message_success(self, mock_create):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "feat(auth): implement user authentication"
        mock_client.models.generate_content.return_value = mock_response
        mock_create.return_value = mock_client

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
                msg = generate_commit_message({"staged_files": []}, root)
                self.assertEqual(msg, "feat(auth): implement user authentication")

    @patch("aivcs.ai.engine._create_client")
    def test_generate_commit_message_strips_backticks(self, mock_create):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "`fix: resolve null pointer in parser`"
        mock_client.models.generate_content.return_value = mock_response
        mock_create.return_value = mock_client

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
                msg = generate_commit_message({"staged_files": []}, root)
                self.assertEqual(msg, "fix: resolve null pointer in parser")

    @patch("aivcs.ai.engine._create_client")
    def test_invalid_commit_format_raises(self, mock_create):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Here is the commit message:\nChanged a file"
        mock_client.models.generate_content.return_value = mock_response
        mock_create.return_value = mock_client

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy-key"}):
                with self.assertRaises(RuntimeError) as ctx:
                    generate_commit_message({"staged_files": []}, root)
                self.assertIn("invalid commit message", str(ctx.exception))


class TestAiAgent(unittest.TestCase):
    def test_no_staged_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            output = []
            res = run_ai_commit(root, output_fn=output.append)
            self.assertIsNone(res)
            self.assertTrue(any("No staged changes to commit." in line for line in output))

    @patch("aivcs.ai.agent.generate_commit_message")
    def test_user_rejection(self, mock_gen):
        mock_gen.return_value = "feat: add feature"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / "test.txt").write_text("content", encoding="utf-8")
            add(root, ["test.txt"])

            output = []
            res = run_ai_commit(root, input_fn=lambda _: "n", output_fn=output.append)
            self.assertIsNone(res)
            self.assertIn("Commit canceled; no commit was created.", output)
            self.assertEqual(len(history(root)), 0)

    @patch("aivcs.ai.agent.generate_commit_message")
    def test_user_approval(self, mock_gen):
        mock_gen.return_value = "feat: add feature"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / "test.txt").write_text("content", encoding="utf-8")
            add(root, ["test.txt"])

            output = []
            commit = run_ai_commit(root, input_fn=lambda _: "y", output_fn=output.append)
            self.assertIsNotNone(commit)
            self.assertEqual(commit["message"], "feat: add feature")
            self.assertEqual(len(history(root)), 1)


class TestAutonomousAiAgent(unittest.TestCase):
    def test_autonomous_clean_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            output = []
            # In clean repo, autonomous agent completes immediately without calling Gemini or user prompt
            res = run_ai_autonomous(root, output_fn=output.append)
            self.assertTrue(res)
            self.assertTrue(any("Repository is clean." in line for line in output))
            self.assertTrue(any("No action is required." in line for line in output))

    @patch("aivcs.ai.agent.generate_text")
    def test_autonomous_normal_workflow_no_confirmation_needed(self, mock_gen):
        mock_gen.return_value = '{"summary": "Update auth logic", "actions": [{"action": "stage", "files": ["auth.py"]}, {"action": "commit", "message": "fix: correct authentication flow"}], "complete": false}'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / "auth.py").write_text("print('auth')\n", encoding="utf-8")

            output = []
            # Normal changes should stage and commit automatically without asking confirmation!
            res = run_ai_autonomous(root, output_fn=output.append)
            self.assertTrue(res)
            self.assertTrue(any("fix: correct authentication flow" in line for line in output))
            commits = history(root)
            self.assertEqual(len(commits), 1)
            self.assertEqual(commits[0]["message"], "fix: correct authentication flow")

    def test_validate_action_plan_filters_sensitive_and_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / ".gitignore").write_text("ignored.txt\n*.log\n", encoding="utf-8")
            (root / ".env").write_text("SECRET=123\n", encoding="utf-8")
            (root / "valid.py").write_text("print(1)\n", encoding="utf-8")
            (root / "ignored.txt").write_text("skip\n", encoding="utf-8")

            plan = {
                "summary": "Staging",
                "actions": [
                    {"action": "stage", "files": [".env", "valid.py", "ignored.txt", ".aivcs/HEAD"]},
                    {"action": "push", "remote": "origin", "branch": "main"},
                ],
            }
            validated = validate_action_plan(plan, {"status": {"staged": [], "modified": [], "deleted": [], "untracked": []}}, root)
            stage_act = next(a for a in validated["actions"] if a["action"] == "stage")
            self.assertEqual(stage_act["files"], ["valid.py"])
            self.assertFalse(stage_act["requires_approval"])

            push_act = next(a for a in validated["actions"] if a["action"] == "push")
            self.assertTrue(push_act["requires_approval"])

    @patch("aivcs.ai.context.get_remote_sync_state", return_value={"is_configured": True, "status": "ahead", "ahead_count": 1, "repo": "origin"})
    @patch("aivcs.ai.agent.generate_text")
    def test_autonomous_push_requires_approval_rejected(self, mock_gen, _mock_remote):
        mock_gen.return_value = '{"summary": "Push commits", "actions": [{"action": "push", "remote": "origin", "branch": "main"}], "complete": false}'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / "file.txt").write_text("data\n", encoding="utf-8")
            add(root, ["file.txt"])
            create_commit(root, "feat: initial commit")

            output = []
            # User rejects push
            res = run_ai_autonomous(root, input_fn=lambda _: "n", output_fn=output.append)
            self.assertTrue(res)
            self.assertTrue(any("Push canceled by user." in line for line in output))

    def test_confirm_dangerous_operation_defaults_to_no(self):
        output = []
        # Pressing Enter on dangerous operation defaults to False
        res = confirm_dangerous_operation("reset", "HEAD~1", "Discards commits", input_fn=lambda _: "", output_fn=output.append)
        self.assertFalse(res)

    @patch("aivcs.ai.agent.generate_text")
    def test_autonomous_post_action_summary_generated(self, mock_gen):
        mock_gen.return_value = '{"summary": "Changes ready", "actions": [{"action": "stage", "files": ["autonomous-test.txt"]}, {"action": "commit", "message": "test: add autonomous test file"}], "complete": false}'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_repository(root)
            (root / "autonomous-test.txt").write_text("Autonomous AIVCS test\n", encoding="utf-8")

            output = []
            res = run_ai_autonomous(root, output_fn=output.append)
            self.assertTrue(res)
            combined_output = "\n".join(output)
            self.assertIn("AI ACTIVITY SUMMARY", combined_output)
            self.assertIn("What I did:", combined_output)
            self.assertIn("What changed:", combined_output)
            self.assertIn("Difference from previous state:", combined_output)
            self.assertIn("Effect:", combined_output)
            self.assertIn("Final state:", combined_output)
            self.assertIn("autonomous-test.txt", combined_output)


