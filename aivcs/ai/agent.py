from __future__ import annotations

import difflib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..branches import BRANCH_NAME, create_branch, current_branch, switch_branch
from ..commits import create_commit, history, read_commit
from ..diff import object_text
from ..remote import pull, push
from ..repository import head_id
from ..staging import add, load_index, status
from .approval import (
    confirm_action,
    confirm_commit,
    confirm_dangerous_operation,
    confirm_merge,
    confirm_pull,
    confirm_push,
    is_dangerous_action,
)
from .context import (
    build_autonomous_context,
    build_commit_context,
    build_diff_context,
    build_explain_context,
    build_fix_context,
    build_merge_context,
    build_repo_overview_context,
    build_review_context,
    build_search_context,
    build_status_context,
    is_ignored_path,
    is_sensitive_path,
    load_gitignore,
)
from .engine import generate_commit_message, generate_text
from .prompts import (
    AUTONOMOUS_AGENT_PROMPT_TEMPLATE,
    DIFF_EXPLAIN_PROMPT_TEMPLATE,
    EXPLAIN_TARGET_PROMPT_TEMPLATE,
    FIX_PROMPT_TEMPLATE,
    MERGE_PROMPT_TEMPLATE,
    ORCHESTRATOR_PROMPT_TEMPLATE,
    POST_ACTION_SUMMARY_PROMPT_TEMPLATE,
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


MAX_AGENT_ITERATIONS = 5


def validate_action_plan(
    raw_plan: dict[str, Any],
    context: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    if not isinstance(raw_plan, dict):
        return {"summary": "Invalid plan format", "actions": [], "complete": True}

    root = root.resolve()
    summary = str(raw_plan.get("summary", "")).strip()
    reasoning = str(raw_plan.get("reasoning", "")).strip()
    raw_actions = raw_plan.get("actions", [])
    if not isinstance(raw_actions, list):
        raw_actions = []

    validated_actions: list[dict[str, Any]] = []
    rules = load_gitignore(root)

    for act in raw_actions:
        if not isinstance(act, dict):
            continue
        action_name = str(act.get("action", "")).lower().strip()

        # Reject any shell or git commands strictly
        if any(bad in action_name for bad in ("git", "exec", "shell", "bash", "cmd")):
            continue

        if action_name in ("stage", "add"):
            files = act.get("files", [])
            if not isinstance(files, list):
                files = [files] if isinstance(files, str) else []
            valid_files = []
            for f in files:
                if not isinstance(f, str):
                    continue
                clean = f.strip().replace("\\", "/")
                if clean.startswith(("/", "\\")) or clean.startswith((".aivcs", ".git")):
                    continue
                if is_sensitive_path(clean):
                    continue
                if is_ignored_path(clean, rules):
                    continue
                target_p = (root / clean).resolve()
                if target_p == root or root not in target_p.parents:
                    continue
                if not target_p.exists():
                    continue
                valid_files.append(clean)
            if valid_files:
                validated_actions.append({
                    "action": "stage",
                    "files": valid_files,
                    "requires_approval": False,
                })

        elif action_name == "commit":
            msg = str(act.get("message", "")).strip("`'\"").strip()
            if not msg:
                msg = "chore: update repository changes"
            lines = [l.strip("`'\"").strip() for l in msg.splitlines() if l.strip()]
            first_line = lines[0] if lines else "chore: update repository changes"
            validated_actions.append({
                "action": "commit",
                "message": first_line,
                "requires_approval": False,
            })

        elif action_name == "create_branch":
            name = str(act.get("name", "")).strip()
            if BRANCH_NAME.fullmatch(name):
                validated_actions.append({
                    "action": "create_branch",
                    "name": name,
                    "requires_approval": False,
                })

        elif action_name in ("switch_branch", "switch"):
            name = str(act.get("name", "")).strip()
            has_changes = bool(
                context.get("status", {}).get("staged")
                or context.get("status", {}).get("modified")
                or context.get("status", {}).get("deleted")
                or context.get("status", {}).get("untracked")
            )
            validated_actions.append({
                "action": "switch_branch",
                "name": name,
                "requires_approval": has_changes,
                "approval_reason": "Switching branches with uncommitted changes could affect local work." if has_changes else None,
            })

        elif action_name == "push":
            remote = str(act.get("remote") or context.get("remote_status", {}).get("repo") or "origin").strip()
            branch = str(act.get("branch") or context.get("branch") or "main").strip()
            validated_actions.append({
                "action": "push",
                "remote": remote,
                "branch": branch,
                "requires_approval": True,
                "approval_reason": "This will publish local commits to the remote repository.",
            })

        elif action_name == "pull":
            remote = str(act.get("remote") or context.get("remote_status", {}).get("repo") or "origin").strip()
            branch = str(act.get("branch") or context.get("branch") or "main").strip()
            validated_actions.append({
                "action": "pull",
                "remote": remote,
                "branch": branch,
                "requires_approval": True,
                "approval_reason": "This will fetch remote commits and may alter the local working tree.",
            })

        elif action_name == "merge":
            branch = str(act.get("branch", "")).strip()
            validated_actions.append({
                "action": "merge",
                "branch": branch,
                "requires_approval": True,
                "approval_reason": f"This will merge branch '{branch}' into the current branch.",
            })

        elif action_name in ("reset", "hard_reset"):
            validated_actions.append({
                "action": "reset",
                "target": str(act.get("target", "HEAD")),
                "requires_approval": True,
                "approval_reason": "This will discard local commits or working changes irreversibly.",
            })

        elif action_name in ("delete", "delete_branch"):
            validated_actions.append({
                "action": "delete_branch",
                "name": str(act.get("name", "")).strip(),
                "requires_approval": True,
                "approval_reason": f"This will delete branch '{act.get('name')}'.",
            })

    complete = raw_plan.get("complete", False)
    if not validated_actions:
        complete = True

    return {
        "summary": summary,
        "reasoning": reasoning,
        "actions": validated_actions,
        "complete": complete,
    }


def _mark_symbol() -> str:
    import sys
    try:
        "✓".encode(sys.stdout.encoding or "ascii")
        return "✓"
    except Exception:
        return "[OK]"


def _horizontal_bar() -> str:
    import sys
    try:
        "─".encode(sys.stdout.encoding or "ascii")
        return "─" * 36
    except Exception:
        return "-" * 36


def _bullet_symbol() -> str:
    import sys
    try:
        "•".encode(sys.stdout.encoding or "ascii")
        return "•"
    except Exception:
        return "*"


def _dash_symbol() -> str:
    import sys
    try:
        "—".encode(sys.stdout.encoding or "ascii")
        return "—"
    except Exception:
        return "-"


def generate_post_activity_summary(
    root: Path,
    initial_context: dict[str, Any],
    final_context: dict[str, Any],
    activity_log: list[str],
    commits_created: list[dict[str, Any]],
) -> str:
    bar = _horizontal_bar()
    bullet = _bullet_symbol()
    dash = _dash_symbol()

    initial_head = initial_context.get("head_id")
    final_head = (commits_created[-1]["id"] if commits_created else None) or head_id(root)
    branch = final_context.get("branch") or current_branch(root) or "main"
    working_tree_clean = final_context.get("is_clean", True)
    working_tree_desc = "clean" if working_tree_clean else "uncommitted changes present"
    final_commit_display = final_head[:7] if final_head else "none"

    initial_files: dict[str, str] = {}
    if initial_head:
        try:
            initial_files = read_commit(root, initial_head).get("files", {})
        except Exception:
            initial_files = {}

    final_files: dict[str, str] = {}
    if commits_created:
        final_files = dict(commits_created[-1].get("files", {}))
    elif final_head:
        try:
            final_files = read_commit(root, final_head).get("files", {})
        except Exception:
            final_files = {}

    added = sorted(set(final_files.keys()) - set(initial_files.keys()))
    modified = sorted([f for f in set(initial_files.keys()) & set(final_files.keys()) if initial_files[f] != final_files[f]])
    deleted = sorted(set(initial_files.keys()) - set(final_files.keys()))

    diff_lines: list[str] = []
    for path in added:
        new_text = object_text(root, final_files[path]).splitlines(keepends=True)
        diff_lines.extend(difflib.unified_diff([], new_text, fromfile=f"a/{path}", tofile=f"b/{path}"))
    for path in modified:
        old_text = object_text(root, initial_files[path]).splitlines(keepends=True)
        new_text = object_text(root, final_files[path]).splitlines(keepends=True)
        diff_lines.extend(difflib.unified_diff(old_text, new_text, fromfile=f"a/{path}", tofile=f"b/{path}"))
    for path in deleted:
        old_text = object_text(root, initial_files[path]).splitlines(keepends=True)
        diff_lines.extend(difflib.unified_diff(old_text, [], fromfile=f"a/{path}", tofile=f"b/{path}"))

    full_diff = "".join(diff_lines)
    if len(full_diff) > 20000:
        full_diff = full_diff[:20000] + "\n[diff truncated]"

    commit_details = "\n".join(
        f"Commit {c['id'][:7]}: {c['message']}" for c in commits_created
    ) or (f"Latest commit: {final_commit_display}" if final_head else "No new commits")

    gemini_summary: str | None = None
    try:
        prompt = POST_ACTION_SUMMARY_PROMPT_TEMPLATE.format(
            activities="\n".join(f"- {act}" for act in activity_log) or "- Inspected repository",
            commit_details=commit_details,
            diff=full_diff or "[No code changes]",
            branch=branch,
            working_tree_state=working_tree_desc,
            commit_id=final_commit_display,
        )
        ai_resp = generate_text(prompt, root).strip()
        if "What I did:" in ai_resp and "Final state:" in ai_resp:
            gemini_summary = ai_resp
    except Exception:
        gemini_summary = None

    if gemini_summary:
        return f"{bar}\nAI ACTIVITY SUMMARY\n{bar}\n\n{gemini_summary}"

    what_i_did_bullets = [f"{bullet} {act}" for act in activity_log] if activity_log else [f"{bullet} Inspected repository state"]

    what_changed_bullets = []
    diff_previous_bullets = []
    effect_bullets = []

    for path in added:
        what_changed_bullets.append(f"{bullet} Added {path}")
        diff_previous_bullets.append(f"{bullet} This file did not exist in the previous commit.")
        effect_bullets.append(f"{bullet} The repository now contains the new test file." if "test" in path else f"{bullet} The repository now contains {path}.")

    for path in modified:
        what_changed_bullets.append(f"{bullet} {path} {dash} updated implementation")
        diff_previous_bullets.append(f"{bullet} Previous state: {path} had previous contents.")
        diff_previous_bullets.append(f"{bullet} Current state: {path} has new modifications applied.")
        effect_bullets.append(f"{bullet} Applied updates to {path}.")

    for path in deleted:
        what_changed_bullets.append(f"{bullet} Removed {path}")
        diff_previous_bullets.append(f"{bullet} {path} existed in the previous commit.")
        effect_bullets.append(f"{bullet} {path} was removed from the repository.")

    if not what_changed_bullets:
        what_changed_bullets.append(f"{bullet} No tracked files were modified.")
        diff_previous_bullets.append(f"{bullet} Repository files match the previous state.")
        effect_bullets.append(f"{bullet} Repository state verified and up to date.")

    if commits_created:
        effect_bullets.append(f"{bullet} Created commit {commits_created[-1]['id'][:7]}: {commits_created[-1]['message']}")

    final_state_bullets = [
        f"{bullet} Branch: {branch}",
        f"{bullet} Working tree: {working_tree_desc}",
        f"{bullet} Commit: {final_commit_display}",
    ]

    parts = [
        f"{bar}",
        "AI ACTIVITY SUMMARY",
        f"{bar}",
        "",
        "What I did:",
        "\n".join(what_i_did_bullets),
        "",
        "What changed:",
        "\n".join(what_changed_bullets),
        "",
        "Difference from previous state:",
        "\n".join(diff_previous_bullets),
        "",
        "Effect:",
        "\n".join(effect_bullets),
        "",
        "Final state:",
        "\n".join(final_state_bullets),
    ]
    return "\n".join(parts)


def run_ai_autonomous(
    root: Path,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], Any] = print,
) -> bool:
    root = root.resolve()
    mark = _mark_symbol()
    output_fn("Analyzing repository...")

    initial_context = build_autonomous_context(root)
    initial_context["head_id"] = head_id(root)
    activity_log: list[str] = []
    commits_created: list[dict[str, Any]] = []
    actions_executed_total = 0

    for iteration in range(MAX_AGENT_ITERATIONS):
        context = initial_context if iteration == 0 else build_autonomous_context(root)

        # 1. Clean check on first iteration:
        if iteration == 0 and context["is_clean"]:
            remote_status = context.get("remote_status", {})
            if remote_status.get("status") == "ahead" and remote_status.get("ahead_count", 0) > 0:
                pass
            else:
                output_fn("\nRepository is clean.\nNo action is required.")
                return True

        # If repo is clean on later iterations:
        if iteration > 0 and context["is_clean"]:
            remote_status = context.get("remote_status", {})
            if remote_status.get("status") != "ahead":
                output_fn(f"\n{mark} Repository workflow complete.")
                if actions_executed_total > 0:
                    summary_text = generate_post_activity_summary(
                        root, initial_context, context, activity_log, commits_created
                    )
                    output_fn(f"\n{summary_text}")
                return True

        if iteration == 0 and not context["is_clean"]:
            output_fn("\nAnalyzing changes...")
            mod_count = len(context["status"]["modified"])
            untr_count = len(context["status"]["untracked"])
            if mod_count + untr_count > 0:
                parts = []
                if mod_count > 0:
                    parts.append(f"{mod_count} modified")
                if untr_count > 0:
                    parts.append(f"{untr_count} untracked")
                activity_log.append(f"Detected {' and '.join(parts)} file(s)")

        # 2. Query Gemini for action plan
        context_json = json.dumps(context, ensure_ascii=False, indent=2)
        prompt = AUTONOMOUS_AGENT_PROMPT_TEMPLATE.format(context_json=context_json)

        try:
            raw_response = generate_text(prompt, root)
        except Exception as exc:
            output_fn(f"\nAI reasoning failed ({exc}).")
            return False

        # 3. Clean and parse JSON
        clean_json = raw_response.strip()
        if "```" in clean_json:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_json)
            if match:
                clean_json = match.group(1).strip()

        plan_data: dict[str, Any] = {}
        try:
            plan_data = json.loads(clean_json)
        except json.JSONDecodeError:
            start = clean_json.find("{")
            end = clean_json.rfind("}")
            if start != -1 and end != -1:
                try:
                    plan_data = json.loads(clean_json[start : end + 1])
                except json.JSONDecodeError:
                    output_fn(f"\nUnable to parse AI action plan:\n{raw_response}")
                    return False
            else:
                output_fn(f"\nUnable to parse AI action plan:\n{raw_response}")
                return False

        # 4. Validate action plan
        plan = validate_action_plan(plan_data, context, root)

        summary = plan.get("summary")
        if summary and summary != "Repository is clean. No action is required." and iteration == 0:
            output_fn(f"\n{summary}\n")

        if plan.get("complete") or not plan.get("actions"):
            if iteration == 0:
                output_fn(f"\n{summary or 'Repository is clean. No action is required.'}")
            else:
                output_fn(f"\n{mark} Repository workflow complete.")
                if actions_executed_total > 0:
                    final_context = build_autonomous_context(root)
                    summary_text = generate_post_activity_summary(
                        root, initial_context, final_context, activity_log, commits_created
                    )
                    output_fn(f"\n{summary_text}")
            return True

        # 5. Execute actions in plan
        actions_executed = 0
        for action in plan["actions"]:
            act_type = action["action"]

            # Approvals for dangerous / externally visible operations
            if action.get("requires_approval"):
                if act_type == "push":
                    remote = action.get("remote", "origin")
                    branch = action.get("branch", current_branch(root) or "main")
                    ahead = context.get("remote_status", {}).get("ahead_count", 1)
                    if not confirm_push(remote=remote, branch=branch, commits_ahead=ahead, input_fn=input_fn, output_fn=output_fn):
                        output_fn("Push canceled by user.")
                        if actions_executed_total > 0:
                            final_context = build_autonomous_context(root)
                            summary_text = generate_post_activity_summary(
                                root, initial_context, final_context, activity_log, commits_created
                            )
                            output_fn(f"\n{summary_text}")
                        return True

                elif act_type == "pull":
                    remote = action.get("remote", "origin")
                    branch = action.get("branch", current_branch(root) or "main")
                    has_uncommitted = not context["is_clean"]
                    if not confirm_pull(remote=remote, branch=branch, input_fn=input_fn, output_fn=output_fn, warn_overwrite=has_uncommitted):
                        output_fn("Pull canceled by user.")
                        return True

                elif act_type == "merge":
                    target_branch = action.get("branch", "")
                    curr_b = current_branch(root) or "main"
                    if not confirm_merge(source_branch=target_branch, target_branch=curr_b, input_fn=input_fn, output_fn=output_fn):
                        output_fn("Merge canceled by user.")
                        return True

                else:
                    reason = action.get("approval_reason", "This operation is irreversible.")
                    target_desc = action.get("name") or action.get("target") or act_type
                    if not confirm_dangerous_operation(operation=act_type, target=target_desc, effect=reason, input_fn=input_fn, output_fn=output_fn):
                        output_fn(f"Operation '{act_type}' canceled by user.")
                        return True

            # Execution of safe or approved action
            if act_type == "stage":
                files = action["files"]
                output_fn("Staging the relevant files...")
                add(root, files)
                activity_log.append("Staged the related changes")
                actions_executed += 1
                actions_executed_total += 1

            elif act_type == "commit":
                message = action["message"]
                index = load_index(root)
                if not index:
                    rules = load_gitignore(root)
                    candidates = [
                        p for p in context["status"]["modified"] + context["status"]["untracked"]
                        if not is_sensitive_path(p) and not is_ignored_path(p, rules) and (root / p).exists()
                    ]
                    if candidates:
                        output_fn("Staging the relevant files...")
                        add(root, candidates)
                        activity_log.append("Staged the related changes")
                output_fn("Generating commit message...")
                activity_log.append("Generated a commit message")
                output_fn("Committing...")
                commit = create_commit(root, message)
                commits_created.append(commit)
                activity_log.append(f"Created commit {commit['id'][:7]}")
                output_fn(f"\n{mark} Committed:\n  [{commit['id'][:7]}] {commit['message']}")
                actions_executed += 1
                actions_executed_total += 1

            elif act_type == "create_branch":
                bname = action["name"]
                output_fn(f"Creating branch '{bname}'...")
                create_branch(root, bname)
                activity_log.append(f"Created branch '{bname}'")
                output_fn(f"{mark} Created branch '{bname}'")
                actions_executed += 1
                actions_executed_total += 1

            elif act_type == "switch_branch":
                bname = action["name"]
                output_fn(f"Switching to branch '{bname}'...")
                switch_branch(root, bname)
                activity_log.append(f"Switched to branch '{bname}'")
                output_fn(f"{mark} Switched to branch '{bname}'")
                actions_executed += 1
                actions_executed_total += 1

            elif act_type == "push":
                remote = action.get("remote", "origin")
                branch = action.get("branch")
                target_b = branch or (current_branch(root) or "main")
                output_fn(f"Pushing to {remote}/{target_b}...")
                try:
                    res = push(root, remote, branch)
                    activity_log.append(f"Pushed to {remote}/{target_b}")
                    output_fn(f"{mark} {res.get('message', 'Pushed successfully.')}")
                    actions_executed += 1
                    actions_executed_total += 1
                except Exception as exc:
                    output_fn(f"Push failed: {exc}")
                    return False

            elif act_type == "pull":
                remote = action.get("remote", "origin")
                branch = action.get("branch")
                target_b = branch or (current_branch(root) or "main")
                output_fn(f"Pulling from {remote}/{target_b}...")
                try:
                    res = pull(root, remote, branch)
                    activity_log.append(f"Pulled from {remote}/{target_b}")
                    output_fn(f"{mark} {res.get('message', 'Pulled successfully.')}")
                    actions_executed += 1
                    actions_executed_total += 1
                except Exception as exc:
                    output_fn(f"Pull failed: {exc}")
                    return False

            elif act_type == "merge":
                target_branch = action.get("branch", "")
                output_fn(f"Merging '{target_branch}'...")
                success = run_ai_merge(root, target_branch, input_fn=input_fn, output_fn=output_fn)
                if not success:
                    return False
                activity_log.append(f"Merged branch '{target_branch}'")
                actions_executed += 1
                actions_executed_total += 1

        if actions_executed == 0:
            break

    output_fn(f"\n{mark} Repository workflow complete.")
    if actions_executed_total > 0:
        final_context = build_autonomous_context(root)
        summary_text = generate_post_activity_summary(
            root, initial_context, final_context, activity_log, commits_created
        )
        output_fn(f"\n{summary_text}")
    return True