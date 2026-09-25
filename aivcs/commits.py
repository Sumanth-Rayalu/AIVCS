from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .hashing import hash_file
from .repository import COMMITS_DIR, OBJECTS_DIR, aivcs_path, head_id, read_json, update_head, write_json
from .staging import load_index, save_index


def create_commit(root: Path, message: str, author: str = "AIVCS User") -> dict:
    index = load_index(root)
    if not index:
        raise RuntimeError("Nothing staged to commit.")
    changed_after_staging = [path for path, digest in index.items() if not (root / path).exists() or hash_file(root / path) != digest]
    if changed_after_staging:
        raise RuntimeError("Working tree changed after staging: " + ", ".join(sorted(changed_after_staging)))
    parent = head_id(root)
    parent_files = read_commit(root, parent).get("files", {}) if parent else {}
    snapshot = {**parent_files, **index}
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = f"{parent or ''}{message}{timestamp}{sorted(snapshot.items())}".encode()
    commit_id = hashlib.sha256(payload).hexdigest()[:12]
    for path, digest in index.items():
        source = root / path
        if not source.exists():
            continue
        destination = aivcs_path(root, OBJECTS_DIR, digest)
        if not destination.exists():
            destination.write_bytes(source.read_bytes())
    commit = {"id": commit_id, "message": message, "timestamp": timestamp, "author": author, "parent": parent, "files": snapshot}
    write_json(aivcs_path(root, COMMITS_DIR, f"{commit_id}.json"), commit)
    update_head(root, commit_id)
    save_index(root, {})
    return commit


def read_commit(root: Path, commit_id: str) -> dict:
    path = aivcs_path(root, COMMITS_DIR, f"{commit_id}.json")
    if not path.exists():
        raise FileNotFoundError(f"Commit not found: {commit_id}")
    return read_json(path, {})  # type: ignore[return-value]


def history(root: Path, commit_id: str | None = None) -> list[dict]:
    commits: list[dict] = []
    current = commit_id if commit_id is not None else head_id(root)
    while current:
        commit = read_commit(root, current)
        commits.append(commit)
        current = commit.get("parent")
    return commits
