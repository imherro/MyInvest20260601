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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMMIT_MESSAGE = "feat(web): add market position mapping service baseline"

API_PATHS = [
    "/api/health",
    "/api/current",
    "/api/latest-index",
    "/api/modules/current",
    "/api/market-position/mapping",
    "/api/market-position/current",
    "/api/market-position/score/25",
    "/api/market-position/score/30",
    "/api/market-position/score/31",
    "/api/market-position/score/100",
    "/api/action-plan/current",
    "/api/target-allocation/current",
    "/api/portfolio/current",
    "/api/intraday-rules/current",
    "/api/research-first/current",
    "/api/system-check/current",
    "/api/decision-log/current",
    "/api/export/review_package?format=json",
]

PAGE_PATHS = [
    "/",
    "/action-plan",
    "/target-allocation",
    "/research-first",
    "/portfolio",
    "/intraday-rules",
    "/decision-log",
    "/system-checks",
]

INTERACTIVE_PAGE_CHECKS = {
    "/action-plan": ["data-table-search", "data-sort", "actionRows"],
    "/target-allocation": ["data-table-search", "data-sort", "targetRows"],
    "/portfolio": ["data-table-search", "data-sort", "portfolioRows"],
    "/intraday-rules": ["data-table-search", "data-sort", "intradayRows", "disabledTriggerRows"],
    "/decision-log": ["data-table-search", "data-sort", "decisionRows"],
}

DASHBOARD_CHECKS = [
    "bucketGapChart",
    'data-status-card="research-first"',
    'data-status-card="intraday"',
    'data-status-card="project-check"',
]

JS_CHECKS = [
    "function assertRatioOnly",
    "function renderPagination",
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
        self.check_no_research_logic_changes()
        self.check_phase5a_contract_files()
        self.check_phase5c_contract_files()
        self.run_ingest()
        self.run_pytest()
        action_path = self.latest_action_plan_path()
        self.run_ratio_and_gate_checks(action_path)
        self.run_project_checks()
        self.check_api_and_export()
        self.check_frontend_interactions()
        self.check_current_only_code_paths()
        self.print_summary()
        return 1 if self.failures else 0

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
        self.run_command("pytest_web_backend", [sys.executable, "-m", "pytest", "web/backend/tests"])

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
        self.check_export_json(client, ratio)
        self.check_export_zip(client, ratio)

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

    def check_current_only_code_paths(self) -> None:
        files = [
            ROOT / "scripts" / "ingest_current_state.py",
            ROOT / "scripts" / "ingest_current_state_to_web_db.py",
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
