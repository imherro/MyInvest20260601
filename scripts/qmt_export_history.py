#!/usr/bin/env python3
"""Export QMT local daily history to JSON.

Run this with the QMT bundled pythonw.exe when normal Python cannot import
xtquant binary extensions.
"""

import argparse
import json
import os
import sys
import traceback


def bootstrap_paths(qmt_site):
    qmt_site = os.path.abspath(qmt_site)
    qmt_root = os.path.abspath(os.path.join(qmt_site, os.pardir, os.pardir, os.pardir))
    for path in [os.path.join(qmt_root, "python", "DLLs"), os.path.join(qmt_root, "python", "Lib"), qmt_site]:
        sys.path.insert(0, path)


def export_history(codes, start, end):
    from xtquant import xtdata  # type: ignore

    items = {}
    errors = {}
    for code in codes:
        try:
            try:
                xtdata.download_history_data(code, period="1d", start_time=start, end_time=end)
            except Exception as exc:
                errors.setdefault(code, []).append("download_history_data: " + str(exc))
            data = xtdata.get_market_data_ex([], [code], period="1d", start_time=start, end_time=end, count=-1)
            frame = data.get(code)
            if frame is None or len(frame) == 0:
                errors.setdefault(code, []).append("empty daily history")
                continue
            rows = []
            for trade_date, row in frame.iterrows():
                rows.append(
                    {
                        "trade_date": str(trade_date),
                        "open": float(row.get("open", 0) or 0),
                        "high": float(row.get("high", 0) or 0),
                        "low": float(row.get("low", 0) or 0),
                        "close": float(row.get("close", 0) or 0),
                        "volume": float(row.get("volume", 0) or 0),
                        "amount": float(row.get("amount", 0) or 0),
                    }
                )
            items[code] = rows
        except Exception:
            errors.setdefault(code, []).append(traceback.format_exc())
    return {"items": items, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qmt-site", required=True)
    parser.add_argument("--codes", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    try:
        bootstrap_paths(args.qmt_site)
        payload = export_history(args.codes, args.start, args.end)
        payload.update(
            {
                "ok": not payload["errors"],
                "source": "qmt_xtdata_local_history",
                "period": "1d",
                "start": args.start,
                "end": args.end,
                "codes": args.codes,
            }
        )
    except Exception:
        payload = {"ok": False, "source": "qmt_xtdata_local_history", "errors": {"_fatal": [traceback.format_exc()]}}
    with open(args.output, "w", encoding="utf-8") as output_file:
        output_file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
