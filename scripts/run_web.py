from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
APP_IMPORT = "web.backend.app.main:app"
ROOT = Path(__file__).resolve().parents[1]


def ensure_repo_on_path() -> None:
    root = str(ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the read-only MyInvest Web UI.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host. Defaults to trusted-LAN access.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Bind port.")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload for local development.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ensure_repo_on_path()
    import uvicorn

    uvicorn.run(APP_IMPORT, host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
