from __future__ import annotations

import argparse
from pathlib import Path

from .commits import create_commit, history, read_commit
from .diff import build_diff, object_text
from .repository import find_root, init_repository
from .staging import add, status


def print_status(root: Path) -> None:
    result = status(root)
    print("AIVCS Status\n")
    for title in ("staged", "modified", "deleted", "untracked"):
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
    args = parser.parse_args()
    try:
        if args.command == "init": command_init()
        elif args.command == "add": print("Staged:\n  " + "\n  ".join(add(find_root(), args.paths)))
        elif args.command == "status": print_status(find_root())
        elif args.command == "diff": print(build_diff(find_root(), args.staged), end="")
        elif args.command == "commit": command_commit(args.message)
        elif args.command == "log": command_log(args.oneline)
        elif args.command == "show": command_show(args.commit)
    except (RuntimeError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
