from __future__ import annotations

import fnmatch
import io
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "temp" / "web_db" / "myinvest.sqlite"
LATEST_INDEX = ROOT / "research" / "latest_index.json"
CANDIDATE_EXPORT_DIR = ROOT / "temp" / "candidate_exports"
HISTORY_EXPORT_DIR = ROOT / "temp" / "history_exports"
HISTORY_DB_PATH = ROOT / "temp" / "web_runtime" / "history_snapshot.sqlite"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMMIT_MESSAGE = "feat(web): add allocation drilldown and drill-through actions"

API_PATHS = [
    "/api/health",
    "/api/dashboard/current",
    "/api/current",
    "/api/latest-index",
    "/api/modules/current",
    "/api/subjects/status",
    "/api/subjects/status/511360.SH",
    "/api/subjects/freshness",
    "/api/subjects/gap",
    "/api/themes/status",
    "/api/buckets/drilldown?detail=full",
    "/api/subjects/drilldown?detail=full",
    "/api/subjects/drilldown?subject=511360.SH&detail=full",
    "/api/market-position/mapping",
    "/api/market-position/current",
    "/api/market-position/score/25",
    "/api/market-position/score/30",
    "/api/market-position/score/31",
    "/api/market-position/score/100",
    "/api/action-plan/current",
    "/api/target-allocation/current",
    "/api/target-allocation/shadow",
    "/api/target-allocation/shadow/compare",
    "/api/target-allocation/shadow/export?format=json",
    "/api/target-allocation/candidate-audit",
    "/api/target-allocation/candidate-audit?format=json",
    "/api/history/export",
    "/api/history/export?format=json",
    "/api/portfolio/current",
    "/api/intraday-rules/current",
    "/api/research-first/current",
    "/api/system-check/current",
    "/api/decision-log/current",
    "/api/export/review_package?format=json",
]

PAGE_PATHS = [
    "/",
    "/dashboard",
    "/action-plan",
    "/target-allocation",
    "/research-first",
    "/subjects",
    "/subjects/gap",
    "/themes",
    "/buckets/drilldown",
    "/subjects/drilldown",
    "/portfolio",
    "/intraday-rules",
    "/decision-log",
    "/system-checks",
]

INTERACTIVE_PAGE_CHECKS = {
    "/action-plan": ["data-table-search", "data-sort", "actionRows"],
    "/target-allocation": ["data-table-search", "data-sort", "targetRows"],
    "/subjects": ["data-table-search", "data-sort", "subjectsRows"],
    "/subjects/gap": ["data-table-search", "data-sort", "subjectGapRows"],
    "/themes": ["data-table-search", "data-table-filter", "data-sort", "themesRows"],
    "/buckets/drilldown": ["data-table-search", "data-table-filter", "data-sort", "bucketDrilldownRows", "bucketDrilldownChart"],
    "/subjects/drilldown": ["data-table-search", "data-table-filter", "data-sort", "subjectDrilldownRows"],
    "/portfolio": ["data-table-search", "data-sort", "portfolioRows"],
    "/intraday-rules": ["data-table-search", "data-sort", "intradayRows", "disabledTriggerRows"],
    "/decision-log": ["data-table-search", "data-sort", "decisionRows"],
}

DASHBOARD_CHECKS = [
    "bucketGapChart",
    'data-dashboard-section="system-status"',
    'data-dashboard-section="market-position"',
    'data-dashboard-section="action-plan-summary"',
    'data-dashboard-section="allocation-summary"',
    'data-dashboard-section="subject-summaries"',
    'data-dashboard-section="quick-links"',
    'data-status-card="system"',
    'data-status-card="research-first"',
    'data-status-card="intraday"',
]

JS_CHECKS = [
    "function assertRatioOnly",
    "function renderPagination",
    "function renderDashboardQuickLinks",
    "function renderSubjectStatus",
    "function renderSubjectGap",
    "function renderThemes",
    "function renderBucketDrilldown",
    "function renderBucketDrilldownChart",
    "function renderSubjectDrilldown",
    "function setupFilters",
    "detail-row",
    "expandable-row",
    "setInterval(refresh",
    "fetch(apiPath",
]

PHASE5A_TEST_FILES = [
    ROOT / "web" / "backend" / "tests" / "test_database_schema_contract.py",
    ROOT / "web" / "backend" / "tests" / "test_current_state_contract.py",
    ROOT / "web" / "backend" / "tests" / "test_golden_current_state.py",
]

PHASE5A_DOC_FILES = [
    ROOT / "web" / "docs" / "DATABASE_SCHEMA.md",
    ROOT / "web" / "docs" / "CURRENT_STATE_CONTRACT.md",
    ROOT / "web" / "docs" / "GOLDEN_REFERENCE.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
]

PHASE5C_TEST_FILES = [
    ROOT / "web" / "backend" / "tests" / "test_market_position_service.py",
]

PHASE5C2_TEST_FILES = [
    ROOT / "web" / "backend" / "tests" / "test_target_allocation_generation_shadow.py",
]

PHASE5C3_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "target_allocation_export.py",
    ROOT / "web" / "backend" / "tests" / "test_target_allocation_controlled_export.py",
    ROOT / "scripts" / "export_target_allocation_shadow.py",
]

PHASE5D_FILES = [
    ROOT / "web" / "backend" / "tests" / "test_target_allocation_shadow_replay.py",
    ROOT / "web" / "docs" / "TARGET_ALLOCATION_RULES.md",
]

PHASE5D_FIXTURE_DIR = ROOT / "web" / "backend" / "tests" / "fixtures" / "target_allocation_scenarios"

PHASE5E_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "target_allocation_mode.py",
    ROOT / "web" / "backend" / "tests" / "test_target_allocation_promotion_mode.py",
    ROOT / "web" / "docs" / "TARGET_ALLOCATION_PROMOTION_PLAN.md",
]

PHASE5F_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "target_allocation_promotion.py",
    ROOT / "web" / "backend" / "tests" / "test_target_allocation_promotion_simulation.py",
    ROOT / "scripts" / "simulate_target_allocation_promotion.py",
    ROOT / "web" / "docs" / "TARGET_ALLOCATION_PROMOTION_PLAN.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
]

PHASE5G_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "target_allocation_candidate_audit.py",
    ROOT / "web" / "backend" / "tests" / "test_target_allocation_candidate_audit.py",
    ROOT / "scripts" / "export_target_allocation_candidate_audit.py",
    ROOT / "web" / "backend" / "app" / "routers" / "current.py",
    ROOT / "web" / "docs" / "TARGET_ALLOCATION_PROMOTION_PLAN.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "GOLDEN_REFERENCE.md",
    ROOT / "web" / "docs" / "TARGET_ALLOCATION_RULES.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
    ROOT / "web" / "docs" / "API_SPEC.md",
]

PHASE6_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "history_snapshot.py",
    ROOT / "web" / "backend" / "tests" / "test_history_snapshot.py",
    ROOT / "scripts" / "export_history_snapshot.py",
    ROOT / "web" / "backend" / "app" / "routers" / "current.py",
    ROOT / "web" / "docs" / "HISTORY_SNAPSHOT.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "GOLDEN_REFERENCE.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
]

PHASE7A_FILES = [
    ROOT / "web" / "backend" / "app" / "repositories" / "subject_status_repo.py",
    ROOT / "web" / "backend" / "app" / "services" / "subject_status.py",
    ROOT / "web" / "backend" / "app" / "templates" / "subjects.html",
    ROOT / "web" / "backend" / "tests" / "test_subject_status.py",
    ROOT / "web" / "docs" / "API_SPEC.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
]

PHASE7B_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "subject_gap.py",
    ROOT / "web" / "backend" / "app" / "templates" / "subjects_gap.html",
    ROOT / "web" / "backend" / "tests" / "test_subject_gap.py",
    ROOT / "web" / "docs" / "API_SPEC.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
]

PHASE7D_FILES = [
    ROOT / "scripts" / "run_web.py",
    ROOT / "web" / "backend" / "app" / "services" / "dashboard.py",
    ROOT / "web" / "backend" / "app" / "templates" / "dashboard.html",
    ROOT / "web" / "backend" / "tests" / "test_dashboard_current.py",
    ROOT / "web" / "docs" / "API_SPEC.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
]

PHASE7E_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "theme_status.py",
    ROOT / "web" / "backend" / "app" / "templates" / "themes.html",
    ROOT / "web" / "backend" / "tests" / "test_theme_status.py",
    ROOT / "web" / "docs" / "THEME_RESEARCH_CENTER.md",
    ROOT / "web" / "docs" / "API_SPEC.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
]

PHASE7H_FILES = [
    ROOT / "web" / "backend" / "app" / "services" / "allocation_drilldown.py",
    ROOT / "web" / "backend" / "app" / "templates" / "buckets_drilldown.html",
    ROOT / "web" / "backend" / "app" / "templates" / "subjects_drilldown.html",
    ROOT / "web" / "backend" / "tests" / "test_allocation_drilldown.py",
    ROOT / "web" / "docs" / "ALLOCATION_DRILLDOWN.md",
    ROOT / "web" / "docs" / "API_SPEC.md",
    ROOT / "web" / "docs" / "SERVICE_LAYER_PLAN.md",
    ROOT / "web" / "docs" / "WEB_RUNBOOK.md",
]

PROTECTED_SIDE_EFFECT_FILES = [
    ROOT / "research" / "latest_index.json",
    ROOT / "research" / "alerts" / "intraday_rules.json",
    ROOT / "research" / "logs" / "decision_log.md",
    ROOT / "scripts" / "check_valuation_updates.py",
    ROOT / "scripts" / "generate_premarket_check.py",
]

PROTECTED_GENERATED_DIRS = [
    ROOT / "research" / "actions",
    ROOT / "research" / "allocation",
    ROOT / "research" / "checks",
    ROOT / "research" / "market",
    ROOT / "research" / "portfolio",
]

