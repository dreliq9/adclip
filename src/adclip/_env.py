"""Minimal stdlib .env loader. No new dependency.

Call `load()` early in CLI/MCP entrypoints. Reads `.env` from the project
root (walks up from cwd until one is found or filesystem root is hit).
Only sets keys that aren't already in os.environ — explicit env always wins.
"""

from __future__ import annotations

import os
from pathlib import Path


def _find_dotenv(start: Path | None = None) -> Path | None:
    # 1. Walk up from cwd (respects user-supplied override in any dir).
    here = (start or Path.cwd()).resolve()
    for p in (here, *here.parents):
        candidate = p / ".env"
        if candidate.exists():
            return candidate
    # 2. Fallback: .env at the adclip project root, regardless of cwd.
    #    This lets the MCP server find .env even when spawned from elsewhere.
    #    __file__ is src/adclip/_env.py; project root is three parents up.
    project_env = Path(__file__).resolve().parents[2] / ".env"
    if project_env.exists():
        return project_env
    return None


def load(path: Path | None = None) -> None:
    env_path = path or _find_dotenv()
    if env_path is None or not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
