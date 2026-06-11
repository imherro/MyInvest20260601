from __future__ import annotations

import argparse
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

COMMIT_MESSAGE = "feat(web): add assistant feature suite"
CHECK_MODES = {"smoke", "release"}

API_PATHS = [
    "/api/health",
    "/api/environment/status",
    "/api/diagnostics/schema",
    "/api/diagnostics/historical-metrics",
    "/api/readiness/summary",
    "/api/readiness/checks",
    "/api/user/preferences",
    "/api/user/preferences/default",
    "/api/dashboard/summary",
    "/api/dashboard/user_metrics/default",
    "/api/assistant/daily",
    "/api/assistant/risk-center",
    "/api/assistant/research-tasks",
    "/api/assistant/preferences",
    "/api/assistant/scenarios",
    "/api/assistant/history-visuals",
    "/api/assistant/review-score",
    "/api/assistant/premarket",
    "/api/assistant/search?q=688333",
    "/api/assistant/securities/688333.SH",
    "/api/assistant/weekly-safety",
    "/api/workbench/integration",
    "/api/audit/bundle",
    "/api/audit/bundle?time_window=7d&module_filter=dashboard",
    "/api/dashboard/current",
    "/api/current",
    "/api/latest-index",
    "/api/modules/current",
    "/api/subjects/status",
    "/api/subjects/status/511360.SH",
    "/api/subjects/freshness",
    "/api/subjects/gap",
    "/api/themes/status",
    "/api/buckets/status",
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
    "/api/history/gap-summary",
    "/api/securities/688333.SH/valuation-history",
    "/api/securities/688333.SH/history",
    "/api/market/history",
    "/api/positions/history?bucket=defense",
    "/api/actions/history?action_type=Reduce",
    "/api/history/quality",
    "/api/history/coverage",
    "/api/portfolio/current",
    "/api/intraday-rules/current",
    "/api/research-first/current",
    "/api/system-check/current",
    "/api/decision-log/current",
    "/api/decision-timeline",
    "/api/decision-timeline/current-action-plan",
    "/api/historical-metrics",
    "/api/historical-metrics/bucket-attack_mainline",
    "/api/export/review_package?format=json",
]

API_SMOKE_EXCLUDED_PREFIXES = (
    "/api/export/",
    "/api/history/export",
    "/api/target-allocation/candidate-audit",
    "/api/target-allocation/shadow",
)
API_SMOKE_PATHS = [
    path for path in API_PATHS if not path.startswith(API_SMOKE_EXCLUDED_PREFIXES)
]

PAGE_PATHS = [
    "/",
    "/dashboard",
    "/assistant",
    "/assistant/risk-center",
    "/assistant/research-tasks",
    "/assistant/preferences",
    "/assistant/scenarios",
    "/assistant/history-visuals",
    "/assistant/review-score",
    "/assistant/premarket",
    "/assistant/search?q=688333",
    "/assistant/securities/688333.SH",
    "/assistant/weekly-safety",
    "/settings",
    "/environment",
    "/preferences",
    "/audit",
    "/readiness",
    "/manager",
    "/researcher",
    "/trader",
    "/system",
    "/action-plan",
    "/target-allocation",
    "/research-first",
    "/subjects",
    "/subjects/gap",
    "/themes",
    "/history/gap-dashboard",
    "/buckets",
    "/buckets/drilldown",
    "/subjects/drilldown",
    "/portfolio",
    "/intraday-rules",
    "/decision-log",
    "/decision-timeline",
    "/historical-metrics",
    "/history",
    "/securities/688333.SH/history",
    "/securities/688333.SH/valuation",
    "/market/history",
    "/positions/history?bucket=defense",
    "/actions/history?action_type=Reduce",
    "/history/quality",
    "/history/coverage",
    "/system-checks",
]

