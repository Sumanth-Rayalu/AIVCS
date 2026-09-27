import tempfile
import unittest
from pathlib import Path

from aivcs.commits import create_commit, history
from aivcs.diff import build_diff
from aivcs.remotes import add_remote, pull, push
from aivcs.repository import find_root, init_repository
from aivcs.staging import add, status


class CoreWorkflowTests(unittest.TestCase):
    def test_nested_file_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text('print("one")\n', encoding="utf-8")
            init_repository(root)

            self.assertEqual(add(root, ["src"]), ["src/app.py"])
            first = create_commit(root, "feat: initialize app")
            self.assertEqual(first["files"], {"src/app.py": first["files"]["src/app.py"]})

            (root / "src" / "app.py").write_text('print("two")\n', encoding="utf-8")
            self.assertEqual(status(root)["modified"], ["src/app.py"])
            self.assertIn('-print("one")', build_diff(root))

            add(root, ["src/app.py"])
            second = create_commit(root, "fix: update output")
            self.assertEqual(len(history(root)), 2)
            self.assertEqual(second["parent"], first["id"])
            self.assertFalse(status(root)["staged"])

    def test_nested_discovery_deletion_and_staged_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("one\n", encoding="utf-8")
            init_repository(root)
            add(root, ["README.md"])
            first = create_commit(root, "docs: add readme")
            (root / "README.md").write_text("two\n", encoding="utf-8")
            self.assertIn("-one", build_diff(root))
            add(root, ["README.md"])
            self.assertIn("+two", build_diff(root, staged=True))
            (root / "README.md").unlink()
            add(root, ["."])
            second = create_commit(root, "docs: remove readme")
            self.assertEqual(status(root), {"staged": [], "modified": [], "deleted": [], "untracked": []})
            self.assertEqual(second["parent"], first["id"])

            nested = root / "src" / "components"
            nested.mkdir(parents=True)
            self.assertTrue(find_root(nested).samefile(root))

    def test_add_dot_synchronizes_deleted_and_ignored_index_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            (root / "generated.txt").write_text("generated\n", encoding="utf-8")
            init_repository(root)
            add(root, ["tracked.txt", "generated.txt"])
            create_commit(root, "feat: add files")

            (root / "generated.txt").write_text("generated again\n", encoding="utf-8")
            add(root, ["generated.txt"])
            (root / ".gitignore").write_text("generated.txt\n", encoding="utf-8")
            (root / "tracked.txt").unlink()
            add(root, ["."])

            result = status(root)
            self.assertEqual(result["staged"], [".gitignore", "tracked.txt"])
            self.assertEqual(result["deleted"], [])
            self.assertNotIn("generated.txt", result["staged"])
            commit = create_commit(root, "fix: synchronize index")
            self.assertIsNone(commit["files"].get("tracked.txt"))
            self.assertEqual(status(root)["deleted"], [])

    def test_local_remote_push_and_pull(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            local = base / "local"
            remote = base / "remote"
            local.mkdir()
            init_repository(local)
            (local / "app.py").write_text("print('one')\n", encoding="utf-8")
            add(local, ["app.py"])
            commit = create_commit(local, "feat: add app")
            add_remote(local, "origin", str(remote))
            self.assertEqual(push(local)["remote"], "origin")

            clone = base / "clone"
            clone.mkdir()
            init_repository(clone)
            add_remote(clone, "origin", str(remote))
            result = pull(clone)
            self.assertEqual(result["remote"], "origin")
            self.assertEqual((clone / "app.py").read_text(encoding="utf-8"), "print('one')\n")
            self.assertEqual(history(clone)[0]["id"], commit["id"])

    def test_partial_commit_preserves_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.txt").write_text("one\n", encoding="utf-8")
            (root / "two.txt").write_text("two\n", encoding="utf-8")
            init_repository(root)
            add(root, ["."])
            create_commit(root, "feat: add files")
            (root / "one.txt").write_text("updated\n", encoding="utf-8")
            add(root, ["one.txt"])
            commit = create_commit(root, "fix: update one")
            self.assertEqual(set(commit["files"]), {"one.txt", "two.txt"})
            self.assertEqual(status(root), {"staged": [], "modified": [], "deleted": [], "untracked": []})


if __name__ == "__main__":
    unittest.main()
# Phase 1 modification test