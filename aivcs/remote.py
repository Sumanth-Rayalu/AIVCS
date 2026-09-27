from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .branches import current_branch
from .commits import history
from .config import remote_config
from .hashing import hash_bytes
from .repository import BRANCHES_DIR, COMMITS_DIR, HEAD_FILE, OBJECTS_DIR, aivcs_path, head_id, write_json
from .staging import load_index, status


def _require_identity() -> dict[str, str]:
    config = remote_config()
    if not config["username"] or not config["email"]:
        raise RuntimeError('Configure your identity first: aivcs config username "username" and aivcs config email "email"')
    return config


def build_push_payload(root: Path, repository: str, branch: str | None = None) -> dict:
    config = _require_identity()
    branch = branch or _current_branch(root)
    branch_ref = aivcs_path(root, BRANCHES_DIR, branch)
    if not branch_ref.is_file():
        raise RuntimeError(f"Branch not found: {branch}")
    current = branch_ref.read_text(encoding="utf-8").strip() or None
    if not current:
        raise RuntimeError(f"Nothing to push on branch '{branch}': create a commit first.")

    commits = []
    for commit in reversed(history(root, current)):
        files = []
        for filename, digest in commit["files"].items():
            content = aivcs_path(root, OBJECTS_DIR, digest).read_bytes()
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise RuntimeError(f"Cannot push binary file as JSON content: {filename}") from error
            files.append({
                "filename": str(Path(filename).with_suffix("")),
                "fileextension": Path(filename).suffix,
                "content": text,
                "contentHash": digest,
            })
        commits.append({
            "commitId": commit["id"],
            "message": commit["message"],
            "timestamp": commit["timestamp"],
            "author": commit["author"],
            "parent": commit.get("parent"),
            "fileDetails": files,
        })

    return {
        "email": config["email"],
        "username": config["username"],
        "repository": {
            "repositoryId": repository,
            "branches": [
                {
                    "branchName": branch,
                    "headCommitId": current,
                    "commits": commits,
                }
            ],
        },
    }


