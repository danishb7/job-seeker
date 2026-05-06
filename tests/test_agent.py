"""Tests for app.agent (OpenAI Responses API wrapper)."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest
from openai import APIStatusError

from app import agent
from app.agent import (
    MAX_JOBS,
    SYSTEM_PROMPT,
    _extract_json,
    _normalise_jobs,
    _retry_delay_after_429,
    search_jobs,
)
from app.config import OPENAI_MAX_WEB_SEARCH_CALLS


# ---------- _extract_json ----------


def test_extract_json_clean() -> None:
    assert _extract_json('{"jobs":[]}') == {"jobs": []}


def test_extract_json_with_json_fence() -> None:
    text = '```json\n{"jobs":[{"title":"x"}]}\n```'
    assert _extract_json(text) == {"jobs": [{"title": "x"}]}


def test_extract_json_with_plain_fence() -> None:
    text = '```\n{"jobs":[]}\n```'
    assert _extract_json(text) == {"jobs": []}


def test_extract_json_with_surrounding_prose() -> None:
    text = 'Here is your data: {"jobs":[{"title":"x"}]} thanks!'
    assert _extract_json(text) == {"jobs": [{"title": "x"}]}


def test_extract_json_empty_string() -> None:
    assert _extract_json("") == {"jobs": []}


def test_extract_json_unrecoverable_keeps_raw() -> None:
    out = _extract_json("totally not json")
    assert out["jobs"] == []
    assert out["_raw"] == "totally not json"


def test_extract_json_braces_present_but_invalid() -> None:
    text = "prefix {not valid json} suffix"
    out = _extract_json(text)
    assert out["jobs"] == []
    assert out["_raw"] == text


# ---------- _normalise_jobs ----------


def test_normalise_strips_whitespace() -> None:
    out = _normalise_jobs({"jobs": [{"title": "  hi ", "company": " A "}]})
    assert out[0]["title"] == "hi"
    assert out[0]["company"] == "A"


def test_normalise_returns_empty_for_non_list() -> None:
    assert _normalise_jobs({"jobs": "not a list"}) == []
    assert _normalise_jobs({}) == []


def test_normalise_skips_non_dict_items() -> None:
    out = _normalise_jobs({"jobs": ["bad", 5, None, {"title": "ok"}]})
    assert len(out) == 1
    assert out[0]["title"] == "ok"


def test_normalise_caps_at_max_jobs() -> None:
    payload = {"jobs": [{"title": f"job{i}"} for i in range(MAX_JOBS + 5)]}
    out = _normalise_jobs(payload)
    assert len(out) == MAX_JOBS


def test_normalise_handles_missing_fields() -> None:
    out = _normalise_jobs({"jobs": [{}]})
    assert out[0]["title"] == ""
    assert out[0]["salary"] is None
    assert out[0]["is_nonprofit_or_h1b_cap_exempt"] is None
    assert out[0]["posted"] is None


def test_normalise_preserves_nonprofit_flag() -> None:
    out = _normalise_jobs({"jobs": [{"is_nonprofit_or_h1b_cap_exempt": True}]})
    assert out[0]["is_nonprofit_or_h1b_cap_exempt"] is True


def test_normalise_truncates_why_match(monkeypatch) -> None:
    monkeypatch.setattr(agent, "WHY_MATCH_MAX_CHARS", 5)
    payload = {"jobs": [{"why_match": "abcdefghi"}]}
    out = _normalise_jobs(payload)
    assert out[0]["why_match"] == "abcde"


def test_system_prompt_mentions_web_search_cap() -> None:
    needle = str(OPENAI_MAX_WEB_SEARCH_CALLS)
    assert needle in SYSTEM_PROMPT


# ---------- _retry_delay_after_429 ----------


def test_retry_delay_uses_hint_from_message() -> None:
    exc = Exception("Please try again in 3.5s thanks")
    assert _retry_delay_after_429(exc, 0) == pytest.approx(4.0)


def test_retry_delay_falls_back_to_exponential() -> None:
    exc = Exception("rate limit")
    assert _retry_delay_after_429(exc, 0) == 2.0
    assert _retry_delay_after_429(exc, 1) == 4.0
    assert _retry_delay_after_429(exc, 2) == 8.0


def test_retry_delay_capped_at_32() -> None:
    exc = Exception("rate limit")
    assert _retry_delay_after_429(exc, 10) == 32.0


# ---------- search_jobs ----------


class _FakeResponse:
    """Stand-in for openai Responses object exposing only output_text."""

    def __init__(self, text: str) -> None:
        self.output_text = text


def _status_error(status_code: int, msg: str = "rate limit") -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(status_code, request=request)
    return APIStatusError(message=msg, response=response, body=None)


def test_search_jobs_no_key_raises(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        search_jobs("prefs")


def test_search_jobs_success(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "sk-test")
    fake_client = MagicMock()
    fake_client.responses.create.return_value = _FakeResponse(
        '{"jobs":[{"title":"SWE","company":"X","url":"https://e.com"}]}'
    )
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)

    out = search_jobs("prefs", model="gpt-test")
    assert len(out) == 1
    assert out[0]["title"] == "SWE"
    assert out[0]["company"] == "X"
    assert out[0]["url"] == "https://e.com"
    fake_client.responses.create.assert_called_once()
    call_kwargs = fake_client.responses.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-test"
    assert call_kwargs["max_tool_calls"] == OPENAI_MAX_WEB_SEARCH_CALLS
    assert "verbosity" in call_kwargs.get("text", {})


def test_search_jobs_uses_default_model(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(agent, "OPENAI_MODEL", "default-model")
    fake_client = MagicMock()
    fake_client.responses.create.return_value = _FakeResponse('{"jobs":[]}')
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)

    search_jobs("prefs")
    assert fake_client.responses.create.call_args.kwargs["model"] == "default-model"


def test_search_jobs_retries_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(agent.time, "sleep", lambda *_: None)

    fake_client = MagicMock()
    fake_client.responses.create.side_effect = [
        _status_error(429, "rate limit, try again in 1s"),
        _FakeResponse('{"jobs":[]}'),
    ]
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)

    out = search_jobs("prefs")
    assert out == []
    assert fake_client.responses.create.call_count == 2


def test_search_jobs_exhausts_429_retries(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(agent.time, "sleep", lambda *_: None)

    fake_client = MagicMock()
    fake_client.responses.create.side_effect = _status_error(429, "rate limit")
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)

    with pytest.raises(RuntimeError, match="Agent call failed"):
        search_jobs("prefs")
    assert fake_client.responses.create.call_count == agent._MAX_RATE_LIMIT_RETRIES


def test_search_jobs_non_429_status_error_raises(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "sk-test")

    fake_client = MagicMock()
    fake_client.responses.create.side_effect = _status_error(500, "server error")
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)

    with pytest.raises(RuntimeError, match="Agent call failed"):
        search_jobs("prefs")


def test_search_jobs_generic_exception_raises(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "sk-test")

    fake_client = MagicMock()
    fake_client.responses.create.side_effect = ValueError("boom")
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)

    with pytest.raises(RuntimeError, match="Agent call failed"):
        search_jobs("prefs")


def test_search_jobs_handles_empty_output(monkeypatch) -> None:
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "sk-test")
    fake_client = MagicMock()
    fake_resp = _FakeResponse("")
    fake_resp.output_text = None  # simulate missing attribute value
    fake_client.responses.create.return_value = fake_resp
    monkeypatch.setattr(agent, "OpenAI", lambda **_kwargs: fake_client)

    out = search_jobs("prefs")
    assert out == []
