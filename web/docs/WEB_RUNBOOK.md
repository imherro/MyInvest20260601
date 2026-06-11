# MyInvest Web Runbook

## Scope

This Web MVP is read-only. It reads current research state from `research/latest_index.json` through `latest_index.modules`, ingests a ratio-only subset into SQLite, and serves local browser views through FastAPI.

## Initialize Database

```bash
python scripts/ingest_current_state.py
```

The database is written to `temp/web_db/myinvest.sqlite`. This path is ignored by Git. The ingest reads only `research/latest_index.json` `modules` pointers; it does not treat `latest_index.files` as current.

The lower-level implementation remains available at:

```bash
python scripts/ingest_current_state_to_web_db.py
```

## Start Backend

```bash
python scripts/run_web.py
```

The default binds to `0.0.0.0` on port `8000` for trusted-LAN review. Open `http://127.0.0.1:8000/` locally, or open `http://<your-lan-ip>:8000/` from another trusted device on the same LAN.

Local-only override:

```bash
python scripts/run_web.py --host 127.0.0.1 --port 8000
```

Reload for local Web development:

```bash
python scripts/run_web.py --reload
```

The equivalent direct FastAPI command remains available:

```bash
python -m uvicorn web.backend.app.main:app --host 0.0.0.0 --port 8000
```

Use trusted-LAN mode only on networks you control. Do not expose the Web UI to the public internet, untrusted networks, or public company networks. The Web app is read-only and ratio-only, but research context can still be sensitive. Never expose `.env`, tokens, runtime files, SQLite databases, or account information through LAN access.

The Web UI is FastAPI + Jinja2 with a small static refresh script. There is no React build step in this phase.

## Local Tools Page

The Web app also provides a local operator page:

```text
http://127.0.0.1:8000/tools
```

The page lists the existing MyInvest scripts and workflow prompts. Script buttons call only a fixed server-side whitelist under `/ops`; the browser never sends arbitrary command text. The page reports each run as `PASS`, `FAIL`, or `PROMPT`, with sanitized stdout/stderr for local review.

Tools are grouped and sorted for day-to-day use:

- `日常使用`: ordered roughly by workflow sequence, from QMT ratio snapshot, Web DB refresh, valuation check, premarket check, intraday check, post-market review, to weekly review.
- `组合与研究维护`: action plan, target allocation, latest index, staleness, ResearchFirst backlog, valuation reports, theme leaders, and snapshot repair.
- `QMT 只读`: QMT connectivity checks that do not create orders.
- `导出与审计`: review packages and controlled current-only exports under ignored `temp/`.
- `开发验收`: project checks, ratio-only, ResearchFirst, allocation consistency, hidden Unicode, Web smoke and Web release checks.
- `Codex 研究提示`: copyable prompts for workflows that still need a research conversation.

Each tool row includes `When to use`, which explains the intended timing and workflow boundary before you press `Run` or copy a prompt.

Tool coverage includes:

- Web database refresh, daily Web smoke checks, and release checks.
- ratio-only, ResearchFirst, allocation consistency, staleness, valuation, and hidden-Unicode checks.
- premarket check, action-plan generation, target-allocation generation, post-market review, and weekly review scripts.
- QMT read-only probes, QMT ratio snapshot refresh, and one-shot intraday rule checks.
- current ResearchFirst backlog, P2 position review, theme leader, valuation report, and portfolio snapshot quality helpers.
- current-only review/export packages under ignored `temp/`.
- Codex prompt cards for workflows that still require a research conversation, such as strategy briefing, theme research, ETF research, and stock research.

Safety boundaries:

- `/api/*` remains read-only and has no POST/PUT/PATCH/DELETE methods.
- Mutating local tool runs are exposed only under `/ops/*`.
- Tool execution is whitelist-only by tool id; no shell command input is accepted from the browser.
- QMT tools are read-only and still require the local QMT terminal to be open and logged in.
- No automatic trading, order, execution, or QMT write interface is added.
- Command output is sanitized before it is returned to the browser. Local absolute paths and sensitive ratio-only terms are redacted.
- Use trusted-LAN mode only on networks you control. Anyone who can access the local Web UI can press local tool buttons.

## Run Tests

```bash
pytest web/backend/tests
```

## Phase 13B CI And Test Warning Hygiene

The Web test suite is expected to pass with warnings promoted to errors:

```bash
python -m pytest web/backend/tests -q -W error
```

The test configuration isolates only the known external Starlette/httpx `TestClient`
compatibility warning. Other warnings still fail under `-W error`. Tests and
runtime-history helpers must explicitly close SQLite connections and file handles.

GitHub Actions runs the same strict warning check before the daily Web smoke check.
The workflow uses current Node-runtime-backed major versions for
`actions/checkout` and `actions/setup-python`.

## Current Release Handoff Snapshot

Current stable release snapshot:

