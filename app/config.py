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

_DEF_OPTS = os.getenv(
    "OPENAI_MODEL_OPTIONS", "gpt-5.5,gpt-5.5-mini,gpt-4o"
).strip()
_parts = [p.strip() for p in _DEF_OPTS.split(",") if p.strip()]
if len(_parts) != 3:
    raise ValueError(
        "OPENAI_MODEL_OPTIONS must contain exactly three comma-separated model IDs; "
        f"got {len(_parts)}: {_parts!r}"
    )
OPENAI_MODEL_OPTIONS: tuple[str, str, str] = (_parts[0], _parts[1], _parts[2])

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
_RAW_MODEL = (os.getenv("OPENAI_MODEL") or OPENAI_MODEL_OPTIONS[0]).strip()
OPENAI_MODEL: str = _RAW_MODEL if _RAW_MODEL else OPENAI_MODEL_OPTIONS[0]

if OPENAI_MODEL not in OPENAI_MODEL_OPTIONS:
    raise ValueError(
        "OPENAI_MODEL must be one of OPENAI_MODEL_OPTIONS: "
        f"{list(OPENAI_MODEL_OPTIONS)!r}; got {OPENAI_MODEL!r}"
    )

# Labels for toolbar select (slots 1–3). Override with OPENAI_MODEL_LABELS="A,B,C"
_label_raw = os.getenv("OPENAI_MODEL_LABELS", "").strip()
if _label_raw:
    _labels = [x.strip() for x in _label_raw.split(",")]
    if len(_labels) != 3:
        raise ValueError(
            "OPENAI_MODEL_LABELS must have exactly three comma-separated labels when set."
        )
    OPENAI_MODEL_LABELS: tuple[str, str, str] = (_labels[0], _labels[1], _labels[2])
else:
    OPENAI_MODEL_LABELS = ("Quality", "Balanced", "Economy")

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


# Cap completion (JSON job list). ~4096 fits 10 jobs + tool context (opt #7).
OPENAI_MAX_OUTPUT_TOKENS: int = _int_env("OPENAI_MAX_OUTPUT_TOKENS", 4096, 1024)

# Max web_search tool calls per Responses run (matches prompt + max_tool_calls; opt #2).
OPENAI_MAX_WEB_SEARCH_CALLS: int = max(
    1, min(_int_env("OPENAI_MAX_WEB_SEARCH_CALLS", 2, 1), 10)
)

# Prompt + normalisation cap for rationale text (opt #8).
WHY_MATCH_MAX_CHARS: int = max(
    40, min(_int_env("WHY_MATCH_MAX_CHARS", 100, 40), 500)
)


# reasoning.effort for gpt-5 / o-series when set (omit keyword entirely when empty).
_raw_eff = (os.getenv("OPENAI_REASONING_EFFORT") or "").strip().lower()
OPENAI_REASONING_EFFORT: str | None = (
    _raw_eff
    if _raw_eff
    in (
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
    )
    else None
)


def resolve_model(choice: str | None) -> str:
    """Return the model id to use: override if whitelisted, else default OPENAI_MODEL."""
    if choice is None or not str(choice).strip():
        return OPENAI_MODEL
    c = str(choice).strip()
    if c not in OPENAI_MODEL_OPTIONS:
        raise ValueError(
            "Unsupported model. Choose one of: "
            + ", ".join(OPENAI_MODEL_OPTIONS)
        )
    return c


def model_selector_rows() -> list[tuple[str, str]]:
    """(model_id, short_label) for Jinja / index template."""
    return [
        (OPENAI_MODEL_OPTIONS[0], OPENAI_MODEL_LABELS[0]),
        (OPENAI_MODEL_OPTIONS[1], OPENAI_MODEL_LABELS[1]),
        (OPENAI_MODEL_OPTIONS[2], OPENAI_MODEL_LABELS[2]),
    ]


def reasoning_params_for_model(model: str) -> dict[str, object]:
    """Pass reasoning.effort only for models that support it (opt #1-style token trim)."""
    if not OPENAI_REASONING_EFFORT:
        return {}
    m = model.lower()
    if m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3"):
        return {"reasoning": {"effort": OPENAI_REASONING_EFFORT}}
    return {}


RESULTS_DIR.mkdir(parents=True, exist_ok=True)
