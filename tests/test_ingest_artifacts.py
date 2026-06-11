from __future__ import annotations

from pathlib import Path

from myinvest.db.ingest import extract_dependency_paths, normalize_module
from myinvest.db.privacy import scan_json_privacy


def test_privacy_scanner_flags_exact_amount_key_without_policy_false_positive() -> None:
    findings = scan_json_privacy({"amount_policy": "ratio-only", "amount": "10"})

    assert [item["path"] for item in findings] == ["amount"]


def test_privacy_scanner_flags_local_absolute_path() -> None:
    findings = scan_json_privacy({"path": r"C:\Users\kunpeng\Documents\secret.json"})

    assert findings[0]["reason"] == "local_absolute_path"


def test_extract_dependency_paths_from_source_files_and_required_dependencies() -> None:
    data = {
        "source_files": ["research/market/market_score_2026-06-11_090000.json"],
        "dependencies": {"required": [{"path": "research/themes/theme_review_2026-06-11_090000.json"}]},
    }

    assert extract_dependency_paths(data) == (
        "research/market/market_score_2026-06-11_090000.json",
        "research/themes/theme_review_2026-06-11_090000.json",
    )


def test_normalize_module_uses_research_directory_when_missing() -> None:
    path = Path("research/valuations/valuation_688333_SH_x_2026-06-11_090000.json")

    assert normalize_module(None, path) == "valuation_report"
