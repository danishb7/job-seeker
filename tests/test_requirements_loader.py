"""Tests for preferences read / agent-only stripping."""
from __future__ import annotations

from pathlib import Path

from app.requirements_loader import read_for_agent, read_preferences


def test_read_preferences_round_trip_keeps_intro(tmp_path: Path, monkeypatch) -> None:
    md = "# Job Search Preferences\n\n> intro line\n\n## Location\n\nSC\n"
    p = tmp_path / "job_requirements.md"
    p.write_text(md, encoding="utf-8")
    monkeypatch.setattr("app.requirements_loader.PREFERENCES_FILE", p)
    assert "> intro line" in read_preferences()


def test_read_for_agent_removes_heading_and_quote(tmp_path: Path, monkeypatch) -> None:
    md = (
        "# Job Search Preferences\r\n\r\n"
        "> Save me in the modal.\r\n"
        "> second quote line\r\n\r\n"
        "## Job Titles\r\n\r\n"
        "- Coach\r\n"
    )
    p = tmp_path / "job_requirements.md"
    p.write_text(md, encoding="utf-8")
    monkeypatch.setattr("app.requirements_loader.PREFERENCES_FILE", p)
    out = read_for_agent()
    assert "# Job Search" not in out
    assert "> Save" not in out
    assert "## Job Titles" in out
    assert "- Coach" in out


def test_read_for_agent_drops_empty_minimum_bullet(tmp_path: Path, monkeypatch) -> None:
    md = (
        "## Salary\n\n"
        "- Minimum: (leave blank if no requirement)\n"
        "- Preferred:\n\n"
        "## End\n\nok\n"
    )
    p = tmp_path / "job_requirements.md"
    p.write_text(md, encoding="utf-8")
    monkeypatch.setattr("app.requirements_loader.PREFERENCES_FILE", p)
    out = read_for_agent()
    assert "- Minimum:" not in out
    assert "ok" in out
