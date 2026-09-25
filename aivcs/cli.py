from __future__ import annotations

import argparse
from pathlib import Path

from .branches import branch_names, create_branch, current_branch, switch_branch
from .commits import create_commit, history, read_commit
from .config import set_config
from .diff import build_diff, object_text
from .remote import clone, push
from .repository import find_root, init_repository
from .staging import add, status


def print_status(root: Path) -> None:
    result = status(root)
    print("AIVCS Status")
    print(f"On branch: {current_branch(root) or 'detached'}\n")
    for title in ("staged", "committed", "modified", "deleted", "untracked"):
        print(f"{title.title()}:")
        for path in result[title]:
            print(f"  {path}")
        print()


def command_init() -> None:
    root = Path.cwd()
    init_repository(root)
    print("Initialized empty AIVCS repository.")


def command_commit(message: str | None) -> None:
    root = find_root()
    if not message:
        message = input("Commit message: ").strip()
    if not message:
        raise RuntimeError("A commit message is required.")
    commit = create_commit(root, message)
    print(f"[{commit['id'][:7]}] {commit['message']}")


def command_log(oneline: bool) -> None:
    commits = history(find_root())
    if not commits:
        print("No commits yet.")
        return
    print("AIVCS History\n")
    for commit in commits:
        if oneline:
            print(f"{commit['id'][:7]} {commit['message']}")
        else:
            print(f"commit {commit['id']}\n{commit['message']}\n{commit['author']}\n{commit['timestamp']}\n")


def command_show(commit_id: str) -> None:
    root = find_root()
    commits = history(root)
    match = next((commit for commit in commits if commit["id"].startswith(commit_id)), None)
    if not match:
        raise RuntimeError(f"Commit not found: {commit_id}")
    print(f"Commit:\n{match['id']}\n\nMessage:\n{match['message']}\n\nFiles:")
    parent_files = read_commit(root, match["parent"])["files"] if match.get("parent") else {}
    for path, digest in match["files"].items():
        marker = "A" if path not in parent_files else "M"
        print(f"{marker} {path}")
    print("\nDiff:")
    for path, digest in match["files"].items():
        old = object_text(root, parent_files.get(path)).splitlines(keepends=True)
        new = object_text(root, digest).splitlines(keepends=True)
        import difflib
        print("".join(difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}")), end="")


def command_config(key: str, value: str) -> None:
    allowed = {"email", "username", "password", "backend-url"}
    if key not in allowed:
        raise RuntimeError(f"Unknown config key: {key}. Choose email, username, password, or backend-url.")
    set_config(key.replace("-", "_"), value)
    print(f"Configured {key}.")


def command_push(branch: str | None, repository: str) -> None:
    result = push(find_root(), repository, branch)
    print(result.get("message", "Pushed successfully."))


def command_branch(name: str | None) -> None:
    root = find_root()
    if name:
        create_branch(root, name)
        print(f"Created branch '{name}'.")
        return
    active = current_branch(root)
    for branch in branch_names(root):
        marker = "*" if branch == active else " "
        print(f"{marker} {branch}")


def command_switch(name: str) -> None:
    root = find_root()
    switch_branch(root, name)
    print(f"Switched to branch '{name}'.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="aivcs", description="AI-native version control, Phase 1 core")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("paths", nargs="+", metavar="file")
    subparsers.add_parser("status")
    diff_parser = subparsers.add_parser("diff")
    diff_parser.add_argument("--staged", action="store_true")
    commit_parser = subparsers.add_parser("commit")
    commit_parser.add_argument("-m", "--message")
    log_parser = subparsers.add_parser("log")
    log_parser.add_argument("--oneline", action="store_true")
    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("commit")
    config_parser = subparsers.add_parser("config")
    config_parser.add_argument("key", choices=("email", "username", "password", "backend-url"))
    config_parser.add_argument("value")
    push_parser = subparsers.add_parser("push")
    push_parser.add_argument("branch", nargs="?", default=None)
    push_parser.add_argument("--repository", default="default")
    clone_parser = subparsers.add_parser("clone")
    clone_parser.add_argument("repository")
    clone_parser.add_argument("destination", nargs="?", default=None)
    branch_parser = subparsers.add_parser("branch")
    branch_parser.add_argument("name", nargs="?")
    switch_parser = subparsers.add_parser("switch")
    switch_parser.add_argument("name")
    args = parser.parse_args()
    try:
        if args.command == "init": command_init()
        elif args.command == "add": print("Staged:\n  " + "\n  ".join(add(find_root(), args.paths)))
        elif args.command == "status": print_status(find_root())
        elif args.command == "diff": print(build_diff(find_root(), args.staged), end="")
        elif args.command == "commit": command_commit(args.message)
        elif args.command == "log": command_log(args.oneline)
        elif args.command == "show": command_show(args.commit)
        elif args.command == "config": command_config(args.key, args.value)
        elif args.command == "push": command_push(args.branch, args.repository)
        elif args.command == "clone":
            destination = Path(args.destination or args.repository)
            clone(args.repository, destination)
            print(f"Cloned {args.repository} into {destination}.")
        elif args.command == "branch": command_branch(args.name)
        elif args.command == "switch": command_switch(args.name)
    except (RuntimeError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
