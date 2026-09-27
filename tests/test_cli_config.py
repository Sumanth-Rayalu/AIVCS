import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aivcs import cli
from aivcs.config import load_config, set_config


class ConfigListTests(unittest.TestCase):
    def test_clone_share_url_configures_identity_and_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            with (
                patch.dict(os.environ, {"AIVCS_CONFIG": str(config_path)}),
                patch.object(cli, "clone") as clone,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                set_config("backend_url", "http://backend.example.test")
                cli.command_clone("https://aivcs/bob/alice/demo-repo", None)
                saved_config = load_config()

        self.assertEqual(saved_config["email"], "bob@gmail.com")
        self.assertEqual(saved_config["username"], "alice")
        self.assertEqual(saved_config["repo"], "demo-repo")
        self.assertEqual(saved_config["backend_url"], "http://backend.example.test")
        clone.assert_called_once_with("demo-repo", Path("demo-repo"))

    def test_push_and_pull_default_repository_to_worktree_directory(self) -> None:
        root = Path("/projects/sample-app")
        with (
            patch.object(cli, "find_root", return_value=root),
            patch.object(cli, "remote_config", return_value={"repo": ""}),
            patch.object(cli, "push", return_value={"message": "Pushed"}) as push,
            patch.object(cli, "pull", return_value={"message": "Pulled"}) as pull,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli.command_push(None, None)
            cli.command_pull(None, None)

        push.assert_called_once_with(root, "sample-app", None)
        pull.assert_called_once_with(root, "sample-app", None)

    def test_list_displays_identity_and_repo_without_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            with patch.dict(os.environ, {"AIVCS_CONFIG": str(config_path)}):
                set_config("username", "bob")
                set_config("email", "bob@example.com")
                set_config("repo", "demo")
                set_config("backend_url", "http://localhost:8000")
                set_config("password", "legacy-password")

                output = io.StringIO()
                with (
                    patch.object(sys, "argv", ["aivcs", "config", "--list"]),
                    contextlib.redirect_stdout(output),
                ):
                    cli.main()
                saved_config = load_config()

        result = output.getvalue()
        self.assertIn("Username: bob", result)
        self.assertIn("Email: bob@example.com", result)
        self.assertNotIn("Repository:", result)
        self.assertNotIn("Backend URL:", result)
        self.assertNotIn("Password:", result)
        self.assertNotIn("legacy-password", result)
        self.assertEqual(saved_config["repo"], "demo")
        self.assertEqual(saved_config["backend_url"], "http://localhost:8000")


if __name__ == "__main__":
    unittest.main()