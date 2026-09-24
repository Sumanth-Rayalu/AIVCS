from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_BACKEND_URL = "http://localhost:8000"


def config_path() -> Path:
    return Path(os.environ.get("AIVCS_CONFIG", Path.home() / ".aivcsconfig.json"))


def load_config() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Invalid AIVCS config: {path}")
    return {str(key): str(item) for key, item in value.items()}


def set_config(key: str, value: str) -> None:
    values = load_config()
    values[key] = value
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")


def remote_config() -> dict[str, str]:
    values = load_config()
    return {
        "email": values.get("email", ""),
        "username": values.get("username", ""),
        "password": values.get("password", ""),
        "backend_url": values.get("backend_url", DEFAULT_BACKEND_URL).rstrip("/"),
    }