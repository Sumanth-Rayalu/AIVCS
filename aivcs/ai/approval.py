from __future__ import annotations

from collections.abc import Callable


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