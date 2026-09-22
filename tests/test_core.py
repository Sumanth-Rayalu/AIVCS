import tempfile
import unittest
from pathlib import Path

from aivcs.commits import create_commit, history
from aivcs.diff import build_diff
from aivcs.repository import init_repository
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


if __name__ == "__main__":
    unittest.main()
# Phase 1 modification test