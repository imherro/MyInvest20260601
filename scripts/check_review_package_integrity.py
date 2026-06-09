#!/usr/bin/env python3
"""Verify a staged or zipped MyInvest review package."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path


REQUIRED_FILES = [
    ".gitignore",
    "README.md",
    "docs/DATA_SOURCES.md",
    "docs/FILE_NAMING.md",
    "docs/MODULES.md",
    "docs/RUNBOOK.md",
    "scripts/project_check.py",
    "scripts/build_latest_index.py",
    "scripts/build_review_package.py",
    "research/logs/decision_log.md",
    "research/latest_index.json",
    "research/config/bucket_registry.json",
    "research/config/market_position_mapping.json",
    "research/alerts/intraday_rules.json",
    "REVIEW_PACKAGE_MANIFEST.md",
    "SENSITIVE_CONTENT_SCAN.md",
]
FORBIDDEN_PARTS = {".git", "runtime", "temp", "__pycache__"}


def check_dir(root: Path) -> list[str]:
    errors: list[str] = []
    files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    for item in REQUIRED_FILES:
        if item not in files:
            errors.append(f"missing required file: {item}")
    for item in files:
        bad = set(Path(item).parts) & FORBIDDEN_PARTS
        if bad:
            errors.append(f"forbidden path part {sorted(bad)} in {item}")
        if item.endswith(".json"):
            try:
                json.loads((root / item).read_text(encoding="utf-8-sig"))
            except Exception as exc:  # noqa: BLE001 - report parser detail.
                errors.append(f"invalid JSON: {item}: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Review package directory or zip file.")
    args = parser.parse_args(argv)
    target = args.path.resolve()
    if target.is_dir():
        errors = check_dir(target)
    elif target.is_file() and target.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(target) as archive:
                archive.extractall(tmp)
            errors = check_dir(Path(tmp))
    else:
        print(f"Unsupported package path: {target}")
        return 2
    if errors:
        print("Review package integrity: FAIL")
        for item in errors:
            print(f"[FAIL] {item}")
        return 1
    print("Review package integrity: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
