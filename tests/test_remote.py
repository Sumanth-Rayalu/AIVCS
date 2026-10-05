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
from aivcs.remote import _request, build_push_payload, clone, pull, push
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


class TextAndBinaryTransportTests(unittest.TestCase):
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
        set_config("username", "testuser")
        set_config("email", "testuser@example.com")
        set_config("repo", "demo")

    def test_push_utf8_txt_file(self) -> None:
        file_path = self.root / "autonomous-test.txt"
        expected_bytes = b"Autonomous AIVCS test\n"
        file_path.write_bytes(expected_bytes)
        init_repository(self.root)
        add(self.root, ["autonomous-test.txt"])
        create_commit(self.root, "test: add autonomous test file")

        payload = build_push_payload(self.root, "demo")
        file_details = payload["repository"]["branches"][0]["commits"][0]["fileDetails"][0]

        self.assertEqual(file_details["path"], "autonomous-test.txt")
        self.assertFalse(file_details["is_binary"])
        self.assertEqual(file_details["encoding"], "utf-8")
        self.assertEqual(file_details["content"], "Autonomous AIVCS test\n")
        self.assertEqual(file_details["content"].encode("utf-8"), expected_bytes)

    def test_push_python_source_file(self) -> None:
        file_path = self.root / "module.py"
        expected_bytes = b"def main():\n    return 42\n"
        file_path.write_bytes(expected_bytes)
        init_repository(self.root)
        add(self.root, ["module.py"])
        create_commit(self.root, "feat: add python module")

        payload = build_push_payload(self.root, "demo")
        file_details = payload["repository"]["branches"][0]["commits"][0]["fileDetails"][0]

        self.assertEqual(file_details["path"], "module.py")
        self.assertFalse(file_details["is_binary"])
        self.assertEqual(file_details["encoding"], "utf-8")
        self.assertEqual(file_details["content"], "def main():\n    return 42\n")
        self.assertEqual(file_details["content"].encode("utf-8"), expected_bytes)

    def test_push_json_file(self) -> None:
        file_path = self.root / "data.json"
        expected_bytes = b'{\n  "name": "aivcs",\n  "version": 1\n}\n'
        file_path.write_bytes(expected_bytes)
        init_repository(self.root)
        add(self.root, ["data.json"])
        create_commit(self.root, "feat: add config json")

        payload = build_push_payload(self.root, "demo")
        file_details = payload["repository"]["branches"][0]["commits"][0]["fileDetails"][0]

        self.assertEqual(file_details["path"], "data.json")
        self.assertFalse(file_details["is_binary"])
        self.assertEqual(file_details["encoding"], "utf-8")
        self.assertEqual(file_details["content"].encode("utf-8"), expected_bytes)

    def test_push_binary_file(self) -> None:
        file_path = self.root / "image.png"
        expected_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        file_path.write_bytes(expected_bytes)
        init_repository(self.root)
        add(self.root, ["image.png"])
        create_commit(self.root, "feat: add binary image")

        payload = build_push_payload(self.root, "demo")
        file_details = payload["repository"]["branches"][0]["commits"][0]["fileDetails"][0]

        self.assertEqual(file_details["path"], "image.png")
        self.assertTrue(file_details["is_binary"])
        self.assertEqual(file_details["encoding"], "base64")
        import base64
        self.assertEqual(base64.b64decode(file_details["content"]), expected_bytes)

    def test_clone_repository_containing_text_files(self) -> None:
        repo = self.root / "original"
        repo.mkdir()
        txt_path = repo / "notes.txt"
        txt_bytes = b"Hello world, UTF-8 text file!\nWith unicode: \xc3\xa9\xc3\xa0\xc3\xb6\n"
        txt_path.write_bytes(txt_bytes)

        init_repository(repo)
        add(repo, ["notes.txt"])
        create_commit(repo, "commit notes")

        payload = build_push_payload(repo, "demo")
        clone_dest = self.root / "clone_text"

        with patch("aivcs.remote._fetch_repository", return_value=payload["repository"]):
            clone("demo", clone_dest)

        pulled_txt = clone_dest / "notes.txt"
        self.assertTrue(pulled_txt.is_file())
        self.assertEqual(pulled_txt.read_bytes(), txt_bytes)

    def test_clone_repository_containing_binary_files(self) -> None:
        repo = self.root / "original_bin"
        repo.mkdir()
        bin_path = repo / "logo.png"
        bin_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00\xff\xfe\x00\x12\x34\x56\x78\x9a\xbc\xde\xf0"
        bin_path.write_bytes(bin_bytes)

        init_repository(repo)
        add(repo, ["logo.png"])
        create_commit(repo, "commit binary logo")

        payload = build_push_payload(repo, "demo")
        clone_dest = self.root / "clone_bin"

        with patch("aivcs.remote._fetch_repository", return_value=payload["repository"]):
            clone("demo", clone_dest)

        pulled_bin = clone_dest / "logo.png"
        self.assertTrue(pulled_bin.is_file())
        self.assertEqual(pulled_bin.read_bytes(), bin_bytes)

    def test_pull_commit_containing_text_file(self) -> None:
        clone_dest = self.root / "work_pull_text"
        initial_commit = {
            "commitId": "c1",
            "message": "initial",
            "timestamp": "2026-10-05T10:00:00+00:00",
            "author": "testuser",
            "parent": None,
            "fileDetails": [],
        }
        text_bytes = b"Added text file content in pull\n"
        text_commit = {
            "commitId": "c2",
            "message": "add text file",
            "timestamp": "2026-10-05T10:05:00+00:00",
            "author": "testuser",
            "parent": "c1",
            "fileDetails": [
                {
                    "path": "doc.txt",
                    "filename": "doc",
                    "fileextension": ".txt",
                    "content": "Added text file content in pull\n",
                    "contentHash": hash_bytes(text_bytes),
                    "encoding": "utf-8",
                    "is_binary": False,
                }
            ],
        }
        initial_resp = {
            "repositoryId": "demo",
            "branches": [{"branchName": "main", "headCommitId": "c1", "commits": [initial_commit]}],
        }
        updated_resp = {
            "repositoryId": "demo",
            "branches": [{"branchName": "main", "headCommitId": "c2", "commits": [initial_commit, text_commit]}],
        }

        with patch("aivcs.remote._fetch_repository", return_value=initial_resp):
            clone("demo", clone_dest)

        with patch("aivcs.remote._fetch_repository", return_value=updated_resp):
            pull(clone_dest, "demo")

        pulled_doc = clone_dest / "doc.txt"
        self.assertTrue(pulled_doc.is_file())
        self.assertEqual(pulled_doc.read_bytes(), text_bytes)

    def test_pull_commit_containing_binary_file(self) -> None:
        clone_dest = self.root / "work_pull_bin"
        initial_commit = {
            "commitId": "c1",
            "message": "initial",
            "timestamp": "2026-10-05T10:00:00+00:00",
            "author": "testuser",
            "parent": None,
            "fileDetails": [],
        }
        bin_bytes = bytes(range(256))
        import base64
        b64_content = base64.b64encode(bin_bytes).decode("ascii")
        bin_commit = {
            "commitId": "c2",
            "message": "add binary data",
            "timestamp": "2026-10-05T10:05:00+00:00",
            "author": "testuser",
            "parent": "c1",
            "fileDetails": [
                {
                    "path": "data.bin",
                    "filename": "data",
                    "fileextension": ".bin",
                    "content": b64_content,
                    "contentHash": hash_bytes(bin_bytes),
                    "encoding": "base64",
                    "is_binary": True,
                }
            ],
        }
        initial_resp = {
            "repositoryId": "demo",
            "branches": [{"branchName": "main", "headCommitId": "c1", "commits": [initial_commit]}],
        }
        updated_resp = {
            "repositoryId": "demo",
            "branches": [{"branchName": "main", "headCommitId": "c2", "commits": [initial_commit, bin_commit]}],
        }

        with patch("aivcs.remote._fetch_repository", return_value=initial_resp):
            clone("demo", clone_dest)

        with patch("aivcs.remote._fetch_repository", return_value=updated_resp):
            pull(clone_dest, "demo")

        pulled_bin = clone_dest / "data.bin"
        self.assertTrue(pulled_bin.is_file())
        self.assertEqual(pulled_bin.read_bytes(), bin_bytes)

    def test_regression_autonomous_test_txt_push_and_clone(self) -> None:
        txt_path = self.root / "autonomous-test.txt"
        expected_bytes = b"Autonomous AIVCS test"
        txt_path.write_bytes(expected_bytes)

        init_repository(self.root)
        add(self.root, ["autonomous-test.txt"])
        create_commit(self.root, "test: add autonomous test file")

        captured_payload = None

        def fake_request(method, url, payload=None):
            nonlocal captured_payload
            captured_payload = payload
            return {"message": "Pushed successfully."}

        with patch("aivcs.remote._request", side_effect=fake_request):
            res = push(self.root, "demo", "main")
            self.assertEqual(res["message"], "Pushed successfully.")

        self.assertIsNotNone(captured_payload)
        repo_data = captured_payload["repository"]

        clone_dest = self.root / "cloned_autonomous"
        with patch("aivcs.remote._fetch_repository", return_value=repo_data):
            clone("demo", clone_dest)

        cloned_file = clone_dest / "autonomous-test.txt"
        self.assertTrue(cloned_file.is_file())
        self.assertEqual(cloned_file.read_bytes(), expected_bytes)


if __name__ == "__main__":
    unittest.main()