- Stable commit: `107be68b638159e289e638e1c0c3bb0c3a45a8a3`
- Stable tag: `web-workbench-phase10-12-v0.4.5`
- PR #24 through PR #37 are merged.
- `web-workbench-phase10-12-v0.4.0`: Phase 10-12 Workbench release.
- `web-workbench-phase10-12-v0.4.1`: Phase 13A review package privacy scan hygiene.
- `web-workbench-phase10-12-v0.4.2`: Phase 13B CI/test warning hygiene.
- `web-workbench-phase10-12-v0.4.3`: Phase 14C schema guard full read-only enforcement.
- `web-workbench-phase10-12-v0.4.4`: Phase 15B Historical Metrics guard skeleton.
- `web-workbench-phase10-12-v0.4.5`: Phase 15C Historical Metrics guard full read-only enforcement.

Phase 16 work must start from `main` at or after
`web-workbench-phase10-12-v0.4.5`. Before Phase 16, read `AGENTS.md`,
`web/docs/PHASE_HANDOFF.md`, `web/docs/WEB_RUNBOOK.md`,
`web/docs/SERVICE_LAYER_PLAN.md`, and `web/docs/API_SPEC.md`.
Default Web boundaries remain read-only, ratio-only, current-only, and
OpenAPI GET-only.

## Phase 14A DB Schema Versioning Design

Phase 14A adds only a design document:

- `web/docs/DB_SCHEMA_VERSIONING_PLAN.md`

The plan defines a future Web SQLite read-model schema versioning approach for
`temp/web_db/myinvest.sqlite`. It does not implement migration behavior, write
SQLite, change ingest, introduce Alembic, add an API, or modify Web UI
behavior.

The future guard should fail closed on missing or mismatched schema metadata,
return only safe status text, avoid destructive migration, and keep the Web
layer read-only, ratio-only, current-only, and OpenAPI GET-only.

## Phase 14B Read-Only Schema Guard

Phase 14B adds a read-only schema guard skeleton for the local Web SQLite read
model:

- `GET /api/diagnostics/schema`
- `SchemaGuardService`
- `SchemaGuardRepository`
- `DatabaseService.table_info(...)`

The guard checks the current read-model table and column contract and reads
`schema_version` or `schema_metadata` only when those tables already exist. It
does not create, alter, drop, migrate, seed, or write SQLite objects. It does
not change ingest, research outputs, current module pointers, action-plan
generation, target-allocation generation, trading/QMT behavior, or review
package boundaries.

Expected schema version remains:

```text
web_read_model_v1
```

Current databases that do not yet have a version table return `degraded` with
`missing_version_table`. This is safe operational metadata and does not break
Web smoke checks.

Validation:

```bash
python -m pytest web/backend/tests/test_schema_guard.py -q
python scripts/web_check.py
```

## Phase 14C Schema Guard Enforcement

Phase 14C keeps `GET /api/diagnostics/schema` and strengthens its report:

- deterministic required-schema fingerprint
- observed fingerprint from existing `schema_version` or `schema_metadata`
- required table/column counts
- `schema_fingerprint_match`
- `enforcement.fail_closed`
- `enforcement.web_smoke_compatible`
- `enforcement.read_model_usable`

The current database still has no version table, so the expected local status is
`degraded` with `missing_version_table`, `read_model_usable=true`, and
`web_smoke_compatible=true`. If required tables or columns are missing, or if an
existing version/fingerprint does not match, the guard reports `mismatch` and
`fail_closed=true` without writing SQLite or changing Web routes.

Validation:

```bash
python -m pytest web/backend/tests/test_schema_guard.py -q
python -m pytest web/backend/tests -q -W error
python scripts/web_check.py
```

## Phase 15A Historical Metrics Audit Design

Phase 15A is documentation only. It adds:

- `web/docs/HISTORICAL_METRICS_PLAN.md`

The plan describes how a future Phase 15B should audit Historical Metrics and
its Audit Bundle integration without changing current Web behavior. It covers
current architecture, data sources, audit integration points, safe diagnostics,
fail-closed behavior, and acceptance commands.

No Python code, SQLite schema, ingest flow, API endpoint, template, static JS,
research artifact, release package, or tag changes are part of Phase 15A.

## Phase 15B Historical Metrics Guard Skeleton

Phase 15B adds a read-only Historical Metrics guard skeleton:

- `GET /api/diagnostics/historical-metrics`
- `HistoricalMetricsGuardService`
- `HistoricalMetricsGuardRepository`

The guard checks required read-model table counts and required current-module
sources for Historical Metrics. It reports optional history snapshot absence as
`degraded`, missing required inputs as `mismatch`, and read exceptions as
`unavailable`. The endpoint returns sanitized operational metadata only and does
not change existing Historical Metrics, Audit Bundle, ingest, SQLite schema, or
research generation behavior.

Validation:

```bash
python -m pytest web/backend/tests/test_historical_metrics_guard.py -q
python -m pytest web/backend/tests -q -W error
python scripts/web_check.py
```

## Phase 15C Historical Metrics Guard Enforcement

Phase 15C keeps the same read-only diagnostics endpoint and strengthens the
report:

- deterministic `historical_metrics_guard_v1` contract
- expected and observed SHA-256 fingerprints
- required, observed, and missing read-model inputs
- required, observed, and missing current-module sources
- required, observed, and missing integration payload readiness
- enforcement fields for `fail_closed`, `read_model_usable`,
  `web_smoke_compatible`, and `audit_bundle_compatible`

Expected interpretation:

- `ok`: required inputs, source modules, integration payloads, and contract
  fingerprint match; optional history snapshot is available.
