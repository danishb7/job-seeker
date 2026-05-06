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
   OPENAI_MODEL_OPTIONS=gpt-5.5,gpt-5.5-mini,gpt-4o
   ```

   `OPENAI_MODEL` is the server default when a search sends no override; it **must**
   be one of the three IDs listed in `OPENAI_MODEL_OPTIONS`. The in-app **Model**
   dropdown uses the same list (labels optional via `OPENAI_MODEL_LABELS`) and your
   choice is stored per browser tab (`sessionStorage`). Swap model IDs only if all
   three support the Responses API + built-in `web_search` on your account.

4. **Run the app**

   **Windows — easiest:** double-click **`run.bat`** in this folder (Explorer
   sets the working directory correctly).

   **macOS — easiest:** double-click **`run.command`** in Finder.

   - **First time only:** open Terminal in this folder and run  
     `chmod +x run.command`  
     so Finder is allowed to execute it.
   - If macOS says the file cannot be verified: **right-click** `run.command` →
     **Open** → **Open** (you only need this once).
   - A Terminal window opens and prints the app URL. Leave it open while you
     use the browser; press **Ctrl+C** in that window to stop the server.
   - If you use a virtual environment, `run.command` prefers  
     `.venv/bin/python3` automatically when that exists.

   **From a terminal** (Windows, macOS, or Linux):

   ```
   python run_server.py
   ```

   On macOS/Linux you may need `python3` instead of `python`.

   **Windows only:** in PowerShell, **`.\run.bat`** (note the `.\`).  
   **`.\run.ps1`** only works if scripts are allowed; if you see *running scripts
   is disabled*, use `python run_server.py` or `.\run.bat`, or run once with:

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

- **Model** &mdash; Pick one of three whitelisted OpenAI models (same API key).
  The footer still shows your `.env` default; the status line after each run shows
  the model that actually searched.
- **Find me jobs** &mdash; Runs the agent (sends `{ "model": "..." }` in the POST
  body). Results appear as cards and a CSV is auto-saved.
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

Open `job_requirements.md` (or use the **Job Requirements** button). The file is
stored **verbatim**. When you search, the app sends a slightly trimmed copy to the
agent (drops the `# Job Search Preferences` title, the introductory `>` quote
block, and a few obvious empty placeholders) so browsing stays on-token while the
editor UI sees the full template.

You can freely add, remove, or rename sections; the agent will treat them as
guidance.

## Token / cost tuning

- **Two `web_search` calls** per run by default (`OPENAI_MAX_WEB_SEARCH_CALLS`),
  aligned with the system prompt and `max_tool_calls` on the Responses API.
- **Smaller output cap** (`OPENAI_MAX_OUTPUT_TOKENS`, default `4096`) so the model
  does not over-allocate completion budget.
- **Shorter system prompt** + **structured JSON** (`text.format` / json_schema) when
  the API accepts it; automatic one-time retry without schema if the platform
  rejects the format.
- **Tighter `why_match`** (`WHY_MATCH_MAX_CHARS`, default `100`).
- **`reasoning.effort`** for gpt-5 / o-series when you set `OPENAI_REASONING_EFFORT`
  (e.g. `minimal`).
- Preferences **stripping** for the agent-only payload (see above).

## Contributing

Use topic branches for larger changes — for example, token optimizations were developed
on `feature-optimize-tokens` — and open pull requests targeting `main`.

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
  run.command          # macOS: double-click to start (after chmod +x)
  run.bat              # Windows: double-click to start
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

- Search uses OpenAI's `web_search` tool with `search_context_size` defaulting to
  `low` (configurable via `OPENAI_SEARCH_CONTEXT_SIZE`) plus a Fort Mill, SC geo
  hint.
- The agent targets strict JSON (`json_schema` on the Responses API when
  supported), with defensive parsing fallback if outputs include stray prose or
  code fences.
- Preferences are written atomically (temp file + rename) so a save
  never corrupts the file mid-write.
