"""Shared test fixtures and bootstrap.

We set a dummy OPENAI_API_KEY before any `app.*` module is imported so that
tests never need real credentials. Individual tests that exercise the
"missing key" branch override this via `monkeypatch`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