- `degraded`: required inputs and contract fingerprint match, but optional
  history snapshot state is unavailable.
- `mismatch`: a required table, current-module source, integration payload, or
  contract fingerprint is missing or inconsistent.
- `unavailable`: diagnostics metadata could not be read safely.

The guard is reporting only. It does not create or alter SQLite objects, run
ingest, repair the read model, write research artifacts, or change dashboard,
audit bundle, preference, schema diagnostics, or Historical Metrics behavior.

Validation:

```bash
python -m pytest web/backend/tests/test_historical_metrics_guard.py -q
python -m pytest web/backend/tests -q -W error
python scripts/web_check.py
```

## Phase 16A Workbench Readiness Design

Phase 16A is a design-only phase for a future Workbench Readiness surface. It
does not add a page, API, service, repository, template, static JavaScript,
SQLite table, ingest behavior, runtime writer, or research artifact.

Design goal:

- summarize existing safe diagnostics into a future read-only readiness view
- keep validation command execution outside Web
- report only safe status, counts, timestamps, repo-relative source metadata,
  and links to existing local Web surfaces
- preserve read-only, ratio-only, current-only, ResearchFirst-neutral, and
  OpenAPI GET-only boundaries

Candidate future surfaces, pending a later implementation phase:

- `GET /api/readiness/summary`
- `GET /api/readiness/checks`
- `GET /readiness`

Phase 16A validation draft:

```bash
python scripts/check_hidden_unicode.py
python -m pytest web/backend/tests -q -W error
python scripts/web_release_check.py
python scripts/project_check.py --current-only
```

Validation:

```bash
python scripts/check_hidden_unicode.py
python -m pytest web/backend/tests -q -W error
python scripts/web_release_check.py
python scripts/project_check.py --current-only
```

## Phase 16B Workbench Readiness API Skeleton

Phase 16B adds an API-only Workbench Readiness skeleton:

- `GET /api/readiness/summary`
- `GET /api/readiness/checks`

The endpoints aggregate existing safe operational metadata from
environment/settings metadata, schema diagnostics, Historical Metrics
diagnostics, dashboard summary, audit bundle availability, and current
validation summary metadata. They do not add a `/readiness` page, do not run
validation commands from Web, do not write files, do not write SQLite, do not
rebuild ingest, and do not generate research artifacts.

Readiness status values:

- `ok`: all checks are available and compatible.
- `degraded`: one or more non-mutating signals are missing or optional context
  is unavailable, while Web smoke remains compatible.
- `mismatch`: a required safety or read-model signal failed closed.
- `unavailable`: readiness metadata could not be read safely.

Expected local smoke behavior is `ok` or `degraded` with
`web_smoke_compatible=true` and `fail_closed=false`. `mismatch`,
`unavailable`, `fail_closed=true`, or `web_smoke_compatible=false` blocks the
Web gate.

Direct smoke:

```bash
python -m pytest web/backend/tests/test_workbench_readiness.py -q
python scripts/web_check.py
```

## Phase 16C Workbench Readiness Page

Phase 16C adds the read-only page:

- `GET /readiness`

The page renders the Phase 16B readiness summary and checks APIs. It supports
frontend switching between summary and checks and refreshes by calling only:

- `GET /api/readiness/summary`
- `GET /api/readiness/checks`

The page is a display surface only. It does not run validation commands from
Web, write files, write SQLite, rebuild ingest, generate research artifacts,
generate target allocations, generate action plans, or add mutating APIs.

Smoke checks:

```bash
python -m pytest web/backend/tests/test_workbench_readiness_page.py -q
python scripts/web_check.py
```

Failure interpretation is the same as the API skeleton: `ok` and `degraded`
are Web-smoke compatible when `fail_closed=false`; `mismatch`, `unavailable`,
or `fail_closed=true` blocks the gate.

## Web Check Modes

The Web checks are split by purpose. The daily command stays small; release checks remain available when their extra scope is needed.

Daily Web smoke check:

```bash
python scripts/web_check.py
```

This check runs:

- `python scripts/ingest_current_state.py`
- `python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_cross_file_allocation_consistency.py`
- `python scripts/project_check.py --current-only`
- API forbidden-field and local-path scans for non-export endpoints
- page status and local-path scans
- current-only code-path checks
- `run_web.py` startup contract checks

Release check:

```bash
python scripts/web_release_check.py
```

This adds `pytest`, hidden Unicode, protected research logic, Git forbidden-file scope, full API/export scans, controlled export checks, candidate audit, history snapshot export, and frontend interaction marker checks.

Output statuses:

- `PASS`: safe to prepare a commit.
- `WARN`: command passed, but a non-blocking warning needs review.
- `FAIL`: blocks commit; fix the listed file/reason and rerun the check.

The release script prints a suggested commit message and the files that belong in the commit. Do not commit `temp/`, SQLite/DB files, `runtime/`, caches, `node_modules/`, build/dist outputs, `.env`, ZIP, or log artifacts.

GitHub Actions runs Web tests with warnings as errors and then the daily Web smoke check via `.github/workflows/web_check.yml` on push and pull request.

## Source Review Package Builder

The source review package builder is a local release and audit helper:

```bash
python scripts/build_review_package.py --fail-on-privacy
python scripts/check_review_package_integrity.py temp/review_packages/<package>.zip
```

