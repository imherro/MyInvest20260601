#!/usr/bin/env python3
"""Query stock/ETF profile history from the MyInvest history database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.queries.security_research_history import format_json, query_security_research_history  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3")
    parser.add_argument("--code", required=True)
    args = parser.parse_args(argv)
    print(format_json(query_security_research_history(args.db, args.code), args.code))
    return 0


if __name__ == "__main__":
    sys.exit(main())
