from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..branches import current_branch
from ..commits import create_commit
from ..staging import add
from .approval import confirm_action, confirm_commit
from .context import (
    build_commit_context,
    build_diff_context,
    build_explain_context,
    build_fix_context,
    build_merge_context,
    build_repo_overview_context,
    build_review_context,
    build_search_context,
    build_status_context,
)
from .engine import generate_commit_message, generate_text
from .prompts import (
    DIFF_EXPLAIN_PROMPT_TEMPLATE,
    EXPLAIN_TARGET_PROMPT_TEMPLATE,
    FIX_PROMPT_TEMPLATE,
    MERGE_PROMPT_TEMPLATE,
    ORCHESTRATOR_PROMPT_TEMPLATE,
    REVIEW_PROMPT_TEMPLATE,
    SEARCH_PROMPT_TEMPLATE,
    STATUS_EXPLAIN_PROMPT_TEMPLATE,
)


def _safe_target_path(root: Path, filename: str) -> Path:
    if not isinstance(filename, str) or not filename.strip():
        raise RuntimeError("Invalid target filename.")
    clean = filename.strip().replace("\\", "/")
    if clean.startswith(("/", "\\")) or clean.startswith((".aivcs", ".git")):
        raise RuntimeError(f"Cannot modify internal or reserved path: {filename}")
    relative = Path(clean)
    target = (root / relative).resolve()
    if target == root or root not in target.parents:
        raise RuntimeError(f"Path escapes repository boundary: {filename}")
    return target


