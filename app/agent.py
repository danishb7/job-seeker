"""OpenAI agent: Responses API + built-in web_search + structured JSON output."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from openai import APIStatusError, OpenAI

from .config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MAX_WEB_SEARCH_CALLS,
    OPENAI_MODEL,
    OPENAI_SEARCH_CONTEXT_SIZE,
    WHY_MATCH_MAX_CHARS,
    reasoning_params_for_model,
)

MAX_JOBS = 10

_MAX_RATE_LIMIT_RETRIES = 8
_RETRY_HINT_RE = re.compile(r"try again in ([\d.]+)\s*s", re.IGNORECASE)

_use_json_schema_env = (
    os.getenv("OPENAI_RESPONSE_JSON_SCHEMA", "true").strip().lower()
    not in ("0", "false", "no", "off")
)


def _job_list_json_schema(max_jobs: int, why_cap: int) -> dict[str, Any]:
    item = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "company": {"type": "string"},
            "location": {"type": "string"},
            "work_mode": {"type": "string"},
            "salary": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "is_nonprofit_or_h1b_cap_exempt": {
                "anyOf": [{"type": "boolean"}, {"type": "null"}]
            },
            "why_match": {"type": "string", "maxLength": why_cap},
            "posted": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "url": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": [
            "title",
            "company",
            "location",
            "work_mode",
            "salary",
            "is_nonprofit_or_h1b_cap_exempt",
            "why_match",
            "posted",
            "url",
            "source",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "maxItems": max_jobs,
                "items": item,
            }
        },
        "required": ["jobs"],
        "additionalProperties": False,
    }


JOB_LIST_JSON_SCHEMA: dict[str, Any] = _job_list_json_schema(
    MAX_JOBS, WHY_MATCH_MAX_CHARS
)

# Immutable system prompt: static prefix aids OpenAI prompt cache (opt #6).
SYSTEM_PROMPT = (
    "You find CURRENTLY OPEN US job postings that match the user's Markdown "
    "preferences.\n\n"
    f"Searching: call web_search at most {OPENAI_MAX_WEB_SEARCH_CALLS} times for "
    "the whole run — combine keywords in each query.\n\n"
    "Sources: prioritize LinkedIn, Indeed, Idealist, HigherEdJobs, university "
    "careers, non-profit boards. Verify postings exist and honour Must-Have / "
    "Exclude.\n\n"
    "Return at most "
    + str(MAX_JOBS)
    + " jobs — aim for that many when enough good listings exist — rank strongest "
    "first.\n"
    + f'"why_match" must be one short sentence under {WHY_MATCH_MAX_CHARS} chars; '
    "use null where unknown.\n\n"
    "Respond with JSON only matching the structured schema — no prose, no Markdown "
    "fences.\n"
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json(text: str) -> dict[str, Any]:
    """Fallback JSON extraction when structured outputs are unavailable."""
    if not text:
        return {"jobs": []}
    cleaned = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {"jobs": [], "_raw": text}


def _normalise_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("jobs", [])
    if not isinstance(raw, list):
        return []
    cap = WHY_MATCH_MAX_CHARS
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        wm = (item.get("why_match") or "").strip()
        if len(wm) > cap:
            wm = wm[:cap].rstrip()
        out.append(
            {
                "title": (item.get("title") or "").strip(),
                "company": (item.get("company") or "").strip(),
                "location": (item.get("location") or "").strip(),
                "work_mode": (item.get("work_mode") or "").strip(),
                "salary": item.get("salary") or None,
                "is_nonprofit_or_h1b_cap_exempt": item.get(
                    "is_nonprofit_or_h1b_cap_exempt"
                ),
                "why_match": wm,
                "posted": item.get("posted") or None,
                "url": (item.get("url") or "").strip(),
                "source": (item.get("source") or "").strip(),
            }
        )
        if len(out) >= MAX_JOBS:
            break
    return out[:MAX_JOBS]


def _retry_delay_after_429(exc: BaseException, attempt: int) -> float:
    m = _RETRY_HINT_RE.search(str(exc))
    if m:
        return float(m.group(1)) + 0.5
    return min(32.0, 2.0 * (2**attempt))


def search_jobs(preferences_md: str, model: str | None = None) -> list[dict[str, Any]]:
    """Run the agent and return a list of normalised job dicts."""
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    client = OpenAI(api_key=OPENAI_API_KEY)
    chosen_model = model or OPENAI_MODEL

    req: dict[str, Any] = dict(
        model=chosen_model,
        max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        tools=[
            {
                "type": "web_search",
                "search_context_size": OPENAI_SEARCH_CONTEXT_SIZE,
                "user_location": {
                    "type": "approximate",
                    "country": "US",
                    "region": "South Carolina",
                    "city": "Fort Mill",
                },
            }
        ],
        max_tool_calls=OPENAI_MAX_WEB_SEARCH_CALLS,
        parallel_tool_calls=True,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"USER PREFERENCES (Markdown):\n\n{preferences_md}",
            },
        ],
    )
    req.update(reasoning_params_for_model(chosen_model))

    if _use_json_schema_env:
        req["text"] = {
            "format": {
                "type": "json_schema",
                "name": "job_search_results",
                "strict": True,
                "schema": JOB_LIST_JSON_SCHEMA,
            },
            "verbosity": "low",
        }

    last_exc: BaseException | None = None
    response = None
    stripped_schema = False

    for attempt in range(_MAX_RATE_LIMIT_RETRIES):
        try:
            response = client.responses.create(**req)
            break
        except APIStatusError as exc:
            last_exc = exc
            if (
                not stripped_schema
                and exc.status_code in (400, 422)
                and req.get("text") is not None
                and _use_json_schema_env
            ):
                req.pop("text", None)
                stripped_schema = True
                continue
            if exc.status_code != 429 or attempt >= _MAX_RATE_LIMIT_RETRIES - 1:
                suffix = ""
                if exc.status_code == 429:
                    suffix = (
                        " — Tip: wait ~60s between searches; keep "
                        "OPENAI_SEARCH_CONTEXT_SIZE=low "
                        "(default). Upgrade TPM at platform.openai.com/account/"
                        "rate-limits if needed."
                    )
                raise RuntimeError("Agent call failed: " + str(exc) + suffix) from exc
            time.sleep(_retry_delay_after_429(exc, attempt))
        except Exception as exc:
            raise RuntimeError(f"Agent call failed: {exc}") from exc

    if response is None:
        raise RuntimeError(
            f"Agent call failed after {_MAX_RATE_LIMIT_RETRIES} tries: {last_exc}"
        ) from last_exc

    text = getattr(response, "output_text", None) or ""
    parsed: dict[str, Any]
    if not text.strip():
        parsed = {"jobs": []}
    else:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = _extract_json(text)

    return _normalise_jobs(parsed)