INTERACTIVE_PAGE_CHECKS = {
    "/settings": [
        'data-environment-section="git"',
        'data-environment-section="safety"',
        'data-status-card="env-readonly"',
        'data-bind="env_branch"',
        "environmentCheckRows",
    ],
    "/preferences": [
        'data-preferences-section="display"',
        'data-preferences-section="dashboard"',
        'data-preferences-section="safety"',
        'data-status-card="pref-readonly"',
        'data-bind="pref_refresh"',
        "preferenceRows",
        "preferenceSourceRows",
    ],
    "/audit": [
        'data-audit-section="summary"',
        "data-audit-window",
        "data-audit-module",
        "auditPreviewChart",
        "auditBundleRows",
        "/static/audit.js",
    ],
    "/readiness": [
        'data-readiness-section="summary"',
        'data-readiness-section="signals"',
        'data-readiness-section="safety"',
        'data-readiness-view="summary"',
        'data-readiness-view="checks"',
        'data-table-search="readinessCheckTable"',
        "readinessCheckRows",
        "readinessSafetyRows",
        "/static/readiness.js",
    ],
    "/assistant": [
        'data-assistant-section="today"',
        'data-assistant-section="next-steps"',
        'data-assistant-section="risk-heatmap"',
        'data-assistant-section="research-priorities"',
        'data-assistant-section="scenario-simulation"',
        'data-assistant-section="allocation-drift"',
        'data-assistant-section="review-loop"',
        'data-assistant-section="history-visuals"',
        'data-assistant-section="explanations"',
        'data-assistant-section="suite-links"',
    ],
    "/assistant/risk-center": ["data-assistant-suite", "data-assistant-suite-table"],
    "/assistant/research-tasks": ["data-assistant-suite", "data-assistant-suite-table"],
    "/assistant/preferences": ["data-assistant-suite", "data-assistant-suite-table"],
    "/assistant/scenarios": ["data-assistant-suite", "data-assistant-suite-table"],
    "/assistant/history-visuals": ["data-assistant-suite", "data-assistant-suite-table"],
    "/assistant/review-score": ["data-assistant-suite", "data-assistant-suite-table"],
    "/assistant/premarket": ["data-assistant-suite", "data-assistant-suite-table"],
    "/assistant/search?q=688333": ["data-assistant-suite", "data-assistant-suite-search", "data-assistant-suite-table"],
    "/assistant/securities/688333.SH": ["data-assistant-suite", "data-assistant-suite-links", "data-assistant-suite-table"],
    "/assistant/weekly-safety": ["data-assistant-suite", "data-assistant-suite-sections", "data-assistant-suite-table"],
    "/manager": ["data-role-workbench", "data-role-workflows", "data-role-links", "data-role-tools", "/tools?group=基金经理"],
    "/researcher": ["data-role-workbench", "data-role-workflows", "data-role-links", "data-role-tools", "/tools?group=研究员"],
    "/trader": ["data-role-workbench", "data-role-workflows", "data-role-links", "data-role-tools", "/tools?group=操盘手"],
    "/system": ["data-role-workbench", "data-role-workflows", "data-role-links", "data-role-tools", "/tools?group=系统与开发"],
    "/action-plan": ["data-table-search", "data-sort", "actionRows"],
    "/target-allocation": ["data-table-search", "data-sort", "targetRows"],
    "/subjects": ["data-table-search", "data-sort", "subjectsRows"],
    "/subjects/gap": ["data-table-search", "data-sort", "subjectGapRows"],
    "/themes": ["data-table-search", "data-table-filter", "data-sort", "themesRows"],
    "/history/gap-dashboard": ["data-table-search", "data-table-filter", "data-sort", "historyGapRows", "historyEntryRows"],
    "/buckets": ["data-table-search", "data-table-filter", "data-sort", "bucketRows", "bucketSubjectRows"],
    "/buckets/drilldown": ["data-table-search", "data-table-filter", "data-sort", "bucketDrilldownRows", "bucketDrilldownChart"],
    "/subjects/drilldown": ["data-table-search", "data-table-filter", "data-sort", "subjectDrilldownRows"],
    "/portfolio": ["data-table-search", "data-sort", "portfolioRows"],
    "/intraday-rules": ["data-table-search", "data-sort", "intradayRows", "disabledTriggerRows"],
    "/decision-log": ["data-table-search", "data-sort", "decisionRows"],
    "/decision-timeline": ["data-table-search", "data-table-filter", "data-sort", "decisionTimelineRows", "decisionTimelineChart"],
    "/historical-metrics": ["data-table-search", "data-table-filter", "data-sort", "historicalMetricRows", "historicalMetricsChart"],
}

DASHBOARD_CHECKS = [
    "bucketGapChart",
    'data-dashboard-section="system-status"',
    'data-dashboard-section="market-position"',
    'data-dashboard-section="action-plan-summary"',
    'data-dashboard-section="allocation-summary"',
    'data-dashboard-section="workbench-integration"',
    'data-dashboard-section="analytics"',
    'data-dashboard-section="subject-summaries"',
    'data-dashboard-section="quick-links"',
    "workbenchIntegrationRows",
    "workbenchModuleLinks",
    "dashboardAnalyticsRows",
    "data-dashboard-window",
    'data-status-card="system"',
    'data-status-card="research-first"',
    'data-status-card="intraday"',
]

