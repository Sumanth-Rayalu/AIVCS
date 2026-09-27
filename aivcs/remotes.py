from __future__ import annotations

import os
import shutil
from pathlib import Path

from .commits import copy_reachable_objects, history, read_commit
from .repository import REMOTES_DIR, aivcs_path, branch_id, current_branch, list_branches, read_json, write_json

REMOTE_FILE = "remotes.json"


def _remote_file(root: Path) -> Path:
    return aivcs_path(root, REMOTE_FILE)


def _load(root: Path) -> dict[str, str]:
    return read_json(_remote_file(root), {})  # type: ignore[return-value]


def _save(root: Path, remotes: dict[str, str]) -> None:
    write_json(_remote_file(root), remotes)


def add_remote(root: Path, name: str, location: str) -> None:
    if not name or any(ch.isspace() for ch in name):
        raise RuntimeError("Invalid remote name.")
    remotes = _load(root)
    remotes[name] = location
    _save(root, remotes)


def remove_remote(root: Path, name: str) -> None:
    remotes = _load(root)
    if name not in remotes:
        raise RuntimeError(f"Remote not found: {name}")
    del remotes[name]
    _save(root, remotes)


def list_remotes(root: Path) -> dict[str, str]:
    return _load(root)


def _resolve_location(location: str) -> Path:
    if location.startswith("aivcs://"):
        relative = location[len("aivcs://"):].strip("/")
        if not relative or len(relative.split("/")) < 2:
            raise RuntimeError("Invalid AIVCS remote URL.")
        remote_root = Path(os.environ.get("AIVCS_REMOTE_ROOT", Path.home() / ".aivcs-remotes")).expanduser().resolve()
        return remote_root.joinpath(*relative.split("/"))
    return Path(location).expanduser().resolve()


def _ensure_bare(remote: Path) -> None:
    metadata = remote / ".aivcs"
    (metadata / "objects").mkdir(parents=True, exist_ok=True)
    (metadata / "commits").mkdir(parents=True, exist_ok=True)
    (metadata / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (metadata / "refs" / "remotes").mkdir(parents=True, exist_ok=True)
    (metadata / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    if not (metadata / "index.json").exists():
        (metadata / "index.json").write_text("{}\n", encoding="utf-8")


def push(root: Path, remote_name: str = "origin", branch: str | None = None) -> dict[str, object]:
    remotes = _load(root)
    if remote_name not in remotes:
        raise RuntimeError(f"Remote not found: {remote_name}")
    branch = branch or current_branch(root)
    if not branch:
        raise RuntimeError("Cannot push from a detached HEAD.")
    head = branch_id(root, branch)
    if not head:
        raise RuntimeError(f"Branch has no commits: {branch}")
    remote = _resolve_location(remotes[remote_name])
    _ensure_bare(remote)
    copy_reachable_objects(root, remote / ".aivcs", [head])
    ref = remote / ".aivcs" / "refs" / "heads" / Path(branch)
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(head + "\n", encoding="utf-8")
    tracking = aivcs_path(root, "refs", "remotes", remote_name, *Path(branch).parts)
    tracking.parent.mkdir(parents=True, exist_ok=True)
    tracking.write_text(head + "\n", encoding="utf-8")
    return {"remote": remote_name, "branch": branch, "head": head, "location": remotes[remote_name]}


def _remote_branches(remote: Path) -> list[str]:
    base = remote / ".aivcs" / "refs" / "heads"
    return sorted(p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()) if base.exists() else []


def pull(root: Path, remote_name: str = "origin", branch: str | None = None) -> dict[str, object]:
    remotes = _load(root)
    if remote_name not in remotes:
        raise RuntimeError(f"Remote not found: {remote_name}")
    branch = branch or current_branch(root)
    if not branch:
        raise RuntimeError("Cannot pull into a detached HEAD.")
    remote = _resolve_location(remotes[remote_name])
    if not (remote / ".aivcs").is_dir():
        raise RuntimeError("Remote repository not found.")
    ref = remote / ".aivcs" / "refs" / "heads" / Path(branch)
    if not ref.exists():
        raise RuntimeError(f"Remote branch not found: {branch}")
    remote_head = ref.read_text(encoding="utf-8").strip()
    copy_reachable_objects(remote / ".aivcs", root / ".aivcs", [remote_head])
    local_ref = aivcs_path(root, "refs", "remotes", remote_name, *Path(branch).parts)
    local_ref.parent.mkdir(parents=True, exist_ok=True)
    local_ref.write_text(remote_head + "\n", encoding="utf-8")
    branch_ref = aivcs_path(root, "refs", "heads", *Path(branch).parts)
    branch_ref.parent.mkdir(parents=True, exist_ok=True)
    branch_ref.write_text(remote_head + "\n", encoding="utf-8")
    from .repository import checkout_branch
    checkout_branch(root, branch)
    return {"remote": remote_name, "branch": branch, "head": remote_head, "location": remotes[remote_name]}


def clone(location: str, target: str | None = None) -> Path:
    remote = _resolve_location(location)
    metadata = remote / ".aivcs"
    if not metadata.is_dir():
        raise RuntimeError("Remote repository not found.")
    name = target or remote.name
    destination = Path(name).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise RuntimeError(f"Destination already exists and is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    from .repository import init_repository, aivcs_path
    init_repository(destination)
    shutil.rmtree(destination / ".aivcs")
    shutil.copytree(metadata, destination / ".aivcs")
    add_remote(destination, "origin", location)
    branches = _remote_branches(remote)
    if not branches:
        raise RuntimeError("Remote repository has no branches.")
    branch = "main" if "main" in branches and (remote / ".aivcs" / "refs" / "heads" / "main").read_text(encoding="utf-8").strip() else next(
        (candidate for candidate in branches if (remote / ".aivcs" / "refs" / "heads" / candidate).read_text(encoding="utf-8").strip()),
        branches[0],
    )
    from .repository import checkout_branch
    aivcs_path(destination, "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    checkout_branch(destination, branch, force=True)
    return destination
