from __future__ import annotations

import argparse
from pathlib import Path

from .commits import create_commit, history, read_commit
from .diff import build_diff, object_text
from .remotes import add_remote, clone, list_remotes, pull, push, remove_remote
from .repository import checkout_branch, create_branch, current_branch, find_root, head_id, list_branches, init_repository
from .staging import add, stage_all, status


def print_status(root: Path) -> None:
    result = status(root)
    print("AIVCS Status\n")
    for title in ("staged", "modified", "deleted", "untracked"):
        print(f"{title.title()}:")
        for path in result[title]: print(f"  {path}")
        print()


def command_init() -> None:
    init_repository(Path.cwd())
    print("Initialized empty AIVCS repository.")


def command_commit(message: str | None) -> None:
    root = find_root()
    message = message or input("Commit message: ").strip()
    if not message: raise RuntimeError("A commit message is required.")
    commit = create_commit(root, message)
    print(f"[{commit['id'][:7]}] {commit['message']}")


def command_log(oneline: bool) -> None:
    commits = history(find_root())
    if not commits: print("No commits yet."); return
    for commit in commits:
        print(f"{commit['id'][:7]} {commit['message']}" if oneline else f"commit {commit['id']}\n{commit['message']}\n{commit['author']}\n{commit['timestamp']}\n")


def command_show(commit_id: str) -> None:
    root = find_root(); commits = history(root)
    match = next((c for c in commits if c["id"].startswith(commit_id)), None)
    if not match: raise RuntimeError(f"Commit not found: {commit_id}")
    parent = read_commit(root, match["parent"]) if match.get("parent") else {"files": {}}
    print(f"Commit:\n{match['id']}\n\nMessage:\n{match['message']}\n\nFiles:")
    for path in match["files"]: print(f"  {path}")
    import difflib
    print("\nDiff:")
    for path in sorted(set(parent.get("files", {})) | set(match["files"])):
        old = object_text(root, parent.get("files", {}).get(path)).splitlines(keepends=True)
        new = object_text(root, match.get("files", {}).get(path)).splitlines(keepends=True)
        print("".join(difflib.unified_diff(old, new, fromfile=f"a/{path}", tofile=f"b/{path}")), end="")


def main() -> None:
    parser = argparse.ArgumentParser(prog="aivcs", description="AIVCS version control")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init")
    p = subs.add_parser("add"); p.add_argument("paths", nargs="+")
    subs.add_parser("status")
    p = subs.add_parser("diff"); p.add_argument("--staged", action="store_true")
    p = subs.add_parser("commit"); p.add_argument("-m", "--message")
    p = subs.add_parser("log"); p.add_argument("--oneline", action="store_true")
    p = subs.add_parser("show"); p.add_argument("commit")
    p = subs.add_parser("branch"); p.add_argument("name", nargs="?"); p.add_argument("-a", "--all", action="store_true")
    p = subs.add_parser("checkout"); p.add_argument("branch")
    p = subs.add_parser("remote"); p.add_argument("action", nargs="?", choices=["add", "remove"]); p.add_argument("name", nargs="?"); p.add_argument("location", nargs="?"); p.add_argument("-v", "--verbose", action="store_true")
    p = subs.add_parser("push"); p.add_argument("remote"); p.add_argument("branch")
    p = subs.add_parser("pull"); p.add_argument("remote"); p.add_argument("branch")
    p = subs.add_parser("clone"); p.add_argument("url"); p.add_argument("folder", nargs="?")
    args = parser.parse_args()
    try:
        if args.command == "init": command_init()
        elif args.command == "add": print("Staged:\n  " + "\n  ".join(stage_all(find_root()) if args.paths == ["."] else add(find_root(), args.paths)))
        elif args.command == "status": print_status(find_root())
        elif args.command == "diff": print(build_diff(find_root(), args.staged), end="")
        elif args.command == "commit": command_commit(args.message)
        elif args.command == "log": command_log(args.oneline)
        elif args.command == "show": command_show(args.commit)
        elif args.command == "branch":
            root = find_root()
            if args.name: create_branch(root, args.name); print(f"Created branch {args.name}")
            else:
                active = current_branch(root)
                for name in list_branches(root): print(("* " if name == active else "  ") + name)
        elif args.command == "checkout": checkout_branch(find_root(), args.branch); print(f"Switched to branch '{args.branch}'")
        elif args.command == "remote":
            root = find_root()
            if args.verbose or args.action is None:
                for name, location in list_remotes(root).items(): print(f"{name}\t{location}")
            elif args.action == "add":
                if not args.name or not args.location: raise RuntimeError("Usage: aivcs remote add <name> <url>")
                add_remote(root, args.name, args.location); print(f"Added remote {args.name}")
            elif args.action == "remove":
                if not args.name: raise RuntimeError("Usage: aivcs remote remove <name>")
                remove_remote(root, args.name); print(f"Removed remote {args.name}")
        elif args.command == "push": print(push(find_root(), args.remote, args.branch))
        elif args.command == "pull": print(pull(find_root(), args.remote, args.branch))
        elif args.command == "clone": print(f"Cloned into {clone(args.url, args.folder)}")
    except (RuntimeError, FileNotFoundError) as error:
        parser.error(str(error))


if __name__ == "__main__": main()
