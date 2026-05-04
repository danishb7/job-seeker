# Job Seeker

A small FastAPI web app that uses an OpenAI agent (with the built-in
`web_search` tool) to find U.S. job postings that match preferences you
write in plain Markdown.

- One editable file (`job_requirements.md`) drives every search.
- Click **Find me jobs** to let the agent browse multiple job boards.
- Every run is auto-saved as a CSV in `results/`.
- Minimalist UI with a casual, friendly style.

## Setup

1. **Clone / open the folder** and create a virtual environment:

   ```
   python -m venv .venv
   ```

   Activate it:

   - Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
   - macOS / Linux: `source .venv/bin/activate`

2. **Install dependencies:**

   ```
   pip install -r requirements.txt
   ```

3. **Add your OpenAI API key.** Copy `.env.example` to `.env` and fill in
   your key:

   ```
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-5.5
   ```

   The model is configurable, so you can swap to `gpt-5`, `gpt-5-mini`,
   `gpt-4o`, etc. without touching code.

4. **Run the app** (recommended on Windows):

   **Easiest:** double-click **`run.bat`** in this folder (Explorer sets the
   working directory correctly).

   **From a terminal** (any of these work the same way):

   ```
   python run_server.py
   ```

   Or in PowerShell: **`.\run.bat`** (note the `.\` — PowerShell does not run
   `run.bat` without it). **`.\run.ps1`** only works if scripts are allowed; if
   you see *running scripts is disabled*, either use `python run_server.py` /
   `.\run.bat` instead, or run once with:

   ```
   powershell -ExecutionPolicy Bypass -File .\run.ps1
   ```

   To allow local scripts permanently (optional):

   ```
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

   The launcher picks a **free port** on `127.0.0.1` and prints the exact URL.
   Open that link in your browser.

   If you use the default `uvicorn app.main:app --reload` (port `8000`, host
   `0.0.0.0`), Windows may return **WinError 10013** (socket access forbidden).
   The launchers above avoid that.

5. Open the URL printed in the terminal (starts with `http://127.0.0.1:`).

## Using the app

- **Find me jobs** &mdash; Runs the agent. Results appear as cards and a
  CSV is auto-saved.
- **Job Requirements** &mdash; Opens a popup with your current
  preferences. Edit them in-browser. Choose:
  - **Save** &mdash; persist the file and close.
  - **Save & Search** &mdash; persist and immediately run a search.
  - **Cancel** &mdash; discard changes (with a guard if you've edited).
  - Keyboard: `Esc` cancels, `Ctrl/Cmd+S` saves.
- **Reload preferences** &mdash; Re-reads `job_requirements.md` from disk
  if you edited it externally.
- **Download CSV** &mdash; Hidden until the first successful run; then
  downloads the latest CSV.
- **History** &mdash; Hidden until at least one CSV exists. Lists every
  past run with its own download link.
- **Filter chips & Sort dropdown** &mdash; Refine the visible results
  client-side (Remote / Hybrid / Non-profit / Has salary, and sort by
  best match / newest / salary).
- **Per-card** &mdash; Open posting in a new tab, or copy its link.

## Editing your preferences

Open `job_requirements.md` (or use the **Job Requirements** button). Each
section is sent verbatim to the agent as Markdown. You can freely add,
remove, or rename sections; the agent will treat them as guidance.

## CSV output

Every search writes `results/jobs_YYYYMMDD_HHMMSS.csv` with these columns:

| Column | Description |
| --- | --- |
| `title` | Job title |
| `company` | Employer |
| `type` | Work mode (Remote / Hybrid / On-site) |
| `location` | City, State (or "Remote") |
| `salary` | As posted; blank if not listed |
| `posting_date` | As posted; blank if not listed |
| `link` | Direct URL to the posting |
| `source` | Site/board the listing was found on |
| `is_nonprofit_or_h1b_cap_exempt` | True / False / blank |
| `why_match` | One-line agent rationale |

Missing data is left as an empty cell so spreadsheets stay clean.

## Project layout

```
job-seeker/
  app/
    main.py
    agent.py
    csv_writer.py
    requirements_loader.py
    config.py
    schemas.py
    static/
      styles.css
      app.js
    templates/
      index.html
  results/
  job_requirements.md
  .env.example
  requirements.txt
  README.md
```

## Notes

- Search uses OpenAI's `web_search` tool with `search_context_size: high`
  and a user-location bias toward Fort Mill, SC.
- The agent is asked to return strict JSON; the response is parsed
  defensively (handles stray code fences) so the UI and CSV always get
  a clean list.
- Preferences are written atomically (temp file + rename) so a save
  never corrupts the file mid-write.
