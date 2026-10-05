from __future__ import annotations

import difflib
import fnmatch
import json
from pathlib import Path
from typing import Any

from ..branches import BRANCHES_DIR, _snapshot, branch_names, current_branch
from ..commits import history, read_commit
from ..diff import build_diff, object_text
from ..hashing import hash_bytes
from ..repository import aivcs_path, head_id
from ..staging import committed_snapshot, load_index, status

MAX_CONTEXT_FILES = 50
MAX_FILE_CHARACTERS = 12_000
MAX_TOTAL_FILE_CHARACTERS = 40_000
MAX_DIFF_CHARACTERS = 40_000


def _safe_read_file(root: Path, relative_path: str, max_chars: int = MAX_FILE_CHARACTERS) -> str:
    file_path = (root / relative_path).resolve()
    if file_path == root or root not in file_path.parents:
        raise RuntimeError(f"Path escapes repository: {relative_path}")
    if not file_path.is_file():
        return "[file does not exist on disk]"
    content_bytes = file_path.read_bytes()
    if b"\0" in content_bytes:
        return "[binary file content omitted]"
    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return "[binary file content omitted]"
    if len(text) > max_chars:
        return text[:max_chars] + "\n[content truncated]"
    return text


def build_commit_context(root: Path) -> dict[str, Any]:
    root = root.resolve()
    index = load_index(root)
    committed = committed_snapshot(root)
    staged_paths = sorted(
        path for path, digest in index.items() if digest != committed.get(path)
    )
    if not staged_paths:
        return {"staged_files": [], "staged_diff": "", "recent_commits": []}

    staged_diff = build_diff(root, staged=True)
    if len(staged_diff) > MAX_DIFF_CHARACTERS:
        staged_diff = staged_diff[:MAX_DIFF_CHARACTERS] + "\n[diff truncated]"

    files = []
    remaining_characters = MAX_TOTAL_FILE_CHARACTERS
    for relative_path in staged_paths[:MAX_CONTEXT_FILES]:
        content = _safe_read_file(root, relative_path, min(MAX_FILE_CHARACTERS, remaining_characters))
        remaining_characters -= len(content)
        files.append({"path": relative_path, "content": content})
        if remaining_characters <= 0:
            break

    recent_commits = [
        {"id": commit["id"][:7], "message": commit["message"], "author": commit.get("author", "")}
        for commit in history(root)[:5]
    ]
    return {
        "branch": current_branch(root) or "detached",
        "staged_files": files,
        "staged_diff": staged_diff,
        "recent_commits": recent_commits,
    }


def build_diff_context(root: Path, staged: bool = False) -> dict[str, Any]:
    root = root.resolve()
    diff_text = build_diff(root, staged=staged)
    if len(diff_text) > MAX_DIFF_CHARACTERS:
        diff_text = diff_text[:MAX_DIFF_CHARACTERS] + "\n[diff truncated]"
    repo_status = status(root)
    return {
        "branch": current_branch(root) or "detached",
        "mode": "staged" if staged else "working_tree",
        "diff": diff_text,
        "staged_files": repo_status["staged"],
        "modified_files": repo_status["modified"],
        "untracked_files": repo_status["untracked"],
    }


def build_status_context(root: Path) -> dict[str, Any]:
    root = root.resolve()
    repo_status = status(root)
    recent = history(root)[:3]
    return {
        "branch": current_branch(root) or "detached",
        "head_commit": head_id(root),
        "staged": repo_status["staged"],
        "modified": repo_status["modified"],
        "deleted": repo_status["deleted"],
        "untracked": repo_status["untracked"],
        "recent_commits": [
            {"id": c["id"][:7], "message": c["message"], "timestamp": c.get("timestamp", "")}
            for c in recent
        ],
    }


