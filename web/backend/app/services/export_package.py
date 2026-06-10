from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import ROOT
from .current_state import CurrentStateService
from .ratio_only import RatioOnlyService
from .research_first_gate import ResearchFirstGateService
from .system_check import SystemCheckService


class ReviewPackageExportService:
    source_modules = [
        "action_plan",
        "target_allocation",
        "intraday_rules",
        "portfolio_snapshot",
        "market_score",
        "market_position_mapping",
        "bucket_registry",
        "liquidity_gate_registry",
    ]

    def __init__(self, session: Session):
        self.current = CurrentStateService(session)
        self.session = session

    def payload(self) -> dict[str, Any]:
        sources = {module: self.current.source_for_module(module) for module in self.source_modules}
        package = {
            "package": {
                "name": "myinvest_current_review_package",
                "mode": "current-only",
                "generated_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                "boundary": "read-only ratio-only snapshot; no trading interface",
            },
            "sources": sources,
            "latest_index": self.current.latest_index(),
            "action_plan": self.current.action_plan(),
            "target_allocation": self.current.target_allocation(),
            "intraday_rules": self.current.intraday_rules(),
            "portfolio_snapshot": self.current.portfolio(),
            "market_score": self.current.market_score(),
            "market_position_mapping": self.current.market_position_mapping(),
            "bucket_registry": self.current_source_json("bucket_registry"),
            "liquidity_gate_registry": self.current_source_json("liquidity_gate_registry"),
            "research_first_gate": ResearchFirstGateService(self.session).check(),
            "decision_log": {"entries": self.current.decision_log_entries()},
            "system_checks": SystemCheckService(self.session).current(),
        }
        sanitized = RatioOnlyService.sanitize(package)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized

    def current_source_json(self, module: str) -> dict[str, Any] | None:
        artifact = self.current.current_artifact(module)
        if not artifact:
            return None
        path = self.resolve_repo_path(artifact["path"])
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            data = {"module": module, "parse_status": "unavailable", "source": artifact}
        sanitized = RatioOnlyService.sanitize(data)
        RatioOnlyService.assert_safe(sanitized)
        return sanitized

    @staticmethod
    def resolve_repo_path(value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            raise ValueError("absolute source path is not allowed")
        resolved = (ROOT / path).resolve()
        root = ROOT.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("source path escapes repository root")
        return resolved

    def zip_bytes(self, payload: dict[str, Any] | None = None) -> bytes:
        payload = payload or self.payload()
        files = {
            "manifest.json": {
                "package": payload["package"],
                "sources": payload["sources"],
                "files": [
                    "current_snapshot.json",
                    "action_plan.json",
                    "target_allocation.json",
                    "intraday_rules.json",
                    "portfolio_snapshot.json",
                    "market_position_mapping.json",
                    "bucket_registry.json",
                    "liquidity_gate_registry.json",
                    "decision_log.json",
                    "system_checks.json",
                ],
            },
            "current_snapshot.json": payload,
            "action_plan.json": payload["action_plan"],
            "target_allocation.json": payload["target_allocation"],
            "intraday_rules.json": payload["intraday_rules"],
            "portfolio_snapshot.json": payload["portfolio_snapshot"],
            "market_position_mapping.json": payload["market_position_mapping"],
            "bucket_registry.json": payload["bucket_registry"],
            "liquidity_gate_registry.json": payload["liquidity_gate_registry"],
            "decision_log.json": payload["decision_log"],
            "system_checks.json": payload["system_checks"],
        }
        RatioOnlyService.assert_safe(files)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True))
        return buffer.getvalue()
