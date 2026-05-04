"""Read and write the user-editable job_requirements.md file."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .config import PREFERENCES_FILE


def read_preferences(path: Path = PREFERENCES_FILE) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_preferences(content: str, path: Path = PREFERENCES_FILE) -> None:
    """Atomically replace the preferences file. Rejects empty content."""
    stripped = content.strip()
    if not stripped:
        raise ValueError("Refusing to save empty preferences.")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".job_requirements_", suffix=".md.tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content if content.endswith("\n") else content + "\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
