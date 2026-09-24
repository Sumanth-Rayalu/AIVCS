import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aivcs.branches import create_branch, switch_branch
from aivcs.commits import create_commit
from aivcs.config import set_config
from aivcs.remote import build_push_payload
from aivcs.repository import init_repository
from aivcs.staging import add


class RemotePayloadTests(unittest.TestCase):
    def test_push_payload_matches_repository_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as config_dir:
            root = Path(directory)
            config_path = Path(config_dir) / "config.json"
            with patch.dict(os.environ, {"AIVCS_CONFIG": str(config_path)}):
                set_config("username", "username")
                set_config("password", "password")
                set_config("email", "user@example.com")
                (root / "Hello.txt").write_bytes(b"hello\n")
                init_repository(root)
                add(root, ["Hello.txt"])
                commit = create_commit(root, "initial commit")

                payload = build_push_payload(root, "demo")

        repository = payload["repository"]
        branch = repository["branches"][0]
        stored_commit = branch["commits"][0]
        self.assertEqual(payload["username"], "username")
        self.assertEqual(repository["repositoryId"], "demo")
        self.assertEqual(stored_commit["commitId"], commit["id"])
        self.assertEqual(stored_commit["fileDetails"][0]["filename"], "Hello.txt")
        self.assertEqual(stored_commit["fileDetails"][0]["fileextension"], ".txt")
        self.assertEqual(stored_commit["fileDetails"][0]["content"], "hello\n")

    def test_push_payload_can_target_a_different_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as config_dir:
            root = Path(directory)
            config_path = Path(config_dir) / "config.json"
            with patch.dict(os.environ, {"AIVCS_CONFIG": str(config_path)}):
                set_config("username", "username")
                set_config("password", "password")
                (root / "main.txt").write_text("main\n", encoding="utf-8")
                init_repository(root)
                add(root, ["main.txt"])
                main_commit = create_commit(root, "initial main")
                create_branch(root, "feature")
                switch_branch(root, "feature")
                (root / "feature.txt").write_text("feature\n", encoding="utf-8")
                add(root, ["feature.txt"])
                create_commit(root, "add feature")

                main_payload = build_push_payload(root, "demo", "main")
                feature_payload = build_push_payload(root, "demo", "feature")

        self.assertEqual(main_payload["repository"]["branches"][0]["branchName"], "main")
        self.assertEqual(main_payload["repository"]["branches"][0]["commits"][-1]["commitId"], main_commit["id"])
        self.assertEqual(feature_payload["repository"]["branches"][0]["branchName"], "feature")


if __name__ == "__main__":
    unittest.main()