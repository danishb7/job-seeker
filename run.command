#!/usr/bin/env bash
# Double-click this file in Finder to start Job Seeker (macOS).
# First time: Terminal → chmod +x run.command
# If macOS blocks it: right-click → Open (once).

set -u
cd "$(dirname "$0")" || exit 1

if [[ -x ".venv/bin/python3" ]]; then
  PY=".venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo ""
  echo "  Python 3 not found."
  echo "  Install from https://www.python.org/downloads/macos/"
  echo "  Then create a venv and install deps (see README)."
  echo ""
  read -r -p "Press Enter to close..."
  exit 1
fi

"$PY" run_server.py
