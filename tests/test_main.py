"""Tests for the FastAPI app in app.main."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------- basic routes ----------


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "model" in body


def test_index_renders(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_favicon_redirects(client: TestClient) -> None:
    r = client.get("/favicon.ico", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/static/favicon.svg"


# ---------- /api/preferences ----------


def test_get_preferences_returns_stored(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        main_module.requirements_loader, "read_preferences", lambda: "stored prefs"
    )
    r = client.get("/api/preferences")
    assert r.status_code == 200
    assert r.json() == {"content": "stored prefs"}


def test_put_preferences_saves(client: TestClient, monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_write(content: str) -> None:
        captured["content"] = content

    monkeypatch.setattr(main_module.requirements_loader, "write_preferences", fake_write)
    r = client.put("/api/preferences", json={"content": "hello world"})
    assert r.status_code == 200
    assert r.json() == {"status": "saved"}
    assert captured["content"] == "hello world"


def test_put_preferences_rejects_empty(client: TestClient, monkeypatch) -> None:
    def boom(_content: str) -> None:
        raise ValueError("Refusing to save empty preferences.")

    monkeypatch.setattr(main_module.requirements_loader, "write_preferences", boom)
    r = client.put("/api/preferences", json={"content": "   "})
    assert r.status_code == 400
    assert "empty" in r.json()["detail"].lower()


def test_reload_preferences(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        main_module.requirements_loader, "read_preferences", lambda: "fresh content"
    )
    r = client.post("/api/preferences/reload")
    assert r.status_code == 200
    assert r.json() == {"content": "fresh content"}


# ---------- /api/search ----------


def test_search_with_empty_prefs_returns_400(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main_module.requirements_loader, "read_preferences", lambda: "")
    r = client.post("/api/search")
    assert r.status_code == 400
    assert "empty" in r.json()["detail"].lower()


def test_search_success_writes_csv(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        main_module.requirements_loader, "read_preferences", lambda: "must be remote"
    )

    fake_jobs = [
        {"title": "SWE", "company": "X", "work_mode": "Remote", "url": "https://e.com"}
    ]
    monkeypatch.setattr(main_module.agent, "search_jobs", lambda _prefs: fake_jobs)

    captured: dict[str, object] = {}

    def fake_write_csv(jobs):
        out = tmp_path / "jobs_test.csv"
        out.write_text("title\nSWE\n")
        captured["jobs"] = list(jobs)
        return out

    monkeypatch.setattr(main_module.csv_writer, "write_csv", fake_write_csv)

    r = client.post("/api/search")
    assert r.status_code == 200
    body = r.json()
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["title"] == "SWE"
    assert body["csv_filename"] == "jobs_test.csv"
    assert body["model"]
    assert body["elapsed_seconds"] >= 0
    assert captured["jobs"] == fake_jobs


def test_search_no_jobs_returns_no_csv(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        main_module.requirements_loader, "read_preferences", lambda: "x"
    )
    monkeypatch.setattr(main_module.agent, "search_jobs", lambda _prefs: [])

    called = {"write": False}

    def should_not_be_called(_jobs):
        called["write"] = True
        raise AssertionError("write_csv should not run when there are no jobs")

    monkeypatch.setattr(main_module.csv_writer, "write_csv", should_not_be_called)

    r = client.post("/api/search")
    assert r.status_code == 200
    assert r.json()["csv_filename"] is None
    assert called["write"] is False


def test_search_runtime_error_becomes_500(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        main_module.requirements_loader, "read_preferences", lambda: "x"
    )

    def boom(_prefs):
        raise RuntimeError("openai exploded")

    monkeypatch.setattr(main_module.agent, "search_jobs", boom)
    r = client.post("/api/search")
    assert r.status_code == 500
    assert "openai exploded" in r.json()["detail"]


def test_search_unknown_exception_becomes_502(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        main_module.requirements_loader, "read_preferences", lambda: "x"
    )

    def boom(_prefs):
        raise ValueError("totally unexpected")

    monkeypatch.setattr(main_module.agent, "search_jobs", boom)
    r = client.post("/api/search")
    assert r.status_code == 502
    assert "totally unexpected" in r.json()["detail"]


# ---------- /api/results ----------


def test_list_results(client: TestClient, monkeypatch) -> None:
    fake = [
        {
            "filename": "jobs_x.csv",
            "created_at": "2026-01-01T00:00:00",
            "rows": 3,
            "size_bytes": 100,
        }
    ]
    monkeypatch.setattr(main_module.csv_writer, "list_results", lambda: fake)
    r = client.get("/api/results")
    assert r.status_code == 200
    assert r.json() == {"results": fake}


def test_download_result(client: TestClient, monkeypatch, tmp_path: Path) -> None:
    f = tmp_path / "jobs_20260101_000000.csv"
    f.write_text("title\nA\n")
    monkeypatch.setattr(main_module, "RESULTS_DIR", tmp_path)
    r = client.get(f"/api/results/{f.name}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.text.startswith("title")


def test_download_result_path_traversal_rejected(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main_module, "RESULTS_DIR", tmp_path)
    # Anything that resolves outside of RESULTS_DIR should fail.
    r = client.get("/api/results/..%2Fescape.csv")
    # FastAPI may treat as 400 (rejected) or 404 (not found); either is fine.
    assert r.status_code in (400, 404)


def test_download_result_missing_returns_404(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main_module, "RESULTS_DIR", tmp_path)
    r = client.get("/api/results/jobs_missing.csv")
    assert r.status_code == 404


def test_download_result_wrong_extension_returns_400(
    client: TestClient, monkeypatch, tmp_path: Path
) -> None:
    f = tmp_path / "report.txt"
    f.write_text("hello")
    monkeypatch.setattr(main_module, "RESULTS_DIR", tmp_path)
    r = client.get("/api/results/report.txt")
    assert r.status_code == 400
