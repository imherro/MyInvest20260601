#!/usr/bin/env python3
"""Build and verify a review package for MyInvest.

The package is intended for manual ChatGPT review. It includes project logic,
scripts, templates, and the decision log, while excluding runtime/temp output,
local secrets, caches, archives, and database-like files.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "temp" / "review_packages"
PROJECT_NAME = "MyInvest"

INCLUDE_PREFIXES = [
    ".gitignore",
    "README.md",
    "requirements.txt",
    ".env.example",
    "package_review_safe.bat",
    "start_intraday_dashboard.bat",
    "refresh_qmt_portfolio_snapshot.bat",
    "docs/",
    "templates/",
    "scripts/",
]
ALWAYS_INCLUDE_RESEARCH_PREFIXES = [
    "research/config/",
    "research/logs/",
]
ALWAYS_INCLUDE_RESEARCH_FILES = {
    "research/latest_index.json",
    "research/alerts/intraday_rules.json",
    "research/config/liquidity_gate_registry.json",
    "research/themes/theme_registry.json",
    "research/etfs/etf_registry.json",
    "research/stocks/stock_registry.json",
    "research/portfolio/current_holdings_template.md",
}

EXCLUDE_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "runtime",
    "temp",
    "cache",
}

EXCLUDE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.test",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".zip",
    ".7z",
    ".rar",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".pem",
    ".key",
    ".pfx",
    ".p12",
}

SENSITIVE_NAME_RE = re.compile(
    r"(token|secret|password|passwd|credential|cookie|session|apikey|api_key)",
    re.IGNORECASE,
)

SECRET_CONTENT_RE = re.compile(
    r"(^\s*TUSHARE_TOKEN\s*=\s*\S+|api[_-]?key\s*[:=]\s*\S+|"
    r"secret\s*[:=]\s*\S+|password\s*[:=]\s*\S+|"
    r"authorization\s*:\s*bearer\s+\S+)",
    re.IGNORECASE,
)
PLACEHOLDER_SECRET_RE = re.compile(r"(你的|your|example|changeme|placeholder|可选)", re.IGNORECASE)
LOCAL_ABSOLUTE_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/](?:Users|Documents|ProgramData|Program Files|Windows)[^\"'\s,}]*|"
    r"/(?:Users|home)/[^\"'\s,}]*)",
    re.IGNORECASE,
)
LOCAL_RUNTIME_SOURCE_RE = re.compile(r"source_report.*runtime[\\/]", re.IGNORECASE)

PRIVACY_FIELD_NAMES = {
    "account",
    "account_masked",
    "available_quantity",
    "available_qty",
    "cost_price",
    "current_price",
    "full_account",
    "market_value",
    "masked_account",
    "profit_amount",
    "qty",
    "quantity",
    "raw_cost_price",
    "reference_pnl_pct",
    "share_count",
    "shares",
    "total_amount",
    "total_asset",
    "trade_amount",
}
PRIVACY_TEXT_RE = re.compile(
    r"(账号|成本价|现价|参考盈亏|总资产|金额|市值|股数|可用数量|交易金额|盈亏金额)",
    re.IGNORECASE,
)
PRIVACY_SCAN_TEXT_EXEMPT_PREFIXES = ("docs/", "scripts/", "templates/", "web/")
PRIVACY_SCAN_TEXT_EXEMPT_FILES = {
    "research/logs/decision_log.md",
    "research/portfolio/current_holdings_template.md",
}
SCANNER_IMPLEMENTATION_FILES = {
    "scripts/build_review_package.py",
    "scripts/web_check.py",
}

TEXT_SUFFIXES = {".md", ".txt", ".json", ".py", ".bat", ".toml", ".yml", ".yaml", ".cfg"}

REQUIRED_PACKAGE_FILES = [
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
    "research/alerts/intraday_rules.json",
]

FORBIDDEN_PACKAGE_PARTS = {".git", "runtime", "temp", "__pycache__"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_sensitive_research_file(rel_path: str) -> bool:
    """Exclude raw research evidence files that can carry private account context."""
    if rel_path.startswith("research/portfolio/portfolio_snapshot_"):
        return True
    if rel_path.startswith("research/stocks/") and rel_path != "research/stocks/stock_registry.json":
        return True
    if rel_path.startswith("research/etfs/") and rel_path != "research/etfs/etf_registry.json":
        return True
    if rel_path.startswith("research/valuations/"):
        return True
    return False


def current_research_files() -> set[str]:
    latest_path = ROOT / "research" / "latest_index.json"
    if not latest_path.exists():
        return set()
    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    result = set(ALWAYS_INCLUDE_RESEARCH_FILES)
    result.update(str(item.get("path")) for item in (latest.get("modules") or {}).values() if item.get("path"))
    for item in latest.get("files", []):
        module = item.get("module")
        path = item.get("path")
        if module in {"market_position_mapping", "bucket_registry"} and path:
            result.add(str(path))
    add_gate_evidence_files(result)
    return {item for item in result if not is_sensitive_research_file(item)}


def registry_profile_paths(codes: set[str]) -> set[str]:
    paths: set[str] = set()
    for rel, key in [("research/etfs/etf_registry.json", "etfs"), ("research/stocks/stock_registry.json", "stocks")]:
        data = read_stage_source_json(ROOT / rel)
        for item in data.get(key, []):
            code = re.sub(r"\D", "", str(item.get("code") or ""))
            if code not in codes:
                continue
            for field in ["last_profile_json", "last_profile_file"]:
                value = item.get(field)
                if value:
                    paths.add(str(value))
    return paths


def valuation_paths(codes: set[str]) -> set[str]:
    paths: set[str] = set()
    for code in codes:
        for path in (ROOT / "research" / "valuations").glob(f"valuation_{code}_*.*"):
            if path.suffix.lower() in {".json", ".md"}:
                paths.add(rel(path))
    return paths


def read_stage_source_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def add_gate_evidence_files(result: set[str]) -> None:
    liquidity_registry = read_stage_source_json(ROOT / "research" / "config" / "liquidity_gate_registry.json")
    for row in (liquidity_registry.get("instruments") or {}).values():
        source_profile = row.get("source_profile")
        if source_profile:
            result.add(str(source_profile))

    action_record = read_stage_source_json(ROOT / "research" / "latest_index.json").get("modules", {}).get("action_plan", {})
    action_path = action_record.get("path")
    action_plan = read_stage_source_json(ROOT / action_path) if action_path else {}
    executable_codes: set[str] = set()
    for action in action_plan.get("actions", []):
        action_type = str(action.get("action_type") or "").lower()
        if action_type not in {"buy", "add", "reduce", "sell"}:
            continue
        subject = action.get("subject") or {}
        code = re.sub(r"\D", "", str(subject.get("code") or ""))
        if code:
            executable_codes.add(code)
    result.update(registry_profile_paths(executable_codes))
    result.update(valuation_paths(executable_codes))


def include_path(path: Path, current_only: bool = True, current_research: set[str] | None = None) -> bool:
    rel_path = rel(path)
    parts = path.relative_to(ROOT).parts
    if any(part in EXCLUDE_PARTS for part in parts):
        return False
    if path.name in EXCLUDE_NAMES or path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if SENSITIVE_NAME_RE.search(path.name) and path.name != ".env.example":
        return False
    if rel_path.startswith("research/"):
        if not current_only:
            return True
        current_research = current_research or set()
        if rel_path in current_research:
            return True
        return any(rel_path.startswith(prefix) for prefix in ALWAYS_INCLUDE_RESEARCH_PREFIXES)
    return any(rel_path == prefix or rel_path.startswith(prefix) for prefix in INCLUDE_PREFIXES)


def collect_files(current_only: bool = True) -> list[Path]:
    current_research = current_research_files() if current_only else set()
    return sorted(path for path in ROOT.rglob("*") if path.is_file() and include_path(path, current_only, current_research))


def copy_stage(files: list[Path], stage: Path) -> list[str]:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    rels: list[str] = []
    for path in files:
        relative = rel(path)
        rels.append(relative)
        dest = stage / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    return rels


def scan_sensitive_content(stage: Path) -> tuple[list[str], list[str]]:
    secret_hits: list[str] = []
    privacy_warnings: list[str] = []
    for path in sorted(stage.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(stage).as_posix()
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception as exc:  # noqa: BLE001 - keep package build diagnostic.
            privacy_warnings.append(f"{relative}: unreadable text file: {exc}")
            continue
        secret_lines = []
        local_path_lines = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            if SECRET_CONTENT_RE.search(line) and not PLACEHOLDER_SECRET_RE.search(line):
                secret_lines.append(f"{relative}:{line_no}")
            if (
                not is_scanner_local_path_rule_text(relative, line)
                and (LOCAL_ABSOLUTE_PATH_RE.search(line) or LOCAL_RUNTIME_SOURCE_RE.search(line))
            ):
                local_path_lines.append(f"{relative}:{line_no}: local path or runtime source reference")
        if secret_lines:
            secret_hits.extend(secret_lines)
        if local_path_lines:
            secret_hits.extend(local_path_lines)
        if has_privacy_review_warning(relative, path, text):
            privacy_warnings.append(relative)
    return sorted(set(secret_hits)), sorted(set(privacy_warnings))


def is_scanner_local_path_rule_text(relative: str, line: str) -> bool:
    """Allow scanner source to document the local-path regex without self-failing."""
    if relative not in SCANNER_IMPLEMENTATION_FILES:
        return False
    return (
        (
            "LOCAL_PATH_RE" in line
            and "[A-Za-z]" in line
            and ("/Users/" in line or "/home/" in line)
        )
        or ('"/Users/"' in line and '"/home/"' in line)
    )


def has_privacy_review_warning(relative: str, path: Path, text: str) -> bool:
    if relative in PRIVACY_SCAN_TEXT_EXEMPT_FILES:
        return False
    if any(relative.startswith(prefix) for prefix in PRIVACY_SCAN_TEXT_EXEMPT_PREFIXES):
        return False
    if path.suffix.lower() == ".json":
        return json_has_privacy_key(text)
    return bool(PRIVACY_TEXT_RE.search(text))


def json_has_privacy_key(text: str) -> bool:
    try:
        data = json.loads(text)
    except Exception:
        return bool(PRIVACY_TEXT_RE.search(text))
    return object_has_privacy_key(data)


def object_has_privacy_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in PRIVACY_FIELD_NAMES:
                return True
            if object_has_privacy_key(child):
                return True
    elif isinstance(value, list):
        return any(object_has_privacy_key(item) for item in value)
    return False


def verify_stage(stage: Path, rels: list[str]) -> list[str]:
    errors: list[str] = []
    rel_set = set(rels)
    for required in REQUIRED_PACKAGE_FILES:
        if required not in rel_set:
            errors.append(f"missing required file: {required}")
    for item in rels:
        parts = set(Path(item).parts)
        bad = parts & FORBIDDEN_PACKAGE_PARTS
        if bad:
            errors.append(f"forbidden path part {sorted(bad)} in {item}")
    for item in rels:
        if item.endswith(".json"):
            path = stage / item
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:  # noqa: BLE001 - report exact parse issue.
                errors.append(f"invalid JSON in package: {item}: {exc}")
    return errors


def write_manifest(stage: Path, rels: list[str], timestamp: str, secret_hits: list[str], privacy_warnings: list[str], current_only: bool) -> None:
    lines = [
        "# MyInvest Review Package Manifest",
        "",
        f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"Timestamp: {timestamp}",
        "Source path: local repository root (full path omitted)",
        "",
        "## Scope",
        "",
        f"Mode: {'current-only' if current_only else 'full-history'}",
        "Included: README, .gitignore, .env.example, docs, templates, scripts, selected helper BAT files, and research audit/config/current artifacts.",
        "Excluded: .env, .git, runtime, temp, caches, virtual environments, archives, databases, logs outside research, and credential-like filenames.",
        "",
        "## Required Audit Files",
        "",
    ]
    rel_set = set(rels)
    for required in REQUIRED_PACKAGE_FILES:
        status = "present" if required in rel_set else "missing"
        lines.append(f"- {status}: `{required}`")
    lines.extend(["", "## Sensitive Scan", ""])
    if secret_hits:
        lines.append("Blocking secret-like content hits:")
        lines.extend(f"- `{item}`" for item in secret_hits)
    else:
        lines.append("No blocking secret-like content hits.")
    lines.append("")
    if privacy_warnings:
        lines.append("Privacy-review warnings. These may include portfolio or research context and should be reviewed before external sharing:")
        lines.extend(f"- `{item}`" for item in privacy_warnings[:200])
        if len(privacy_warnings) > 200:
            lines.append(f"- ... {len(privacy_warnings) - 200} more")
    else:
        lines.append("No privacy-review warnings.")
    lines.extend(["", "## File List", ""])
    lines.extend(f"- `{item}`" for item in rels)
    (stage / "REVIEW_PACKAGE_MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_file_lists(stage: Path, rels: list[str], secret_hits: list[str], privacy_warnings: list[str]) -> None:
    (stage / "FILE_LIST.txt").write_text("\n".join(rels) + "\n", encoding="utf-8")
    content_lines = ["# Sensitive Content Scan", ""]
    content_lines.append("## Blocking Secret-Like Hits")
    content_lines.extend(f"- {item}" for item in secret_hits) if secret_hits else content_lines.append("- none")
    content_lines.extend(["", "## Privacy Review Warnings"])
    content_lines.extend(f"- {item}" for item in privacy_warnings) if privacy_warnings else content_lines.append("- none")
    (stage / "SENSITIVE_CONTENT_SCAN.md").write_text("\n".join(content_lines) + "\n", encoding="utf-8")


def zip_stage(stage: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(stage).as_posix())


def build_package(timestamp: str, fail_on_privacy: bool = False, current_only: bool = True) -> tuple[Path, list[str], list[str]]:
    files = collect_files(current_only=current_only)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage = OUTPUT_DIR / f"myinvest_review_safe_{timestamp}"
    rels = copy_stage(files, stage)
    secret_hits, privacy_warnings = scan_sensitive_content(stage)
    errors = verify_stage(stage, rels)
    if secret_hits:
        errors.append("blocking secret-like content found; see SENSITIVE_CONTENT_SCAN.md")
    if fail_on_privacy and privacy_warnings:
        errors.append("privacy warnings found and --fail-on-privacy was set")
    write_file_lists(stage, rels, secret_hits, privacy_warnings)
    write_manifest(stage, rels, timestamp, secret_hits, privacy_warnings, current_only)
    if errors:
        (stage / "REVIEW_PACKAGE_ERRORS.txt").write_text("\n".join(errors) + "\n", encoding="utf-8")
        raise RuntimeError("; ".join(errors))

    zip_path = OUTPUT_DIR / f"{PROJECT_NAME}_review_safe_{timestamp}.zip"
    zip_stage(stage, zip_path)

    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/"))
    expected = sorted(["FILE_LIST.txt", "REVIEW_PACKAGE_MANIFEST.md", "SENSITIVE_CONTENT_SCAN.md"] + rels)
    if names != expected:
        missing = sorted(set(expected) - set(names))
        extra = sorted(set(names) - set(expected))
        raise RuntimeError(f"zip manifest mismatch; missing={missing[:10]} extra={extra[:10]}")
    return zip_path, rels, privacy_warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    parser.add_argument("--fail-on-privacy", action="store_true", help="Fail if portfolio/privacy warning terms are present.")
    parser.add_argument("--full-history", action="store_true", help="Include all timestamped research history. Default package is current-only.")
    args = parser.parse_args(argv)
    zip_path, rels, privacy_warnings = build_package(args.timestamp, fail_on_privacy=args.fail_on_privacy, current_only=not args.full_history)
    print(
        json.dumps(
            {
                "created": str(zip_path),
                "files": len(rels),
                "privacy_warnings": len(privacy_warnings),
                "verified": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
