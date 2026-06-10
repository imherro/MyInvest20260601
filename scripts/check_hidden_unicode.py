from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SCAN_ROOTS = [
    ROOT / "scripts",
    ROOT / "web",
    ROOT / "docs",
    ROOT / "templates",
]

TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".rst",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "runtime",
    "temp",
    "venv",
}

HIDDEN_CODEPOINTS = {
    0x200B,  # zero width space
    0x200C,  # zero width non-joiner
    0x200D,  # zero width joiner
    0x200E,  # left-to-right mark
    0x200F,  # right-to-left mark
    0x202A,  # left-to-right embedding
    0x202B,  # right-to-left embedding
    0x202C,  # pop directional formatting
    0x202D,  # left-to-right override
    0x202E,  # right-to-left override
    0x2066,  # left-to-right isolate
    0x2067,  # right-to-left isolate
    0x2068,  # first strong isolate
    0x2069,  # pop directional isolate
    0xFEFF,  # byte order mark / zero width no-break space
}


@dataclass(frozen=True)
class HiddenUnicodeFinding:
    path: Path
    line: int
    column: int
    codepoint: str
    name: str
    preview: str

    def format(self) -> str:
        return (
            f"{self.path.as_posix()}:{self.line}:{self.column}: "
            f"{self.codepoint} {self.name} preview={self.preview}"
        )


def is_hidden_unicode(char: str) -> bool:
    return ord(char) in HIDDEN_CODEPOINTS or unicodedata.category(char) == "Cf"


def safe_preview(line: str, column: int, radius: int = 24) -> str:
    start = max(0, column - radius - 1)
    end = min(len(line), column + radius)
    chars: list[str] = []
    for char in line[start:end].rstrip("\r\n"):
        if is_hidden_unicode(char):
            chars.append(f"<U+{ord(char):04X}>")
        elif char == "\t":
            chars.append("\\t")
        elif char == "\r":
            chars.append("\\r")
        elif char == "\n":
            chars.append("\\n")
        elif unicodedata.category(char).startswith("C"):
            chars.append(f"<U+{ord(char):04X}>")
        else:
            chars.append(char)
    return "".join(chars)


def scan_text(text: str, path: Path) -> list[HiddenUnicodeFinding]:
    findings: list[HiddenUnicodeFinding] = []
    for line_no, line in enumerate(text.splitlines(keepends=True), 1):
        for column, char in enumerate(line, 1):
            if is_hidden_unicode(char):
                codepoint = f"U+{ord(char):04X}"
                name = unicodedata.name(char, "UNKNOWN")
                findings.append(
                    HiddenUnicodeFinding(
                        path,
                        line_no,
                        column,
                        codepoint,
                        name,
                        safe_preview(line, column),
                    )
                )
    return findings


def scan_file(path: Path) -> list[HiddenUnicodeFinding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return scan_text(text, path)


def iter_scan_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix.lower() in TEXT_SUFFIXES:
                files.append(path)
            continue
        for item in path.rglob("*"):
            if item.is_dir():
                continue
            rel_parts = item.relative_to(path).parts
            if any(part in SKIP_DIRS for part in (*path.relative_to(ROOT).parts, *rel_parts) if part):
                continue
            if item.suffix.lower() in TEXT_SUFFIXES:
                files.append(item)
    return sorted(set(files))


def display_path(path: Path) -> Path:
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError:
        return path


def finding_to_dict(finding: HiddenUnicodeFinding) -> dict[str, object]:
    return {
        "path": display_path(finding.path).as_posix(),
        "line": finding.line,
        "column": finding.column,
        "codepoint": finding.codepoint,
        "name": finding.name,
        "preview": finding.preview,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan source files for hidden Unicode format controls.")
    parser.add_argument("positional_paths", nargs="*", help="Optional files or directories to scan.")
    parser.add_argument("--paths", nargs="+", help="Explicit files or directories to scan.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable JSON summary.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    requested_paths = [*(args.paths or []), *args.positional_paths]
    roots = [Path(path).resolve() for path in requested_paths] if requested_paths else DEFAULT_SCAN_ROOTS
    findings: list[HiddenUnicodeFinding] = []
    files = iter_scan_files(roots)
    for path in files:
        findings.extend(scan_file(path))

    summary = {
        "status": "FAIL" if findings else "OK",
        "scanned_file_count": len(files),
        "finding_count": len(findings),
        "findings": [finding_to_dict(finding) for finding in findings],
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1 if findings else 0

    if findings:
        print("Hidden Unicode check: FAIL")
        for finding in findings:
            print(
                HiddenUnicodeFinding(
                    display_path(finding.path),
                    finding.line,
                    finding.column,
                    finding.codepoint,
                    finding.name,
                    finding.preview,
                ).format()
            )
        print(f"scanned_file_count={len(files)}")
        return 1

    print("Hidden Unicode check: OK")
    print(f"scanned_file_count={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
