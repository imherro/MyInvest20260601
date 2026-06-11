#!/usr/bin/env python3
"""Query portfolio position history from the MyInvest history database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.queries.position_history import format_json, query_position_history  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3", help="SQLite database path.")
    parser.add_argument("--code", help="Security code, such as 511360.SH.")
    parser.add_argument("--bucket", help="Allocation bucket, such as defense.")
    args = parser.parse_args(argv)
    if not args.code and not args.bucket:
        parser.error("Use --code or --bucket")

    rows = query_position_history(args.db, code=args.code, bucket=args.bucket)
    print(format_json(rows, code=args.code, bucket=args.bucket))
    return 0


if __name__ == "__main__":
    sys.exit(main())
