# MyInvest Phase Handoff

This handoff file is the durable cross-session starting point for new Codex sessions, ChatGPT reviews, and future maintainers. It should be read before continuing Web/DB development.

## Current Baseline

- Project: MyInvest
- Current stable tag: `web-workbench-phase10-12-v0.4.2`
- Previous read-only repository baseline tag: `web-db-repository-readonly-baseline-v0.3.0`
- Stable baseline meaning:
  - Web + DB repository read-only baseline.
  - SQLite ingest.
  - FastAPI read-only API.
  - Jinja2 + static JS Web workbench.
  - `DatabaseService` read-only facade.
  - Repository read-only consolidation baseline.
  - `HistorySnapshotRepository` is the only documented runtime DB write exception, limited to `temp/web_runtime/history_snapshot.sqlite`.
  - Phase 10-12 Workbench release is merged and tagged.
  - Phase 13A release packaging hygiene is merged and tagged.
  - Phase 13B CI/test warning hygiene is merged and tagged.
- Current worktree:
  - Phase 10 worktree: local sibling worktree, not the stable production worktree.
- Stable web port: `8000`
- Phase 10 development port: `8010`
- Stable web service and Phase 10 development service must use separate `temp/`, SQLite, and runtime directories.

## Release Snapshot v0.4.2

- Stable commit: `cf0e42cac05ce78f7e108bf41425399514d17e92`
- Stable tag: `web-workbench-phase10-12-v0.4.2`
- Release tags:
  - `web-workbench-phase10-12-v0.4.0`: Phase 10-12 Workbench release.
  - `web-workbench-phase10-12-v0.4.1`: Phase 13A review package privacy scan hygiene.
  - `web-workbench-phase10-12-v0.4.2`: Phase 13B CI/test warning hygiene.
- PR status:
  - PR #24 through PR #30 are merged.
  - Phase 13B merge commit is `cf0e42cac05ce78f7e108bf41425399514d17e92`.
- Current validation baseline:
  - `python scripts/check_hidden_unicode.py`: PASS.
  - `python scripts/ingest_current_state.py`: PASS.
  - `python -m pytest web/backend/tests -q`: PASS.
  - `python -m pytest web/backend/tests -q -W error`: PASS.
  - `python scripts/web_check.py`: PASS with 0 WARN.
  - `python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>`: PASS.
  - `python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>`: PASS.
  - `python scripts/check_cross_file_allocation_consistency.py`: PASS.
  - `python scripts/project_check.py --current-only`: PASS.
  - Strict source review package build: PASS with `privacy_warnings=0`.
- Next phase entry:
  - Phase 14 must start from `main` at or after `web-workbench-phase10-12-v0.4.2`.
  - New sessions must read `AGENTS.md`, this file, `web/docs/WEB_RUNBOOK.md`, `web/docs/SERVICE_LAYER_PLAN.md`, and `web/docs/API_SPEC.md`.
  - Default boundaries remain read-only, ratio-only, current-only, and OpenAPI GET-only.
  - Do not start from the older `web-db-repository-readonly-baseline-v0.3.0` tag for Phase 14 work unless explicitly asked to inspect historical state.

## Hard Boundaries

1. No automatic trading.
2. No QMT write interface.
3. No order generation.
4. No fill, deal, or execution records.
5. No share count.
6. No trade amount.
7. No total asset, monetary amount, market value, profit amount, or account exposure in Web/API/export.
8. Web/API/export must remain ratio-only.
9. Current-only means only `research/latest_index.json` `modules`.
10. `latest_index.files` must never be used as a current resolver.
11. The ResearchFirst gate must not be bypassed.
12. Single-security buy/add/reduce/sell still requires profile pass, valuation pass, and liquidity pass.
13. Cash/short-duration instruments also require profile, valuation, liquidity, duration, interest-rate, credit, and liquidity risk disclosure.
14. Do not modify `generate_action_plan.py` or `generate_target_allocation.py` unless explicitly entering a dedicated audited generation phase.
15. Do not modify `research/latest_index.json`, `research/actions`, or `research/allocation` unless explicitly entering a controlled research-generation phase.
16. Do not commit `temp/`, SQLite, runtime, cache, `.env`, ZIP, log, `node_modules`, build, or dist artifacts.
17. All new work must pass the standard validation commands.

