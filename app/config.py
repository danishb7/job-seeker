"""Centralised configuration: env vars and absolute paths."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
APP_DIR: Path = PROJECT_ROOT / "app"
TEMPLATES_DIR: Path = APP_DIR / "templates"
STATIC_DIR: Path = APP_DIR / "static"
RESULTS_DIR: Path = PROJECT_ROOT / "results"
PREFERENCES_FILE: Path = PROJECT_ROOT / "job_requirements.md"

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.5")

# web_search: "low" uses fewer TPM than "medium"/"high" (helps avoid 429 rate limits).
_raw_ctx = (os.getenv("OPENAI_SEARCH_CONTEXT_SIZE") or "low").strip().lower()
OPENAI_SEARCH_CONTEXT_SIZE: str = (
    _raw_ctx if _raw_ctx in ("low", "medium", "high") else "low"
)

def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


# Cap completion size (JSON job list). Tune via env if responses truncate.
OPENAI_MAX_OUTPUT_TOKENS: int = _int_env("OPENAI_MAX_OUTPUT_TOKENS", 6144, 1024)

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
