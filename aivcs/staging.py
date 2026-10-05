from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from .hashing import hash_file
from .repository import INDEX_FILE, aivcs_path, head_id, read_json, write_json

IGNORED_NAMES = {".aivcs", ".git", ".env", "__pycache__", "node_modules", ".venv", "venv", "dist"}


def load_gitignore(root: Path) -> list[tuple[bool, str]]:
    gi_path = root / ".gitignore"
    if not gi_path.is_file():
        return []
    rules: list[tuple[bool, str]] = []
    try:
        content = gi_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
        rules.append((negated, line))
    return rules


def is_ignored_path(rel_path: str, rules: list[tuple[bool, str]]) -> bool:
    rel_path = rel_path.replace("\\", "/").strip("/")
    parts = rel_path.split("/")
    ignored = False
    for negated, pattern in rules:
        pattern = pattern.strip("/")
        if not pattern:
            continue
        if "/" in pattern:
            if (
                fnmatch.fnmatch(rel_path, pattern)
                or fnmatch.fnmatch(rel_path, f"{pattern}/*")
                or fnmatch.fnmatch(rel_path, f"*/{pattern}")
                or fnmatch.fnmatch(rel_path, f"*/{pattern}/*")
            ):
                ignored = not negated
        else:
            if (
                fnmatch.fnmatch(parts[-1], pattern)
                or any(fnmatch.fnmatch(p, pattern) for p in parts)
                or fnmatch.fnmatch(rel_path, f"*{pattern}*")
            ):
                ignored = not negated
    return ignored


def relative_files(root: Path) -> list[str]:
    root = root.resolve()
    repo_root = root
    for p in [root, *root.parents]:
        if (p / ".aivcs").is_dir():
            repo_root = p
            break

    committed = set(committed_snapshot(repo_root)) if (repo_root / ".aivcs").is_dir() else set()
    staged = set(load_index(repo_root)) if (repo_root / ".aivcs").is_dir() else set()
    tracked = committed | staged
    rules = load_gitignore(repo_root)

    paths: list[str] = []
    for current, directories, files in os.walk(root):
        directories[:] = [
            name
            for name in directories
            if name not in IGNORED_NAMES
            and not is_ignored_path((Path(current) / name).relative_to(repo_root).as_posix(), rules)
        ]
        for name in files:
            path = Path(current) / name
            if name in IGNORED_NAMES:
                continue
            rel_repo = path.relative_to(repo_root).as_posix()
            rel_root = path.relative_to(root).as_posix()
            if rel_repo not in tracked and rules and is_ignored_path(rel_repo, rules):
                continue
            paths.append(rel_root)
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
