import tempfile
import unittest
from pathlib import Path

from aivcs.branches import create_branch, switch_branch
from aivcs.commits import create_commit, history
from aivcs.diff import build_diff
from aivcs.repository import head_id, init_repository
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
            self.assertEqual(status(root)["committed"], ["src/app.py"])

            (root / "src" / "app.py").write_text('print("two")\n', encoding="utf-8")
            self.assertEqual(status(root)["modified"], ["src/app.py"])
            self.assertIn('-print("one")', build_diff(root))

            add(root, ["src/app.py"])
            second = create_commit(root, "fix: update output")
            self.assertEqual(len(history(root)), 2)
            self.assertEqual(second["parent"], first["id"])
            self.assertFalse(status(root)["staged"])

    def test_switch_recreates_branch_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "shared.txt").write_text("main\n", encoding="utf-8")
            init_repository(root)
            add(root, ["shared.txt"])
            main_commit = create_commit(root, "initial main")
            create_branch(root, "feature")
            switch_branch(root, "feature")

            (root / "feature.txt").write_text("feature\n", encoding="utf-8")
            add(root, ["feature.txt"])
            feature_commit = create_commit(root, "add feature file")
            switch_branch(root, "main")
            self.assertEqual((root / "shared.txt").read_text(encoding="utf-8"), "main\n")
            self.assertFalse((root / "feature.txt").exists())
            self.assertEqual(status(root)["committed"], ["shared.txt"])

            switch_branch(root, "feature")
            self.assertEqual((root / "feature.txt").read_text(encoding="utf-8"), "feature\n")
            self.assertEqual((root / "shared.txt").read_text(encoding="utf-8"), "main\n")
            self.assertEqual(status(root)["committed"], ["feature.txt", "shared.txt"])
            self.assertEqual(head_id(root), feature_commit["id"])
            self.assertNotEqual(main_commit["id"], feature_commit["id"])


if __name__ == "__main__":
    unittest.main()
# Phase 1 modification test