JS_CHECKS = [
    "function assertRatioOnly",
    "function renderPagination",
    "function renderEnvironment",
    "function renderUserPreferences",
    "function renderDashboardAnalytics",
    "function renderWorkbenchIntegration",
    "function setupDashboardWindow",
    "function renderDashboardQuickLinks",
    "function renderDecisionAssistant",
    "function renderAssistantFeature",
    "function renderSubjectStatus",
    "function renderSubjectGap",
    "function renderThemes",
    "function renderHistoryGapDashboard",
    "function renderHistoryGapChart",
    "function renderBuckets",
    "function renderBucketDrilldown",
    "function renderBucketDrilldownChart",
    "function renderSubjectDrilldown",
    "function renderDecisionTimeline",
    "function renderDecisionTimelineChart",
    "function renderHistoricalMetricsChart",
    "function updateHistoricalMetricsSummary",
    "function setupFilters",
    "detail-row",
    "expandable-row",
    "setInterval(refresh",
    "fetch(apiPath",
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
ALLOWED_FORBIDDEN_KEY_PATHS: set[str] = set()
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
    def __init__(self, mode: str = "smoke") -> None:
        if mode not in CHECK_MODES:
            raise ValueError(f"Unsupported Web check mode: {mode}")
        self.mode = mode
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
        if self.mode == "smoke":
            self.run_smoke()
        elif self.mode == "release":
            self.run_release()
        self.print_summary()
        return 1 if self.failures else 0

    def run_smoke(self) -> None:
        self.run_ingest()
        action_path = self.latest_action_plan_path()
        self.run_ratio_and_gate_checks(action_path)
        self.run_project_checks()
        self.check_api_smoke()
        self.check_frontend_smoke()
        self.check_run_web_script()
        self.check_current_only_code_paths()

    def run_release(self) -> None:
        self.check_git_scope()
        self.run_hidden_unicode_check()
        self.check_no_research_logic_changes()
        self.run_ingest()
        self.run_pytest()
        action_path = self.latest_action_plan_path()
        self.run_ratio_and_gate_checks(action_path)
        self.run_project_checks()
        self.check_api_and_export()
        self.check_frontend_interactions()
        self.check_run_web_script()
        self.check_current_only_code_paths()

    def run_hidden_unicode_check(self) -> None:
        args = [sys.executable, "scripts/check_hidden_unicode.py", "--json"]
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
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            self.add_result("check_hidden_unicode", "FAIL", tail(output))
            self.fail(
                "check_hidden_unicode",
                command_label(args),
                "Hidden Unicode checker did not return valid JSON.",
                "Run python scripts/check_hidden_unicode.py --json and fix the reported output.",
            )
            return
        scanned = payload.get("scanned_file_count", 0)
        finding_count = payload.get("finding_count", 0)
        if proc.returncode != 0 or payload.get("status") != "OK" or finding_count:
            detail = f"Hidden Unicode check: FAIL; scanned_file_count={scanned}; finding_count={finding_count}"
            self.add_result("check_hidden_unicode", "FAIL", detail)
            self.fail(
                "check_hidden_unicode",
                command_label(args),
                "Hidden Unicode format controls were found.",
                "Run python scripts/check_hidden_unicode.py to inspect path, line, column, codepoint, Unicode name, and preview; remove only hidden control characters.",
            )
            return
        self.add_result("check_hidden_unicode", "PASS", f"Hidden Unicode check: OK; scanned_file_count={scanned}")

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

    def check_api_smoke(self) -> None:
        try:
            TestClient = import_test_client()

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

        for path in API_SMOKE_PATHS:
            response = client.get(path)
            if response.status_code != 200:
                self.fail(
                    "api_smoke_status",
                    path,
                    f"Expected 200, got {response.status_code}.",
                    "Fix the endpoint or ingest data source and rerun scripts/web_check.py.",
                )
                continue
            try:
                data = response.json()
                if path == "/api/environment/status":
                    assert_environment_status_payload(data)
                else:
                    ratio.assert_safe(data)
                    assert_safe_payload(data)
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    "api_smoke_safety",
                    path,
                    f"API response failed ratio-only or path scan: {exc}",
                    "Sanitize the endpoint response before returning it.",
                )
        api_status = "FAIL" if self.has_fail("api_smoke_status") or self.has_fail("api_smoke_safety") else "PASS"
        self.add_result("api_smoke", api_status, f"{len(API_SMOKE_PATHS)} endpoints")

        self.check_api_is_read_only(client)
        self.check_environment_status_api(client)
        self.check_schema_guard_api(client, ratio)
        self.check_historical_metrics_guard_api(client, ratio)
        self.check_workbench_readiness_api(client, ratio)

    def check_api_and_export(self) -> None:
        try:
            TestClient = import_test_client()

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
                if path == "/api/environment/status":
                    assert_environment_status_payload(data)
                else:
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
        self.check_environment_status_api(client)
        self.check_schema_guard_api(client, ratio)
        self.check_historical_metrics_guard_api(client, ratio)
        self.check_workbench_readiness_api(client, ratio)
        self.check_subject_status_api(client, ratio)
        self.check_subject_gap_api(client, ratio)
        self.check_dashboard_api(client, ratio)
        self.check_theme_status_api(client, ratio)
        self.check_history_gap_api(client, ratio)
        self.check_bucket_status_api(client, ratio)
        self.check_allocation_drilldown_api(client, ratio)
        self.check_decision_timeline_api(client, ratio)
        self.check_historical_metrics_api(client, ratio)
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
                "Remove write endpoints from the read-only Web API.",
            )
            self.add_result("openapi_read_only", "FAIL", "; ".join(mutating))
        else:
            self.add_result("openapi_read_only", "PASS", "No POST/PUT/PATCH/DELETE under /api")

    def check_environment_status_api(self, client: Any) -> None:
        try:
            response = client.get("/api/environment/status")
            if response.status_code != 200:
                raise ValueError(f"Expected 200, got {response.status_code}")
            envelope = response.json()
            if envelope.get("ok") is not True:
                raise ValueError("environment response ok flag is not true")
            assert_safe_payload(envelope)
            payload = envelope.get("data") or {}
            assert_environment_status_payload(payload)
            if payload.get("module") != "environment_status":
                raise ValueError("module mismatch")
            if payload.get("readonly") is not True or payload.get("current_only") is not True:
                raise ValueError("top-level readonly/current-only flags are not true")
            safety = payload.get("safety") or {}
            for key in ["no_trading", "no_qmt_write", "no_execution_generation", "research_first_gate_required"]:
                if safety.get(key) is not True:
                    raise ValueError(f"safety flag is not true: {key}")
            if safety.get("research_current_mutation") is not False:
                raise ValueError("research_current_mutation must be false")
            web = payload.get("web") or {}
            if web.get("default_host") != "0.0.0.0" or web.get("default_port") != 8000:
                raise ValueError("default Web host/port changed")
            paths = payload.get("paths") or {}
            if paths.get("web_db_path") != "temp/web_db/myinvest.sqlite":
                raise ValueError("web_db_path must be repo-relative temp/web_db/myinvest.sqlite")
        except Exception as exc:  # noqa: BLE001
            self.add_result("environment_status_api", "FAIL", str(exc))
            self.fail(
                "environment_status_api",
                "/api/environment/status",
                f"Environment status API failed safety check: {exc}",
                "Return sanitized read-only metadata only, with repo-relative paths.",
            )
            return
        self.add_result("environment_status_api", "PASS", "read-only workbench environment status safe")

    def check_schema_guard_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/diagnostics/schema")
            if response.status_code != 200:
                raise ValueError(f"Expected 200, got {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            guard = ((payload.get("data") or {}).get("schema_guard") or {})
            if guard.get("module") != "schema_guard":
                raise ValueError("module mismatch")
            if guard.get("current_only") is not True or guard.get("read_only") is not True:
                raise ValueError("schema guard is not marked current-only/read-only")
            if guard.get("expected_schema_version") != "web_read_model_v1":
                raise ValueError("expected schema version mismatch")
            if guard.get("status") not in {"ok", "degraded", "mismatch", "unavailable"}:
                raise ValueError(f"unsupported schema guard status: {guard.get('status')}")
            if guard.get("status") in {"mismatch", "unavailable"}:
                raise ValueError(f"schema guard reported blocking status: {guard.get('status')}")
            if not guard.get("expected_schema_fingerprint"):
                raise ValueError("expected schema fingerprint is empty")
            if guard.get("observed_schema_fingerprint") and guard.get("schema_fingerprint_match") is not True:
                raise ValueError("observed schema fingerprint did not match")
            if guard.get("required_tables_present") is not True or guard.get("required_columns_present") is not True:
                raise ValueError("required schema contract is not present")
            if not isinstance(guard.get("missing_required_tables"), list):
                raise ValueError("missing_required_tables is not a list")
            if not isinstance(guard.get("missing_required_columns"), dict):
                raise ValueError("missing_required_columns is not a dict")
            contract = guard.get("schema_contract") or {}
            if contract.get("required_table_count", 0) <= 0 or contract.get("required_column_count", 0) <= 0:
                raise ValueError("schema contract counts are empty")
            if contract.get("missing_required_table_count") != 0 or contract.get("missing_required_column_count") != 0:
                raise ValueError("schema contract reports missing structures")
            enforcement = guard.get("enforcement") or {}
            if enforcement.get("mode") != "read_only_schema_guard":
                raise ValueError("schema guard enforcement mode mismatch")
            if enforcement.get("read_model_usable") is not True:
                raise ValueError("schema guard reports read model unusable")
            if enforcement.get("web_smoke_compatible") is not True:
                raise ValueError("schema guard is not Web-smoke compatible")
            if enforcement.get("fail_closed") is not False:
                raise ValueError("schema guard fail_closed is unexpectedly true for current DB")
            safety = guard.get("safety") or {}
            for key in ["no_sqlite_writes", "no_migration", "get_only", "ratio_only", "current_only"]:
                if safety.get(key) is not True:
                    raise ValueError(f"safety flag is not true: {key}")
        except Exception as exc:  # noqa: BLE001
            self.add_result("schema_guard_api", "FAIL", str(exc))
            self.fail(
                "schema_guard_api",
                "/api/diagnostics/schema",
                f"Schema guard API failed safety check: {exc}",
                "Return sanitized read-only schema metadata only.",
            )
            return
        self.add_result("schema_guard_api", "PASS", "read-only schema guard diagnostics safe")

    def check_historical_metrics_guard_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/diagnostics/historical-metrics")
            if response.status_code != 200:
                raise ValueError(f"Expected 200, got {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            guard = ((payload.get("data") or {}).get("historical_metrics_guard") or {})
            if guard.get("module") != "historical_metrics_guard":
                raise ValueError("module mismatch")
            if guard.get("current_only") is not True or guard.get("read_only") is not True:
                raise ValueError("guard is not marked current-only/read-only")
            if guard.get("ratio_only") is not True:
                raise ValueError("guard is not marked ratio-only")
            if guard.get("status") not in {"ok", "degraded", "mismatch", "unavailable"}:
                raise ValueError(f"unsupported guard status: {guard.get('status')}")
            if guard.get("status") in {"mismatch", "unavailable"}:
                raise ValueError(f"historical metrics guard reported blocking status: {guard.get('status')}")
            if guard.get("required_inputs_present") is not True:
                raise ValueError("required inputs are not present")
            if guard.get("missing_inputs") != []:
                raise ValueError("missing inputs should be empty for current DB")
            if not isinstance(guard.get("table_counts"), dict) or not guard.get("table_counts"):
                raise ValueError("table_counts is empty")
            if not isinstance(guard.get("source_modules"), dict) or not guard.get("source_modules"):
                raise ValueError("source_modules is empty")
            contract = guard.get("contract") or {}
            if contract.get("contract_version") != "historical_metrics_guard_v1":
                raise ValueError("contract version mismatch")
            for key in [
                "required_inputs",
                "observed_inputs",
                "missing_inputs",
                "required_source_modules",
                "observed_source_modules",
                "missing_source_modules",
                "expected_fingerprint",
                "observed_fingerprint",
                "fingerprint_match",
            ]:
                if key not in contract:
                    raise ValueError(f"contract field missing: {key}")
            if not contract.get("expected_fingerprint") or not contract.get("observed_fingerprint"):
                raise ValueError("contract fingerprint is missing")
            if contract.get("fingerprint_match") is not True:
                raise ValueError("contract fingerprint mismatch for current DB")
            if contract.get("missing_source_modules") != []:
                raise ValueError("source modules should be complete for current DB")
            if contract.get("missing_integration_payloads") != []:
                raise ValueError("integration payloads should be complete for current DB")
            enforcement = guard.get("enforcement") or {}
            if enforcement.get("mode") != "full_read_only_historical_metrics_guard":
                raise ValueError("enforcement mode mismatch")
            if enforcement.get("fail_closed") is not False:
                raise ValueError("fail_closed should be false for current DB")
            if enforcement.get("read_model_usable") is not True:
                raise ValueError("read model should be usable for current DB")
            if enforcement.get("web_smoke_compatible") is not True:
                raise ValueError("guard is not Web-smoke compatible")
            if enforcement.get("audit_bundle_compatible") is not True:
                raise ValueError("guard is not audit-bundle compatible")
            if enforcement.get("contract_match") is not True:
                raise ValueError("enforcement contract_match should be true")
            safety = guard.get("safety") or {}
            for key in ["read_only", "ratio_only", "current_only", "research_first_neutral", "openapi_get_only"]:
                if safety.get(key) is not True:
                    raise ValueError(f"safety flag is not true: {key}")
            if safety.get("uses_latest_index_files") is not False:
                raise ValueError("latest_index.files safety flag must be false")
        except Exception as exc:  # noqa: BLE001
            self.add_result("historical_metrics_guard_api", "FAIL", str(exc))
            self.fail(
                "historical_metrics_guard_api",
                "/api/diagnostics/historical-metrics",
                f"Historical metrics guard API failed safety check: {exc}",
                "Return sanitized read-only Historical Metrics guard metadata only.",
            )
            return
        self.add_result("historical_metrics_guard_api", "PASS", "read-only Historical Metrics guard diagnostics safe")

    def check_workbench_readiness_api(self, client: Any, ratio: Any) -> None:
        try:
            for path in ["/api/readiness/summary", "/api/readiness/checks"]:
                response = client.get(path)
                if response.status_code != 200:
                    raise ValueError(f"{path} expected 200, got {response.status_code}")
                payload = response.json()
                ratio.assert_safe(payload)
                assert_safe_payload(payload)
                readiness = payload.get("data") or {}
                if readiness.get("module") != "workbench_readiness":
                    raise ValueError(f"{path} module mismatch")
                if readiness.get("status") not in {"ok", "degraded", "mismatch", "unavailable"}:
                    raise ValueError(f"{path} unsupported status: {readiness.get('status')}")
                if readiness.get("status") in {"mismatch", "unavailable"}:
                    raise ValueError(f"{path} reported blocking status: {readiness.get('status')}")
                if readiness.get("fail_closed") is not False:
                    raise ValueError(f"{path} fail_closed should be false for current DB")
                if readiness.get("web_smoke_compatible") is not True:
                    raise ValueError(f"{path} is not Web-smoke compatible")
                if not isinstance(readiness.get("checks"), list) or not readiness.get("checks"):
                    raise ValueError(f"{path} checks are missing")
                if not isinstance(readiness.get("summary"), dict) or not readiness.get("summary"):
                    raise ValueError(f"{path} summary is missing")
                safety = readiness.get("safety") or {}
                for key in [
                    "read_only",
                    "ratio_only",
                    "current_only",
                    "research_first",
                    "get_only",
                    "no_validation_commands",
                    "no_file_writes",
                    "no_sqlite_writes",
                ]:
                    if safety.get(key) is not True:
                        raise ValueError(f"{path} safety flag is not true: {key}")
                if safety.get("uses_latest_index_files") is not False:
                    raise ValueError(f"{path} latest_index.files safety flag must be false")
                names = {str(check.get("name")) for check in readiness.get("checks") or []}
                required = {
                    "environment_settings",
                    "schema_diagnostics",
                    "historical_metrics_diagnostics",
                    "dashboard_summary",
                    "audit_bundle_availability",
                    "current_validation_summary",
                }
                if not required.issubset(names):
                    raise ValueError(f"{path} missing readiness checks: {sorted(required - names)}")
                for check in readiness.get("checks") or []:
                    if check.get("status") not in {"ok", "degraded", "mismatch", "unavailable"}:
                        raise ValueError(f"{path} unsupported check status: {check.get('name')}")
                    if check.get("fail_closed") is True:
                        raise ValueError(f"{path} check failed closed: {check.get('name')}")
                    if check.get("web_smoke_compatible") is not True:
                        raise ValueError(f"{path} check is not Web-smoke compatible: {check.get('name')}")
        except Exception as exc:  # noqa: BLE001
            self.add_result("workbench_readiness_api", "FAIL", str(exc))
            self.fail(
                "workbench_readiness_api",
                "/api/readiness/summary",
                f"Workbench readiness API failed safety check: {exc}",
                "Return sanitized read-only readiness metadata only.",
            )
            return
        self.add_result("workbench_readiness_api", "PASS", "read-only Workbench readiness APIs safe")

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
                for source_path in (item.get("source_paths") or {}).values():
                    source_text = str(source_path)
                    if LOCAL_PATH_RE.search(source_text):
                        raise ValueError(f"local source path leaked for {item.get('code')}")
                    if Path(source_text).is_absolute() or ".." in Path(source_text).parts:
                        raise ValueError(f"unsafe source path leaked for {item.get('code')}: {source_text}")
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
                if cash.get("research_first_status") != "pass" or cash.get("gate_conclusion") != "eligible_for_review":
                    raise ValueError("511360 gate status is not eligible_for_review/pass")
            else:
                raise ValueError("511360 subject status is missing")

            cash_detail_response = client.get("/api/subjects/status/511360.SH")
            if cash_detail_response.status_code != 200:
                raise ValueError(f"511360 detail returned {cash_detail_response.status_code}")
            ratio.assert_safe(cash_detail_response.json())
            assert_safe_payload(cash_detail_response.json())

            missing_response = client.get("/api/subjects/status/NO_SUCH_CODE")
            if missing_response.status_code != 404:
                raise ValueError(f"missing subject returned {missing_response.status_code}, expected 404")
            ratio.assert_safe(missing_response.json())
            assert_safe_payload(missing_response.json())

            page_response = client.get("/subjects")
            if page_response.status_code != 200:
                raise ValueError(f"subjects page returned {page_response.status_code}")
            if LOCAL_PATH_RE.search(page_response.text):
                raise ValueError("subjects page contains local absolute path")
            if FORBIDDEN_TEXT_RE.search(page_response.text):
                raise ValueError("subjects page contains forbidden text")
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
            expected = {
                "Action Plan",
                "Target Allocation",
                "Subject Status",
                "Subject Gap",
                "Themes",
                "Buckets",
                "Portfolio",
                "Intraday Rules",
                "Decision Log",
                "History Snapshot",
            }
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
            summary_response = client.get("/api/dashboard/summary?time_window=7d")
            if summary_response.status_code != 200:
                raise ValueError(f"dashboard summary API returned {summary_response.status_code}")
            summary_payload = summary_response.json()
            ratio.assert_safe(summary_payload)
            assert_safe_payload(summary_payload)
            summary_data = summary_payload.get("data") or {}
            if summary_data.get("module") != "workbench_analytics_dashboard":
                raise ValueError("dashboard summary payload module mismatch")
            if summary_data.get("window", {}).get("selected") != "7d":
                raise ValueError("dashboard summary time window was not honored")
            if (summary_data.get("metrics") or {}).get("current_module_count", 0) <= 0:
                raise ValueError("dashboard summary current module count is empty")
            user_response = client.get("/api/dashboard/user_metrics/default?time_window=30d")
            if user_response.status_code != 200:
                raise ValueError(f"dashboard user metrics API returned {user_response.status_code}")
            user_payload = user_response.json()
            ratio.assert_safe(user_payload)
            assert_safe_payload(user_payload)
            user_data = user_payload.get("data") or {}
            if user_data.get("module") != "workbench_user_metrics" or user_data.get("user_id") != "default":
                raise ValueError("dashboard user metrics payload mismatch")
            missing_response = client.get("/api/dashboard/user_metrics/unknown_user")
            if missing_response.status_code != 404:
                raise ValueError("dashboard user metrics unknown id did not return safe 404")
            integration_response = client.get("/api/workbench/integration?time_window=7d")
            if integration_response.status_code != 200:
                raise ValueError(f"workbench integration API returned {integration_response.status_code}")
            integration_payload = integration_response.json()
            ratio.assert_safe(integration_payload)
            assert_safe_payload(integration_payload)
            integration_data = integration_payload.get("data") or {}
            if integration_data.get("module") != "workbench_integration":
                raise ValueError("workbench integration payload module mismatch")
            labels = {item.get("label") for item in integration_data.get("modules") or []}
            if not {"Settings", "Preferences", "Dashboard", "Research Centers"}.issubset(labels):
                raise ValueError("workbench integration missing module links")
            audit_response = client.get("/api/audit/bundle?time_window=7d&module_filter=dashboard")
            if audit_response.status_code != 200:
                raise ValueError(f"audit bundle API returned {audit_response.status_code}")
            audit_payload = audit_response.json()
            ratio.assert_safe(audit_payload)
            assert_safe_payload(audit_payload)
            audit_data = audit_payload.get("data") or {}
            if audit_data.get("module") != "workbench_audit_bundle":
                raise ValueError("audit bundle payload module mismatch")
            if audit_data.get("window", {}).get("selected") != "7d":
                raise ValueError("audit bundle time window was not honored")
            if audit_data.get("module_filter", {}).get("selected") != "dashboard":
                raise ValueError("audit bundle module filter was not honored")
            if not audit_data.get("sections"):
                raise ValueError("audit bundle sections are empty")
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "dashboard_api",
                "/api/dashboard/current",
                f"Dashboard API failed safety/current-state scan: {exc}",
                "Fix DashboardService or its route and rerun scripts/web_check.py.",
            )
            self.add_result("dashboard_api", "FAIL", str(exc))
        else:
            self.add_result("dashboard_api", "PASS", "summary, analytics, integration, audit bundle, quick links, and cash-equivalent gate safe")

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

    def check_history_gap_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/history/gap-summary")
            if response.status_code != 200:
                raise ValueError(f"history gap API returned {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            data = payload.get("data") or {}
            if data.get("module") != "history_gap_dashboard" or data.get("current_only") is not True:
                raise ValueError("history gap payload is not marked current-only")
            for key in ["summary", "buckets", "history_entries", "safety"]:
                if key not in data:
                    raise ValueError(f"history gap payload missing {key}")
            buckets = data.get("buckets") or []
            summary = data.get("summary") or {}
            if summary.get("bucket_count") != len(buckets):
                raise ValueError("history gap summary count does not match buckets list")
            target_response = client.get("/api/target-allocation/current")
            target = (((target_response.json() or {}).get("data") or {}).get("target_allocation") or {})
            current_buckets = {row.get("bucket"): row for row in target.get("buckets", [])}
            for row in buckets:
                if row.get("gap_status") not in {"green", "yellow", "red", "unknown"}:
                    raise ValueError(f"unexpected history gap status for {row.get('bucket')}: {row.get('gap_status')}")
                if row.get("alert_status") not in {"ok", "review", "attention", "unknown"}:
                    raise ValueError(f"unexpected alert status for {row.get('bucket')}: {row.get('alert_status')}")
                expected = current_buckets.get(row.get("bucket"))
                if expected:
                    for field in ["actual_pct", "target_pct", "gap_pct"]:
                        if row.get(field) != expected.get(field):
                            raise ValueError(f"{row.get('bucket')} {field} mismatch with current target allocation")
            if buckets:
                from urllib.parse import quote

                detail = client.get("/api/history/gap-summary/" + quote(str(buckets[0].get("bucket")), safe=""))
                if detail.status_code != 200:
                    raise ValueError(f"history gap detail returned {detail.status_code}")
                ratio.assert_safe(detail.json())
                assert_safe_payload(detail.json())
            missing = client.get("/api/history/gap-summary/NO_SUCH_BUCKET")
            if missing.status_code != 404:
                raise ValueError(f"missing history gap bucket returned {missing.status_code}, expected 404")
            ratio.assert_safe(missing.json())
            assert_safe_payload(missing.json())
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "history_gap_api",
                "/api/history/gap-summary",
                f"History gap dashboard API failed safety/current-state scan: {exc}",
                "Fix HistoryGapDashboardService or its routes and rerun scripts/web_check.py.",
            )
            self.add_result("history_gap_api", "FAIL", str(exc))
        else:
            self.add_result("history_gap_api", "PASS", "history gap summary, details, and neutral alerts safe")

    def check_bucket_status_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/buckets/status")
            if response.status_code != 200:
                raise ValueError(f"bucket status API returned {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            data = payload.get("data") or {}
            if data.get("module") != "bucket_explorer" or data.get("current_only") is not True:
                raise ValueError("bucket payload is not marked current-only")
            for key in ["summary", "buckets", "safety", "source_modules"]:
                if key not in data:
                    raise ValueError(f"bucket payload missing {key}")
            buckets = data.get("buckets") or []
            summary = data.get("summary") or {}
            if summary.get("bucket_count") != len(buckets):
                raise ValueError("bucket summary count does not match bucket list")
            for bucket in buckets:
                if bucket.get("gap_status") in {"buy", "add", "reduce", "sell"}:
                    raise ValueError(f"bucket gap status leaked action conclusion: {bucket.get('bucket')}")
                for subject in bucket.get("subjects") or []:
                    if subject.get("gate_conclusion") in {"buy", "add", "reduce", "sell"}:
                        raise ValueError(f"subject gate leaked action conclusion: {subject.get('code')}")
            if buckets:
                from urllib.parse import quote

                detail = client.get("/api/buckets/status/" + quote(str(buckets[0].get("bucket")), safe=""))
                if detail.status_code != 200:
                    raise ValueError(f"bucket detail returned {detail.status_code}")
                ratio.assert_safe(detail.json())
                assert_safe_payload(detail.json())
            missing = client.get("/api/buckets/status/NO_SUCH_BUCKET")
            if missing.status_code != 404:
                raise ValueError(f"missing bucket returned {missing.status_code}, expected 404")
            ratio.assert_safe(missing.json())
            assert_safe_payload(missing.json())
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "bucket_status_api",
                "/api/buckets/status",
                f"Bucket Explorer API failed safety/current-state scan: {exc}",
                "Fix BucketExplorerService or its route and rerun scripts/web_check.py.",
            )
            self.add_result("bucket_status_api", "FAIL", str(exc))
        else:
            self.add_result("bucket_status_api", "PASS", "bucket summary, details, and neutral statuses safe")

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
            for key in [
                "uses_latest_index_files",
                "generates_action_plan",
                "generates_target_allocation",
                "trading_feature",
                "qmt_write_feature",
            ]:
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

    def check_decision_timeline_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/decision-timeline")
            if response.status_code != 200:
                raise ValueError(f"decision timeline API returned {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            data = payload.get("data") or {}
            if data.get("module") != "decision_timeline" or data.get("current_only") is not True:
                raise ValueError("decision timeline payload is not marked current-only")
            for key in ["summary", "events", "source_modules", "safety"]:
                if key not in data:
                    raise ValueError(f"decision timeline payload missing {key}")
            events = data.get("events") or []
            if not events:
                raise ValueError("decision timeline events are empty")
            summary = data.get("summary") or {}
            if summary.get("event_count") != len(events):
                raise ValueError("decision timeline summary count does not match events")
            event_types = {event.get("event_type") for event in events}
            for required in ["action_plan", "target_allocation", "decision_log"]:
                if required not in event_types:
                    raise ValueError(f"decision timeline missing {required} event")
            safety = data.get("safety") or {}
            for key in ["ratio_only", "current_only", "read_only", "uses_latest_index_modules"]:
                if safety.get(key) is not True:
                    raise ValueError(f"decision timeline safety check failed: {key}")
            for key in ["uses_latest_index_files", "generates_action_plan", "generates_target_allocation", "trading_feature", "qmt_write_feature"]:
                if safety.get(key) is not False:
                    raise ValueError(f"decision timeline boundary check failed: {key}")

            action_plan = client.get("/api/action-plan/current").json().get("data", {}).get("action_plan") or {}
            target = client.get("/api/target-allocation/current").json().get("data", {}).get("target_allocation") or {}
            by_id = {event.get("event_id"): event for event in events}
            if by_id.get("current-action-plan", {}).get("timestamp") != action_plan.get("generated_at"):
                raise ValueError("decision timeline action-plan timestamp mismatch")
            if by_id.get("current-target-allocation", {}).get("timestamp") != target.get("generated_at"):
                raise ValueError("decision timeline target-allocation timestamp mismatch")

            detail = client.get("/api/decision-timeline/current-action-plan")
            if detail.status_code != 200:
                raise ValueError(f"decision timeline detail returned {detail.status_code}")
            ratio.assert_safe(detail.json())
            assert_safe_payload(detail.json())
            missing = client.get("/api/decision-timeline/NO_SUCH_EVENT")
            if missing.status_code != 404:
                raise ValueError(f"missing decision timeline event returned {missing.status_code}, expected 404")
            ratio.assert_safe(missing.json())
            assert_safe_payload(missing.json())
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "decision_timeline_api",
                "/api/decision-timeline",
                f"Decision timeline API failed safety/current-state scan: {exc}",
                "Fix DecisionTimelineService or its routes and rerun scripts/web_check.py.",
            )
            self.add_result("decision_timeline_api", "FAIL", str(exc))
        else:
            self.add_result("decision_timeline_api", "PASS", "timeline events safe and current-state aligned")

    def check_historical_metrics_api(self, client: Any, ratio: Any) -> None:
        try:
            response = client.get("/api/historical-metrics")
            if response.status_code != 200:
                raise ValueError(f"historical metrics API returned {response.status_code}")
            payload = response.json()
            ratio.assert_safe(payload)
            assert_safe_payload(payload)
            data = payload.get("data") or {}
            if data.get("module") != "historical_metrics" or data.get("current_only") is not True:
                raise ValueError("historical metrics payload is not marked current-only")
            for key in ["summary", "series", "aggregations", "entities", "source_modules", "safety"]:
                if key not in data:
                    raise ValueError(f"historical metrics payload missing {key}")
            entities = data.get("entities") or []
            if not entities:
                raise ValueError("historical metrics entities are empty")
            summary = data.get("summary") or {}
            if summary.get("entity_count") != len(entities):
                raise ValueError("historical metrics summary count does not match entities")
            aggregations = data.get("aggregations") or {}
            for required in ["buckets", "subjects", "themes", "decision_types"]:
                if not aggregations.get(required):
                    raise ValueError(f"historical metrics missing {required} aggregation")
            safety = data.get("safety") or {}
            for key in ["ratio_only", "current_only", "read_only", "uses_latest_index_modules"]:
                if safety.get(key) is not True:
                    raise ValueError(f"historical metrics safety check failed: {key}")
            for key in ["uses_latest_index_files", "generates_action_plan", "generates_target_allocation", "trading_feature", "qmt_write_feature"]:
                if safety.get(key) is not False:
                    raise ValueError(f"historical metrics boundary check failed: {key}")

            history = client.get("/api/history/gap-summary").json().get("data", {})
            history_buckets = {row.get("bucket"): row for row in history.get("buckets") or []}
            metric_buckets = {row.get("bucket"): row for row in aggregations.get("buckets") or []}
            for bucket, expected in history_buckets.items():
                actual = metric_buckets.get(bucket)
                if not actual:
                    raise ValueError(f"historical metrics missing bucket {bucket}")
                for field in ["actual_pct", "target_pct", "gap_pct"]:
                    if actual.get(field) != expected.get(field):
                        raise ValueError(f"historical metrics {bucket} {field} mismatch")

            detail = client.get("/api/historical-metrics/bucket-attack_mainline")
            if detail.status_code != 200:
                raise ValueError(f"historical metrics detail returned {detail.status_code}")
            ratio.assert_safe(detail.json())
            assert_safe_payload(detail.json())
            missing = client.get("/api/historical-metrics/NO_SUCH_ENTITY")
            if missing.status_code != 404:
                raise ValueError(f"missing historical metrics entity returned {missing.status_code}, expected 404")
            ratio.assert_safe(missing.json())
            assert_safe_payload(missing.json())
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "historical_metrics_api",
                "/api/historical-metrics",
                f"Historical metrics API failed safety/current-state scan: {exc}",
                "Fix HistoricalMetricsService or its routes and rerun scripts/web_check.py.",
            )
            self.add_result("historical_metrics_api", "FAIL", str(exc))
        else:
            self.add_result("historical_metrics_api", "PASS", "historical metrics entities safe and aligned")

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

    def check_frontend_smoke(self) -> None:
        try:
            TestClient = import_test_client()

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

        for path in ["/static/app.js", "/static/readiness.js"]:
            response = client.get(path)
            if response.status_code != 200:
                self.fail("frontend_static", path, f"Expected 200, got {response.status_code}.", "Fix StaticFiles mount.")

        status = "FAIL" if self.has_fail("page_status") or self.has_fail("page_safety") or self.has_fail("frontend_static") else "PASS"
        self.add_result("frontend_smoke", status, f"{len(PAGE_PATHS)} pages and static JS")

    def check_frontend_interactions(self) -> None:
        try:
            TestClient = import_test_client()

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
        readiness_js = client.get("/static/readiness.js")
        if readiness_js.status_code != 200:
            self.fail(
                "readiness_frontend_js",
                "web/backend/app/static/readiness.js",
                "Readiness static JS not served.",
                "Restore the Phase 16C readiness page script.",
            )
        else:
            script = readiness_js.text
            missing = [
                marker
                for marker in [
                    "function refreshReadiness",
                    "function renderReadiness",
                    "function assertSafe",
                    "/api/readiness/summary",
                    "/api/readiness/checks",
                ]
                if marker not in script
            ]
            if missing:
                self.fail(
                    "readiness_frontend_js",
                    "web/backend/app/static/readiness.js",
                    "Missing readiness JS markers: " + ", ".join(missing),
                    "Restore readiness page refresh, render, and sanitizer logic.",
                )
        if not any(
            item.check
            in {
                "frontend_interactions",
                "dashboard_visuals",
                "frontend_js",
                "readiness_frontend_js",
                "page_status",
                "page_safety",
            }
            for item in self.failures
        ):
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
                "Protected research generation logic changed in this release check.",
                "Move those changes out of this Web verification scope.",
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
        print(f"\n=== MyInvest Web Check ({self.mode}) ===")
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

        if self.mode == "release":
            print("\nCommit suggestion:")
            print(f"  {COMMIT_MESSAGE}")
            print("\nCommit file list:")
            files = commit_file_list()
            if files:
                for path in files:
                    print(f"  {path}")
            else:
                print("  No pending files. Current branch may already contain the release commit.")
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