def _current_branch(root: Path) -> str:
    head = aivcs_path(root, "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        return head.removeprefix(f"ref: {BRANCHES_DIR}/")
    return "detached"


def _request(method: str, url: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(body)
        except json.JSONDecodeError:
            error_payload = {}
        detail = error_payload.get("detail") if isinstance(error_payload, dict) else None
        if detail == "AIVCS account not found":
            message = (
                "No AIVCS account matches the configured username and email. "
                "Check them with `aivcs config --list`, then update them using "
                '`aivcs config username "..."` and `aivcs config email "..."`. '
                "Retry the command after correcting the account settings."
            )
        elif isinstance(detail, str) and detail:
            message = f"Request failed (HTTP {error.code}): {detail}"
        else:
            message = f"The backend could not complete the request (HTTP {error.code})."
        raise RuntimeError(message) from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to backend at {url}: {error.reason}") from error
    if not isinstance(result, dict):
        raise RuntimeError("Backend returned an invalid JSON response.")
    return result


def _repository_url(config: dict[str, str], repository: str) -> str:
    return f"{config['backend_url']}/repositories/{quote(repository, safe='')}"


def _fetch_repository(config: dict[str, str], repository: str) -> dict:
    query = urlencode({"username": config["username"], "email": config["email"]})
    return _request("GET", f"{_repository_url(config, repository)}/clone?{query}")


def push(root: Path, repository: str, branch: str | None = None) -> dict:
    config = _require_identity()
    payload = build_push_payload(root, repository, branch)
    return _request("POST", f"{_repository_url(config, repository)}/push", payload)


def _safe_file_path(root: Path, filename: str) -> Path:
    if not isinstance(filename, str) or not filename:
        raise RuntimeError("Remote snapshot contains an invalid filename.")
    relative_path = Path(filename)
    if relative_path.is_absolute() or relative_path.parts[0].casefold() in {".aivcs", ".git"}:
        raise RuntimeError(f"Remote snapshot contains a reserved path: {filename}")
    root = root.resolve()
    target = (root / relative_path).resolve()
    if target == root or root not in target.parents:
        raise RuntimeError(f"Remote snapshot path escapes the repository: {filename}")
    return target


def _write_remote_branch(root: Path, branch: dict) -> None:
    branch_name = branch.get("branchName")
    if not isinstance(branch_name, str) or not branch_name or Path(branch_name).name != branch_name:
        raise RuntimeError("Remote repository contains an invalid branch name.")
    commits = branch.get("commits")
    if not isinstance(commits, list):
        raise RuntimeError(f"Remote branch '{branch_name}' has invalid commit history.")

    imported_ids = set()
    for commit in commits:
        if not isinstance(commit, dict) or not commit.get("commitId"):
            raise RuntimeError(f"Remote branch '{branch_name}' contains an invalid commit.")
        details = commit.get("fileDetails")
        if not isinstance(details, list):
            raise RuntimeError(f"Remote commit '{commit['commitId']}' has invalid files.")
        files = {}
        for detail in details:
            if not isinstance(detail, dict) or not isinstance(detail.get("content"), str):
                raise RuntimeError(f"Remote commit '{commit['commitId']}' contains invalid file data.")
            filename = detail.get("filename")
            _safe_file_path(root, filename)
            content = detail["content"].encode("utf-8")
            actual_digest = hash_bytes(content)
            digest = detail.get("contentHash")
            if digest != actual_digest:
                digest = actual_digest
            object_path = aivcs_path(root, OBJECTS_DIR, digest)
            object_path.parent.mkdir(parents=True, exist_ok=True)
            object_path.write_bytes(content)
            files[filename] = digest
        commit_id = str(commit["commitId"])
        write_json(aivcs_path(root, COMMITS_DIR, f"{commit_id}.json"), {
            "id": commit_id,
            "message": commit.get("message", ""),
            "timestamp": commit.get("timestamp", ""),
            "author": commit.get("author", ""),
            "parent": commit.get("parent"),
            "files": files,
        })
        imported_ids.add(commit_id)

    remote_head = branch.get("headCommitId")
    if remote_head and remote_head not in imported_ids:
        raise RuntimeError(f"Remote branch '{branch_name}' is missing its head commit.")
    ref_path = aivcs_path(root, BRANCHES_DIR, branch_name)
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_text(f"{remote_head or ''}\n", encoding="utf-8")


def _checkout_branch(root: Path, branch_name: str, old_head: str | None) -> None:
    old_files = {}
    if old_head:
        old_commit = json.loads(aivcs_path(root, COMMITS_DIR, f"{old_head}.json").read_text(encoding="utf-8"))
        old_files = old_commit.get("files", {})
    branch_ref = aivcs_path(root, BRANCHES_DIR, branch_name)
    new_head = branch_ref.read_text(encoding="utf-8").strip() or None
    new_files = {}
    if new_head:
        new_commit = json.loads(aivcs_path(root, COMMITS_DIR, f"{new_head}.json").read_text(encoding="utf-8"))
        new_files = new_commit.get("files", {})

    for filename in old_files.keys() - new_files.keys():
        path = _safe_file_path(root, filename)
        if path.is_file():
            path.unlink()
    for filename, digest in new_files.items():
        path = _safe_file_path(root, filename)
        object_path = aivcs_path(root, OBJECTS_DIR, digest)
        if not object_path.is_file():
            raise RuntimeError(f"Missing content object for {filename}: {digest}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(object_path.read_bytes())
    aivcs_path(root, HEAD_FILE).write_text(f"ref: {BRANCHES_DIR}/{branch_name}\n", encoding="utf-8")


def _require_clean_worktree(root: Path) -> None:
    changes = status(root)
    change_sections = ("staged", "modified", "deleted", "untracked")
    if any(changes[section] for section in change_sections) or load_index(root):
        raise RuntimeError("Cannot pull with uncommitted changes. Commit or remove them first.")


def clone(repository: str, destination: Path) -> None:
    config = _require_identity()
    response = _fetch_repository(config, repository)
    branches = response.get("branches")
    if not isinstance(branches, list) or not branches:
        raise RuntimeError("Remote repository has no branches to clone.")
    if destination.exists() and any(destination.iterdir()):
        raise RuntimeError(f"Clone destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    metadata = destination / ".aivcs"
    (metadata / OBJECTS_DIR).mkdir(parents=True)
    (metadata / COMMITS_DIR).mkdir()
    (metadata / "refs" / "heads").mkdir(parents=True)
    (metadata / "index.json").write_text("{}\n", encoding="utf-8")
    for branch in branches:
        _write_remote_branch(destination, branch)
    checkout = next((item for item in branches if item.get("branchName") == "main"), branches[0])
    _checkout_branch(destination, checkout["branchName"], None)


def pull(root: Path, repository: str, branch_name: str | None = None) -> dict:
    config = _require_identity()
    active_branch = current_branch(root)
    target_branch = branch_name or active_branch
    if not target_branch:
        raise RuntimeError("Specify a branch to pull while HEAD is detached.")
    response = _fetch_repository(config, repository)
    remote_branch = next(
        (item for item in response.get("branches", []) if item.get("branchName") == target_branch),
        None,
    )
    if not remote_branch:
        raise RuntimeError(f"Remote branch not found: {target_branch}")
    _require_clean_worktree(root)

    local_ref = aivcs_path(root, BRANCHES_DIR, target_branch)
    local_head = local_ref.read_text(encoding="utf-8").strip() or None if local_ref.is_file() else None
    remote_head = remote_branch.get("headCommitId")
    remote_commit_ids = {commit.get("commitId") for commit in remote_branch.get("commits", [])}
    local_commit_ids = {commit["id"] for commit in history(root, local_head)} if local_head else set()
    if local_head and remote_head != local_head and local_head not in remote_commit_ids:
        if remote_head in local_commit_ids or not remote_head:
            return {"message": f"Already ahead of the remote '{target_branch}' branch."}
        raise RuntimeError(
            f"Local and remote '{target_branch}' branches have diverged. Reconcile them before pulling."
        )

    old_head = head_id(root) if active_branch else None
    _write_remote_branch(root, remote_branch)
    _checkout_branch(root, target_branch, old_head)
    return {"message": f"Pulled {repository} ({target_branch}) successfully."}