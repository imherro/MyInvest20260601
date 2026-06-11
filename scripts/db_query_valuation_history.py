#!/usr/bin/env python3
"""Query valuation history from the MyInvest history database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from myinvest.db.queries.valuation_history import format_json, format_markdown, query_valuation_history  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="temp/history_db/myinvest_history.sqlite3", help="SQLite database path.")
    parser.add_argument("--code", required=True, help="Security code, such as 688333.SH or 511360.SH.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--export", help="Optional output file path.")
    args = parser.parse_args(argv)

    rows = query_valuation_history(args.db, args.code)
    text = format_markdown(rows, args.code) if args.format == "markdown" else format_json(rows, args.code)
    if args.export:
        export_path = Path(args.export)
        if not export_path.is_absolute():
            export_path = ROOT / export_path
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