## Completed Phase Summary

### Phase 0-4

- Web read-only dashboard baseline.
- SQLite ingest.
- FastAPI current-only APIs.
- `RatioOnlyService`.
- ResearchFirst gate preservation.
- `web_check.py` and CI.

### Phase 5

- `MarketPositionService` baseline.
- `TargetAllocationGenerationService` shadow mode.
- Controlled target allocation shadow export.
- Multi-scenario target allocation shadow replay fixtures.
- Controlled promotion plan.
- Candidate / official promotion simulation.
- Candidate audit bundle.
- History snapshot audit export.

### Phase 6

- History snapshot audit export.
- History export edge-case hardening.

### Phase 7

- Research Dashboard Landing Page.
- Subject Research Status Center.
- Subject Gap / Freshness Center.
- Subject Gap visualization.
- Theme Research Center.
- Bucket Explorer.
- History Gap Dashboard.
- Allocation Drilldown.
- Decision Timeline / Review Timeline.

### Phase 8

- Historical Metrics Dashboard.
- Hidden Unicode reconciliation and `check_hidden_unicode.py` hardening.

### Phase 9

- `DatabaseService` read-only facade.
- `CurrentStateService` through `DatabaseService`.
- SubjectStatus DB access consolidation.
- SubjectGap / Bucket / Theme / Dashboard DB access consolidation.
- Allocation / History / DecisionTimeline DB read-only coverage.
- HistorySnapshot runtime DB policy.
- Repository read-only baseline.
- Stable tag: `web-db-repository-readonly-baseline-v0.3.0`

### Phase 10-12

- Workbench environment status, user preferences, analytics dashboard, integration, and audit bundle are complete.
- Stable tag: `web-workbench-phase10-12-v0.4.0`

### Phase 13A

- Source review package privacy scan false-positive hygiene is complete.
- Hidden Unicode warning risk was triaged and removed from the release packaging changes.
- Stable tag: `web-workbench-phase10-12-v0.4.1`

### Phase 13B

- CI/test warning hygiene is complete.
- `pytest -W error` is part of the Web CI gate.
- Starlette/httpx `TestClient` deprecation handling is narrow and documented.
- SQLite/file resource cleanup is explicit in warning-sensitive tests.
- Stable tag: `web-workbench-phase10-12-v0.4.2`

## Current Architecture Summary

- Old research generation layer still exists:
  - `generate_market`, `generate_target_allocation`, `generate_action_plan`, profile, and valuation scripts remain the reference generation layer.
- Web DB layer:
  - `scripts/ingest_current_state.py` imports current-only research state into SQLite.
  - FastAPI APIs read from SQLite / `DatabaseService`.
  - Web pages are read-only.
  - No official target allocation or action plan generation is replaced.
- JSON/Markdown research artifacts remain the auditable source of formal research outputs.
- DB/Web layer is a read-only workbench and audit/shadow/candidate analysis layer.

## Phase 10 Roadmap

### Phase 10A - Workbench Settings & Environment Center

Goal:

- Add `/api/environment/status`.
- Add `/settings` or `/environment` page.
- Show branch, commit, baseline tag, worktree status, temp paths, DB path, web host/port, safety boundaries, and check status.
- Paths must be repo-relative or redacted.
- Do not return local absolute paths such as user-home paths.
- Phase 10 dev port should be `8010`.
- Stable port is `8000`.

Status:

- In progress in the Phase 10 worktree until validation and commit are complete.

### Phase 10B - Local Web Operations Center

Goal:

- Add a read-only Operations Center page.
- Show common local commands:
  - `ingest_current_state`
  - `web_check`
  - `pytest`
  - `check_hidden_unicode`
  - `check_ratio_only`
  - `check_research_first_gate`
  - `check_cross_file_allocation_consistency`
  - `project_check --current-only`
  - export shadow / candidate / history snapshot commands
- First version must be a read-only command catalog and status display.
- It must not execute shell commands from Web.
- It can show copyable commands.
- It can show last-known status if already stored safely.
- No command execution in Phase 10B.

