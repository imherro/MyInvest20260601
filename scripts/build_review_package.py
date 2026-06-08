#!/usr/bin/env python3
"""Build a deterministic design-review package and verify manifest consistency."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "runtime" / "review_packages"
INCLUDE_PREFIXES = [
    "README.md",
    "requirements.txt",
    ".env.example",
    "start_intraday_dashboard.bat",
    "refresh_qmt_portfolio_snapshot.bat",
    "docs/",
    "templates/",
    "scripts/",
    "research/",
]
EXCLUDE_PARTS = {".git", "__pycache__", "runtime"}
EXCLUDE_SUFFIXES = {".pyc", ".zip"}
EXCLUDE_NAMES = {".env"}


def include_path(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    if any(part in EXCLUDE_PARTS for part in path.relative_to(ROOT).parts):
        return False
    if path.name in EXCLUDE_NAMES or path.suffix in EXCLUDE_SUFFIXES:
        return False
    return any(rel == prefix or rel.startswith(prefix) for prefix in INCLUDE_PREFIXES)


def collect_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*") if path.is_file() and include_path(path))


def manifest_text(files: list[Path], timestamp: str) -> str:
    rels = [path.relative_to(ROOT).as_posix() for path in files]
    required = [
        "scripts/project_check.py",
        "scripts/build_latest_index.py",
        "scripts/check_staleness.py",
        "scripts/build_review_package.py",
        "research/alerts/intraday_rules.json",
        "research/latest_index.json",
    ]
    rows = "\n".join(f"- `{item}`" for item in rels)
    missing_required = [item for item in required if item not in rels]
    missing_text = "\n".join(f"- `{item}`" for item in missing_required) if missing_required else "- 无"
    return f"""# MyInvest 设计审查包 Manifest

生成时间：{timestamp}

## 范围

包含 docs、templates、scripts、research、bat、README、requirements 和 .env.example。  
排除 .env、.git、runtime、__pycache__、zip、pyc。

## 必备文件缺失

{missing_text}

## 文件清单

{rows}
"""


def build_package(timestamp: str) -> tuple[Path, list[str]]:
    files = collect_files()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage = OUTPUT_DIR / f"myinvest_design_review_{timestamp}"
    stage.mkdir(parents=True, exist_ok=True)
    rels = [path.relative_to(ROOT).as_posix() for path in files]
    (stage / "FILE_LIST.txt").write_text("\n".join(rels) + "\n", encoding="utf-8")
    (stage / "REVIEW_PACKAGE_MANIFEST.md").write_text(manifest_text(files, timestamp), encoding="utf-8")

    zip_path = OUTPUT_DIR / f"myinvest_design_review_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(stage / "FILE_LIST.txt", "FILE_LIST.txt")
        archive.write(stage / "REVIEW_PACKAGE_MANIFEST.md", "REVIEW_PACKAGE_MANIFEST.md")
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())

    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/"))
    expected = sorted(["FILE_LIST.txt", "REVIEW_PACKAGE_MANIFEST.md"] + rels)
    if names != expected:
        missing = sorted(set(expected) - set(names))
        extra = sorted(set(names) - set(expected))
        raise RuntimeError(f"zip manifest mismatch; missing={missing[:10]} extra={extra[:10]}")
    return zip_path, rels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    args = parser.parse_args(argv)
    zip_path, rels = build_package(args.timestamp)
    print(json.dumps({"created": str(zip_path), "files": len(rels), "verified": True}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

