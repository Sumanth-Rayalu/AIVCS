from __future__ import annotations

import difflib
from pathlib import Path

from .repository import aivcs_path
from .staging import committed_snapshot, load_index, working_snapshot


def object_text(root: Path, digest: str | None) -> str:
    if not digest:
        return ""
    path = aivcs_path(root, "objects", digest)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_diff(root: Path, staged: bool = False) -> str:
    before = committed_snapshot(root)
    after = load_index(root) if staged else working_snapshot(root)
    paths = sorted(set(before) | set(after))
    chunks: list[str] = []
    for path in paths:
        old = object_text(root, before.get(path)).splitlines(keepends=True)
        if staged:
            new = object_text(root, after.get(path)).splitlines(keepends=True)
        else:
            file_path = root / path
            new = file_path.read_text(encoding="utf-8").splitlines(keepends=True) if file_path.exists() else []
        if old == new:
            continue
        chunks.extend(difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}"))
    return "".join(chunks)