The default package is current-only and writes only under ignored `temp/review_packages/`. It includes project logic, scripts, templates, docs, registries, and safe current pointers. It excludes raw portfolio snapshots, raw stock or ETF profile files, and valuation reports because those evidence files can carry private account context or price fields.

The privacy scan still blocks real local paths such as user-home paths and Windows user paths. Scanner implementation files may contain the regex text that defines those checks without self-failing the package build.

## Phase 9F Repository Read-Only Baseline

Phase 9F establishes the Web repository read-only baseline. All current SQLite repository reads must go through `DatabaseService`; direct `session.execute(...)`, direct `read_text(...)`, and `latest_index.files` current resolution are blocked for repositories. `HistorySnapshotRepository` is the only documented exception because it owns the Phase 9E temp-only runtime DB write to `temp/web_runtime/history_snapshot.sqlite`.

Validation:

```bash
python scripts/web_release_check.py
```

The gate scans `web/backend/app/repositories/*.py`, checks API/page forbidden fields, confirms OpenAPI remains read-only, and verifies ratio-only, ResearchFirst, allocation consistency, and `project_check.py --current-only`. Do not tag or merge a repository baseline if `phase9f_repository_baseline_files` is not `PASS`.

## Hidden Unicode Warning Review

If GitHub displays a hidden or bidirectional Unicode warning on a Web PR, run the local scanner before changing files:

```bash
python scripts/check_hidden_unicode.py
```

To recheck only the files shown by GitHub or a PR diff:

```bash
python scripts/check_hidden_unicode.py --paths scripts/web_check.py web/backend/app/static/app.js web/docs/WEB_RUNBOOK.md
```

Machine-readable output is available for automation:

```bash
python scripts/check_hidden_unicode.py --json
```

The scanner reports `scanned_file_count`, path, line, column, codepoint, Unicode name, and a safe nearby preview when hidden format controls are found. Normal Chinese text in Markdown, templates, tests, or documentation is allowed. Remove only hidden or format-control characters such as bidi controls, direction marks, zero-width characters, or other Unicode `Cf` characters. Do not reformat unrelated business logic while clearing a warning.

## Phase 7D Research Dashboard

Phase 7D adds the read-only Research Dashboard Landing Page. It aggregates existing current-state services into one homepage; it does not generate target allocation, generate action plans, create research artifacts, or connect to execution adapters.

Read-only API:

- `GET /api/dashboard/current`

Pages:

- `GET /`
- `GET /dashboard`

Dashboard sections:

- System Status: project check, ResearchFirst, allocation consistency, sensitive scan, and intraday stale/degraded state.
- Market Position: score, label, equity target range, and cash target range.
- Action Plan Summary: generated timestamp, action count, ResearchFirst count, and manual review count.
- Allocation Summary: equity current/target and cash-short current/target ratios.
- Bucket Gap: current bucket actual/target/gap chart.
- Subject Research Status Summary: subject counts and 511360 cash-equivalent gate.
- Subject Gap Summary: green/yellow/red/unknown/stale counts.
- Quick Links: Action Plan, Target Allocation, Subject Status, Subject Gap, Themes, Buckets, Portfolio, Intraday Rules, Decision Log, and History Snapshot.

Validation:

```bash
python scripts/run_web.py --help
python scripts/web_check.py
```

The dashboard remains current-only and ratio-only. It reads SQLite current state produced from `research/latest_index.json` `modules`, not `latest_index.files`. It does not display or export sensitive business fields, local absolute paths, runtime files, database files, account context, trading records, or execution output.

## Phase 7E Theme Research Center

Phase 7E adds the read-only Theme Research Center. It aggregates current theme registry, theme leader, ETF registry, stock registry, and subject gate data into a Web review page. It does not generate target allocation, generate action plans, write research files, or create trading instructions.

Read-only API:

- `GET /api/themes/status`
- `GET /api/themes/status/{theme_name}`

Page:

- `GET /themes`

The API returns `summary`, `themes`, associated ETF/stock gate summaries, leaders, conflicts, and safety flags. Theme states are neutral research states: `confirmed`, `watch`, `research_first`, `stale`, `conflict`, or `unknown`. Theme states are not buy/add/reduce/sell actions.

The page supports refresh, search, status/rating/stage filters, sorting, pagination, and expandable details through the shared static JS. Every refresh still passes the frontend forbidden-field scan before rendering.

Theme Center remains current-only and read-only. It reads current SQLite state produced from `research/latest_index.json` `modules`, not `latest_index.files`. It does not write `research/latest_index.json`, `research/actions`, `research/allocation`, target-allocation artifacts, action-plan artifacts, trading records, or QMT write calls.

Direct tests:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_theme_status.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 7F Bucket Explorer

Phase 7F adds the read-only Bucket Explorer. It drills from target-allocation buckets into current portfolio subjects, ResearchFirst gate status, and freshness status. It does not generate target allocation, generate action plans, write research files, or create trading instructions.

Read-only API:

- `GET /api/buckets/status`
- `GET /api/buckets/status/{bucket}`

Page:

- `GET /buckets`