def import_test_client() -> Any:
    import warnings

    from starlette.exceptions import StarletteDeprecationWarning

    warnings.filterwarnings(
        "ignore",
        message=r"Using `httpx` with `starlette\.testclient` is deprecated; install `httpx2` instead\.",
        category=StarletteDeprecationWarning,
    )
    from starlette.testclient import TestClient

    return TestClient


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


def assert_environment_status_payload(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if LOCAL_PATH_RE.search(serialized):
        raise ValueError("environment status contains a local absolute path")
    if re.search(r"(\.env|token|secret|password|api key)", serialized, re.IGNORECASE):
        raise ValueError("environment status contains a secret-like term")
    assert_safe_payload(value)


def assert_safe_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            key_path = f"{path}.{key_text}"
            if key_path not in ALLOWED_FORBIDDEN_KEY_PATHS and FORBIDDEN_KEY_RE.search(key_text):
                raise ValueError(f"forbidden key {path}.{key_text}")
            assert_safe_keys(item, key_path)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MyInvest Web checks.")
    parser.add_argument(
        "--mode",
        choices=sorted(CHECK_MODES),
        default="smoke",
        help="smoke is the default daily Web check; release adds export/repo gates.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return WebCheck(mode=args.mode).run()


if __name__ == "__main__":
    raise SystemExit(main())