def build_explain_context(root: Path, target: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    commits = history(root)
    # Check if target is a commit ID or prefix
    if target:
        match_commit = next((c for c in commits if c["id"].startswith(target)), None)
        if match_commit:
            parent = match_commit.get("parent")
            parent_files = read_commit(root, parent).get("files", {}) if parent else {}
            commit_files = match_commit.get("files", {})
            diff_lines = []
            for path, digest in commit_files.items():
                old = object_text(root, parent_files.get(path)).splitlines(keepends=True)
                new = object_text(root, digest).splitlines(keepends=True)
                diff_lines.extend(difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}"))
            return {
                "target_type": "commit",
                "commit_id": match_commit["id"],
                "message": match_commit["message"],
                "author": match_commit.get("author"),
                "timestamp": match_commit.get("timestamp"),
                "files_changed": list(commit_files.keys()),
                "diff": "".join(diff_lines)[:MAX_DIFF_CHARACTERS],
            }
        # Check if target is a file in the repo
        target_path = Path(target)
        if (root / target_path).is_file():
            content = _safe_read_file(root, target)
            return {
                "target_type": "file",
                "path": target,
                "content": content,
            }

    # If no target specified or not matched, explain current pending changes
    staged_diff = build_diff(root, staged=True)
    working_diff = build_diff(root, staged=False)
    diff = staged_diff or working_diff
    return {
        "target_type": "current_changes",
        "branch": current_branch(root) or "detached",
        "has_staged": bool(staged_diff),
        "diff": diff[:MAX_DIFF_CHARACTERS] if diff else "[no active changes in repository]",
        "status": status(root),
    }


def build_search_context(root: Path, query: str) -> dict[str, Any]:
    root = root.resolve()
    all_commits = history(root)
    commit_entries = []
    for c in all_commits[:100]:
        files_touched = list(c.get("files", {}).keys())
        commit_entries.append({
            "id": c["id"][:7],
            "full_id": c["id"],
            "message": c["message"],
            "author": c.get("author", "unknown"),
            "timestamp": c.get("timestamp", ""),
            "files": files_touched,
        })
    return {
        "query": query,
        "total_commits_searched": len(commit_entries),
        "commits": commit_entries,
    }


def build_review_context(root: Path, staged: bool = False) -> dict[str, Any]:
    root = root.resolve()
    diff_text = build_diff(root, staged=staged)
    if not diff_text and not staged:
        # Fall back to staged diff if working tree is clean
        diff_text = build_diff(root, staged=True)
        staged = True

    repo_status = status(root)
    files = []
    target_paths = repo_status["staged"] if staged else repo_status["modified"]
    for path in target_paths[:MAX_CONTEXT_FILES]:
        file_text = _safe_read_file(root, path)
        if len(file_text) > 1500:
            file_text = file_text[:1500] + "\n... [content truncated for review]"
        files.append({"path": path, "content": file_text})

    return {
        "branch": current_branch(root) or "detached",
        "is_staged": staged,
        "diff": diff_text[:MAX_DIFF_CHARACTERS],
        "files": files,
    }


def build_fix_context(root: Path, file_path: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    repo_status = status(root)
    target = file_path
    if not target:
        if repo_status["staged"]:
            target = repo_status["staged"][0]
        elif repo_status["modified"]:
            target = repo_status["modified"][0]
        elif repo_status["untracked"]:
            target = repo_status["untracked"][0]

    if not target:
        raise RuntimeError("No modified or staged files found to fix.")

    content = _safe_read_file(root, target)
    diff = build_diff(root, staged=False) or build_diff(root, staged=True)
    return {
        "target_file": target,
        "content": content,
        "diff": diff[:MAX_DIFF_CHARACTERS],
    }


def build_merge_context(root: Path, target_branch: str) -> dict[str, Any]:
    root = root.resolve()
    curr_branch = current_branch(root)
    if not curr_branch:
        raise RuntimeError("Cannot merge on a detached HEAD.")
    if curr_branch == target_branch:
        raise RuntimeError(f"Cannot merge branch '{target_branch}' into itself.")

    all_branches = branch_names(root)
    if target_branch not in all_branches:
        raise RuntimeError(f"Target branch '{target_branch}' does not exist. Available branches: {', '.join(all_branches)}")

    curr_head = head_id(root)
    target_ref = aivcs_path(root, BRANCHES_DIR, target_branch)
    target_head = target_ref.read_text(encoding="utf-8").strip() or None

    curr_snapshot = _snapshot(root, curr_head)
    target_snapshot = _snapshot(root, target_head)

    # Detect files added, modified, conflicting
    only_in_current = [p for p in curr_snapshot if p not in target_snapshot]
    only_in_target = [p for p in target_snapshot if p not in curr_snapshot]
    common_files = [p for p in curr_snapshot if p in target_snapshot]

    conflicting_files: list[dict[str, Any]] = []
    for path in common_files:
        if curr_snapshot[path] != target_snapshot[path]:
            curr_text = object_text(root, curr_snapshot[path])
            target_text = object_text(root, target_snapshot[path])
            diff_lines = list(difflib.unified_diff(
                curr_text.splitlines(keepends=True),
                target_text.splitlines(keepends=True),
                fromfile=f"{curr_branch}:{path}",
                tofile=f"{target_branch}:{path}"
            ))
            conflicting_files.append({
                "path": path,
                "current_content": curr_text[:MAX_FILE_CHARACTERS],
                "target_content": target_text[:MAX_FILE_CHARACTERS],
                "diff": "".join(diff_lines)[:MAX_DIFF_CHARACTERS],
            })

    return {
        "current_branch": curr_branch,
        "target_branch": target_branch,
        "current_head": curr_head[:7] if curr_head else None,
        "target_head": target_head[:7] if target_head else None,
        "only_in_current": only_in_current,
        "only_in_target": only_in_target,
        "conflicts": conflicting_files,
        "is_fast_forward": curr_head == target_head or not conflicting_files and not only_in_target,
    }


def build_repo_overview_context(root: Path) -> dict[str, Any]:
    root = root.resolve()
    repo_status = status(root)
    commits = history(root)
    return {
        "branch": current_branch(root) or "detached",
        "head_commit": head_id(root),
        "total_commits": len(commits),
        "recent_commits": [
            {"id": c["id"][:7], "message": c["message"]} for c in commits[:5]
        ],
        "status": repo_status,
        "branches": branch_names(root),
    }


FORBIDDEN_SENSITIVE_PATTERNS = {
    ".env", ".env.*", "*.env", "*credential*", "*secret*", "*token*", "*password*",
    "*.pem", "*.key", "*.crt", "*.pfx", "*.p12",
    ".aivcs*", ".git*", "__pycache__*", "node_modules*",
    "*.tmp", "*.temp", "*.bak", "*.swp"
}


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


def is_sensitive_path(rel_path: str) -> bool:
    rel_path = rel_path.replace("\\", "/").strip("/")
    parts = rel_path.split("/")
    filename = parts[-1].lower()
    for pattern in FORBIDDEN_SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path.lower(), pattern):
            return True
    return False


def get_remote_sync_state(root: Path) -> dict[str, Any]:
    try:
        from ..config import remote_config
        from ..remote import _fetch_repository
        config = remote_config()
        if not config.get("username") or not config.get("email") or not config.get("repo"):
            return {"is_configured": False, "status": "unconfigured"}

        try:
            repo_data = _fetch_repository(config, config["repo"])
        except Exception as e:
            return {
                "is_configured": True,
                "reachable": False,
                "repo": config["repo"],
                "backend_url": config.get("backend_url", ""),
                "error": str(e),
                "status": "unreachable",
            }

        curr_branch = current_branch(root) or "main"
        remote_branches = repo_data.get("branches", [])
        remote_branch = next((b for b in remote_branches if b.get("branchName") == curr_branch), None)

        local_head = head_id(root)
        if not remote_branch:
            local_commits = history(root, local_head) if local_head else []
            return {
                "is_configured": True,
                "reachable": True,
                "repo": config["repo"],
                "branch": curr_branch,
                "remote_head": None,
                "local_head": local_head[:7] if local_head else None,
                "ahead_count": len(local_commits),
                "behind_count": 0,
                "status": "new_branch",
            }

        remote_head = remote_branch.get("headCommitId")
        if local_head == remote_head:
            return {
                "is_configured": True,
                "reachable": True,
                "repo": config["repo"],
                "branch": curr_branch,
                "remote_head": remote_head[:7] if remote_head else None,
                "local_head": local_head[:7] if local_head else None,
                "ahead_count": 0,
                "behind_count": 0,
                "status": "up_to_date",
            }

        local_commits = history(root, local_head) if local_head else []
        local_ids = [c["id"] for c in local_commits]
        remote_commits = [c.get("commitId") for c in remote_branch.get("commits", [])]

        if remote_head in local_ids:
            ahead_by = local_ids.index(remote_head)
            return {
                "is_configured": True,
                "reachable": True,
                "repo": config["repo"],
                "branch": curr_branch,
                "remote_head": remote_head[:7] if remote_head else None,
                "local_head": local_head[:7] if local_head else None,
                "ahead_count": ahead_by,
                "behind_count": 0,
                "status": "ahead",
            }
        elif local_head in remote_commits:
            behind_by = len(remote_commits) - 1 - remote_commits.index(local_head)
            return {
                "is_configured": True,
                "reachable": True,
                "repo": config["repo"],
                "branch": curr_branch,
                "remote_head": remote_head[:7] if remote_head else None,
                "local_head": local_head[:7] if local_head else None,
                "ahead_count": 0,
                "behind_count": behind_by,
                "status": "behind",
            }
        else:
            return {
                "is_configured": True,
                "reachable": True,
                "repo": config["repo"],
                "branch": curr_branch,
                "remote_head": remote_head[:7] if remote_head else None,
                "local_head": local_head[:7] if local_head else None,
                "ahead_count": len(local_commits),
                "behind_count": len(remote_commits),
                "status": "diverged",
            }
    except Exception as exc:
        return {"is_configured": False, "status": "error", "error": str(exc)}


def build_autonomous_context(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rules = load_gitignore(root)
    repo_status = status(root)

    clean_untracked = []
    ignored_untracked = []
    for p in repo_status["untracked"]:
        if is_sensitive_path(p) or is_ignored_path(p, rules):
            ignored_untracked.append(p)
        else:
            clean_untracked.append(p)

    staged_diff = build_diff(root, staged=True)
    if len(staged_diff) > MAX_DIFF_CHARACTERS:
        staged_diff = staged_diff[:MAX_DIFF_CHARACTERS] + "\n[staged diff truncated]"

    working_diff = build_diff(root, staged=False)
    if len(working_diff) > MAX_DIFF_CHARACTERS:
        working_diff = working_diff[:MAX_DIFF_CHARACTERS] + "\n[working diff truncated]"

    curr_head = head_id(root)
    recent = [
        {"id": c["id"][:7], "message": c["message"], "author": c.get("author", ""), "timestamp": c.get("timestamp", "")}
        for c in history(root)[:5]
    ]

    remote_state = get_remote_sync_state(root)
    is_clean = not (repo_status["staged"] or repo_status["modified"] or repo_status["deleted"] or clean_untracked)

    return {
        "branch": current_branch(root) or "detached",
        "head_commit": curr_head[:7] if curr_head else None,
        "branches": branch_names(root),
        "status": {
            "staged": repo_status["staged"],
            "modified": repo_status["modified"],
            "deleted": repo_status["deleted"],
            "untracked": clean_untracked,
        },
        "ignored_untracked_count": len(ignored_untracked),
        "staged_diff": staged_diff,
        "working_diff": working_diff,
        "recent_commits": recent,
        "remote_status": remote_state,
        "is_clean": is_clean,
    }