The API returns `summary`, bucket rows, per-bucket actual/target/gap percentages, neutral gap status, risk notes, and per-subject gate status. Gap statuses are display states only: `near_target`, `overweight`, `underweight`, `zero_target_nonzero_actual`, or `unknown`.

The page supports refresh, search, bucket/gate filters, sorting, pagination, and expandable details through the shared static JS. Every refresh still passes the frontend forbidden-field scan before rendering.

Bucket Explorer remains current-only and read-only. It reads current SQLite state produced from `research/latest_index.json` `modules`, not `latest_index.files`. It does not write `research/latest_index.json`, `research/actions`, `research/allocation`, target-allocation artifacts, action-plan artifacts, trading records, or QMT write calls.

Direct tests:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_bucket_explorer.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 7G History Gap Dashboard

Phase 7G adds the read-only History Gap Dashboard. It aggregates current target allocation, controlled shadow allocation, candidate audit allocation, and history entry summaries into a Web review page. It does not generate target allocation, generate action plans, write research files, write temporary exports, or create trading instructions.

Read-only API:

- `GET /api/history/gap-summary`
- `GET /api/history/gap-summary/{bucket}`

Page:

- `GET /history/gap-dashboard`

The API returns summary counts, bucket actual/target/gap percentages, neutral gap status, alert status, per-bucket timeline points, history entry summaries, and safety flags. Gap and alert status are display-only review states.

The page supports refresh, search, gap-status filter, sorting, pagination, expandable details, and bucket gap evolution visualization with tooltip text through the shared static JS. Every refresh still passes the frontend forbidden-field scan before rendering.

History Gap Dashboard remains current-only and read-only. It reads current SQLite state produced from `research/latest_index.json` `modules`, not `latest_index.files`. It does not write `research/latest_index.json`, `research/actions`, `research/allocation`, target-allocation artifacts, action-plan artifacts, trading records, or QMT write calls.

Direct tests:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_history_gap_dashboard.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 7H Allocation Drilldown

Phase 7H adds read-only allocation drilldown pages for bucket and subject review. It joins current target allocation, portfolio positions, subject gap/freshness, neutral ResearchFirst gate status, market position, and theme association summaries. It does not generate target allocation, generate action plans, write research files, or create trading instructions.

Read-only APIs:

- `GET /api/buckets/drilldown`
- `GET /api/buckets/drilldown?bucket=<bucket>&detail=full`
- `GET /api/subjects/drilldown`
- `GET /api/subjects/drilldown?subject=<code>&detail=full`

Pages:

- `GET /buckets/drilldown`
- `GET /subjects/drilldown`

The bucket page shows actual/target/gap percentages, gap status, subject counts, a bucket actual-vs-target chart, search, gap-status filter, sorting, pagination, and expandable details.

The subject page shows subject position percentage, bucket actual/target/gap, ResearchFirst status, neutral gate conclusion, theme count, search, bucket/status filters, sorting, pagination, and expandable details.

Allocation drilldown remains current-only and read-only. It reads SQLite current state produced from `research/latest_index.json` `modules`, not `latest_index.files`. It does not write `research/latest_index.json`, `research/actions`, `research/allocation`, target-allocation artifacts, action-plan artifacts, trading records, or QMT write calls.

Direct tests:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_allocation_drilldown.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 7I Decision Timeline

Phase 7I adds the read-only Decision Timeline / Review Timeline. It combines current action plan metadata, current target allocation metadata, recent decision log entries, and read-only history snapshot entries into a neutral review timeline. It does not generate target allocation, generate action plans, write research files, write temporary exports, or create trading instructions.

Read-only APIs:

- `GET /api/decision-timeline`
- `GET /api/decision-timeline/{event_id}`

Page:

- `GET /decision-timeline`

The API returns timeline summary counts and event rows with event id, event type, timestamp, status, summary, ratio-only details, and relative Web review links. Event rows are review context only and are not buy/add/reduce/sell instructions.

The page supports refresh, search, event/status filters, sorting, pagination, expandable details, and a compact timeline visualization with tooltip text through the shared static JS. Every refresh still passes the frontend forbidden-field scan before rendering.

Decision Timeline remains current-only and read-only. It reads SQLite current state produced from `research/latest_index.json` `modules`, not `latest_index.files`. It does not write `research/latest_index.json`, `research/actions`, `research/allocation`, target-allocation artifacts, action-plan artifacts, trading records, or QMT write calls.

Direct tests:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_decision_timeline.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 8 Historical Metrics

Phase 8 adds the read-only Historical Metrics dashboard. It aggregates bucket gap trends, current subject status, theme status, decision timeline event types, and market-score context into ratio-only metrics for review. It does not generate target allocation, generate action plans, write research files, write temporary exports, or create trading instructions.

Read-only APIs:

- `GET /api/historical-metrics`
- `GET /api/historical-metrics/{entity_id}`

Page:

- `GET /historical-metrics`

The API returns summary counts, bucket gap series, market-score series, bucket/subject/theme/decision-type aggregations, flattened entity rows, source modules, and safety flags. Metric rows are review context only and are not buy/add/reduce/sell instructions.

The page supports refresh, search, entity/status filters, sorting, pagination, expandable details, and bucket gap visualization with tooltip text through the shared static JS. Every refresh still passes the frontend forbidden-field scan before rendering.

