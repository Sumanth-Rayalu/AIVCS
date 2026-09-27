import io
import os
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from aivcs.branches import create_branch, switch_branch
from aivcs.commits import create_commit
from aivcs.config import set_config
from aivcs.hashing import hash_bytes
from aivcs.remote import _request, build_push_payload, clone, pull
from aivcs.repository import BRANCHES_DIR, HEAD_FILE, aivcs_path, init_repository
from aivcs.staging import add


class RemotePayloadTests(unittest.TestCase):
    def test_account_not_found_error_is_actionable_and_hides_raw_json(self) -> None:
        error = HTTPError(
            "http://localhost:8000/repositories/demo/push",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"detail":"AIVCS account not found"}'),
        )

        with patch("aivcs.remote.urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as raised:
                _request("POST", "http://localhost:8000/repositories/demo/push", {})

        message = str(raised.exception)
        self.assertIn("No AIVCS account matches", message)
        self.assertIn("aivcs config username", message)
        self.assertIn("aivcs config email", message)
        self.assertNotIn('{"detail"', message)

    def test_push_payload_matches_repository_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as config_dir:
            root = Path(directory)
            config_path = Path(config_dir) / "config.json"
            with patch.dict(os.environ, {"AIVCS_CONFIG": str(config_path)}):
                set_config("username", "username")
                set_config("email", "user@example.com")
                set_config("repo", "demo")
                (root / "Hello.txt").write_bytes(b"hello\n")
                init_repository(root)
                add(root, ["Hello.txt"])
                commit = create_commit(root, "initial commit")

                payload = build_push_payload(root, "demo")

        repository = payload["repository"]
        branch = repository["branches"][0]
        stored_commit = branch["commits"][0]
        self.assertEqual(payload["username"], "username")
        self.assertEqual(payload["email"], "user@example.com")
        self.assertNotIn("password", payload)
        self.assertEqual(repository["repositoryId"], "demo")
        self.assertEqual(stored_commit["commitId"], commit["id"])
        self.assertEqual(stored_commit["fileDetails"][0]["filename"], "Hello")
        self.assertEqual(stored_commit["fileDetails"][0]["fileextension"], ".txt")
        self.assertEqual(stored_commit["fileDetails"][0]["content"], "hello\n")

    def test_push_payload_can_target_a_different_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as config_dir:
            root = Path(directory)
            config_path = Path(config_dir) / "config.json"
            with patch.dict(os.environ, {"AIVCS_CONFIG": str(config_path)}):
                set_config("username", "username")
                set_config("email", "user@example.com")
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


class RemoteCheckoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        self.config_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.config_dir.cleanup)
        self.config_path = Path(self.config_dir.name) / "config.json"
        self.config_patch = patch.dict(os.environ, {"AIVCS_CONFIG": str(self.config_path)})
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        set_config("username", "bob")
        set_config("email", "bob@example.com")
        set_config("repo", "demo")

    @staticmethod
    def _commit(commit_id: str, parent: str | None, files: dict[str, str]) -> dict:
        details = [
            {
                "filename": filename,
                "fileextension": Path(filename).suffix,
                "content": content,
                "contentHash": hash_bytes(content.encode("utf-8")),
            }
            for filename, content in files.items()
        ]
        return {
            "commitId": commit_id,
            "message": f"commit {commit_id}",
            "timestamp": "2026-09-27T10:00:00+00:00",
            "author": "bob",
            "parent": parent,
            "fileDetails": details,
        }

    def _remote_branches(self, include_update: bool = True) -> list[dict]:
        first = self._commit("commit-1", None, {"README.md": "base\n"})
        second = self._commit(
            "commit-2", "commit-1", {"README.md": "base\n", "main.py": "print('main')\n"}
        )
        feature = self._commit(
            "feature-1", "commit-1", {"README.md": "base\n", "feature.py": "print('feature')\n"}
        )
        main_commits = [first, second] if include_update else [first]
        return [
            {
                "branchName": "main",
                "headCommitId": main_commits[-1]["commitId"],
                "commits": main_commits,
            },
            {
                "branchName": "feature",
                "headCommitId": "feature-1",
                "commits": [first, feature],
            },
        ]

    def test_clone_imports_all_branches_and_checks_out_main(self) -> None:
        response = {"repositoryId": "demo", "branches": self._remote_branches()}
        with patch("aivcs.remote._fetch_repository", return_value=response):
            clone("demo", self.root / "clone")

        destination = self.root / "clone"
        self.assertEqual(
            (aivcs_path(destination, BRANCHES_DIR, "feature")).read_text(encoding="utf-8").strip(),
            "feature-1",
        )
        self.assertEqual(
            (aivcs_path(destination, HEAD_FILE)).read_text(encoding="utf-8").strip(),
            "ref: refs/heads/main",
        )
        self.assertTrue((destination / "main.py").is_file())
        self.assertFalse((destination / "feature.py").exists())

    def test_pull_fast_forwards_current_branch(self) -> None:
        destination = self.root / "clone"
        initial = {"repositoryId": "demo", "branches": self._remote_branches(include_update=False)}
        updated = {"repositoryId": "demo", "branches": self._remote_branches()}
        with patch("aivcs.remote._fetch_repository", return_value=initial):
            clone("demo", destination)
        with patch("aivcs.remote._fetch_repository", return_value=updated):
            result = pull(destination, "demo")

        self.assertIn("Pulled demo (main)", result["message"])
        self.assertEqual((destination / "main.py").read_text(encoding="utf-8"), "print('main')\n")
        self.assertEqual(aivcs_path(destination, BRANCHES_DIR, "main").read_text(encoding="utf-8").strip(), "commit-2")

    def test_pull_refuses_uncommitted_worktree_changes(self) -> None:
        destination = self.root / "clone"
        response = {"repositoryId": "demo", "branches": self._remote_branches(include_update=False)}
        with patch("aivcs.remote._fetch_repository", return_value=response):
            clone("demo", destination)
        (destination / "README.md").write_text("local edit\n", encoding="utf-8")

        with patch("aivcs.remote._fetch_repository", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "uncommitted changes"):
                pull(destination, "demo")


if __name__ == "__main__":
    unittest.main()