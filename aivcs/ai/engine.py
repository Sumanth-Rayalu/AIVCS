from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Suppress noisy AFC warning from google-genai SDK
logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

import time

DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

_CONVENTIONAL_COMMIT = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([A-Za-z0-9._/-]+\))?!?: .{1,60}$"
)


def _find_project_env() -> Path | None:
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        cand = parent / ".env"
        if cand.is_file():
            return cand
    return None


def _load_api_credentials(root: Path | None = None) -> tuple[str, str]:
    # 1. First load the installed/project-level .env containing GEMINI_API_KEY
    project_env = _find_project_env()
    if project_env is not None and project_env.is_file():
        load_dotenv(project_env, override=False)
        backend_env = project_env.parent / "backend" / ".env"
        if backend_env.is_file():
            load_dotenv(backend_env, override=False)

    # 2. Also support repository-level .env if one exists
    if root is not None:
        repo_env = root / ".env"
        if repo_env.is_file():
            load_dotenv(repo_env, override=False)
        repo_backend = root / "backend" / ".env"
        if repo_backend.is_file():
            load_dotenv(repo_backend, override=False)

    # 3. Read GEMINI_API_KEY from environment (system or loaded from .env)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to the AIVCS project's .env file or environment."
        )

    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return api_key.strip(), model


def _create_client(api_key: str):
    try:
        from google import genai
    except ImportError as error:
        raise RuntimeError(
            "The Gemini SDK is missing. Reinstall with `pip install google-genai`."
        ) from error
    return genai.Client(api_key=api_key)


def generate_text(prompt: str, root: Path, model_override: str | None = None) -> str:
    api_key, default_model = _load_api_credentials(root)
    client = _create_client(api_key)

    chosen_model = model_override or default_model
    candidate_models = [chosen_model]
    for fallback in FALLBACK_MODELS:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

    last_error: Exception | None = None
    for model_name in candidate_models:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = (getattr(response, "text", None) or "").strip()
                if text:
                    return text
            except Exception as error:
                last_error = error
                err_str = str(error)
                # If daily quota is exhausted on this model, immediately switch to next model
                if "Quota exceeded" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    break
                # If temporary spike, wait briefly before retrying
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    time.sleep(1.0)
                    continue
                break

    raise RuntimeError(
        f"Gemini API request failed ({type(last_error).__name__}): {last_error}. "
        "Please check your GEMINI_API_KEY and network connection."
    ) from last_error


def generate_commit_message(context: dict[str, Any], root: Path) -> str:
    from .prompts import COMMIT_PROMPT_TEMPLATE

    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    prompt = COMMIT_PROMPT_TEMPLATE.format(context_json=context_json)

    raw_text = generate_text(prompt, root)
    message = raw_text.strip("`'\"").strip()

    # If response has multiple lines, take the first one that matches Conventional Commit
    lines = [l.strip("`'\"").strip() for l in message.splitlines() if l.strip()]
    matched = next((l for l in lines if _CONVENTIONAL_COMMIT.fullmatch(l)), None)
    if matched:
        return matched

    if lines and _CONVENTIONAL_COMMIT.fullmatch(lines[0]):
        return lines[0]

    raise RuntimeError(
        f"Gemini returned an invalid commit message: '{message}'. Try again or use `aivcs commit -m`."
    )