from __future__ import annotations

import os
from pathlib import Path

from .hashing import hash_file
from .repository import INDEX_FILE, aivcs_path, head_id, read_json, write_json

IGNORED_NAMES = {".aivcs", ".git", ".env", "__pycache__", "node_modules"}


def relative_files(root: Path) -> list[str]:
    paths: list[str] = []
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in IGNORED_NAMES]
        for name in files:
            path = Path(current) / name
            if name in IGNORED_NAMES:
                continue
            paths.append(path.relative_to(root).as_posix())
    return sorted(paths)


def working_snapshot(root: Path) -> dict[str, str]:
    return {path: hash_file(root / path) for path in relative_files(root)}


def load_index(root: Path) -> dict[str, str]:
    return read_json(aivcs_path(root, INDEX_FILE), {})  # type: ignore[return-value]


def save_index(root: Path, index: dict[str, str]) -> None:
    write_json(aivcs_path(root, INDEX_FILE), index)


def add(root: Path, requested: list[str]) -> list[str]:
    root = root.resolve()
    index = load_index(root)
    paths: set[str] = set()
    for requested_path in requested:
        candidate = (root / requested_path).resolve()
        if candidate == root or candidate.is_dir():
            for path in relative_files(candidate):
                paths.add(path if candidate == root else (candidate.relative_to(root) / path).as_posix())
        elif candidate.is_file() and root in candidate.parents:
            paths.add(candidate.relative_to(root).as_posix())
        else:
            raise FileNotFoundError(f"Path does not exist: {requested_path}")
    for path in paths:
        index[path] = hash_file(root / path)
    save_index(root, index)
    return sorted(paths)


def committed_snapshot(root: Path) -> dict[str, str]:
    commit = head_id(root)
    if not commit:
        return {}
    data = read_json(aivcs_path(root, "commits", f"{commit}.json"), {})
    return data.get("files", {})  # type: ignore[union-attr]


def status(root: Path) -> dict[str, list[str]]:
    staged = load_index(root)
    committed = committed_snapshot(root)
    working = working_snapshot(root)
    staged_paths = sorted(path for path, digest in staged.items() if digest != committed.get(path))
    committed_paths = sorted(committed)
    modified = sorted(
        path for path in working
        if path in staged and working[path] != staged[path]
        or path not in staged and path in committed and working[path] != committed[path]
    )
    deleted = sorted(path for path in set(committed) | set(staged) if path not in working)
    untracked = sorted(path for path in working if path not in committed and path not in staged)
    return {
        "staged": staged_paths,
        "committed": committed_paths,
        "modified": modified,
        "deleted": deleted,
        "untracked": untracked,
    }
