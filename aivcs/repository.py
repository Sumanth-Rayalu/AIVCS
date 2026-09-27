from __future__ import annotations

import json
from pathlib import Path

AIVCS_DIR = ".aivcs"
OBJECTS_DIR = "objects"
COMMITS_DIR = "commits"
HEAD_FILE = "HEAD"
BRANCHES_DIR = "refs/heads"
REMOTES_DIR = "refs/remotes"
INDEX_FILE = "index.json"
CONFIG_FILE = "config.json"


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
    root = root.resolve()
    metadata = root / AIVCS_DIR
    if metadata.exists():
        raise RuntimeError("AIVCS repository already exists.")
    (metadata / OBJECTS_DIR).mkdir(parents=True)
    (metadata / COMMITS_DIR).mkdir()
    (metadata / BRANCHES_DIR).mkdir(parents=True)
    (metadata / REMOTES_DIR).mkdir(parents=True)
    (metadata / INDEX_FILE).write_text("{}\n", encoding="utf-8")
    (metadata / HEAD_FILE).write_text("ref: refs/heads/main\n", encoding="utf-8")
    (metadata / BRANCHES_DIR / "main").write_text("\n", encoding="utf-8")
    write_json(metadata / CONFIG_FILE, {"repository": {"name": root.name}})


def current_branch(root: Path) -> str | None:
    head = aivcs_path(root, HEAD_FILE).read_text(encoding="utf-8").strip()
    if head.startswith("ref: refs/heads/"):
        return head[len("ref: refs/heads/"):]
    return None


def branch_ref_path(root: Path, name: str) -> Path:
    if not name or name.startswith("/") or ".." in Path(name).parts:
        raise RuntimeError("Invalid branch name.")
    return aivcs_path(root, BRANCHES_DIR, *Path(name).parts)


def list_branches(root: Path) -> list[str]:
    base = aivcs_path(root, BRANCHES_DIR)
    if not base.exists():
        return []
    return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file())


def head_id(root: Path) -> str | None:
    head = aivcs_path(root, HEAD_FILE).read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = head[5:]
        value = aivcs_path(root, ref).read_text(encoding="utf-8").strip() if aivcs_path(root, ref).exists() else ""
        return value or None
    return head or None


def branch_id(root: Path, name: str) -> str | None:
    path = branch_ref_path(root, name)
    value = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    return value or None


def update_head(root: Path, commit_id: str) -> None:
    head = aivcs_path(root, HEAD_FILE).read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        path = aivcs_path(root, head[5:])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(commit_id + "\n", encoding="utf-8")
    else:
        aivcs_path(root, HEAD_FILE).write_text(commit_id + "\n", encoding="utf-8")


def create_branch(root: Path, name: str, start: str | None = None) -> None:
    path = branch_ref_path(root, name)
    if path.exists():
        raise RuntimeError(f"Branch already exists: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((start if start is not None else (head_id(root) or "")) + "\n", encoding="utf-8")


def checkout_branch(root: Path, name: str, force: bool = False) -> None:
    from .staging import load_index, status, working_snapshot
    from .commits import read_commit
    if name not in list_branches(root):
        raise RuntimeError(f"Branch not found: {name}")
    changes = status(root)
    if any(changes.values()) and not force:
        raise RuntimeError("Cannot checkout with uncommitted changes.")
    commit_id = branch_id(root, name)
    if commit_id:
        commit = read_commit(root, commit_id)
        target = commit.get("files", {})
        current = working_snapshot(root)
        for path in current:
            if path not in target:
                (root / path).unlink(missing_ok=True)
        for path, digest in target.items():
            source = aivcs_path(root, OBJECTS_DIR, digest)
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    aivcs_path(root, HEAD_FILE).write_text(f"ref: refs/heads/{name}\n", encoding="utf-8")
    load_index(root)


def set_config(root: Path, key: str, value: object) -> None:
    config = read_json(aivcs_path(root, CONFIG_FILE), {})
    config[key] = value
    write_json(aivcs_path(root, CONFIG_FILE), config)


def get_config(root: Path, key: str, default: object = None) -> object:
    config = read_json(aivcs_path(root, CONFIG_FILE), {})
    return config.get(key, default)
