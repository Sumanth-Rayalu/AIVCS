from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .hashing import hash_bytes, hash_file
from .repository import COMMITS_DIR, OBJECTS_DIR, aivcs_path, head_id, read_json, update_head, write_json
from .staging import committed_snapshot, load_index, save_index, working_snapshot


def create_commit(root: Path, message: str, author: str = "AIVCS User") -> dict:
    index = load_index(root)
    if not index:
        raise RuntimeError("Nothing staged to commit.")
    working = working_snapshot(root)
    for path, digest in index.items():
        if digest is not None and working.get(path) != digest:
            raise RuntimeError("Working tree changed after staging: " + path)
        if digest is None and path in working:
            raise RuntimeError("Working tree changed after staging: " + path)

    parent = head_id(root)
    previous = committed_snapshot(root)
    snapshot = dict(previous)
    for path, digest in index.items():
        if digest is None:
            snapshot.pop(path, None)
        else:
            snapshot[path] = digest
            source = root / path
            destination = aivcs_path(root, OBJECTS_DIR, digest)
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = f"{parent or ''}{message}{author}{timestamp}{sorted(snapshot.items())}".encode()
    commit_id = hashlib.sha256(payload).hexdigest()[:12]
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


def history(root: Path, start: str | None = None) -> list[dict]:
    commits: list[dict] = []
    current = start or head_id(root)
    while current:
        commit = read_commit(root, current)
        commits.append(commit)
        current = commit.get("parent")
    return commits


def copy_reachable_objects(source: Path, destination: Path, heads: list[str]) -> None:
    source_meta = source / ".aivcs" if (source / ".aivcs").is_dir() else source
    destination.mkdir(parents=True, exist_ok=True)
    for head in heads:
        current = head
        while current:
            commit_path = source_meta / COMMITS_DIR / f"{current}.json"
            if not commit_path.exists():
                raise RuntimeError(f"Commit object not found: {current}")
            commit = read_json(commit_path, {})
            write_json(destination / COMMITS_DIR / f"{commit['id']}.json", commit)
            for digest in commit.get("files", {}).values():
                if digest:
                    src = source_meta / OBJECTS_DIR / digest
                    dst = destination / OBJECTS_DIR / digest
                    if src.exists() and not dst.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(src.read_bytes())
            current = commit.get("parent")
