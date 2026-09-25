from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .commits import history
from .config import remote_config
from .repository import BRANCHES_DIR, COMMITS_DIR, OBJECTS_DIR, aivcs_path, head_id, write_json


def _require_credentials() -> dict[str, str]:
    config = remote_config()
    if not config["username"] or not config["password"]:
        raise RuntimeError('Configure credentials first: aivcs config username "username" and aivcs config password "password"')
    return config


def build_push_payload(root: Path, repository: str, branch: str | None = None) -> dict:
    config = _require_credentials()
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
                "filename": filename,
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
        "password": config["password"],
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
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Backend request failed ({error.code}): {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to backend at {url}: {error.reason}") from error
    if not isinstance(result, dict):
        raise RuntimeError("Backend returned an invalid JSON response.")
    return result


def push(root: Path, repository: str, branch: str | None = None) -> dict:
    config = remote_config()
    payload = build_push_payload(root, repository, branch)
    return _request("POST", f"{config['backend_url']}/repositories/{repository}/push", payload)


def clone(repository: str, destination: Path) -> None:
    config = _require_credentials()
    response = _request(
        "GET",
        f"{config['backend_url']}/repositories/{repository}/clone?username={config['username']}&password={config['password']}",
    )
    if destination.exists() and any(destination.iterdir()):
        raise RuntimeError(f"Clone destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    metadata = destination / ".aivcs"
    (metadata / OBJECTS_DIR).mkdir(parents=True)
    (metadata / COMMITS_DIR).mkdir()
    (metadata / "refs" / "heads").mkdir(parents=True)
    (metadata / "index.json").write_text("{}\n", encoding="utf-8")
    branch = response["branches"][0]
    branch_name = branch["branchName"]
    (metadata / "HEAD").write_text(f"ref: refs/heads/{branch_name}\n", encoding="utf-8")
    (metadata / "refs" / "heads" / branch_name).write_text(branch["headCommitId"] + "\n", encoding="utf-8")
    for commit in branch["commits"]:
        files = {}
        for detail in commit["fileDetails"]:
            content = detail["content"].encode("utf-8")
            digest = detail.get("contentHash") or hashlib.sha256(content).hexdigest()
            (metadata / OBJECTS_DIR / digest).write_bytes(content)
            files[detail["filename"]] = digest
        write_json(metadata / COMMITS_DIR / f"{commit['commitId']}.json", {
            "id": commit["commitId"], "message": commit["message"],
            "timestamp": commit["timestamp"], "author": commit["author"],
            "parent": commit.get("parent"), "files": files,
        })
    latest = branch["commits"][-1]
    for detail in latest["fileDetails"]:
        (destination / detail["filename"]).parent.mkdir(parents=True, exist_ok=True)
        (destination / detail["filename"]).write_bytes(detail["content"].encode("utf-8"))