REQUIRED_EXPORT_MODULES = {
    "action_plan",
    "target_allocation",
    "intraday_rules",
    "portfolio_snapshot",
    "market_position_mapping",
    "bucket_registry",
    "liquidity_gate_registry",
}

EXPECTED_ZIP_FILES = {
    "manifest.json",
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
}

CONTROLLED_EXPORT_ZIP_FILES = {
    "manifest.json",
    "shadow_target_allocation.json",
    "compare_result.json",
    "provenance.json",
    "system_checks.json",
}

CANDIDATE_AUDIT_ZIP_FILES = {
    "manifest.json",
    "candidate_target_allocation.json",
    "compare_result.json",
    "replay_summary.json",
    "promotion_mode.json",
    "safety_checks.json",
    "provenance.json",
}

HISTORY_SNAPSHOT_ZIP_FILES = {
    "manifest.json",
    "history_snapshot.json",
    "history_entries.json",
    "live_current_summary.json",
    "safety_checks.json",
}

FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(total_asset|amount|market_value|shares|quantity|available_quantity|"
    r"trade_amount|profit_amount|account|full_account|order|fill|deal|"
    r"total_amount|share_count|available_qty|qty|cost_price|raw_cost_price|"
    r"current_price|qmt_timetag)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(r"(?:[A-Za-z]:(?!//)[\\/]|\\\\|/Users/|/home/)")
FORBIDDEN_TEXT_RE = re.compile(
    r"(total asset|market value|profit amount|trade amount|share count|available quantity|"
    r"full account|order id|fill record|deal record|\u603b\u8d44\u4ea7|\u91d1\u989d|"
    r"\u5e02\u503c|\u80a1\u6570|\u6570\u91cf|\u53ef\u7528\u6570\u91cf|"
    r"\u4ea4\u6613\u91d1\u989d|\u76c8\u4e8f\u91d1\u989d|\u8d26\u53f7|"
    r"\u8ba2\u5355|\u6210\u4ea4)",
    re.IGNORECASE,
)

EXPORT_BLOCKED_VALUE_TERMS = [
    ".env",
    "temp/",
    "web_runtime",
    ".sqlite",
    ".sqlite3",
    ".db",
    "__pycache__",
    ".pytest_cache",
    ".zip",
    ".log",
]

FORBIDDEN_GIT_PATTERNS = [
    "temp/**",
    "temp/web_db/**",
    "temp/web_runtime/**",
    "data/local/**",
    "*.sqlite",
    "*.sqlite3",
    "*.db",
    "__pycache__/**",
    "*/__pycache__/**",
    ".pytest_cache/**",
    "node_modules/**",
    "*/node_modules/**",
    "frontend/build/**",
    "frontend/dist/**",
    "web/frontend/build/**",
    "web/frontend/dist/**",
    ".env",
    ".env.*",
    "*.zip",
    "*.log",
]

ALLOWED_GIT_PATHS = {".env.example"}


@dataclass
class Problem:
    check: str
    file: str
    reason: str
    fix: str


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""


class WebCheck:
    def __init__(self) -> None:
        self.failures: list[Problem] = []
        self.warnings: list[Problem] = []
        self.results: list[CheckResult] = []

    def add_result(self, name: str, status: str, detail: str = "") -> None:
        self.results.append(CheckResult(name, status, detail))

    def fail(self, check: str, file: str, reason: str, fix: str) -> None:
        self.failures.append(Problem(check, file, reason, fix))

    def warn(self, check: str, file: str, reason: str, fix: str) -> None:
        self.warnings.append(Problem(check, file, reason, fix))

    def side_effect_snapshot(self) -> dict[str, Any]:
        files = {path: path.read_bytes() if path.exists() else None for path in PROTECTED_SIDE_EFFECT_FILES}
        generated = {
            directory: {item for item in directory.glob("*") if item.is_file()}
            for directory in PROTECTED_GENERATED_DIRS
            if directory.exists()
        }
        return {"files": files, "generated": generated}

    def restore_side_effect_snapshot(self, snapshot: dict[str, Any]) -> None:
        for path, content in snapshot.get("files", {}).items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        for directory, before in snapshot.get("generated", {}).items():
            if not directory.exists():
                continue
            for item in directory.glob("*"):
                if item.is_file() and item not in before and item.suffix.lower() in {".json", ".md"}:
                    item.unlink(missing_ok=True)

    def run_with_side_effect_guard(self, callback: Any) -> Any:
        snapshot = self.side_effect_snapshot()
        try:
            return callback()
        finally:
            self.restore_side_effect_snapshot(snapshot)

    def run_command(self, name: str, args: list[str], expect_text: str | None = None) -> str:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = proc.stdout or ""
        if proc.returncode != 0:
            self.add_result(name, "FAIL", tail(output))
            self.fail(
                name,
                command_label(args),
                f"Command exited with {proc.returncode}.",
                "Run the command locally, fix the reported error, then rerun scripts/web_check.py.",
            )
            return output
        if expect_text and expect_text not in output:
            self.add_result(name, "FAIL", tail(output))
            self.fail(
                name,
                command_label(args),
                f"Expected output marker not found: {expect_text}",
                "Inspect the command output and update the failing validation.",
            )
            return output
        status = "PASS"
        detail = first_line(output) or "OK"
        if "warnings summary" in output.lower() or "warning" in output.lower():
            status = "WARN"
            self.warn(
                name,
                command_label(args),
                "Command passed with warnings.",
                "Review the warning. Non-blocking third-party deprecation warnings can be accepted.",
            )
        self.add_result(name, status, detail)
        return output

    def run(self) -> int:
        self.check_git_scope()
        self.run_hidden_unicode_check()
        self.check_no_research_logic_changes()
        self.check_phase5a_contract_files()
        self.check_phase5c_contract_files()
        self.check_phase5c2_contract_files()
        self.check_phase5c3_contract_files()
        self.check_phase5d_contract_files()
        self.check_phase5e_contract_files()
        self.check_phase5f_contract_files()
        self.check_phase5g_contract_files()
        self.check_phase6_contract_files()
        self.check_phase7a_contract_files()
        self.check_phase7b_contract_files()
        self.check_phase7d_contract_files()
        self.check_phase7e_contract_files()
        self.check_phase7h_contract_files()
        self.run_ingest()
        self.run_pytest()
        action_path = self.latest_action_plan_path()
        self.run_ratio_and_gate_checks(action_path)
        self.run_project_checks()
        self.check_api_and_export()
        self.check_frontend_interactions()
        self.check_run_web_script()
        self.check_current_only_code_paths()
        self.print_summary()
        return 1 if self.failures else 0

    def run_hidden_unicode_check(self) -> None:
        self.run_command(
            "check_hidden_unicode",
            [sys.executable, "scripts/check_hidden_unicode.py"],
            "Hidden Unicode check: OK",
        )

    def check_phase5a_contract_files(self) -> None:
        missing = [rel(path) for path in [*PHASE5A_TEST_FILES, *PHASE5A_DOC_FILES] if not path.exists()]
        if missing:
            self.add_result("phase5a_contract_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5a_contract_files",
                ", ".join(missing),
                "Phase 5A schema/current-state/golden contract files are missing.",
                "Add the missing docs/tests, then rerun scripts/web_check.py.",
            )
        else:
            self.add_result("phase5a_contract_files", "PASS", "schema, current-state, golden docs/tests present")

    def check_phase5c_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE5C_TEST_FILES if not path.exists()]
        if missing:
            self.add_result("phase5c_market_position_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5c_market_position_files",
                ", ".join(missing),
                "Phase 5C-1 market-position golden/API tests are missing.",
                "Add the MarketPositionService test file, then rerun scripts/web_check.py.",
            )
        else:
            self.add_result("phase5c_market_position_files", "PASS", "market-position service tests present")

    def check_phase5c2_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE5C2_TEST_FILES if not path.exists()]
        if missing:
            self.add_result("phase5c2_shadow_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5c2_shadow_files",
                ", ".join(missing),
                "Phase 5C-2 target-allocation shadow tests are missing.",
                "Add the shadow-generation test file, then rerun scripts/web_check.py.",
            )
        else:
            self.add_result("phase5c2_shadow_files", "PASS", "target-allocation shadow tests present")

    def check_phase5c3_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE5C3_FILES if not path.exists()]
        if missing:
            self.add_result("phase5c3_controlled_export_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5c3_controlled_export_files",
                ", ".join(missing),
                "Phase 5C-3 controlled export service/script/tests are missing.",
                "Add the controlled export files, then rerun scripts/web_check.py.",
            )
        else:
            self.add_result("phase5c3_controlled_export_files", "PASS", "controlled export service/script/tests present")

    def check_phase5d_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE5D_FILES if not path.exists()]
        if not PHASE5D_FIXTURE_DIR.exists():
            missing.append(rel(PHASE5D_FIXTURE_DIR))
        fixture_paths = sorted(PHASE5D_FIXTURE_DIR.glob("*.json")) if PHASE5D_FIXTURE_DIR.exists() else []
        if len(fixture_paths) < 10:
            missing.append(f"{rel(PHASE5D_FIXTURE_DIR)}/*.json >= 10")
        if missing:
            self.add_result("phase5d_replay_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5d_replay_files",
                ", ".join(missing),
                "Phase 5D replay fixtures, tests, or target-allocation rules doc are missing.",
                "Add replay fixtures, test_target_allocation_shadow_replay.py, and TARGET_ALLOCATION_RULES.md.",
            )
            return
        try:
            for path in fixture_paths:
                payload = json.loads(path.read_text(encoding="utf-8"))
                assert_safe_payload(payload)
                assert_no_export_runtime_terms(payload)
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase5d_fixture_safety", "FAIL", str(exc))
            self.fail(
                "phase5d_fixture_safety",
                rel(path),
                f"Fixture failed ratio-only/current-only safety scan: {exc}",
                "Remove forbidden fields, local paths, runtime terms, or invalid JSON from replay fixtures.",
            )
            return
        self.add_result("phase5d_replay_files", "PASS", f"{len(fixture_paths)} replay fixtures safe")

    def check_phase5e_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE5E_FILES if not path.exists()]
        if missing:
            self.add_result("phase5e_promotion_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5e_promotion_files",
                ", ".join(missing),
                "Phase 5E promotion plan, mode helper, or tests are missing.",
                "Add TARGET_ALLOCATION_PROMOTION_PLAN.md, target_allocation_mode.py, and its tests.",
            )
            return
        try:
            for path in PHASE5E_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md" and "official" not in text:
                    raise ValueError("promotion plan does not describe official-mode blocking")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase5e_promotion_safety", "FAIL", str(exc))
            self.fail(
                "phase5e_promotion_safety",
                rel(path),
                f"Phase 5E file failed safety scan: {exc}",
                "Remove runtime terms or add explicit candidate/official blocking rules.",
            )
            return
        self.add_result("phase5e_promotion_files", "PASS", "promotion plan and blocked mode tests present")

    def check_phase5f_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE5F_FILES if not path.exists()]
        if missing:
            self.add_result("phase5f_promotion_simulation_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5f_promotion_simulation_files",
                ", ".join(missing),
                "Phase 5F candidate/official promotion simulation files are missing.",
                "Add the promotion simulation service, CLI, tests, and docs, then rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE5F_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "candidate" not in lowered or "official" not in lowered:
                        raise ValueError("Phase 5F docs must describe candidate and official mode behavior")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase5f_promotion_simulation_safety", "FAIL", str(exc))
            self.fail(
                "phase5f_promotion_simulation_safety",
                rel(path),
                f"Phase 5F file failed safety scan: {exc}",
                "Remove local paths and document candidate temp export plus official blocking behavior.",
            )
            return
        self.add_result("phase5f_promotion_simulation_files", "PASS", "candidate/official simulation tests present")

    def check_phase5g_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE5G_FILES if not path.exists()]
        if missing:
            self.add_result("phase5g_candidate_audit_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase5g_candidate_audit_files",
                ", ".join(missing),
                "Phase 5G candidate audit service/API/CLI/tests/docs are missing.",
                "Add the candidate audit bundle files and rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE5G_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "candidate audit" not in lowered or "official" not in lowered:
                        raise ValueError("Phase 5G docs must describe candidate audit and official blocking")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase5g_candidate_audit_safety", "FAIL", str(exc))
            self.fail(
                "phase5g_candidate_audit_safety",
                rel(path),
                f"Phase 5G file failed safety scan: {exc}",
                "Remove local paths and document candidate audit plus official blocking behavior.",
            )
            return
        self.add_result("phase5g_candidate_audit_files", "PASS", "candidate audit service/API/CLI/tests present")

    def check_phase6_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE6_FILES if not path.exists()]
        if missing:
            self.add_result("phase6_history_snapshot_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase6_history_snapshot_files",
                ", ".join(missing),
                "Phase 6 history snapshot service/API/CLI/tests/docs are missing.",
                "Add the history snapshot files and rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE6_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "history snapshot" not in lowered or "read-only" not in lowered:
                        raise ValueError("Phase 6 docs must describe history snapshot and read-only boundaries")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase6_history_snapshot_safety", "FAIL", str(exc))
            self.fail(
                "phase6_history_snapshot_safety",
                rel(path),
                f"Phase 6 file failed safety scan: {exc}",
                "Remove local paths and document history snapshot read-only boundaries.",
            )
            return
        self.add_result("phase6_history_snapshot_files", "PASS", "history snapshot service/API/CLI/tests present")

    def check_phase7a_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE7A_FILES if not path.exists()]
        if missing:
            self.add_result("phase7a_subject_status_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase7a_subject_status_files",
                ", ".join(missing),
                "Phase 7A subject-status service/API/page/tests/docs are missing.",
                "Add the subject status files and rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE7A_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "subject status" not in lowered or "read-only" not in lowered:
                        raise ValueError("Phase 7A docs must describe subject status and read-only boundaries")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase7a_subject_status_safety", "FAIL", str(exc))
            self.fail(
                "phase7a_subject_status_safety",
                rel(path),
                f"Phase 7A file failed safety scan: {exc}",
                "Remove local paths and document subject status read-only boundaries.",
            )
            return
        self.add_result("phase7a_subject_status_files", "PASS", "subject status service/API/page/tests present")

    def check_phase7b_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE7B_FILES if not path.exists()]
        if missing:
            self.add_result("phase7b_subject_gap_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase7b_subject_gap_files",
                ", ".join(missing),
                "Phase 7B subject gap service/page/tests/docs are missing.",
                "Add the subject gap files and rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE7B_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "subject gap" not in lowered or "read-only" not in lowered:
                        raise ValueError("Phase 7B docs must describe subject gap and read-only boundaries")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase7b_subject_gap_safety", "FAIL", str(exc))
            self.fail(
                "phase7b_subject_gap_safety",
                rel(path),
                f"Phase 7B file failed safety scan: {exc}",
                "Remove local paths and document subject gap read-only boundaries.",
            )
            return
        self.add_result("phase7b_subject_gap_files", "PASS", "subject gap service/API/page/tests present")

    def check_phase7d_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE7D_FILES if not path.exists()]
        if missing:
            self.add_result("phase7d_dashboard_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase7d_dashboard_files",
                ", ".join(missing),
                "Phase 7D dashboard service/API/page/tests/docs or run script are missing.",
                "Add the dashboard service, template, tests, run_web.py, and docs, then rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE7D_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if "tests" not in path.parts and LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "dashboard" not in lowered or "read-only" not in lowered:
                        raise ValueError("Phase 7D docs must describe dashboard and read-only boundaries")
            run_web_text = (ROOT / "scripts" / "run_web.py").read_text(encoding="utf-8", errors="replace")
            for marker in ['DEFAULT_HOST = "0.0.0.0"', "--host", "--port", "uvicorn.run"]:
                if marker not in run_web_text:
                    raise ValueError(f"run_web.py missing marker: {marker}")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase7d_dashboard_safety", "FAIL", str(exc))
            self.fail(
                "phase7d_dashboard_safety",
                rel(path),
                f"Phase 7D file failed safety scan: {exc}",
                "Remove local paths and document dashboard read-only boundaries.",
            )
            return
        self.add_result("phase7d_dashboard_files", "PASS", "dashboard service/API/page/tests/run script present")

    def check_phase7e_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE7E_FILES if not path.exists()]
        if missing:
            self.add_result("phase7e_theme_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase7e_theme_files",
                ", ".join(missing),
                "Phase 7E theme status service/page/tests/docs are missing.",
                "Add the theme status service, page, tests, and THEME_RESEARCH_CENTER.md, then rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE7E_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if "tests" not in path.parts and LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "theme" not in lowered or "read-only" not in lowered:
                        raise ValueError("Phase 7E docs must describe theme center and read-only boundaries")
            service_text = (ROOT / "web" / "backend" / "app" / "services" / "theme_status.py").read_text(encoding="utf-8", errors="replace")
            if "latest_index.files" in service_text or '["files"]' in service_text or "['files']" in service_text:
                raise ValueError("theme service references latest_index.files")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase7e_theme_safety", "FAIL", str(exc))
            self.fail(
                "phase7e_theme_safety",
                rel(path),
                f"Phase 7E file failed safety scan: {exc}",
                "Remove local paths, keep current-only module resolution, and document theme read-only boundaries.",
            )
            return
        self.add_result("phase7e_theme_files", "PASS", "theme status service/API/page/tests/docs present")

    def check_phase7h_contract_files(self) -> None:
        missing = [rel(path) for path in PHASE7H_FILES if not path.exists()]
        if missing:
            self.add_result("phase7h_allocation_drilldown_files", "FAIL", ", ".join(missing))
            self.fail(
                "phase7h_allocation_drilldown_files",
                ", ".join(missing),
                "Phase 7H allocation drilldown service/pages/tests/docs are missing.",
                "Add the allocation drilldown service, pages, tests, and ALLOCATION_DRILLDOWN.md, then rerun scripts/web_check.py.",
            )
            return
        try:
            for path in PHASE7H_FILES:
                text = path.read_text(encoding="utf-8", errors="replace")
                if "tests" not in path.parts and LOCAL_PATH_RE.search(text):
                    raise ValueError("local absolute path")
                if path.suffix == ".md":
                    lowered = text.lower()
                    if "allocation drilldown" not in lowered or "read-only" not in lowered:
                        raise ValueError("Phase 7H docs must describe allocation drilldown and read-only boundaries")
            service_text = (ROOT / "web" / "backend" / "app" / "services" / "allocation_drilldown.py").read_text(
                encoding="utf-8",
                errors="replace",
            )
            if "latest_index.files" in service_text or '["files"]' in service_text or "['files']" in service_text:
                raise ValueError("allocation drilldown service references latest_index.files")
            for blocked in ["generate_action_plan", "generate_target_allocation", "qmt_portfolio_snapshot", "qmt_export_history"]:
                if blocked in service_text:
                    raise ValueError(f"allocation drilldown service references blocked script/runtime: {blocked}")
        except Exception as exc:  # noqa: BLE001
            self.add_result("phase7h_allocation_drilldown_safety", "FAIL", str(exc))
            self.fail(
                "phase7h_allocation_drilldown_safety",
                rel(path),
                f"Phase 7H file failed safety scan: {exc}",
                "Remove local paths, keep current-only module resolution, and document allocation drilldown read-only boundaries.",
            )
            return
        self.add_result(
            "phase7h_allocation_drilldown_files",
            "PASS",
            "allocation drilldown service/API/pages/tests/docs present",
        )

    def run_ingest(self) -> None:
        self.run_command("ingest_current_state", [sys.executable, "scripts/ingest_current_state.py"])
        if DB_PATH.exists():
            self.add_result("web_db_exists", "PASS", rel(DB_PATH))
        else:
            self.add_result("web_db_exists", "FAIL", rel(DB_PATH))
            self.fail(
                "web_db_exists",
                rel(DB_PATH),
                "SQLite web DB was not generated by ingest_current_state.py.",
                "Fix ingest_current_state.py or the source current modules and rerun the ingest.",
            )

    def run_pytest(self) -> None:
        self.run_with_side_effect_guard(
            lambda: self.run_command("pytest_web_backend", [sys.executable, "-m", "pytest", "web/backend/tests"])
        )

    def run_ratio_and_gate_checks(self, action_path: str) -> None:
        self.run_command(
            "check_ratio_only",
            [sys.executable, "scripts/check_ratio_only.py", "--path", action_path],
            "Ratio-only check: OK",
        )
        self.run_command(
            "check_research_first_gate",
            [sys.executable, "scripts/check_research_first_gate.py", "--path", action_path],
            "ResearchFirst gate: OK",
        )

    def run_project_checks(self) -> None:
        def run_checks() -> None:
            self.run_command(
                "check_cross_file_allocation_consistency",
                [sys.executable, "scripts/check_cross_file_allocation_consistency.py"],
                "Allocation consistency: OK",
            )
            self.run_command(
                "project_check_current_only",
                [sys.executable, "scripts/project_check.py", "--current-only"],
                "0 FAIL",
            )

        self.run_with_side_effect_guard(run_checks)

    def latest_action_plan_path(self) -> str:
        try:
            latest = json.loads(LATEST_INDEX.read_text(encoding="utf-8-sig"))
            path = latest["modules"]["action_plan"]["path"]
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "latest_action_plan_path",
                rel(LATEST_INDEX),
                f"Could not read latest_index.modules.action_plan.path: {exc}",
                "Repair research/latest_index.json and make sure action_plan is in modules.",
            )
            return ""
        self.add_result("latest_action_plan_path", "PASS", path)
        return str(path)

    def check_api_and_export(self) -> None:
        try:
            from fastapi.testclient import TestClient

            from web.backend.app.main import app
            from web.backend.app.services.ratio_only import RatioOnlyService
        except Exception as exc:  # noqa: BLE001
            self.add_result("api_imports", "FAIL", str(exc))
            self.fail(
                "api_imports",
                "web/backend/app",
                f"Could not import FastAPI app or RatioOnlyService: {exc}",
                "Install Web dependencies and fix import errors.",
            )
            return

        client = TestClient(app)
        ratio = RatioOnlyService()

        for path in API_PATHS:
            response = client.get(path)
            if response.status_code != 200:
                self.fail(
                    "api_status",
                    path,
                    f"Expected 200, got {response.status_code}.",
                    "Fix the endpoint or ingest data source and rerun scripts/web_check.py.",
                )
                continue
            try:
                data = response.json()
                ratio.assert_safe(data)
                assert_safe_payload(data)
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    "api_ratio_only",
                    path,
                    f"API response failed ratio-only or path scan: {exc}",
                    "Sanitize the endpoint response before returning it.",
                )
        api_status = "FAIL" if self.has_fail("api_ratio_only") or self.has_fail("api_status") else "PASS"
        self.add_result("api_forbidden_fields", api_status, f"{len(API_PATHS)} endpoints")

        self.check_api_is_read_only(client)
        self.check_subject_status_api(client, ratio)
        self.check_subject_gap_api(client, ratio)
        self.check_dashboard_api(client, ratio)
        self.check_theme_status_api(client, ratio)
        self.check_allocation_drilldown_api(client, ratio)
        self.check_export_json(client, ratio)
        self.check_export_zip(client, ratio)
        self.check_controlled_shadow_export(client, ratio)
        self.check_promotion_simulation_cli_output(ratio)
        self.check_candidate_audit_export(client, ratio)
        self.check_history_snapshot_export(client, ratio)

    def check_api_is_read_only(self, client: Any) -> None:
        response = client.get("/openapi.json")
        if response.status_code != 200:
            self.fail("openapi_read_only", "/openapi.json", "OpenAPI schema is unavailable.", "Fix FastAPI app startup.")
            return
        schema = response.json()
        mutating: list[str] = []
        for route, methods in schema.get("paths", {}).items():
            if not route.startswith("/api/"):
                continue
            bad = sorted(set(methods) & {"post", "put", "patch", "delete"})
            if bad:
                mutating.append(f"{route}: {','.join(bad)}")
        if mutating:
            self.fail(
                "openapi_read_only",
                "web/backend/app/routers/current.py",
                "Mutating /api methods found: " + "; ".join(mutating),
                "Remove write endpoints from Phase 3 Web milestone.",
            )
            self.add_result("openapi_read_only", "FAIL", "; ".join(mutating))
        else:
            self.add_result("openapi_read_only", "PASS", "No POST/PUT/PATCH/DELETE under /api")

    def check_subject_gap_api(self, client: Any, ratio: Any) -> None:
        try:
            freshness_response = client.get("/api/subjects/freshness")
            if freshness_response.status_code != 200:
                raise ValueError(f"freshness API returned {freshness_response.status_code}")
            freshness = freshness_response.json()
            ratio.assert_safe(freshness)
            assert_safe_payload(freshness)
            freshness_rows = ((freshness.get("data") or {}).get("rows") or [])
            if not freshness_rows:
                raise ValueError("freshness rows are empty")
            for row in freshness_rows:
                if not isinstance(row.get("staleness_flag"), bool):
                    raise ValueError(f"staleness_flag is not boolean for {row.get('code')}")

            gap_response = client.get("/api/subjects/gap")
            if gap_response.status_code != 200:
                raise ValueError(f"gap API returned {gap_response.status_code}")
            gap = gap_response.json()
            ratio.assert_safe(gap)
            assert_safe_payload(gap)
            gap_rows = ((gap.get("data") or {}).get("rows") or [])
            if not gap_rows:
                raise ValueError("gap rows are empty")

            target_response = client.get("/api/target-allocation/current")
            target = (((target_response.json() or {}).get("data") or {}).get("target_allocation") or {})
            bucket_map = {row.get("bucket"): row for row in target.get("buckets", [])}
            for row in gap_rows:
                if row.get("gap_status") not in {"green", "yellow", "red", "unknown"}:
                    raise ValueError(f"unexpected gap status for {row.get('code')}: {row.get('gap_status')}")
                bucket = row.get("bucket")
                if bucket in bucket_map and row.get("actual_pct") is not None:
                    expected = bucket_map[bucket]
                    for key in ["actual_pct", "target_pct", "gap_pct"]:
                        if row.get(key) != expected.get(key):
                            raise ValueError(f"{bucket} {key} mismatch for {row.get('code')}")
            cash = next((row for row in gap_rows if row.get("code") == "511360.SH"), None)
            if cash and cash.get("bucket") != "cash_short":
                raise ValueError("511360 gap row is not cash_short")
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "subject_gap_api",
                "/api/subjects/gap",
                f"Subject gap/freshness API failed safety/current-state scan: {exc}",
                "Fix SubjectGapService or its routes and rerun scripts/web_check.py.",
            )
            self.add_result("subject_gap_api", "FAIL", str(exc))
        else:
            self.add_result("subject_gap_api", "PASS", "freshness and bucket gap rows safe")

    def check_subject_status_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/subjects/status")
            if response.status_code != 200:
                raise ValueError(f"status API returned {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            subjects = ((payload.get("data") or {}).get("subjects") or [])
            summary = (payload.get("data") or {}).get("summary") or {}
            if not subjects:
                raise ValueError("subject status list is empty")
            if summary.get("subject_count") != len(subjects):
                raise ValueError("subject summary count does not match list length")
            for item in subjects:
                if item.get("gate_conclusion") in {"buy", "add", "reduce", "sell"}:
                    raise ValueError(f"action conclusion leaked for {item.get('code')}")
                if any(
                    [
                        item.get("missing_profile"),
                        item.get("missing_valuation"),
                        item.get("missing_liquidity"),
                        item.get("missing_theme_binding"),
                    ]
                ) and item.get("research_first_status") not in {"research_first", "blocked"}:
                    raise ValueError(f"ResearchFirst missing item not blocked: {item.get('code')}")

            cash = next((item for item in subjects if item.get("code") == "511360.SH"), None)
            if cash:
                for key in ["profile_status", "valuation_status", "liquidity_status"]:
                    if cash.get(key) != "pass":
                        raise ValueError(f"511360 {key} is not pass: {cash.get(key)}")
                if cash.get("subject_type") != "cash_equivalent" or cash.get("bucket") != "cash_short":
                    raise ValueError("511360 is not displayed as cash_equivalent / cash_short")

            missing_response = client.get("/api/subjects/status/NO_SUCH_CODE")
            if missing_response.status_code != 404:
                raise ValueError(f"missing subject returned {missing_response.status_code}, expected 404")
            ratio.assert_safe(missing_response.json())
            assert_safe_payload(missing_response.json())
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "subject_status_api",
                "/api/subjects/status",
                f"Subject status API failed safety/current-state scan: {exc}",
                "Fix SubjectStatusService or its route and rerun scripts/web_check.py.",
            )
            self.add_result("subject_status_api", "FAIL", str(exc))
        else:
            self.add_result("subject_status_api", "PASS", "current-only status list and 511360 gate safe")

    def check_dashboard_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/dashboard/current")
            if response.status_code != 200:
                raise ValueError(f"dashboard API returned {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            data = payload.get("data") or {}
            if data.get("module") != "dashboard_current" or data.get("current_only") is not True:
                raise ValueError("dashboard payload is not marked current-only")
            for key in [
                "system_status",
                "market_position",
                "action_plan_summary",
                "allocation_summary",
                "subject_status_summary",
                "subject_gap_summary",
                "quick_links",
            ]:
                if key not in data:
                    raise ValueError(f"dashboard missing {key}")
            if not isinstance((data.get("allocation_summary") or {}).get("bucket_gaps"), list):
                raise ValueError("dashboard allocation bucket_gaps is not a list")
            cash_gate = (data.get("subject_status_summary") or {}).get("cash_equivalent_gate")
            if cash_gate:
                if cash_gate.get("code") != "511360.SH" or cash_gate.get("bucket") != "cash_short":
                    raise ValueError("dashboard 511360 cash-equivalent gate is not normalized")
                if cash_gate.get("gate_conclusion") in {"buy", "add", "reduce", "sell"}:
                    raise ValueError("dashboard cash-equivalent gate leaked action conclusion")
            links = data.get("quick_links") or []
            expected = {"Action Plan", "Target Allocation", "Subject Status", "Subject Gap", "Portfolio", "Intraday Rules", "Decision Log", "History Snapshot"}
            labels = {item.get("label") for item in links}
            if not expected.issubset(labels):
                raise ValueError(f"dashboard quick links missing labels: {sorted(expected - labels)}")
            for item in links:
                href = item.get("href")
                if not href or not str(href).startswith("/"):
                    raise ValueError(f"dashboard quick link is not repo-local: {item}")
                link_response = client.get(href)
                if link_response.status_code != 200:
                    raise ValueError(f"dashboard quick link {href} returned {link_response.status_code}")
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "dashboard_api",
                "/api/dashboard/current",
                f"Dashboard API failed safety/current-state scan: {exc}",
                "Fix DashboardService or its route and rerun scripts/web_check.py.",
            )
            self.add_result("dashboard_api", "FAIL", str(exc))
        else:
            self.add_result("dashboard_api", "PASS", "summary, quick links, and cash-equivalent gate safe")

    def check_theme_status_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/themes/status")
            if response.status_code != 200:
                raise ValueError(f"theme status API returned {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            data = payload.get("data") or {}
            if data.get("module") != "theme_research_status" or data.get("current_only") is not True:
                raise ValueError("theme payload is not marked current-only")
            for key in ["summary", "themes", "safety"]:
                if key not in data:
                    raise ValueError(f"theme payload missing {key}")
            themes = data.get("themes") or []
            summary = data.get("summary") or {}
            if summary.get("theme_count") != len(themes):
                raise ValueError("theme summary count does not match themes list")
            for theme in themes:
                if theme.get("status") in {"buy", "add", "reduce", "sell"}:
                    raise ValueError(f"theme status leaked action conclusion: {theme.get('theme_name')}")
                for row in [*(theme.get("associated_etfs") or []), *(theme.get("associated_stocks") or [])]:
                    if row.get("gate_conclusion") in {"buy", "add", "reduce", "sell"}:
                        raise ValueError(f"associated subject leaked action conclusion: {row.get('code')}")
            if themes:
                from urllib.parse import quote

                detail = client.get("/api/themes/status/" + quote(str(themes[0].get("theme_name")), safe=""))
                if detail.status_code != 200:
                    raise ValueError(f"theme detail returned {detail.status_code}")
                ratio.assert_safe(detail.json())
                assert_safe_payload(detail.json())
            missing = client.get("/api/themes/status/NO_SUCH_THEME")
            if missing.status_code != 404:
                raise ValueError(f"missing theme returned {missing.status_code}, expected 404")
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "theme_status_api",
                "/api/themes/status",
                f"Theme status API failed safety/current-state scan: {exc}",
                "Fix ThemeStatusService or its route and rerun scripts/web_check.py.",
            )
            self.add_result("theme_status_api", "FAIL", str(exc))
        else:
            self.add_result("theme_status_api", "PASS", "theme summary, details, and neutral statuses safe")

    def check_allocation_drilldown_api(self, client: Any, ratio: Any) -> None:
        try:
            bucket_response = client.get("/api/buckets/drilldown?detail=full")
            if bucket_response.status_code != 200:
                raise ValueError(f"bucket drilldown API returned {bucket_response.status_code}")
            bucket_payload = bucket_response.json()
            ratio.assert_safe(bucket_payload)
            assert_safe_payload(bucket_payload)
            bucket_data = bucket_payload.get("data") or {}
            if bucket_data.get("module") != "allocation_bucket_drilldown" or bucket_data.get("current_only") is not True:
                raise ValueError("bucket drilldown payload is not marked current-only")
            buckets = bucket_data.get("buckets") or []
            if not buckets:
                raise ValueError("bucket drilldown rows are empty")
            if (bucket_data.get("summary") or {}).get("bucket_count") != len(buckets):
                raise ValueError("bucket drilldown summary count does not match rows")
            safety = bucket_data.get("safety") or {}
            for key in ["ratio_only", "current_only", "read_only", "uses_latest_index_modules"]:
                if safety.get(key) is not True:
                    raise ValueError(f"bucket drilldown safety check failed: {key}")
            for key in ["uses_latest_index_files", "generates_action_plan", "generates_target_allocation", "trading_feature", "qmt_write_feature"]:
                if safety.get(key) is not False:
                    raise ValueError(f"bucket drilldown boundary check failed: {key}")

            target_response = client.get("/api/target-allocation/current")
            target = (((target_response.json() or {}).get("data") or {}).get("target_allocation") or {})
            target_map = {row.get("bucket"): row for row in target.get("buckets", [])}
            for row in buckets:
                bucket = row.get("bucket")
                if bucket not in target_map:
                    raise ValueError(f"bucket drilldown bucket not in target allocation: {bucket}")
                expected = target_map[bucket]
                for key in ["actual_pct", "target_pct", "gap_pct"]:
                    if row.get(key) != expected.get(key):
                        raise ValueError(f"{bucket} {key} mismatch")
                if row.get("gap_status") not in {"green", "yellow", "red", "unknown"}:
                    raise ValueError(f"unexpected bucket gap status: {row.get('gap_status')}")

            first_bucket = buckets[0].get("bucket")
            detail_response = client.get(f"/api/buckets/drilldown?bucket={first_bucket}&detail=full")
            if detail_response.status_code != 200:
                raise ValueError(f"bucket detail returned {detail_response.status_code}")
            ratio.assert_safe(detail_response.json())
            assert_safe_payload(detail_response.json())

            subject_response = client.get("/api/subjects/drilldown?detail=full")
            if subject_response.status_code != 200:
                raise ValueError(f"subject drilldown API returned {subject_response.status_code}")
            subject_payload = subject_response.json()
            ratio.assert_safe(subject_payload)
            assert_safe_payload(subject_payload)
            subject_data = subject_payload.get("data") or {}
            if subject_data.get("module") != "allocation_subject_drilldown" or subject_data.get("current_only") is not True:
                raise ValueError("subject drilldown payload is not marked current-only")
            subjects = subject_data.get("subjects") or []
            if not subjects:
                raise ValueError("subject drilldown rows are empty")
            if (subject_data.get("summary") or {}).get("subject_count") != len(subjects):
                raise ValueError("subject drilldown summary count does not match rows")
            for row in subjects:
                if row.get("gate_conclusion") in {"buy", "add", "reduce", "sell"}:
                    raise ValueError(f"subject drilldown leaked action conclusion: {row.get('code')}")
            cash_response = client.get("/api/subjects/drilldown?subject=511360.SH&detail=full")
            if cash_response.status_code != 200:
                raise ValueError(f"511360 subject detail returned {cash_response.status_code}")
            cash_payload = cash_response.json()
            ratio.assert_safe(cash_payload)
            assert_safe_payload(cash_payload)
            cash_rows = ((cash_payload.get("data") or {}).get("subjects") or [])
            if len(cash_rows) != 1 or cash_rows[0].get("bucket") != "cash_short":
                raise ValueError("511360 subject drilldown is not cash_short")
            missing_bucket = client.get("/api/buckets/drilldown?bucket=NO_SUCH_BUCKET")
            missing_subject = client.get("/api/subjects/drilldown?subject=NO_SUCH_SUBJECT")
            if missing_bucket.status_code != 404 or missing_subject.status_code != 404:
                raise ValueError("missing drilldown lookup did not return 404")
            ratio.assert_safe(missing_bucket.json())
            ratio.assert_safe(missing_subject.json())
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "allocation_drilldown_api",
                "/api/buckets/drilldown, /api/subjects/drilldown",
                f"Allocation drilldown API failed safety/current-state scan: {exc}",
                "Fix AllocationDrilldownService or its routes and rerun scripts/web_check.py.",
            )
            self.add_result("allocation_drilldown_api", "FAIL", str(exc))
        else:
            self.add_result("allocation_drilldown_api", "PASS", "bucket/subject drilldown rows safe and consistent")

    def check_export_json(self, client: Any, ratio: Any) -> None:
        response = client.get("/api/export/review_package?format=json")
        if response.status_code != 200:
            self.fail("export_json", "/api/export/review_package?format=json", f"Status {response.status_code}.", "Fix export endpoint.")
            return
        wrapper = response.json()
        payload = wrapper.get("data")
        if not isinstance(payload, dict):
            self.fail("export_json", "/api/export/review_package?format=json", "Response data is not an object.", "Return a JSON snapshot object.")
            return
        try:
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            assert_no_export_runtime_terms(payload)
            self.assert_export_sources_current(payload)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "export_json",
                "/api/export/review_package?format=json",
                f"Export JSON failed safety/current-only scan: {exc}",
                "Sanitize export payload and source it only from latest_index.modules.",
            )
        else:
            self.add_result("export_json", "PASS", "ratio-only current-only snapshot")

    def check_export_zip(self, client: Any, ratio: Any) -> None:
        response = client.get("/api/export/review_package")
        if response.status_code != 200:
            self.fail("export_zip", "/api/export/review_package", f"Status {response.status_code}.", "Fix export endpoint.")
            return
        content_type = response.headers.get("content-type", "")
        if "application/zip" not in content_type:
            self.fail("export_zip", "/api/export/review_package", f"Unexpected content-type {content_type}.", "Return application/zip.")
            return
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                names = set(archive.namelist())
                missing = EXPECTED_ZIP_FILES - names
                extra = names - EXPECTED_ZIP_FILES
                if missing or extra:
                    raise ValueError(f"zip names mismatch; missing={sorted(missing)} extra={sorted(extra)}")
                for name in names:
                    lname = normalize(name)
                    if any(term in lname for term in EXPORT_BLOCKED_VALUE_TERMS):
                        raise ValueError(f"blocked export filename: {name}")
                    payload = json.loads(archive.read(name).decode("utf-8"))
                    ratio.assert_safe(payload)
                    assert_safe_payload(payload)
                    assert_no_export_runtime_terms(payload)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "export_zip",
                "/api/export/review_package",
                f"Export ZIP failed safety/current-only scan: {exc}",
                "Only include sanitized current snapshot JSON files in the in-memory ZIP.",
            )
        else:
            self.add_result("export_zip", "PASS", ", ".join(sorted(EXPECTED_ZIP_FILES)))

    def check_controlled_shadow_export(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/target-allocation/shadow/export?format=json")
            if response.status_code != 200:
                raise ValueError(f"JSON API status {response.status_code}")
            wrapper = response.json()
            payload = wrapper.get("data")
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            if not ((payload or {}).get("compare") or {}).get("matched"):
                raise ValueError("controlled export compare.matched is not true")
            if ((payload or {}).get("compare") or {}).get("diffs"):
                raise ValueError("controlled export compare has diffs")

            zip_response = client.get("/api/target-allocation/shadow/export?format=zip")
            if zip_response.status_code != 200:
                raise ValueError(f"ZIP API status {zip_response.status_code}")
            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                names = set(archive.namelist())
                if names != CONTROLLED_EXPORT_ZIP_FILES:
                    raise ValueError(f"controlled ZIP names mismatch: {sorted(names)}")
                for name in names:
                    payload = json.loads(archive.read(name).decode("utf-8"))
                    ratio.assert_safe(payload)
                    assert_safe_payload(payload)

            self.check_controlled_export_cli_output(ratio)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "controlled_shadow_export",
                "target-allocation shadow export",
                f"Controlled export safety/current-only scan failed: {exc}",
                "Fix the controlled export service/API/CLI and rerun scripts/web_check.py.",
            )
            self.add_result("controlled_shadow_export", "FAIL", str(exc))
        else:
            self.add_result("controlled_shadow_export", "PASS", "API and CLI JSON/ZIP safe")

    def check_controlled_export_cli_output(self, ratio: Any) -> None:
        dry = self.run_command("controlled_export_dry_run", [sys.executable, "scripts/export_target_allocation_shadow.py", "--dry-run"])
        dry_summary = json.loads(dry)
        if dry_summary.get("output_path") is not None or dry_summary.get("matched") is not True:
            raise ValueError(f"unexpected dry-run summary: {dry_summary}")

        for format_name in ["json", "zip"]:
            output = self.run_command(
                f"controlled_export_{format_name}",
                [sys.executable, "scripts/export_target_allocation_shadow.py", "--format", format_name],
            )
            summary = json.loads(output)
            rel_path_text = str(summary.get("output_path") or "")
            if not rel_path_text.startswith("temp/web_exports/"):
                raise ValueError(f"controlled export path outside temp/web_exports: {rel_path_text}")
            output_path = ROOT / rel_path_text
            if not output_path.exists():
                raise ValueError(f"controlled export file missing: {rel_path_text}")
            if not is_forbidden_git_path(rel_path_text):
                raise ValueError(f"controlled export output is not covered by forbidden/ignored temp patterns: {rel_path_text}")
            try:
                if format_name == "json":
                    payload = json.loads(output_path.read_text(encoding="utf-8"))
                    ratio.assert_safe(payload)
                    assert_safe_payload(payload)
                else:
                    with zipfile.ZipFile(output_path) as archive:
                        names = set(archive.namelist())
                        if names != CONTROLLED_EXPORT_ZIP_FILES:
                            raise ValueError(f"controlled CLI ZIP names mismatch: {sorted(names)}")
                        for name in names:
                            payload = json.loads(archive.read(name).decode("utf-8"))
                            ratio.assert_safe(payload)
                            assert_safe_payload(payload)
            finally:
                output_path.unlink(missing_ok=True)

    def check_promotion_simulation_cli_output(self, ratio: Any) -> None:
        try:
            dry = self.run_command(
                "promotion_candidate_dry_run",
                [sys.executable, "scripts/simulate_target_allocation_promotion.py", "--mode", "candidate"],
            )
            dry_summary = json.loads(dry)
            ratio.assert_safe(dry_summary)
            assert_safe_payload(dry_summary)
            if dry_summary.get("output_path") is not None or dry_summary.get("matched") is not True:
                raise ValueError(f"unexpected candidate dry-run summary: {dry_summary}")

            written = self.run_command(
                "promotion_candidate_write",
                [sys.executable, "scripts/simulate_target_allocation_promotion.py", "--mode", "candidate", "--write"],
            )
            write_summary = json.loads(written)
            ratio.assert_safe(write_summary)
            assert_safe_payload(write_summary)
            rel_path_text = str(write_summary.get("output_path") or "")
            if not rel_path_text.startswith("temp/candidate_exports/"):
                raise ValueError(f"candidate export path outside temp/candidate_exports: {rel_path_text}")
            if "candidate" not in Path(rel_path_text).name:
                raise ValueError(f"candidate export filename missing candidate: {rel_path_text}")
            output_path = ROOT / rel_path_text
            if not output_path.exists():
                raise ValueError(f"candidate export file missing: {rel_path_text}")
            if not is_forbidden_git_path(rel_path_text):
                raise ValueError(f"candidate export output is not covered by forbidden/ignored temp patterns: {rel_path_text}")
            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
                ratio.assert_safe(payload)
                assert_safe_payload(payload)
                assert_no_export_runtime_terms(payload)
                compare = payload.get("golden_compare") or {}
                if compare.get("matched") is not True or compare.get("diffs"):
                    raise ValueError("candidate golden compare failed")
            finally:
                output_path.unlink(missing_ok=True)

            official = self.run_command(
                "promotion_official_blocked",
                [sys.executable, "scripts/simulate_target_allocation_promotion.py", "--mode", "official"],
            )
            official_summary = json.loads(official)
            ratio.assert_safe(official_summary)
            assert_safe_payload(official_summary)
            if official_summary.get("status") != "blocked":
                raise ValueError(f"official mode is not blocked: {official_summary}")
            if official_summary.get("output_path") is not None:
                raise ValueError(f"official mode produced output: {official_summary}")
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "promotion_simulation",
                "target-allocation promotion simulation",
                f"Candidate/official promotion simulation failed safety scan: {exc}",
                "Fix the promotion simulation service/CLI so candidate writes only temp exports and official is blocked.",
            )
            self.add_result("promotion_simulation", "FAIL", str(exc))
        else:
            self.add_result("promotion_simulation", "PASS", "candidate temp export safe and official blocked")

    def check_candidate_audit_export(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/target-allocation/candidate-audit?format=json")
            if response.status_code != 200:
                raise ValueError(f"JSON API status {response.status_code}")
            wrapper = response.json()
            payload = wrapper.get("data")
            self.assert_candidate_audit_payload_safe(payload, ratio)

            zip_response = client.get("/api/target-allocation/candidate-audit?format=zip")
            if zip_response.status_code != 200:
                raise ValueError(f"ZIP API status {zip_response.status_code}")
            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                names = set(archive.namelist())
                if names != CANDIDATE_AUDIT_ZIP_FILES:
                    raise ValueError(f"candidate audit ZIP names mismatch: {sorted(names)}")
                for name in names:
                    item = json.loads(archive.read(name).decode("utf-8"))
                    ratio.assert_safe(item)
                    assert_safe_payload(item)
                    assert_no_export_runtime_terms(item)

            self.check_candidate_audit_cli_output(ratio)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "candidate_audit_export",
                "target-allocation candidate audit",
                f"Candidate audit API/CLI safety scan failed: {exc}",
                "Fix the candidate audit service/API/CLI and rerun scripts/web_check.py.",
            )
            self.add_result("candidate_audit_export", "FAIL", str(exc))
        else:
            self.add_result("candidate_audit_export", "PASS", "API and CLI JSON/ZIP safe")

    def check_candidate_audit_cli_output(self, ratio: Any) -> None:
        dry = self.run_command(
            "candidate_audit_dry_run",
            [sys.executable, "scripts/export_target_allocation_candidate_audit.py", "--dry-run"],
        )
        dry_summary = json.loads(dry)
        ratio.assert_safe(dry_summary)
        assert_safe_payload(dry_summary)
        if dry_summary.get("output_path") is not None or dry_summary.get("matched") is not True:
            raise ValueError(f"unexpected candidate audit dry-run summary: {dry_summary}")
        if dry_summary.get("replay_fail_count") != 0 or dry_summary.get("official_allowed"):
            raise ValueError(f"candidate audit dry-run failed safety gates: {dry_summary}")

        for format_name in ["json", "zip"]:
            output = self.run_command(
                f"candidate_audit_{format_name}",
                [sys.executable, "scripts/export_target_allocation_candidate_audit.py", "--format", format_name],
            )
            summary = json.loads(output)
            ratio.assert_safe(summary)
            assert_safe_payload(summary)
            rel_path_text = str(summary.get("output_path") or "")
            if not rel_path_text.startswith("temp/candidate_exports/"):
                raise ValueError(f"candidate audit path outside temp/candidate_exports: {rel_path_text}")
            if "candidate_audit" not in Path(rel_path_text).name:
                raise ValueError(f"candidate audit filename missing candidate_audit: {rel_path_text}")
            if summary.get("matched") is not True or summary.get("replay_fail_count") != 0 or summary.get("official_allowed"):
                raise ValueError(f"candidate audit export failed safety gates: {summary}")
            output_path = ROOT / rel_path_text
            if not output_path.exists():
                raise ValueError(f"candidate audit export file missing: {rel_path_text}")
            if not is_forbidden_git_path(rel_path_text):
                raise ValueError(f"candidate audit output is not covered by forbidden/ignored temp patterns: {rel_path_text}")
            try:
                if format_name == "json":
                    payload = json.loads(output_path.read_text(encoding="utf-8"))
                    self.assert_candidate_audit_payload_safe(payload, ratio)
                else:
                    with zipfile.ZipFile(output_path) as archive:
                        names = set(archive.namelist())
                        if names != CANDIDATE_AUDIT_ZIP_FILES:
                            raise ValueError(f"candidate audit CLI ZIP names mismatch: {sorted(names)}")
                        for name in names:
                            payload = json.loads(archive.read(name).decode("utf-8"))
                            ratio.assert_safe(payload)
                            assert_safe_payload(payload)
                            assert_no_export_runtime_terms(payload)
            finally:
                output_path.unlink(missing_ok=True)

    @staticmethod
    def assert_candidate_audit_payload_safe(payload: dict[str, Any] | None, ratio: Any) -> None:
        if not payload:
            raise ValueError("candidate audit payload is empty")
        ratio.assert_safe(payload)
        assert_safe_payload(payload)
        assert_no_export_runtime_terms(payload)
        compare = payload.get("compare") or {}
        replay = payload.get("replay_summary") or {}
        promotion = payload.get("promotion_mode") or {}
        if compare.get("matched") is not True or compare.get("diffs"):
            raise ValueError("candidate audit compare failed")
        if compare.get("unsupported_fields"):
            raise ValueError("candidate audit has unsupported fields")
        if replay.get("failed") != 0:
            raise ValueError("candidate audit replay summary has failures")
        if promotion.get("official_allowed"):
            raise ValueError("candidate audit official mode is allowed")

    def check_history_snapshot_export(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/history/export?format=json")
            if response.status_code != 200:
                raise ValueError(f"JSON API status {response.status_code}")
            wrapper = response.json()
            payload = wrapper.get("data")
            self.assert_history_snapshot_payload_safe(payload, ratio)

            zip_response = client.get("/api/history/export?format=zip")
            if zip_response.status_code != 200:
                raise ValueError(f"ZIP API status {zip_response.status_code}")
            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                names = set(archive.namelist())
                if names != HISTORY_SNAPSHOT_ZIP_FILES:
                    raise ValueError(f"history snapshot ZIP names mismatch: {sorted(names)}")
                for name in names:
                    item = json.loads(archive.read(name).decode("utf-8"))
                    ratio.assert_safe(item)
                    assert_safe_payload(item)
                    assert_no_export_runtime_terms(item)

            self.check_history_snapshot_cli_output(ratio)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "history_snapshot_export",
                "history snapshot export",
                f"History snapshot API/CLI safety scan failed: {exc}",
                "Fix the history snapshot service/API/CLI and rerun scripts/web_check.py.",
            )
            self.add_result("history_snapshot_export", "FAIL", str(exc))
        else:
            self.add_result("history_snapshot_export", "PASS", "API and CLI JSON/ZIP safe")

    def check_history_snapshot_cli_output(self, ratio: Any) -> None:
        dry = self.run_command(
            "history_snapshot_dry_run",
            [sys.executable, "scripts/export_history_snapshot.py", "--dry-run"],
        )
        dry_summary = json.loads(dry)
        ratio.assert_safe(dry_summary)
        assert_safe_payload(dry_summary)
        if dry_summary.get("output_path") is not None or dry_summary.get("database_written") is not False:
            raise ValueError(f"unexpected history snapshot dry-run summary: {dry_summary}")
        if dry_summary.get("shadow_matched") is not True or dry_summary.get("candidate_matched") is not True:
            raise ValueError(f"history snapshot dry-run compare failed: {dry_summary}")
        if dry_summary.get("replay_fail_count") != 0 or dry_summary.get("official_allowed"):
            raise ValueError(f"history snapshot dry-run failed safety gates: {dry_summary}")

        for format_name in ["json", "zip"]:
            output = self.run_command(
                f"history_snapshot_{format_name}",
                [sys.executable, "scripts/export_history_snapshot.py", "--format", format_name],
            )
            summary = json.loads(output)
            ratio.assert_safe(summary)
            assert_safe_payload(summary)
            rel_path_text = str(summary.get("output_path") or "")
            if not rel_path_text.startswith("temp/history_exports/"):
                raise ValueError(f"history snapshot path outside temp/history_exports: {rel_path_text}")
            if "history_snapshot" not in Path(rel_path_text).name:
                raise ValueError(f"history snapshot filename missing history_snapshot: {rel_path_text}")
            if summary.get("shadow_matched") is not True or summary.get("candidate_matched") is not True:
                raise ValueError(f"history snapshot export compare failed: {summary}")
            if summary.get("replay_fail_count") != 0 or summary.get("official_allowed"):
                raise ValueError(f"history snapshot export failed safety gates: {summary}")
            if summary.get("database_written") is not True:
                raise ValueError(f"history snapshot database was not written: {summary}")
            output_path = ROOT / rel_path_text
            if not output_path.exists():
                raise ValueError(f"history snapshot export file missing: {rel_path_text}")
            if not is_forbidden_git_path(rel_path_text):
                raise ValueError(f"history snapshot output is not covered by forbidden/ignored temp patterns: {rel_path_text}")
            try:
                if format_name == "json":
                    payload = json.loads(output_path.read_text(encoding="utf-8"))
                    self.assert_history_snapshot_payload_safe(payload, ratio)
                else:
                    with zipfile.ZipFile(output_path) as archive:
                        names = set(archive.namelist())
                        if names != HISTORY_SNAPSHOT_ZIP_FILES:
                            raise ValueError(f"history snapshot CLI ZIP names mismatch: {sorted(names)}")
                        for name in names:
                            payload = json.loads(archive.read(name).decode("utf-8"))
                            ratio.assert_safe(payload)
                            assert_safe_payload(payload)
                            assert_no_export_runtime_terms(payload)
                if not HISTORY_DB_PATH.exists():
                    raise ValueError("history snapshot SQLite database missing")
            finally:
                output_path.unlink(missing_ok=True)
                HISTORY_DB_PATH.unlink(missing_ok=True)

    @staticmethod
    def assert_history_snapshot_payload_safe(payload: dict[str, Any] | None, ratio: Any) -> None:
        if not payload:
            raise ValueError("history snapshot payload is empty")
        ratio.assert_safe(payload)
        assert_safe_payload(payload)
        assert_no_export_runtime_terms(payload)
        live = payload.get("live_current_summary") or {}
        shadow = live.get("shadow_vs_reference") or {}
        candidate = live.get("candidate_audit_compare") or {}
        replay = live.get("replay_fixture_summary") or {}
        promotion = live.get("promotion_mode") or {}
        safety = payload.get("safety") or {}
        if shadow.get("matched") is not True or shadow.get("diff_count") != 0:
            raise ValueError("history snapshot shadow comparison failed")
        if candidate.get("matched") is not True or candidate.get("diff_count") != 0:
            raise ValueError("history snapshot candidate comparison failed")
        if replay.get("failed") != 0:
            raise ValueError("history snapshot replay summary has failures")
        if promotion.get("official_allowed"):
            raise ValueError("history snapshot official mode is allowed")
        for key in [
            "ratio_only",
            "current_only",
            "uses_latest_index_modules",
            "shadow_vs_reference_matched",
            "candidate_audit_matched",
            "official_promotion_blocked",
        ]:
            if safety.get(key) is not True:
                raise ValueError(f"history snapshot safety check failed: {key}")
        for key in [
            "writes_research_files",
            "updates_latest_index",
            "updates_current_modules",
            "generates_action_plan",
            "trading_feature",
            "execution_feature",
        ]:
            if safety.get(key) is not False:
                raise ValueError(f"history snapshot boundary failed: {key}")

    def assert_export_sources_current(self, payload: dict[str, Any]) -> None:
        latest = json.loads(LATEST_INDEX.read_text(encoding="utf-8-sig"))
        modules = latest.get("modules", {})
        sources = payload.get("sources", {})
        missing = REQUIRED_EXPORT_MODULES - set(sources)
        if missing:
            raise ValueError(f"missing export sources: {sorted(missing)}")
        if "files" in payload.get("latest_index", {}):
            raise ValueError("export latest_index contains files; current-only export must expose modules only")
        for module in REQUIRED_EXPORT_MODULES:
            source_path = (sources.get(module) or {}).get("path")
            current_path = (modules.get(module) or {}).get("path")
            if source_path != current_path:
                raise ValueError(f"{module} source mismatch: export={source_path} latest_index.modules={current_path}")

    def check_frontend_interactions(self) -> None:
        try:
            from fastapi.testclient import TestClient

            from web.backend.app.main import app
        except Exception as exc:  # noqa: BLE001
            self.fail("frontend_imports", "web/backend/app/main.py", f"Could not import app: {exc}", "Fix app imports.")
            return

        client = TestClient(app)
        for path in PAGE_PATHS:
            response = client.get(path)
            if response.status_code != 200:
                self.fail("page_status", path, f"Expected 200, got {response.status_code}.", "Fix page route or template.")
                continue
            if LOCAL_PATH_RE.search(response.text):
                self.fail("page_safety", path, "Page contains a local absolute path.", "Remove local absolute paths from templates.")

        for path, markers in INTERACTIVE_PAGE_CHECKS.items():
            html = client.get(path).text
            missing = [marker for marker in markers if marker not in html]
            if missing:
                self.fail(
                    "frontend_interactions",
                    path,
                    "Missing interaction hooks: " + ", ".join(missing),
                    "Restore search, sort, pagination target, and expandable row hooks.",
                )

        dashboard_html = client.get("/").text
        missing_dashboard = [marker for marker in DASHBOARD_CHECKS if marker not in dashboard_html]
        if missing_dashboard:
            self.fail(
                "dashboard_visuals",
                "web/backend/app/templates/dashboard.html",
                "Missing dashboard visual/status hooks: " + ", ".join(missing_dashboard),
                "Restore bucket gap chart and ResearchFirst/Intraday/project_check status cards.",
            )

        js_response = client.get("/static/app.js")
        if js_response.status_code != 200:
            self.fail("frontend_js", "web/backend/app/static/app.js", "Static JS not served.", "Fix StaticFiles mount.")
        else:
            script = js_response.text
            missing_js = [marker for marker in JS_CHECKS if marker not in script]
            if missing_js:
                self.fail(
                    "frontend_js",
                    "web/backend/app/static/app.js",
                    "Missing JS behavior markers: " + ", ".join(missing_js),
                    "Restore refresh sanitizer, pagination, and expandable detail logic.",
                )
        if not any(item.check in {"frontend_interactions", "dashboard_visuals", "frontend_js", "page_status", "page_safety"} for item in self.failures):
            self.add_result("frontend_interactions", "PASS", "tables, dashboard, sanitizer hooks")

    def check_run_web_script(self) -> None:
        try:
            from scripts import run_web

            if run_web.DEFAULT_HOST != "0.0.0.0":
                raise ValueError(f"default host is {run_web.DEFAULT_HOST}")
            if run_web.DEFAULT_PORT != 8000:
                raise ValueError(f"default port is {run_web.DEFAULT_PORT}")
            parser = run_web.build_parser()
            defaults = parser.parse_args([])
            if defaults.host != "0.0.0.0" or defaults.port != 8000:
                raise ValueError("parser defaults do not match trusted-LAN startup contract")
            override = parser.parse_args(["--host", "127.0.0.1", "--port", "8100", "--reload"])
            if override.host != "127.0.0.1" or override.port != 8100 or override.reload is not True:
                raise ValueError("host/port/reload overrides failed")
            output = self.run_command("run_web_help", [sys.executable, "scripts/run_web.py", "--help"])
            if "--host" not in output or "--port" not in output or "--reload" not in output:
                raise ValueError("run_web.py --help does not show host/port/reload options")
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "run_web_script",
                "scripts/run_web.py",
                f"run_web.py failed startup contract check: {exc}",
                "Set DEFAULT_HOST to 0.0.0.0, keep --host/--port/--reload overrides, and make --help runnable.",
            )
            self.add_result("run_web_script", "FAIL", str(exc))
        else:
            self.add_result("run_web_script", "PASS", "default host 0.0.0.0 and --help safe")

    def check_current_only_code_paths(self) -> None:
        files = [
            ROOT / "scripts" / "ingest_current_state.py",
            ROOT / "scripts" / "ingest_current_state_to_web_db.py",
            ROOT / "scripts" / "export_target_allocation_shadow.py",
            ROOT / "scripts" / "simulate_target_allocation_promotion.py",
            ROOT / "scripts" / "export_target_allocation_candidate_audit.py",
            ROOT / "scripts" / "export_history_snapshot.py",
            ROOT / "web" / "scripts" / "ingest_current_state.py",
            *list((ROOT / "web" / "backend" / "app").rglob("*.py")),
        ]
        offenders: list[str] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            if "latest_index.files" in text or '["files"]' in text or "['files']" in text:
                offenders.append(rel(path))
        if offenders:
            self.fail(
                "current_only_code_paths",
                ", ".join(offenders),
                "Code references latest_index.files as a structured source.",
                "Use latest_index.modules pointers for current state.",
            )
            self.add_result("current_only_code_paths", "FAIL", ", ".join(offenders))
        else:
            self.add_result("current_only_code_paths", "PASS", "No latest_index.files code path")

    def check_no_research_logic_changes(self) -> None:
        protected = [
            "scripts/generate_action_plan.py",
            "scripts/generate_target_allocation.py",
            "generate_action_plan.py",
            "generate_target_allocation.py",
        ]
        changed = set(git_lines(["git", "diff", "--name-only", "origin/main...HEAD", "--", *protected]))
        changed.update(git_lines(["git", "diff", "--name-only", "--", *protected]))
        changed.update(git_lines(["git", "diff", "--cached", "--name-only", "--", *protected]))
        if changed:
            self.fail(
                "protected_research_logic",
                ", ".join(sorted(changed)),
                "Protected research generation logic changed in this milestone.",
                "Move those changes out of this Web verification milestone.",
            )
            self.add_result("protected_research_logic", "FAIL", ", ".join(sorted(changed)))
        else:
            self.add_result("protected_research_logic", "PASS", "No protected generator changes")

    def check_git_scope(self) -> None:
        status_paths = status_short_paths()
        changed_paths = set(status_paths)
        changed_paths.update(git_lines(["git", "diff", "--name-only"]))
        changed_paths.update(git_lines(["git", "diff", "--cached", "--name-only"]))
        changed_paths.update(git_lines(["git", "diff", "--name-only", "origin/main...HEAD"]))
        tracked_paths = set(git_lines(["git", "ls-files"]))
        forbidden_changed = sorted(path for path in changed_paths if is_forbidden_git_path(path))
        forbidden_tracked = sorted(path for path in tracked_paths if is_forbidden_git_path(path))
        if forbidden_changed:
            self.fail(
                "git_forbidden_changed_files",
                ", ".join(forbidden_changed),
                "Forbidden runtime/sensitive files are in the commit scope.",
                "Unstage/remove them and keep runtime output under ignored temp/.",
            )
            self.add_result("git_forbidden_changed_files", "FAIL", ", ".join(forbidden_changed))
        else:
            self.add_result("git_forbidden_changed_files", "PASS", "No forbidden changed files")
        if forbidden_tracked:
            self.fail(
                "git_forbidden_tracked_files",
                ", ".join(forbidden_tracked),
                "Forbidden runtime/sensitive files are already tracked by Git.",
                "Remove tracked runtime/sensitive files from Git and keep examples sanitized.",
            )
            self.add_result("git_forbidden_tracked_files", "FAIL", ", ".join(forbidden_tracked))
        else:
            self.add_result("git_forbidden_tracked_files", "PASS", "No forbidden tracked files")

    def has_fail(self, check: str) -> bool:
        return any(problem.check == check for problem in self.failures)

    def print_summary(self) -> None:
        status = "FAIL" if self.failures else ("WARN" if self.warnings else "PASS")
        print("\n=== MyInvest Phase 3 Web Milestone Check ===")
        print(f"SUMMARY: {status}")
        print("\nChecks:")
        for result in self.results:
            detail = f" - {result.detail}" if result.detail else ""
            print(f"  [{result.status}] {result.name}{detail}")

        if self.failures:
            print("\nBlocking failures:")
            for idx, problem in enumerate(self.failures, 1):
                print_problem(idx, problem)

        if self.warnings:
            print("\nWarnings:")
            for idx, problem in enumerate(self.warnings, 1):
                print_problem(idx, problem)

        print("\nCommit suggestion:")
        print(f"  {COMMIT_MESSAGE}")
        print("\nCommit file list:")
        files = commit_file_list()
        if files:
            for path in files:
                print(f"  {path}")
        else:
            print("  No pending files. Current branch may already contain the milestone commit.")
        print("\nDo not commit:")
        print("  temp/, SQLite/DB files, runtime/, caches, node_modules/, build/dist, .env, ZIP/log artifacts")
        print("\nGit status:")
        status_lines = git_lines(["git", "status", "-sb", "-uall"])
        if status_lines:
            for line in status_lines:
                print(f"  {line}")
        else:
            print("  unavailable")


