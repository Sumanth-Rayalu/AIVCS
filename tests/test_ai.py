import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aivcs.ai.agent import run_ai_commit
from aivcs.ai.approval import confirm_commit
from aivcs.ai.context import build_commit_context
from aivcs.ai.engine import generate_commit_message
from aivcs.commits import history
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
