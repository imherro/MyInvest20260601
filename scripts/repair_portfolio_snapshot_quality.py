#!/usr/bin/env python3
"""Create a repaired ratio-only portfolio snapshot from the latest saved QMT snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import qmt_portfolio_snapshot as qmt
from project_utils import ROOT, abs_path, latest_for_module, load_latest_index, read_json, rel_path


PORTFOLIO_DIR = ROOT / "research" / "portfolio"
DECISION_LOG = ROOT / "research" / "logs" / "decision_log.md"


def latest_snapshot_path() -> Path:
    index = load_latest_index()
    record = latest_for_module("portfolio_snapshot", index)
    if not record:
        raise RuntimeError("No latest portfolio_snapshot found.")
    return abs_path(record["path"])


def repair_quality(snapshot: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(snapshot)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    date = timestamp[:10]
    source_path = result.get("_source_path")
    names = qmt.name_maps()

    warnings = list((result.get("quality") or {}).get("warnings") or [])
    remaining_errors: list[dict[str, Any]] = []
    for error in (result.get("quality") or {}).get("errors") or []:
        if error.get("field") == "cost_price":
            warning = dict(error)
            warning["reason"] = "成本字段无效，已排除参考盈亏比例；该问题不阻断比例级仓位分析。"
            warnings.append(warning)
        else:
            remaining_errors.append(error)

    repaired_names = []
    for item in result.get("holdings", []):
        raw = qmt.plain_code(item.get("code", ""))
        mapped = names.get(raw)
        if mapped and (not item.get("name") or str(item.get("name")) == raw):
            item["name"] = mapped
            repaired_names.append(raw)

    result["version"] = "qmt_readonly_ratio_only_v1_quality_repaired"
    result["date"] = date
    result["generated_at"] = timestamp
    result["source"] = "qmt_snapshot_quality_repair_from_latest_saved_snapshot"
    result["repaired_from"] = source_path
    result["quality"] = {
        "status": "error" if remaining_errors else ("warning" if warnings else "ok"),
        "errors": remaining_errors,
        "warnings": warnings,
        "repairs": [
            {
                "type": "name_mapping",
                "codes": repaired_names,
                "reason": "补充 ETF/股票登记册中的正式名称。",
            },
            {
                "type": "cost_quality_downgrade",
                "reason": "无效成本字段不再使比例级组合快照整体 blocked；相关参考盈亏比例保持为空。",
            },
        ],
        "policy": "Invalid cost_price is excluded from reference_pnl_pct and kept as a warning; ratio-only bucket analysis remains usable.",
    }
    result["summary"]["one_line_conclusion"] = "QMT只读持仓快照质量修复版已生成；仅修复名称映射和成本字段质量等级，不新增金额、数量或交易结论。"
    result["decision_log_entry"] = (
        f"{date} QMT只读持仓快照质量修复：生成 portfolio_snapshot_{timestamp}.md/json；"
        f"基于 {source_path or 'latest'} 修复 515880 名称映射，并将无效成本字段降级为比例级警告；仍不保存市值、现金金额、盈亏金额、股数或账号全号。"
    )
    return result


def write_repaired(snapshot: dict[str, Any], sync_rules: bool) -> tuple[Path, Path, bool]:
    qmt.assert_no_sensitive_fields(snapshot)
    timestamp = snapshot["generated_at"]
    json_path = PORTFOLIO_DIR / f"portfolio_snapshot_{timestamp}.json"
    md_path = PORTFOLIO_DIR / f"portfolio_snapshot_{timestamp}.md"
    qmt.write_json(json_path, snapshot)
    md_path.write_text(qmt.render_markdown(snapshot), encoding="utf-8")
    synced = qmt.sync_intraday_rules(snapshot) if sync_rules else False
    DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DECISION_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n" + snapshot["decision_log_entry"] + "\n")
    return md_path, json_path, synced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Snapshot JSON to repair. Defaults to latest portfolio_snapshot.")
    parser.add_argument("--no-sync-rules", action="store_true", help="Do not sync intraday_rules.")
    args = parser.parse_args(argv)

    path = args.snapshot or latest_snapshot_path()
    snapshot = read_json(path, {})
    snapshot["_source_path"] = rel_path(path)
    repaired = repair_quality(snapshot)
    md_path, json_path, synced = write_repaired(repaired, sync_rules=not args.no_sync_rules)
    print(json.dumps({"created": [rel_path(md_path), rel_path(json_path)], "synced_intraday_rules": synced}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
