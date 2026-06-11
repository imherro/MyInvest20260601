#!/usr/bin/env python3
"""Query theme rating history from the MyInvest history database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.queries.theme_history import format_json, query_theme_history  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3")
    parser.add_argument("--theme")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args(argv)
    rows = query_theme_history(args.db, args.theme)[: args.limit]
    print(format_json(rows, args.theme))
    return 0


if __name__ == "__main__":
    sys.exit(main())