Historical Metrics remains current-only and read-only. It reads SQLite current state produced from `research/latest_index.json` `modules` and existing read-only history summaries, not `latest_index.files`. It does not write `research/latest_index.json`, `research/actions`, `research/allocation`, target-allocation artifacts, action-plan artifacts, trading records, or QMT write calls.

Direct tests:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_historical_metrics.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 5A Schema And Golden Baseline

Phase 5A freezes the database schema contract and adds a golden current-state baseline for later service migration. It does not migrate target-allocation generation, action-plan generation, trading logic, order creation, execution handling, or QMT write interfaces.

Core documents:

- `web/docs/DATABASE_SCHEMA.md`
- `web/docs/CURRENT_STATE_CONTRACT.md`
- `web/docs/GOLDEN_REFERENCE.md`
- `web/docs/SERVICE_LAYER_PLAN.md`

Run the current release gate:

```bash
python scripts/web_release_check.py
```

Run the golden reference test directly:

```bash
python -m pytest web/backend/tests/test_golden_current_state.py
```

Run schema and current-state contract tests directly:

```bash
python -m pytest web/backend/tests/test_database_schema_contract.py web/backend/tests/test_current_state_contract.py
```

Confirm DB and current JSON alignment by running:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_golden_current_state.py
```

The golden test dynamically resolves `latest_index.modules` and compares current JSON with SQLite fields. It does not read `latest_index.files` and does not hard-code action-plan timestamps.

## Phase 5C-1 Market Position Baseline

Phase 5C-1 adds `MarketPositionService` as a read-only baseline for `market_position_mapping` reads. It maps a market score to equity/cash percentage ranges from SQLite and keeps `scripts/project_utils.py::market_position_for_score` as the reference implementation.

This phase does not generate target allocation, action plans, orders, fills, share counts, or cash-value instructions. `TargetAllocationGenerationService` remains the next step and should start in shadow mode only.

Direct checks:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_market_position_service.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

Read-only API:

- `GET /api/market-position/mapping`
- `GET /api/market-position/current`
- `GET /api/market-position/score/{score}`

The endpoints return only scores, labels, percentage ranges, and `source = "db.market_position_mappings"`. They do not read `latest_index.files`.

## Phase 5C-2 Target Allocation Shadow Mode

Phase 5C-2 adds `TargetAllocationGenerationService` in shadow mode. The service computes an in-memory target allocation from current SQLite state, `MarketPositionService`, portfolio ratios, and bucket policy, then compares core fields with the current target allocation JSON.

It does not:

- write `research/allocation`
- update `research/latest_index.json`
- update `current_modules` or `artifacts`
- replace `generate_target_allocation.py`
- generate action plans
- generate orders, fills, share counts, or cash-value instructions

Direct checks:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_target_allocation_generation_shadow.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

Read-only API:

- `GET /api/target-allocation/shadow`
- `GET /api/target-allocation/shadow/compare`

The compare endpoint returns `matched`, `diffs`, `compared_fields`, `unsupported_fields`, `source_shadow`, and `source_reference`. Core-field diffs block the release gate. Unsupported fields are allowed only when explicit and not used to hide core mismatches.

## Phase 5C-3 Controlled Export

Phase 5C-3 adds controlled export for shadow target allocation. API exports are in memory. CLI exports write only to `temp/web_exports/`, which is ignored by Git.

It does not:

- write `research/allocation`
- update `research/latest_index.json`
- update `current_modules` or `artifacts`
- generate action plans
- replace current target allocation
- create trading or execution runtime files

Direct checks:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_target_allocation_controlled_export.py
```

CLI:

```bash
python scripts/export_target_allocation_shadow.py --dry-run
python scripts/export_target_allocation_shadow.py --format json
python scripts/export_target_allocation_shadow.py --format zip
```

Read-only API:

- `GET /api/target-allocation/shadow/export`
- `GET /api/target-allocation/shadow/export?format=json`
- `GET /api/target-allocation/shadow/export?format=zip`

The ZIP contains only `manifest.json`, `shadow_target_allocation.json`, `compare_result.json`, `provenance.json`, and `system_checks.json`. If shadow compare has core diffs, controlled export fails instead of producing an audit artifact.

## Phase 5D Shadow Replay Fixtures

Phase 5D adds multi-scenario replay fixtures for `TargetAllocationGenerationService`. The fixtures live under:

```text
web/backend/tests/fixtures/target_allocation_scenarios/
```

They are not current state. Production Web APIs still read SQLite current state generated from `research/latest_index.json` `modules`.

The replay covers:

- risk-off current-like state
- score boundary 30
- score boundary 31
- neutral mid-score state
- risk-on high score
- max score 100
- legacy-watch overweight
- attack-mainline overweight
- cash-short underweight
- missing bucket actual

Direct checks:

