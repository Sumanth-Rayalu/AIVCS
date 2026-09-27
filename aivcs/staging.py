from __future__ import annotations

import os
from pathlib import Path

from .hashing import hash_file
from .repository import INDEX_FILE, aivcs_path, head_id, read_json, write_json

IGNORED_NAMES = {".aivcs", ".git", ".env", "__pycache__", "node_modules", "dist"}


def relative_files(root: Path) -> list[str]:
    paths: list[str] = []
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in IGNORED_NAMES]
        for name in files:
            if name in IGNORED_NAMES:
                continue
            path = Path(current) / name
            paths.append(path.relative_to(root).as_posix())
    return sorted(paths)


def working_snapshot(root: Path) -> dict[str, str]:
    return {path: hash_file(root / path) for path in relative_files(root)}


def load_index(root: Path) -> dict[str, str | None]:
    return read_json(aivcs_path(root, INDEX_FILE), {})  # type: ignore[return-value]


def save_index(root: Path, index: dict[str, str | None]) -> None:
    write_json(aivcs_path(root, INDEX_FILE), index)


def add(root: Path, requested: list[str]) -> list[str]:
    root = root.resolve()
    index = load_index(root)
    paths: set[str] = set()
    for requested_path in requested:
        candidate = (root / requested_path).resolve()
        if candidate == root or candidate.is_dir():
            if root not in candidate.parents and candidate != root:
                raise FileNotFoundError(f"Path is outside repository: {requested_path}")
            for path in relative_files(candidate):
                paths.add(path if candidate == root else (candidate.relative_to(root) / path).as_posix())
        elif candidate.is_file() and root in candidate.parents:
            paths.add(candidate.relative_to(root).as_posix())
        else:
            raise FileNotFoundError(f"Path does not exist: {requested_path}")
    for path in paths:
        index[path] = hash_file(root / path)
    committed = committed_snapshot(root)
    for path in list(index):
        if path in committed and path not in working_snapshot(root) and any((root / requested_path).resolve() == root or (root / requested_path).resolve().is_dir() for requested_path in requested):
            index[path] = None
    save_index(root, index)
    return sorted(paths)


def stage_all(root: Path) -> list[str]:
    committed = committed_snapshot(root)
    working = working_snapshot(root)
    index = load_index(root)
    index.update(working)
    for path in committed:
        if path not in working:
            index[path] = None
    save_index(root, index)
    return sorted(index)


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
    modified = sorted(
        path for path in working
        if (path in staged and working[path] != staged[path])
        or (path not in staged and path in committed and working[path] != committed[path])
    )
    deleted = sorted(path for path in set(committed) | set(staged) if path not in working)
    untracked = sorted(path for path in working if path not in committed and path not in staged)
    return {"staged": staged_paths, "modified": modified, "deleted": deleted, "untracked": untracked}
