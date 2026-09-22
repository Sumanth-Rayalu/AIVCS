from __future__ import annotations

import json
from pathlib import Path

AIVCS_DIR = ".aivcs"
OBJECTS_DIR = "objects"
COMMITS_DIR = "commits"
HEAD_FILE = "HEAD"
BRANCHES_DIR = "refs/heads"
INDEX_FILE = "index.json"


def find_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / AIVCS_DIR).is_dir():
            return candidate
    raise RuntimeError("Not an AIVCS repository (or any parent directory).")


def aivcs_path(root: Path, *parts: str) -> Path:
    return root / AIVCS_DIR / Path(*parts)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def init_repository(root: Path) -> None:
    metadata = root / AIVCS_DIR
    if metadata.exists():
        raise RuntimeError("AIVCS repository already exists.")
    (metadata / OBJECTS_DIR).mkdir(parents=True)
    (metadata / COMMITS_DIR).mkdir()
    (metadata / BRANCHES_DIR).mkdir(parents=True)
    (metadata / INDEX_FILE).write_text("{}\n", encoding="utf-8")
    (metadata / HEAD_FILE).write_text("ref: refs/heads/main\n", encoding="utf-8")
    (metadata / BRANCHES_DIR / "main").write_text("\n", encoding="utf-8")


def head_id(root: Path) -> str | None:
    head = aivcs_path(root, HEAD_FILE).read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = head[5:]
        value = aivcs_path(root, ref).read_text(encoding="utf-8").strip()
        return value or None
    return head or None


def update_head(root: Path, commit_id: str) -> None:
    head = aivcs_path(root, HEAD_FILE).read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        aivcs_path(root, head[5:]).write_text(commit_id + "\n", encoding="utf-8")
    else:
        aivcs_path(root, HEAD_FILE).write_text(commit_id + "\n", encoding="utf-8")