def run_ai_commit(
    root: Path,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> dict | None:
    context = build_commit_context(root)
    if not context["staged_files"]:
        output_fn("No staged changes to commit. Stage changes first using `aivcs add <file>`.")
        return None

    output_fn("Analyzing staged changes with Gemini...")
    message = generate_commit_message(context, root)
    output_fn("\nAI-generated commit message:")
    output_fn(f"  {message}\n")
    if not confirm_commit(input_fn):
        output_fn("Commit canceled; no commit was created.")
        return None

    commit = create_commit(root, message)
    output_fn(f"[{commit['id'][:7]}] {commit['message']}")
    return commit


def run_ai_diff(
    root: Path,
    staged: bool = False,
    output_fn: Callable[[str], Any] = print,
) -> str:
    output_fn(f"Analyzing {'staged' if staged else 'working tree'} diff with Gemini...")
    context = build_diff_context(root, staged=staged)
    if not context["diff"].strip():
        opposite_mode = not staged
        opposite_context = build_diff_context(root, staged=opposite_mode)
        if opposite_context["diff"].strip():
            hint = "staged changes exist. Run `aivcs ai diff --staged`." if opposite_mode else "unstaged working changes exist. Run `aivcs ai diff` without --staged."
            output_fn(f"No {'staged' if staged else 'working tree'} diff found, but {hint}")
        else:
            output_fn("Working tree is completely clean. No changes to diff.")
        return ""

    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = DIFF_EXPLAIN_PROMPT_TEMPLATE.format(context_json=context_json)
    explanation = generate_text(prompt, root)
    output_fn(f"\n{explanation}")
    return explanation


def run_ai_explain(
    root: Path,
    target: str | None = None,
    output_fn: Callable[[str], Any] = print,
) -> str:
    desc = f"'{target}'" if target else "current repository changes"
    output_fn(f"Analyzing {desc} with Gemini...")
    context = build_explain_context(root, target)
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = EXPLAIN_TARGET_PROMPT_TEMPLATE.format(context_json=context_json)
    explanation = generate_text(prompt, root)
    output_fn(f"\n{explanation}")
    return explanation


def run_ai_status(
    root: Path,
    output_fn: Callable[[str], Any] = print,
) -> str:
    output_fn("Analyzing repository status with Gemini...")
    context = build_status_context(root)
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = STATUS_EXPLAIN_PROMPT_TEMPLATE.format(context_json=context_json)
    explanation = generate_text(prompt, root)
    output_fn(f"\n{explanation}")
    return explanation


def run_ai_search(
    root: Path,
    query: str,
    output_fn: Callable[[str], Any] = print,
) -> str:
    if not query or not query.strip():
        output_fn("Provide a search query: `aivcs ai search \"query\"`")
        return ""

    output_fn(f"Searching commit history for \"{query}\" with Gemini...")
    context = build_search_context(root, query.strip())
    if not context["commits"]:
        output_fn("Repository has no commits to search.")
        return ""

    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = SEARCH_PROMPT_TEMPLATE.format(query=query, context_json=context_json)
    results = generate_text(prompt, root)
    output_fn(f"\n{results}")
    return results


def run_ai_review(
    root: Path,
    staged: bool = False,
    output_fn: Callable[[str], Any] = print,
) -> str:
    output_fn(f"Reviewing {'staged' if staged else 'current'} changes with Gemini...")
    context = build_review_context(root, staged=staged)
    if not context["diff"].strip():
        output_fn("No changes found to review. Working tree and staging area are clean.")
        return ""

    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = REVIEW_PROMPT_TEMPLATE.format(context_json=context_json)
    review = generate_text(prompt, root)
    output_fn(f"\n{review}")
    return review


def run_ai_fix(
    root: Path,
    target_file: str | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> bool:
    output_fn("Diagnosing code issues and formulating a fix with Gemini...")
    context = build_fix_context(root, target_file)
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = FIX_PROMPT_TEMPLATE.format(context_json=context_json)

    fix_output = generate_text(prompt, root)
    target = context["target_file"]

    # Parse output sections: --- ANALYSIS --- and --- FILE: <name> ---
    analysis = fix_output
    file_content = None
    file_marker = re.search(r"---\s*FILE:\s*([^\n\r]+)\s*---", fix_output)
    if file_marker:
        analysis_part = fix_output[:file_marker.start()].replace("--- ANALYSIS ---", "").strip()
        analysis = analysis_part or "Identified improvements and fixes."
        raw_code = fix_output[file_marker.end():].strip()
        # Clean potential markdown fences
        if raw_code.startswith("```"):
            lines = raw_code.splitlines()
            if len(lines) >= 2 and lines[-1].strip() == "```":
                raw_code = "\n".join(lines[1:-1])
        file_content = raw_code

    output_fn("\n=== AI Fix Proposal ===")
    output_fn(f"Target: {target}")
    output_fn(f"Analysis:\n{analysis}\n")

    if file_content is None:
        output_fn("Gemini suggested an approach above, but no direct code patch was generated.")
        return False

    output_fn(f"--- Preview of Proposed Fix ({len(file_content.splitlines())} lines) ---")
    preview_lines = file_content.splitlines()[:15]
    for line in preview_lines:
        output_fn(f"  {line}")
    if len(file_content.splitlines()) > 15:
        output_fn(f"  ... ({len(file_content.splitlines()) - 15} more lines)")
    output_fn("")

    if not confirm_action(f"Apply this fix to '{target}'?", input_fn=input_fn, default=False):
        output_fn("Fix canceled; no files were modified.")
        return False

    # Safely apply fix
    dest_path = _safe_target_path(root, target)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(file_content, encoding="utf-8")
    add(root, [target])
    output_fn(f"Successfully applied fix and staged '{target}'.")
    return True


def run_ai_merge(
    root: Path,
    target_branch: str,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> bool:
    output_fn(f"Evaluating merge of '{target_branch}' into '{current_branch(root)}' with Gemini...")
    context = build_merge_context(root, target_branch)

    if context.get("is_fast_forward"):
        output_fn(f"Branches have no conflicts. You can switch and update branches directly.")
        return True

    conflicts = context["conflicts"]
    output_fn(f"Found {len(conflicts)} conflicting file(s):")
    for c in conflicts:
        output_fn(f"  - {c['path']}")

    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = MERGE_PROMPT_TEMPLATE.format(
        source_branch=target_branch,
        current_branch=context["current_branch"],
        context_json=context_json,
    )
    merge_output = generate_text(prompt, root)

    # Parse resolutions for each conflicting file
    resolutions: dict[str, str] = {}
    markers = list(re.finditer(r"---\s*RESOLUTION:\s*([^\n\r]+)\s*---", merge_output))
    for i, match in enumerate(markers):
        fname = match.group(1).strip()
        start = match.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(merge_output)
        content = merge_output[start:end].strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if len(lines) >= 2 and lines[-1].strip() == "```":
                content = "\n".join(lines[1:-1])
        resolutions[fname] = content

    summary = merge_output[:markers[0].start()].replace("--- MERGE SUMMARY ---", "").strip() if markers else merge_output
    output_fn(f"\n=== Merge Resolution Analysis ===\n{summary}\n")

    if not resolutions:
        output_fn("AI could not produce conflict resolutions automatically.")
        return False

    output_fn(f"Proposed resolution generated for: {', '.join(resolutions.keys())}\n")
    if not confirm_action(f"Apply AI merge resolution and commit merge into '{context['current_branch']}'?", input_fn=input_fn, default=False):
        output_fn("Merge canceled; no changes were applied.")
        return False

    # Apply resolved files safely
    for fname, resolved_text in resolutions.items():
        file_path = _safe_target_path(root, fname)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(resolved_text, encoding="utf-8")

    # Stage files and commit merge
    staged_list = add(root, list(resolutions.keys()))
    commit_msg = f"merge: merge branch '{target_branch}' into {context['current_branch']}"
    commit = create_commit(root, commit_msg)
    output_fn(f"[{commit['id'][:7]}] {commit['message']}")
    output_fn(f"Successfully merged '{target_branch}' into '{context['current_branch']}'.")
    return True


def run_ai_assistant(
    root: Path,
    prompt: str | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> str:
    user_prompt = prompt
    if not user_prompt or not user_prompt.strip():
        output_fn("AIVCS AI Assistant")
        output_fn("Available commands: `commit`, `diff`, `explain`, `status`, `search`, `review`, `fix`, `merge`\n")
        try:
            user_prompt = input_fn("What would you like to ask or do? ").strip()
        except EOFError:
            return ""

    if not user_prompt:
        output_fn("No prompt entered. Use `aivcs ai --help` to view all commands.")
        return ""

    output_fn("Consulting AIVCS AI Assistant...")
    context = build_repo_overview_context(root)
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    ai_prompt = ORCHESTRATOR_PROMPT_TEMPLATE.format(prompt=user_prompt, context_json=context_json)
    answer = generate_text(ai_prompt, root)
    output_fn(f"\n{answer}")
    return answer