"""Development / home-server entry point for the wasschluckter web app.

Usage:
    wasschluckter-web                         # binds 127.0.0.1:8000
    wasschluckter-web --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> int:
    parser = argparse.ArgumentParser(prog="wasschluckter-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (dev)")
    args = parser.parse_args()

    uvicorn.run(
        "fuel_analysis.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
