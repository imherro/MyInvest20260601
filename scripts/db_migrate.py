#!/usr/bin/env python3
"""Apply or check MyInvest history database migrations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.migrations import apply_migrations, check_migrations  # noqa: E402


def print_summary(summary: dict) -> None:
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3", help="SQLite database path.")
    parser.add_argument("--check", action="store_true", help="Check migration state without modifying the DB.")
    parser.add_argument("--reset", action="store_true", help="Delete the DB before applying migrations.")
    parser.add_argument(
        "--i-know-this-deletes-data",
        action="store_true",
        help="Allow --reset outside temp/. Use only for explicitly managed local DB files.",
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            summary = check_migrations(args.db)
            print_summary(summary)
            return 0 if summary.get("status") == "ok" else 1

        summary = apply_migrations(
            args.db,
            reset=args.reset,
            allow_reset_outside_temp=args.i_know_this_deletes_data,
        )
        print_summary(summary)
        return 0 if summary.get("status") == "ok" else 1
    except Exception as exc:  # noqa: BLE001 - CLI should return a concise JSON failure.
        print_summary({"status": "failed", "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
