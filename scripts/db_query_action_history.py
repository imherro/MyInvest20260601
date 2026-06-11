#!/usr/bin/env python3
"""Query action history from the MyInvest history database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.queries.action_history import format_json, query_action_history  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3", help="SQLite database path.")
    parser.add_argument("--code", help="Subject code, such as 511360 or 688333.SH.")
    parser.add_argument("--action-type", help="Action type filter, such as Reduce.")
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args(argv)

    rows = query_action_history(args.db, code=args.code, action_type=args.action_type, limit=args.limit)
    print(format_json(rows, code=args.code, action_type=args.action_type))
    return 0


if __name__ == "__main__":
    sys.exit(main())
