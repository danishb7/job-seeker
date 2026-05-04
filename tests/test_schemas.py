"""Tests for app.schemas pydantic models."""
from __future__ import annotations

from app.schemas import Job, PreferencesPayload, ResultFileInfo, SearchResponse


def test_job_defaults() -> None:
    j = Job()
    assert j.title == ""
    assert j.company == ""
    assert j.salary is None
    assert j.is_nonprofit_or_h1b_cap_exempt is None
    assert j.posted is None


def test_job_full_payload() -> None:
    j = Job(
        title="SWE",
        company="Acme",
        location="Remote",
        work_mode="Remote",
        salary="$100k",
        is_nonprofit_or_h1b_cap_exempt=True,
        why_match="strong fit",
        posted="2026-05-01",
        url="https://example.com",
        source="LinkedIn",
    )
    assert j.title == "SWE"
    assert j.is_nonprofit_or_h1b_cap_exempt is True
    assert j.url == "https://example.com"


def test_search_response_defaults() -> None:
    resp = SearchResponse()
    assert resp.jobs == []
    assert resp.csv_filename is None
    assert resp.model == ""
    assert resp.elapsed_seconds == 0.0


def test_search_response_with_jobs() -> None:
    resp = SearchResponse(
        jobs=[Job(title="A")],
        csv_filename="jobs_x.csv",
        model="gpt-test",
        elapsed_seconds=1.5,
    )
    assert len(resp.jobs) == 1
    assert resp.jobs[0].title == "A"
    assert resp.csv_filename == "jobs_x.csv"
    assert resp.elapsed_seconds == 1.5


def test_preferences_payload() -> None:
    p = PreferencesPayload(content="hello")
    assert p.content == "hello"


def test_result_file_info() -> None:
    info = ResultFileInfo(
        filename="jobs_x.csv",
        created_at="2026-01-01T00:00:00",
        rows=5,
        size_bytes=128,
    )
    assert info.filename == "jobs_x.csv"
    assert info.rows == 5
    assert info.size_bytes == 128
