from __future__ import annotations

import difflib
from pathlib import Path

from .hashing import hash_bytes
from .repository import aivcs_path
from .staging import committed_snapshot, load_index, working_snapshot


def object_text(root: Path, digest: str | None) -> str:
    if not digest:
        return ""
    path = aivcs_path(root, "objects", digest)
    if not path.exists():
        return ""
    try:
        raw = path.read_bytes()
        if b"\0" in raw:
            return "[binary content]"
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return "[binary content]"


def build_diff(root: Path, staged: bool = False) -> str:
    before = committed_snapshot(root)
    if staged:
        index = load_index(root)
        paths = sorted(path for path, digest in index.items() if digest != before.get(path))
        after = index
    else:
        after = working_snapshot(root)
        paths = sorted(set(before) | set(after))
    chunks: list[str] = []
    for path in paths:
        old_object = aivcs_path(root, "objects", before[path]) if path in before else None
        old_bytes = old_object.read_bytes() if old_object and old_object.is_file() else b""
        file_path = root / path
        new_bytes = file_path.read_bytes() if path in after and file_path.is_file() else b""
        if staged and path in after and hash_bytes(new_bytes) != after[path]:
            raise RuntimeError(f"Staged file changed after staging: {path}. Stage it again.")
        if old_bytes == new_bytes:
            continue
        try:
            if b"\0" in old_bytes or b"\0" in new_bytes:
                raise UnicodeDecodeError("utf-8", b"\0", 0, 1, "binary file")
            old_text = old_bytes.decode("utf-8")
            new_text = new_bytes.decode("utf-8")
        except UnicodeDecodeError:
            chunks.append(f"Binary file changed: {path}\n")
            continue
        old = old_text.splitlines(keepends=True)
        new = new_text.splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}"))
    return "".join(chunks)
