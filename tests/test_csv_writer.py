"""Tests for app.csv_writer."""
from __future__ import annotations

import csv
from pathlib import Path

from app.csv_writer import CSV_FIELDS, _cell, _row_from_job, list_results, write_csv


def test_cell_handles_none() -> None:
    assert _cell(None) == ""


def test_cell_handles_bool() -> None:
    assert _cell(True) == "True"
    assert _cell(False) == "False"


def test_cell_handles_other_types() -> None:
    assert _cell(42) == "42"
    assert _cell("hello") == "hello"
    assert _cell(3.14) == "3.14"


def test_row_from_job_complete() -> None:
    job = {
        "title": "SWE",
        "company": "Acme",
        "work_mode": "Remote",
        "location": "NYC",
        "salary": "$100k",
        "posted": "2026-05-01",
        "url": "https://example.com",
        "source": "LinkedIn",
        "is_nonprofit_or_h1b_cap_exempt": True,
        "why_match": "Great fit",
    }
    row = _row_from_job(job)
    assert row["type"] == "Remote"
    assert row["link"] == "https://example.com"
    assert row["posting_date"] == "2026-05-01"
    assert row["is_nonprofit_or_h1b_cap_exempt"] == "True"
    assert set(row.keys()) == set(CSV_FIELDS)


def test_row_from_job_missing_nonprofit_becomes_blank() -> None:
    row = _row_from_job({"title": "x"})
    assert row["is_nonprofit_or_h1b_cap_exempt"] == ""
    assert row["title"] == "x"
    assert row["company"] == ""


def test_row_from_job_explicit_false_is_kept() -> None:
    row = _row_from_job({"is_nonprofit_or_h1b_cap_exempt": False})
    assert row["is_nonprofit_or_h1b_cap_exempt"] == "False"


def test_write_csv_creates_file_with_header(tmp_path: Path) -> None:
    out = write_csv([], results_dir=tmp_path)
    assert out.exists()
    with out.open() as f:
        rows = list(csv.reader(f))
    assert rows[0] == CSV_FIELDS
    assert len(rows) == 1


def test_write_csv_writes_jobs(tmp_path: Path) -> None:
    jobs = [
        {"title": "A", "company": "X", "work_mode": "Remote", "url": "u"},
        {"title": "B", "company": "Y"},
    ]
    out = write_csv(jobs, results_dir=tmp_path)
    with out.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["title"] == "A"
    assert rows[0]["type"] == "Remote"
    assert rows[1]["company"] == "Y"


def test_write_csv_creates_results_dir(tmp_path: Path) -> None:
    nested = tmp_path / "newdir" / "results"
    out = write_csv([{"title": "x"}], results_dir=nested)
    assert out.exists()
    assert nested.exists()


def test_write_csv_filename_pattern(tmp_path: Path) -> None:
    out = write_csv([], results_dir=tmp_path)
    assert out.name.startswith("jobs_")
    assert out.suffix == ".csv"


def test_list_results_empty_for_missing_dir(tmp_path: Path) -> None:
    assert list_results(results_dir=tmp_path / "does_not_exist") == []


def test_list_results_returns_metadata(tmp_path: Path) -> None:
    (tmp_path / "jobs_20260101_000000.csv").write_text("title\nA\n")
    (tmp_path / "jobs_20260102_000000.csv").write_text("title\nB\nC\nD\n")
    (tmp_path / "ignore.txt").write_text("x")  # non-matching file is excluded

    info = list_results(results_dir=tmp_path)
    assert len(info) == 2
    # Newest first by filename ordering
    assert info[0]["filename"] == "jobs_20260102_000000.csv"
    assert info[1]["filename"] == "jobs_20260101_000000.csv"
    # Row count = lines minus header
    rows_by_name = {item["filename"]: item["rows"] for item in info}
    assert rows_by_name["jobs_20260101_000000.csv"] == 1
    assert rows_by_name["jobs_20260102_000000.csv"] == 3
    # Each entry has size and timestamp
    for item in info:
        assert isinstance(item["size_bytes"], int)
        assert "T" in item["created_at"]


def test_list_results_skips_unreadable_entries(tmp_path: Path) -> None:
    """A directory matching the glob can't be opened as a file -> entry is skipped."""
    (tmp_path / "jobs_bad.csv").mkdir()
    (tmp_path / "jobs_good.csv").write_text("title\nA\n")
    info = list_results(results_dir=tmp_path)
    assert len(info) == 1
    assert info[0]["filename"] == "jobs_good.csv"