```bash
python -m pytest web/backend/tests/test_target_allocation_shadow_replay.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

Replay fixtures must remain ratio-only and must not include local absolute paths, runtime paths, `.env`, SQLite files, ZIP/log artifacts, monetary amounts, share counts, account identifiers, order records, fill records, or QMT write behavior.

Phase 5D still does not:

- replace `scripts/generate_target_allocation.py`
- replace `scripts/generate_action_plan.py`
- write `research/allocation`
- write `research/actions`
- update `research/latest_index.json`
- update `current_modules` or `artifacts`
- generate action plans
- create trading or execution runtime files

## Phase 5E Promotion Plan

Phase 5E adds the controlled promotion plan for `TargetAllocationGenerationService`. It is not a replacement phase.

Direct checks:

```bash
python -m pytest web/backend/tests/test_target_allocation_promotion_mode.py
```

Full gate:

```bash
python scripts/web_release_check.py
```

Mode helper:

```text
MYINVEST_TARGET_ALLOCATION_MODE
```

Phase 5E allows only:

- `reference`
- `shadow`
- `controlled_export`

Phase 5E blocks:

- `candidate`
- `official`
- unknown values

The default mode is `shadow`. The helper only reports allowed or blocked status. It does not change current API behavior, write `research/`, update `latest_index`, update `current_modules`, generate action plans, generate target-allocation artifacts, or connect to trading interfaces.

Promotion design is documented in `web/docs/TARGET_ALLOCATION_PROMOTION_PLAN.md`. Any future candidate or official promotion must be reviewed as a separate phase.

## Phase 5F Promotion Simulation

Phase 5F adds candidate and official promotion simulation checks. It still does not replace old research generators or current artifacts.

Direct tests:

```bash
python -m pytest web/backend/tests/test_target_allocation_promotion_simulation.py
```

Candidate dry run:

```bash
python scripts/simulate_target_allocation_promotion.py --mode candidate
```

Candidate temporary export:

```bash
python scripts/simulate_target_allocation_promotion.py --mode candidate --write
```

The candidate export path must start with `temp/candidate_exports/`, and the filename must include `candidate`. Candidate files are temporary review artifacts only. They must not be copied into `research/allocation`, must not update `latest_index`, and must not update `current_modules`.

Official blocked check:

```bash
python scripts/simulate_target_allocation_promotion.py --mode official
```

Expected official result:

- `status` is `blocked`
- `output_path` is `null`
- no files are written

Full gate:

```bash
python scripts/web_release_check.py
```

`web_release_check.py` runs candidate dry-run, candidate temp export, payload safety scan, cleanup, and official blocked validation. It also keeps ratio-only, ResearchFirst, allocation consistency, project_check, API/export sensitive scans, and current-only code-path checks in the same gate.

## Phase 5G Candidate Audit Bundle

Phase 5G adds a candidate audit bundle. It is a review artifact only; it is not official target allocation and must not become current.

Direct tests:

```bash
python -m pytest web/backend/tests/test_target_allocation_candidate_audit.py
```

Dry run:

```bash
python scripts/export_target_allocation_candidate_audit.py --dry-run
```

JSON export:

```bash
python scripts/export_target_allocation_candidate_audit.py --format json
```

ZIP export:

```bash
python scripts/export_target_allocation_candidate_audit.py --format zip
```

Candidate audit exports write only to `temp/candidate_exports/`, and filenames must include `candidate_audit`. The export is blocked if compare is not matched, unsupported fields are present, replay failures are nonzero, official mode is allowed, forbidden fields are present, or a local absolute path is present.

Read-only API:

- `GET /api/target-allocation/candidate-audit`
- `GET /api/target-allocation/candidate-audit?format=json`
- `GET /api/target-allocation/candidate-audit?format=zip`

The API generates the bundle in memory and does not write files. Both API and CLI must leave `research/latest_index.json`, `current_modules`, `research/allocation`, and `research/actions` unchanged.

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 6 History Snapshot

Phase 6 adds a read-only history snapshot for shadow replay, controlled export, candidate simulation, and candidate audit review artifacts. It consolidates previous temporary export results and a live current summary for audit. It is not an official target allocation or action plan generator.

Direct tests:

```bash
python -m pytest web/backend/tests/test_history_snapshot.py
```

Dry run:

```bash
python scripts/export_history_snapshot.py --dry-run
```

JSON export:

```bash
python scripts/export_history_snapshot.py --format json
```

ZIP export:

```bash
python scripts/export_history_snapshot.py --format zip
```

History snapshot CLI exports write only to ignored temporary export folders and write the local history database only under ignored runtime storage. Phase 9E keeps this as an explicit temp-only exception: the only allowed runtime database path is `temp/web_runtime/history_snapshot.sqlite`. It is not the current Web SQLite database, not current research state, not a source for `latest_index.modules`, and must never be committed. Exported JSON and ZIP payloads must not contain runtime paths.

Read-only API:

- `GET /api/history/export`
- `GET /api/history/export?format=json`
- `GET /api/history/export?format=zip`

The ZIP contains only `manifest.json`, `history_snapshot.json`, `history_entries.json`, `live_current_summary.json`, and `safety_checks.json`.

The history snapshot is blocked if shadow compare is not matched, candidate audit compare is not matched, replay failures are nonzero, official mode is allowed, forbidden fields are present, a runtime path appears in exported payloads, or a local absolute path is present.

Phase 6 still does not write `research/latest_index.json`, `research/allocation`, `research/actions`, `current_modules`, generate official target allocation, generate action plans, or connect to trading/QMT write interfaces.

Full gate:

```bash
python scripts/web_release_check.py
```

## Phase 7B Subject Gap And Freshness

Phase 7B adds a read-only Data Freshness & Gap Center. It displays subject-level freshness metadata and bucket-level allocation gap rows from the current SQLite read model. It is not a target-allocation generator and does not create action plans.

## Phase 7A Subject Status Center

Phase 7A adds the read-only Subject Research Status page and API. It is a Web display and audit helper only; it does not generate target allocation, action plans, orders, fills, execution instructions, or QMT write calls.

Direct tests:

```bash
python scripts/ingest_current_state.py
python -m pytest web/backend/tests/test_subject_gap.py
python -m pytest web/backend/tests/test_subject_status.py
```

Read-only API:

- `GET /api/subjects/freshness`
- `GET /api/subjects/gap`
- `GET /api/subjects/status`
- `GET /api/subjects/status/{code}`

Page:

- `GET /subjects/gap`
- `GET /subjects`

The gap endpoint returns subject code/name/type, bucket, subject position percentage, bucket actual/target/gap percentages, freshness status, and relative source metadata. Bucket actual/target/gap values must match the current target-allocation bucket rows.

The page supports refresh, automatic refresh, table search, sorting, pagination, and expandable details through the shared static JS. Every refresh still passes the frontend forbidden-field scan before rendering.

Phase 7B remains current-only and read-only. It reads current SQLite state produced from `research/latest_index.json` `modules`, not `latest_index.files`. It does not write `research/latest_index.json`, `research/actions`, `research/allocation`, target-allocation artifacts, action-plan artifacts, trading records, or QMT write calls.

Phase 7C adds a frontend-only bucket gap visualization to the same page. The chart is rendered from `/api/subjects/gap` JSON, color-codes bucket gap status, and shows actual percentage, target percentage, gap percentage points, staleness status, and last-update timestamp on hover. The API contract is unchanged.

The API reads SQLite current-state rows loaded from `research/latest_index.json` `modules`, not `latest_index.files`. It returns neutral gate conclusions only: `eligible_for_review`, `research_first`, `watch`, `hold`, `no_action`, `unknown`, or `blocked`. It must not return buy/add/reduce/sell conclusions. Missing profile, valuation, liquidity, or theme binding keeps a subject in `research_first` or `blocked` status.

Full gate:

```bash
python scripts/web_release_check.py
```

## API and Page Smoke Check

```bash
python scripts/ingest_current_state.py
python scripts/run_web.py
```

Then open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/dashboard`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/dashboard/current`
- `http://127.0.0.1:8000/api/current`
- `http://127.0.0.1:8000/api/market-position/current`
- `http://127.0.0.1:8000/api/target-allocation/shadow/compare`
- `http://127.0.0.1:8000/api/target-allocation/shadow/export?format=json`
- `http://127.0.0.1:8000/api/target-allocation/candidate-audit?format=json`
- `http://127.0.0.1:8000/api/history/export?format=json`
- `http://127.0.0.1:8000/subjects/gap`
- `http://127.0.0.1:8000/api/subjects/gap`
- `http://127.0.0.1:8000/api/subjects/freshness`
- `http://127.0.0.1:8000/subjects`
- `http://127.0.0.1:8000/api/subjects/status`
- `http://127.0.0.1:8000/themes`
- `http://127.0.0.1:8000/api/themes/status`
- `http://127.0.0.1:8000/buckets/drilldown`
- `http://127.0.0.1:8000/api/buckets/drilldown?detail=full`
- `http://127.0.0.1:8000/subjects/drilldown`
- `http://127.0.0.1:8000/api/subjects/drilldown?detail=full`
- `http://127.0.0.1:8000/api/modules/current`
- `http://127.0.0.1:8000/api/export/review_package?format=json`

