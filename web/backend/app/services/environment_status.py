from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ..config import DB_PATH, ROOT, WEB_RUNTIME_DIR


WEB_EXPORTS_DIR = ROOT / "temp" / "web_exports"
CANDIDATE_EXPORTS_DIR = ROOT / "temp" / "candidate_exports"
HISTORY_EXPORTS_DIR = ROOT / "temp" / "history_exports"


class EnvironmentStatusService:
    """Build a sanitized read-only workbench environment summary."""

    module = "environment_status"

    def status(self) -> dict[str, Any]:
        git = self._git_status()
        return {
            "module": self.module,
            "readonly": True,
            "read_only": True,
            "current_only": True,
            "ratio_only": True,
            "git": git,
            "paths": {
                "project_root": ".",
                "temp_dir": "temp",
                "web_db_path": self._repo_path(DB_PATH),
                "web_runtime_dir": self._repo_path(WEB_RUNTIME_DIR),
                "web_exports_dir": self._repo_path(WEB_EXPORTS_DIR),
                "candidate_exports_dir": self._repo_path(CANDIDATE_EXPORTS_DIR),
                "history_exports_dir": self._repo_path(HISTORY_EXPORTS_DIR),
            },
            "web": {
                "default_host": "0.0.0.0",
                "default_port": 8000,
                "current_host": "unknown",
                "current_port": "unknown",
                "phase10_recommended_port": 8010,
                "lan_mode": True,
                "lan_mode_enabled": True,
                "readonly_mode": True,
            },
            "safety": {
                "read_only": True,
                "no_trading": True,
                "no_qmt_write": True,
                "no_execution_generation": True,
                "ratio_only": True,
                "current_only": True,
                "research_first_gate_required": True,
                "research_current_mutation": False,
            },
            "checks": {
                "hidden_unicode": "unknown",
                "ingest_status": "ok" if DB_PATH.exists() else "unknown",
                "web_check_status": "unknown",
                "web_check": "unknown",
                "ratio_only_status": "unknown",
                "research_first_status": "unknown",
                "allocation_consistency_status": "unknown",
                "project_check_status": "unknown",
            },
        }

    def _git_status(self) -> dict[str, Any]:
        branch = self._git(["branch", "--show-current"]) or "unknown"
        commit = self._git(["rev-parse", "HEAD"]) or "unknown"
        dirty = bool(self._git(["status", "--porcelain"]))
        baseline_tag = self._baseline_tag()
        worktree = self._worktree_summary()
        return {
            "branch": branch,
            "current_branch": branch,
            "commit": commit,
            "current_commit": commit,
            "dirty": dirty,
            "dirty_status": "dirty" if dirty else "clean",
            "baseline_tag": baseline_tag,
            "worktree_path": ".",
            "is_worktree": worktree["is_worktree"],
            "main_repo_path": worktree["main_repo_path"],
        }

    def _baseline_tag(self) -> str:
        exact = self._git(["describe", "--tags", "--exact-match", "HEAD"])
        if exact:
            return exact
        nearest = self._git(["describe", "--tags", "--abbrev=0", "HEAD"])
        if nearest:
            return nearest
        tags = self._git(["tag", "--points-at", "HEAD"])
        if not tags:
            return "unknown"
        return tags.splitlines()[0].strip() or "unknown"

    def _worktree_summary(self) -> dict[str, Any]:
        output = self._git(["worktree", "list", "--porcelain"])
        if not output:
            return {"is_worktree": False, "main_repo_path": "unknown"}

        entries: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for line in output.splitlines():
            if not line.strip():
                if current:
                    entries.append(current)
                    current = {}
                continue
            key, _, value = line.partition(" ")
            current[key] = value.strip()
        if current:
            entries.append(current)

        current_root = ROOT.resolve()
        current_entry = next(
            (entry for entry in entries if self._same_path(entry.get("worktree", ""), current_root)),
            None,
        )
        main_entry = next(
            (entry for entry in entries if entry.get("branch", "").endswith("/main")),
            None,
        )
        main_label = "unknown"
        if main_entry and main_entry.get("worktree"):
            main_label = f"redacted:{Path(main_entry['worktree']).name}"
        return {
            "is_worktree": len(entries) > 1 and current_entry is not None,
            "main_repo_path": main_label,
        }

    @staticmethod
    def _same_path(candidate: str, target: Path) -> bool:
        if not candidate:
            return False
        try:
            return Path(candidate).resolve() == target
        except OSError:
            return False

    @staticmethod
    def _repo_path(path: Path) -> str:
        try:
            return path.resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            return "redacted_path"

    @staticmethod
    def _git(args: list[str]) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            return ""
        return proc.stdout.strip()
