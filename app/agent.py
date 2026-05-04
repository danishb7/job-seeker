"""OpenAI agent: uses the Responses API with the built-in web_search tool.

Returns a strict JSON shape so downstream code (UI cards + CSV) is deterministic.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import APIStatusError, OpenAI

from .config import (
    OPENAI_API_KEY,
    OPENAI_MAX_OUTPUT_TOKENS,
    OPENAI_MODEL,
    OPENAI_SEARCH_CONTEXT_SIZE,
)

# Hard cap keeps responses smaller (fewer tokens / TPM) and matches product limit.
MAX_JOBS = 10

# Retries for HTTP 429 (TPM / RPM). OpenAI often says "try again in Xs".
_MAX_RATE_LIMIT_RETRIES = 8
_RETRY_HINT_RE = re.compile(r"try again in ([\d.]+)\s*s", re.IGNORECASE)

_SYSTEM_SCHEMA = """
{
  "jobs": [
    {
      "title": string,
      "company": string,
      "location": string,
      "work_mode": "Remote" | "Hybrid" | "On-site" | "",
      "salary": string | null,
      "is_nonprofit_or_h1b_cap_exempt": boolean | null,
      "why_match": string,
      "posted": string | null,
      "url": string,
      "source": string
    }
  ]
}
"""

SYSTEM_PROMPT = (
    """You are a job-search assistant for a single user.

Your job: use the web_search tool to find CURRENTLY-OPEN US job postings that
match the user's preferences (provided in Markdown by the user message).

How to search:
- Use at most 4 web_search tool calls for the whole run (combine keywords in
  each query). Do not issue many small searches.
- In those searches, cast a wide enough net to surface enough listings to fill
  the job list (see Rules).
- Check multiple sources when possible: LinkedIn Jobs, Indeed, Idealist,
  HigherEdJobs, university career pages, non-profit job boards.
- Verify each posting page actually exists and looks active.
- Strongly prefer postings whose location, work mode, and company type
  match the preferences. Discard listings that clearly violate Must-Have
  or Exclude rules.

Return ONLY a single JSON object that conforms exactly to this schema and
NOTHING else (no prose, no markdown fences):
"""
    + _SYSTEM_SCHEMA
    + f"""

Rules:
- Return at most {MAX_JOBS} of the strongest matches — never more than {MAX_JOBS}.
  **Aim to return {MAX_JOBS} jobs whenever at least {MAX_JOBS} acceptable listings
  exist.** If you only find fewer strong matches, return all of those — but do not
  stop early when more good matches are still available from your searches.
  Rank best matches first.
- Keep "why_match" to one short sentence (under ~140 characters).
- Use null (not the string "N/A") for fields you cannot determine.
- "url" must be the direct link to the posting.
- "source" is the site/board the listing was found on.
- Do NOT include any text outside the JSON object.
"""
)


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from a model response."""
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
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
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
                "why_match": (item.get("why_match") or "").strip(),
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

    last_exc: BaseException | None = None
    response = None

    for attempt in range(_MAX_RATE_LIMIT_RETRIES):
        try:
            response = client.responses.create(
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
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"USER PREFERENCES (Markdown):\n\n{preferences_md}",
                    },
                ],
            )
            break
        except APIStatusError as exc:
            last_exc = exc
            if exc.status_code != 429 or attempt >= _MAX_RATE_LIMIT_RETRIES - 1:
                suffix = ""
                if exc.status_code == 429:
                    suffix = (
                        " — Tip: wait ~60s between searches; keep OPENAI_SEARCH_CONTEXT_SIZE=low "
                        "(default). Upgrade TPM at platform.openai.com/account/rate-limits if needed."
                    )
                raise RuntimeError("Agent call failed: " + str(exc) + suffix) from exc
            time.sleep(_retry_delay_after_429(exc, attempt))
        except Exception as exc:
            raise RuntimeError(f"Agent call failed: {exc}") from exc

    if response is None:
        raise RuntimeError(
            f"Agent call failed after {_MAX_RATE_LIMIT_RETRIES} tries: {last_exc}"
        ) from last_exc

    text = getattr(response, "output_text", "") or ""
    return _normalise_jobs(_extract_json(text))