## Page Interactions

- `Refresh` reloads the current page data from the matching read-only API endpoint.
- Pages also refresh automatically every 60 seconds.
- Table headers with sort markers can be clicked to sort.
- Search boxes filter the current table; `Clear` resets the filter.
- Filter menus narrow supported tables by status, bucket, rating, or stage.
- Tables page rows client-side; use `Prev` and `Next` below the table.
- Click a table row to expand or collapse ratio-only detail text.
- Dashboard shows bucket allocation gaps as a centered bar chart and highlights ResearchFirst and intraday status.
- Bucket Drilldown shows a hover/focus chart tooltip for actual vs target percentage.

Every frontend refresh performs a lightweight forbidden-field scan before rendering. Server responses are also checked by `RatioOnlyService`.

## Export Current Review Package

JSON snapshot:

```bash
curl "http://127.0.0.1:8000/api/export/review_package?format=json"
```

ZIP package:

```bash
curl -o myinvest_current_review_package.zip "http://127.0.0.1:8000/api/export/review_package"
```

The export is current-only and includes the current action plan, target allocation, intraday rules, portfolio ratio snapshot, market-position mapping, bucket registry, liquidity gate registry, decision log entries, and system checks. The export is generated in memory and does not write ZIP files into the repository.

## Validation

The ingest command runs:

- `python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>`
- `python scripts/check_cross_file_allocation_consistency.py`
- `python scripts/project_check.py --current-only`
- `python scripts/run_web.py --help`

Any failure blocks ingest.

The System Checks page also displays the sanitizer summary and table counts from the SQLite read model.
