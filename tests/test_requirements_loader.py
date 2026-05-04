"""Tests for app.requirements_loader."""
from __future__ import annotations

import os as _os
from pathlib import Path

import pytest

from app.requirements_loader import read_preferences, write_preferences


def test_read_preferences_missing_returns_empty(tmp_path: Path) -> None:
    assert read_preferences(tmp_path / "nope.md") == ""


def test_read_preferences_returns_content(tmp_path: Path) -> None:
    p = tmp_path / "prefs.md"
    p.write_text("hello world", encoding="utf-8")
    assert read_preferences(p) == "hello world"


def test_write_preferences_creates_file_and_appends_newline(tmp_path: Path) -> None:
    p = tmp_path / "prefs.md"
    write_preferences("content", p)
    assert p.read_text(encoding="utf-8") == "content\n"


def test_write_preferences_preserves_existing_trailing_newline(tmp_path: Path) -> None:
    p = tmp_path / "prefs.md"
    write_preferences("content\n", p)
    assert p.read_text(encoding="utf-8") == "content\n"


def test_write_preferences_rejects_blank(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_preferences("   \n\t", tmp_path / "prefs.md")


def test_write_preferences_rejects_empty_string(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_preferences("", tmp_path / "prefs.md")


def test_write_preferences_creates_parent_dir(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "prefs.md"
    write_preferences("x", nested)
    assert nested.exists()


def test_write_preferences_cleans_up_temp_on_replace_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """If os.replace blows up, the temp file should not be left behind."""
    p = tmp_path / "prefs.md"

    def fail_replace(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(_os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        write_preferences("content", p)

    leftover = list(tmp_path.glob(".job_requirements_*.md.tmp"))
    assert leftover == []
    assert not p.exists()


def test_write_preferences_replace_failure_when_temp_already_gone(
    tmp_path: Path, monkeypatch
) -> None:
    """Cleanup should swallow OSError if the temp file was already removed."""
    p = tmp_path / "prefs.md"

    def fail_replace(src, _dst):
        # Pre-remove the temp file so the cleanup os.unlink also fails
        try:
            _os.unlink(src)
        except OSError:
            pass
        raise OSError("disk full")

    monkeypatch.setattr(_os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        write_preferences("content", p)
