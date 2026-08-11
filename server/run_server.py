"""Development launcher for the AI Workspace web application."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "accounting" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-core" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "platform-adapters" / "src"))


def load_local_env(path: Path) -> None:
    """Load simple KEY=VALUE settings without overwriting system variables."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def main() -> None:
    load_local_env(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Run AI Workspace locally")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening a browser tab",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    url = f"http://127.0.0.1:{args.port}"
    print(f"AI Workspace is starting at {url}", flush=True)
    print("Press Ctrl+C to stop the server.", flush=True)

    if not args.no_browser:
        timer = threading.Timer(1.25, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()

    uvicorn.run(
        "accounting_app.api:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
