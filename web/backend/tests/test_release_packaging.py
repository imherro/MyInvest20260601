from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts import build_review_package as builder


def test_review_package_scan_allows_scanner_local_path_regex_literal(tmp_path: Path):
    scanner_dir = tmp_path / "scripts"
    scanner_dir.mkdir()
    (scanner_dir / "web_check.py").write_text(
        'LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\\\/]|\\\\\\\\|/Users/|/home/)")\n',
        encoding="utf-8",
    )

    secret_hits, privacy_warnings = builder.scan_sensitive_content(tmp_path)

    assert secret_hits == []
    assert privacy_warnings == []


@pytest.mark.parametrize(
    "local_path",
    [
        "C:/Users/example/private.json",
        r"C:\Users\example\private.json",
        "/Users/example/private.json",
        "/home/example/private.json",
    ],
)
def test_review_package_scan_blocks_real_local_paths(tmp_path: Path, local_path: str):
    (tmp_path / "payload.md").write_text(f"leak: {local_path}\n", encoding="utf-8")

    secret_hits, privacy_warnings = builder.scan_sensitive_content(tmp_path)

    assert secret_hits == ["payload.md:1: local path or runtime source reference"]
    assert privacy_warnings == []


def test_review_package_scan_blocks_privacy_json_keys(tmp_path: Path):
    payload_dir = tmp_path / "research" / "portfolio"
    payload_dir.mkdir(parents=True)
    (payload_dir / "payload.json").write_text(
        '{"holdings": [{"cost_price": "redacted"}]}\n',
        encoding="utf-8",
    )

    secret_hits, privacy_warnings = builder.scan_sensitive_content(tmp_path)

    assert secret_hits == []
    assert privacy_warnings == ["research/portfolio/payload.json"]


def test_current_research_files_exclude_raw_sensitive_evidence():
    current_files = builder.current_research_files()

    assert current_files
    assert not any(builder.is_sensitive_research_file(item) for item in current_files)


def test_review_package_build_passes_strict_privacy_scan():
    timestamp = "phase13a_regression"
    stage = builder.OUTPUT_DIR / f"myinvest_review_safe_{timestamp}"
    zip_path = builder.OUTPUT_DIR / f"{builder.PROJECT_NAME}_review_safe_{timestamp}.zip"

    try:
        package_path, rels, privacy_warnings = builder.build_package(
            timestamp,
            fail_on_privacy=True,
            current_only=True,
        )

        assert package_path == zip_path
        assert privacy_warnings == []
        assert "scripts/web_check.py" in rels
        assert not any(builder.is_sensitive_research_file(item) for item in rels)
        scan_text = (stage / "SENSITIVE_CONTENT_SCAN.md").read_text(encoding="utf-8")
        assert "## Blocking Secret-Like Hits\n- none" in scan_text
        assert "## Privacy Review Warnings\n- none" in scan_text
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if zip_path.exists():
            zip_path.unlink()
