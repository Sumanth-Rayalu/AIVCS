from __future__ import annotations

from collections.abc import Callable


from typing import Any


def confirm_action(
    prompt: str,
    input_fn: Callable[[str], str] = input,
    default: bool = True,
) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        response = input_fn(prompt.rstrip() + suffix).strip().lower()
    except EOFError:
        return False
    if not response:
        return default
    return response in {"y", "yes"}


def confirm_commit(input_fn: Callable[[str], str] = input) -> bool:
    return confirm_action("Use this commit message?", input_fn=input_fn, default=True)


def confirm_push(
    remote: str,
    branch: str,
    commits_ahead: int = 1,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> bool:
    count_str = f"{commits_ahead} commit{'s' if commits_ahead != 1 else ''}"
    output_fn("\nChanges are committed.")
    output_fn(f"\nThe local branch is ahead of {remote}/{branch} by {count_str}.\n")
    output_fn(f"Push to:\n  {remote}/{branch}\n")
    output_fn("This will make the commits available remotely.\n")
    return confirm_action("Push now?", input_fn=input_fn, default=True)


def confirm_pull(
    remote: str,
    branch: str,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
    warn_overwrite: bool = False,
) -> bool:
    output_fn(f"\nPulling from remote '{remote}' ({branch}) will update your local branch.")
    if warn_overwrite:
        output_fn("⚠ Warning: uncommitted local changes could be altered or overwritten.\n")
    return confirm_action("Pull now?", input_fn=input_fn, default=False)


def confirm_merge(
    source_branch: str,
    target_branch: str,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> bool:
    output_fn(f"\nMerging '{source_branch}' into '{target_branch}' will modify repository history.")
    return confirm_action("Proceed with merge?", input_fn=input_fn, default=False)


def _warn_symbol() -> str:
    import sys
    try:
        "⚠".encode(sys.stdout.encoding or "ascii")
        return "⚠"
    except Exception:
        return "[!]"


def confirm_dangerous_operation(
    operation: str,
    target: str,
    effect: str,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> bool:
    warn = _warn_symbol()
    output_fn(f"\n{warn} DANGEROUS OPERATION\n")
    output_fn(f"Operation: {operation}")
    output_fn(f"Target:    {target}")
    output_fn(f"Effect:    {effect}\n")
    return confirm_action("Proceed?", input_fn=input_fn, default=False)


def is_dangerous_action(action_type: str, action_params: dict[str, Any] | None = None) -> tuple[bool, str]:
    act = (action_type or "").lower().strip()
    if act == "push":
        return True, "Publishes commits to a remote repository."
    if act == "pull":
        return True, "Fetches remote commits and modifies the local working tree and history."
    if act == "merge":
        return True, "Modifies repository history and may resolve or introduce conflicts."
    if act in ("reset", "hard_reset"):
        return True, "Discards commits or working changes. This operation cannot be undone."
    if act in ("delete", "delete_branch", "delete_file"):
        return True, "Permanently removes branches, files, or repository data."
    if "force" in act:
        return True, "Destructive force operation."
    if action_params and action_params.get("overwrite"):
        return True, "Overwrites existing uncommitted user changes."
    return False, ""