def command_label(args: list[str]) -> str:
    return " ".join(args)


def tail(value: str, lines: int = 20) -> str:
    parts = value.strip().splitlines()
    return "\n".join(parts[-lines:])


def first_line(value: str) -> str:
    for line in value.splitlines():
        if line.strip():
            return line.strip()
    return ""


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def normalize(path: str) -> str:
    return path.replace("\\", "/").lower()


def git_lines(args: list[str]) -> list[str]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def status_short_paths() -> list[str]:
    paths: list[str] = []
    proc = subprocess.run(
        ["git", "status", "--short", "-uall"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        return paths
    for line in proc.stdout.splitlines():
        if len(line) > 3:
            paths.append(line[3:].strip().strip('"'))
    return paths


def commit_file_list() -> list[str]:
    files: set[str] = set(status_short_paths())
    files.update(git_lines(["git", "diff", "--name-only"]))
    files.update(git_lines(["git", "diff", "--cached", "--name-only"]))
    if not files:
        files.update(git_lines(["git", "diff", "--name-only", "origin/main...HEAD"]))
    return sorted(files)


def is_forbidden_git_path(path: str) -> bool:
    norm = normalize(path)
    if norm in ALLOWED_GIT_PATHS:
        return False
    return any(fnmatch.fnmatch(norm, pattern.lower()) for pattern in FORBIDDEN_GIT_PATTERNS)


def walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}", key
            yield from walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from walk(item, f"{path}[{idx}]")
    else:
        yield path, value


def assert_safe_payload(value: Any) -> None:
    for path, item in walk(value):
        if isinstance(item, str):
            if LOCAL_PATH_RE.search(item):
                raise ValueError(f"local absolute path at {path}")
            if FORBIDDEN_TEXT_RE.search(item):
                raise ValueError(f"forbidden text at {path}")
        else:
            if isinstance(item, str) and FORBIDDEN_TEXT_RE.search(item):
                raise ValueError(f"forbidden text at {path}")
    assert_safe_keys(value)


def assert_safe_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if FORBIDDEN_KEY_RE.search(key_text):
                raise ValueError(f"forbidden key {path}.{key_text}")
            assert_safe_keys(item, f"{path}.{key_text}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            assert_safe_keys(item, f"{path}[{idx}]")


def assert_no_export_runtime_terms(value: Any) -> None:
    for path, item in walk(value):
        if isinstance(item, str):
            lowered = normalize(item)
            if any(term in lowered for term in EXPORT_BLOCKED_VALUE_TERMS):
                raise ValueError(f"blocked export runtime/sensitive term at {path}: {item}")


def print_problem(idx: int, problem: Problem) -> None:
    print(f"  {idx}. {problem.check}")
    print(f"     file: {problem.file}")
    print(f"     reason: {problem.reason}")
    print(f"     fix: {problem.fix}")


def main() -> int:
    return WebCheck().run()


if __name__ == "__main__":
    raise SystemExit(main())
