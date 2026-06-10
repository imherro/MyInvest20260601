from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_hidden_unicode


ROOT = Path(__file__).resolve().parents[3]


def test_hidden_unicode_check_detects_bidi_control(tmp_path: Path):
    path = tmp_path / "sample.py"
    path.write_text("value = 'abc" + chr(0x202E) + "def'\n", encoding="utf-8")

    findings = check_hidden_unicode.scan_file(path)

    assert findings
    assert findings[0].codepoint == "U+202E"
    assert "<U+202E>" in findings[0].preview


def test_hidden_unicode_check_allows_regular_chinese(tmp_path: Path):
    path = tmp_path / "sample.md"
    text = "".join(map(chr, [0x666E, 0x901A, 0x4E2D, 0x6587, 0x6587, 0x672C]))
    path.write_text(text + "\n", encoding="utf-8")

    assert check_hidden_unicode.scan_file(path) == []


def test_current_pr_files_have_no_hidden_unicode_controls():
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        pytest.skip("origin/main is unavailable")

    files = [ROOT / line.strip() for line in proc.stdout.splitlines() if line.strip()]
    findings = []
    for path in files:
        if path.is_file() and path.suffix.lower() in check_hidden_unicode.TEXT_SUFFIXES:
            findings.extend(check_hidden_unicode.scan_file(path))

    assert findings == []


def test_hidden_unicode_cli_allows_regular_chinese(tmp_path: Path):
    path = tmp_path / "sample.md"
    text = "".join(map(chr, [0x4E2D, 0x6587]))
    path.write_text(text + " OK\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/check_hidden_unicode.py", str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    assert proc.returncode == 0
    assert "Hidden Unicode check: OK" in proc.stdout
    assert "scanned_file_count=1" in proc.stdout


def test_hidden_unicode_cli_paths_detects_bidi_control(tmp_path: Path):
    path = tmp_path / "sample.py"
    path.write_text("value = 'abc" + chr(0x202E) + "def'\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/check_hidden_unicode.py", "--paths", str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    assert proc.returncode == 1
    assert "Hidden Unicode check: FAIL" in proc.stdout
    assert "U+202E" in proc.stdout
    assert "<U+202E>" in proc.stdout
    assert "scanned_file_count=1" in proc.stdout


def test_hidden_unicode_cli_json_summary(tmp_path: Path):
    path = tmp_path / "sample.md"
    path.write_text("普通中文 OK\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "scripts/check_hidden_unicode.py", "--json", "--paths", str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["status"] == "OK"
    assert payload["scanned_file_count"] == 1
    assert payload["finding_count"] == 0


def test_current_repository_hidden_unicode_scan_is_ok():
    proc = subprocess.run(
        [sys.executable, "scripts/check_hidden_unicode.py", "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["status"] == "OK"
    assert payload["finding_count"] == 0
    assert payload["scanned_file_count"] > 0
