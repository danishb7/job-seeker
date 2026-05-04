"""FastAPI entrypoint for the Job Seeker agent."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import agent, csv_writer, requirements_loader
from .config import (
    OPENAI_MODEL,
    PREFERENCES_FILE,
    RESULTS_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from .schemas import PreferencesPayload, SearchResponse

app = FastAPI(title="Job Seeker", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/favicon.ico")
def favicon() -> RedirectResponse:
    """Browsers request /favicon.ico by default; redirect to our SVG icon."""
    return RedirectResponse(url="/static/favicon.svg", status_code=307)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "model": OPENAI_MODEL,
            "preferences_path": str(PREFERENCES_FILE.name),
        },
    )


@app.get("/api/preferences")
def get_preferences() -> dict[str, str]:
    return {"content": requirements_loader.read_preferences()}


@app.put("/api/preferences")
def put_preferences(payload: PreferencesPayload) -> dict[str, str]:
    try:
        requirements_loader.write_preferences(payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved"}


@app.post("/api/preferences/reload")
def reload_preferences() -> dict[str, str]:
    return {"content": requirements_loader.read_preferences()}


@app.post("/api/search", response_model=SearchResponse)
def run_search() -> SearchResponse:
    prefs = requirements_loader.read_preferences()
    if not prefs.strip():
        raise HTTPException(
            status_code=400,
            detail="job_requirements.md is empty. Add your preferences first.",
        )

    started = time.perf_counter()
    try:
        jobs = agent.search_jobs(prefs)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Agent call failed: {exc}"
        ) from exc

    elapsed = time.perf_counter() - started
    csv_path = csv_writer.write_csv(jobs) if jobs else None

    return SearchResponse(
        jobs=jobs,
        csv_filename=csv_path.name if csv_path else None,
        model=OPENAI_MODEL,
        elapsed_seconds=round(elapsed, 2),
    )


@app.get("/api/results")
def list_results() -> dict[str, list[dict[str, object]]]:
    return {"results": csv_writer.list_results()}


def _safe_results_path(filename: str) -> Path:
    candidate = (RESULTS_DIR / filename).resolve()
    try:
        candidate.relative_to(RESULTS_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filename.") from exc
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Result not found.")
    if candidate.suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Only CSV files are served.")
    return candidate


@app.get("/api/results/{filename}")
def download_result(filename: str) -> FileResponse:
    path = _safe_results_path(filename)
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename=path.name,
    )


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "model": OPENAI_MODEL})