### Phase 10C - Validation Result Viewer

Goal:

- Display validation results from stored safe summaries.
- Show:
  - latest `web_check` summary
  - pytest summary
  - hidden Unicode summary
  - `project_check` summary
  - ratio-only / ResearchFirst / allocation consistency status
- First version reads safe JSON summaries only.
- Does not run commands.
- Does not write `research/current`.

### Phase 10D - Local Export Center, read-only catalog

Goal:

- Show available export commands and existing temp export summaries:
  - target allocation shadow export
  - candidate audit export
  - history snapshot export
- First version does not trigger exports from Web.
- It only displays safe summaries and copyable CLI commands.

## Phase 11 Roadmap

### Phase 11A - DB Schema Versioning / Migration Plan

Goal:

- Introduce explicit database schema versioning.
- Document current SQLite schema version.
- Add a `schema_version` table or metadata record.
- Do not introduce Alembic yet unless scoped.
- Do not break existing ingest.

### Phase 11B - DB Migration Guard

Goal:

- Add checks that current SQLite schema matches expected version.
- Add `web_check` integration.
- If schema mismatch, fail with safe error.
- No automatic destructive migration.

### Phase 11C - Alembic or Migration Framework Evaluation

Goal:

- Evaluate whether to introduce Alembic or a lightweight migration system.
- Produce design doc first.
- No automatic schema mutation without review.

### Phase 11D - API Response Schema / DTO Stabilization

Goal:

- Define stable response schemas for key APIs:
  - dashboard
  - subjects
  - subject gaps
  - themes
  - buckets
  - decision timeline
  - historical metrics
  - environment
- Prefer Pydantic DTOs if consistent with current stack.
- Must preserve ratio-only.

## Phase 12 Roadmap

### Phase 12A - Controlled DB-native Target Allocation Candidate

Goal:

- Only after schema versioning and API DTOs are stable.
- New DB-native TargetAllocation candidate generator may produce candidate outputs to temp only.
- Must not replace old `generate_target_allocation.py`.
- Must not write `research/allocation`.
- Must not update `latest_index`.
- Must remain shadow/candidate until separately audited.

### Phase 12B - Formal Generation Promotion Review

Goal:

- Design a promotion checklist if DB-native generator ever becomes official.
- Requires:
  - golden tests
  - replay fixtures
  - current review package
  - manual approval
  - `decision_log` entry
  - rollback plan
- Not implemented until explicitly approved.

### Phase 12C - Action Plan Generation remains out of scope

Goal:

- `ActionPlanGenerationService` official replacement is not planned until target allocation official promotion is separately audited.
- No direct trading or order generation.

## Standard Acceptance Commands

All phases must run:

```bash
python scripts/check_hidden_unicode.py
python scripts/ingest_current_state.py
python -m pytest web/backend/tests -q
python -m pytest web/backend/tests -q -W error
python scripts/web_check.py
python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>
python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>
python scripts/check_cross_file_allocation_consistency.py
python scripts/project_check.py --current-only
python scripts/run_web.py --help
```

`<latest_index.modules.action_plan.path>` must be read dynamically from `research/latest_index.json` `modules.action_plan.path`; do not hard-code action-plan timestamps.

## Branch / Worktree Policy

- Stable worktree can continue running port `8000`.
- Phase 10 worktree should run port `8010`.
- Each new phase should use a new branch.
- Do not commit from the stable worktree while Phase 10 development is ongoing.
- Do not share temp directories between stable and Phase 10 worktree.
- Do not commit SQLite DBs or temp artifacts.

## Next-session Instruction

Before doing any new work:

1. Read `AGENTS.md`.
2. Read `web/docs/PHASE_HANDOFF.md`.
3. Read `web/docs/WEB_RUNBOOK.md`.
4. Read `web/docs/SERVICE_LAYER_PLAN.md`.
5. Confirm current branch, worktree path, baseline tag, and validation status.
6. Do not start a new phase until the current phase has passed validation.
7. Maintain no trading / no QMT write / ratio-only / ResearchFirst / current-only boundaries.
