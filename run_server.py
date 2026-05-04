"""
Start Job Seeker without PowerShell scripts or a fixed port.

Usage (from this folder):
  python run_server.py

Double-clicking works if .py files are associated with Python.
"""
from __future__ import annotations

import os
import socket
import sys

# Project root = folder containing this file
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pick_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main() -> None:
    port = pick_free_port()
    url = f"http://127.0.0.1:{port}"
    print()
    print("  Job Seeker")
    print("  ----------")
    print(f"  Open in your browser:  {url}")
    print("  Press Ctrl+C here to stop the server.")
    print(flush=True)

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    main()
