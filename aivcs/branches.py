from __future__ import annotations

import re
from pathlib import Path

from .repository import BRANCHES_DIR, HEAD_FILE, OBJECTS_DIR, aivcs_path, head_id, read_json
from .staging import load_index, save_index, status

BRANCH_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def current_branch(root: Path) -> str | None:
    head = aivcs_path(root, HEAD_FILE).read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return None
    return head.removeprefix(f"ref: {BRANCHES_DIR}/")


def branch_names(root: Path) -> list[str]:
    return sorted(path.name for path in aivcs_path(root, BRANCHES_DIR).iterdir() if path.is_file())


def create_branch(root: Path, name: str) -> None:
    if not BRANCH_NAME.fullmatch(name):
        raise RuntimeError("Invalid branch name. Use letters, numbers, dots, hyphens, or underscores.")
    reference = aivcs_path(root, BRANCHES_DIR, name)
    if reference.exists():
        raise RuntimeError(f"Branch already exists: {name}")
    reference.write_text((head_id(root) or "") + "\n", encoding="utf-8")


def _require_clean_worktree(root: Path) -> None:
    changes = status(root)
    change_sections = ("staged", "modified", "deleted", "untracked")
    if any(changes[section] for section in change_sections) or load_index(root):
        raise RuntimeError("Cannot switch branches with uncommitted changes.")


def _snapshot(root: Path, commit_id: str | None) -> dict[str, str]:
    if not commit_id:
        return {}
    commit = read_json(aivcs_path(root, "commits", f"{commit_id}.json"), {})
    return commit.get("files", {})  # type: ignore[union-attr,return-value]


def switch_branch(root: Path, name: str) -> None:
    target_ref = aivcs_path(root, BRANCHES_DIR, name)
    if not target_ref.is_file():
        raise RuntimeError(f"Branch not found: {name}")
    if current_branch(root) == name:
        print(f"Already on '{name}'.")
        return
    _require_clean_worktree(root)

    old_snapshot = _snapshot(root, head_id(root))
    target_commit = target_ref.read_text(encoding="utf-8").strip() or None
    target_snapshot = _snapshot(root, target_commit)
    for filename in old_snapshot:
        if filename not in target_snapshot:
            path = root / filename
            if path.is_file():
                path.unlink()
    for filename, digest in target_snapshot.items():
        object_path = aivcs_path(root, OBJECTS_DIR, digest)
        if not object_path.is_file():
            raise RuntimeError(f"Missing content object for {filename}: {digest}")
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(object_path.read_bytes())
    aivcs_path(root, HEAD_FILE).write_text(f"ref: {BRANCHES_DIR}/{name}\n", encoding="utf-8")
    save_index(root, {})