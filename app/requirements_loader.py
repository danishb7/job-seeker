"""Read and write the user-editable job_requirements.md file."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from .config import PREFERENCES_FILE


def read_preferences(path: Path | None = None) -> str:
    p = path or PREFERENCES_FILE
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def read_for_agent(path: Path | None = None) -> str:
    """Strip editor boilerplate before sending preferences to the agent (opt #5).

    The on-disk file stays verbose for humans; the agent gets a shorter blob.
    """
    p = path or PREFERENCES_FILE
    raw = read_preferences(p).replace("\ufeff", "")
    if not raw.strip():
        return ""

    # Drop leading H1 if it matches the app's title
    rest = re.sub(
        r"^#\s+Job Search Preferences\s*\r?\n",
        "",
        raw,
        count=1,
        flags=re.IGNORECASE,
    )

    # Remove first contiguous blockquote (UI "Intro" / onboarding lines)
    bq_lines = rest.splitlines()
    i = 0
    while i < len(bq_lines) and bq_lines[i].lstrip().startswith(">"):
        i += 1
    rest = "\n".join(bq_lines[i:]).lstrip("\n")

    # Drop visibly empty templated bullets — keeps token count down without
    # removing real user bullets that mention "blank" incidentally much.
    lines = []
    for line in rest.splitlines():
        if re.match(
            r"^-\s*Minimum\s*:\s*(\(leave blank.*)?\s*$",
            line,
            re.IGNORECASE,
        ):
            continue
        if re.match(
            r"^-\s*Preferred\s*:\s*(\(leave blank.*)?\s*$",
            line,
            re.IGNORECASE,
        ):
            continue
        if re.search(r"\(leave blank if no requirement\)", line, re.IGNORECASE):
            low = line.lower().strip()
            if low.startswith("-") and len(low) < 80:
                continue
        lines.append(line)

    out = "\n".join(lines).strip()
    return out if out else raw.strip()


def write_preferences(content: str, path: Path | None = None) -> None:
    """Atomically replace the preferences file. Rejects empty content."""
    p = path or PREFERENCES_FILE
    stripped = content.strip()
    if not stripped:
        raise ValueError("Refusing to save empty preferences.")

    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".job_requirements_", suffix=".md.tmp", dir=str(p.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content if content.endswith("\n") else content + "\n")
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
