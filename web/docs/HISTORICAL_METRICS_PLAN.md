# Historical Metrics And Audit Integration Plan

## Scope

Phase 15A is design-only. It documents the next Historical Metrics and Audit
Integration step before implementation.

This phase does not:

- modify Python services, repositories, routers, templates, or static JS
- modify SQLite files or create tables
- modify ingest
- add Alembic or another migration framework
- add API endpoints
- write research artifacts
- change target allocation or action plan generation
- change trading, QMT, order, or fill behavior

## Current Architecture

Historical Metrics is already a read-only Web review surface.

Current API and page:

- `GET /api/historical-metrics`
- `GET /api/historical-metrics/{entity_id}`
- `GET /historical-metrics`

`HistoricalMetricsService` composes existing read-only services:

- `HistoryGapDashboardService` for bucket history summaries
- `SubjectGapService` for current bucket/subject gap rows
- `SubjectStatusService` for ResearchFirst, profile, valuation, and liquidity
  status
- `ThemeStatusService` for theme status summaries
- `DecisionTimelineService` for neutral review events
- `CurrentStateService` for current market score and current-module source
  metadata

The service returns:

- summary counts
- bucket, subject, theme, and decision-type aggregations
- bucket and market-score series
- entity rows with ratio-only percentages, percentage-point gaps, status labels,
  timestamps, and relative review links
- source module metadata
- safety flags

`AuditBundleService` already includes Historical Metrics as a section in
`GET /api/audit/bundle`, alongside dashboard analytics, preferences, workbench
integration, current-module source metadata, and guarded history snapshot
availability.

## Data Sources

The design keeps current-only resolution unchanged:

- current SQLite read model generated from `research/latest_index.json`
  `modules`
- current target allocation, portfolio snapshot, market score, action plan, and
  intraday rules already ingested into `temp/web_db/myinvest.sqlite`
- current decision log summary exposed through existing read-only services
- optional guarded history snapshot runtime summary, where available

`latest_index.files` must not be used as a current resolver.

## Phase 15B Design Goal

Phase 15B should make Historical Metrics easier to audit without changing
research generation. The likely implementation should add a narrow read-only
audit/reporting layer that answers:

- which Historical Metrics inputs were used
- whether required inputs are present
- whether Historical Metrics, Audit Bundle, and Dashboard analytics agree on
  shared safe counts and current-module source metadata
- whether the optional history snapshot was available or absent
- whether the result stayed current-only, ratio-only, ResearchFirst-safe, and
  GET-only

This should be a reporting layer, not a data-generation layer.

## Proposed Phase 15B Service Boundary

Recommended service:

```text
HistoricalMetricsAuditService.status() -> {
  "module": "historical_metrics_audit",
  "status": "ok" | "degraded" | "mismatch" | "unavailable",
  "current_only": true,
  "read_only": true,
  "ratio_only": true,
  "required_inputs_present": bool,
  "missing_inputs": string[],
  "source_modules": object,
  "consistency_checks": object,
  "history_snapshot_available": bool,
  "diagnostics_warnings": string[],
  "checked_at": string
}
```

Recommended repository behavior:

- use existing services and repositories that already delegate to
  `DatabaseService`
- do not open raw SQLite connections for diagnostics
- do not read files directly unless the existing current-state service already
  provides a sanitized source payload
- do not read `latest_index.files`

## Proposed Diagnostics Endpoint

If Phase 15B exposes Web status, use a GET-only diagnostics endpoint:

```text
GET /api/diagnostics/historical-metrics
```

The endpoint should return only safe operational metadata:

- status strings
- boolean readiness flags
- safe counts
- repo-relative source metadata
- warning codes
- timestamps

It must not return row-level SQLite contents, local absolute paths, credentials,
runtime paths, or trading/execution records.

## Audit Bundle Integration

Phase 15B may add the Historical Metrics audit status into the existing audit
bundle as a safe section. The bundle should continue to be generated in memory
and returned over GET.

Suggested bundle field:

```text
data.sections[].name == "historical_metrics_audit"
```

or a nested field under the existing `historical_metrics` section:

```text
historical_metrics.audit_status
```

The implementation should avoid duplicating full Historical Metrics payloads in
the audit status. It should report whether Historical Metrics is ready and how
it was checked.

## Fail-Closed Strategy

Historical Metrics audit status should classify failures without mutating state:

- `ok`: all required current-only inputs are present and consistency checks pass
- `degraded`: optional history snapshot is absent or nonessential context is
  unavailable
- `mismatch`: shared counts or current-module source metadata disagree across
  Historical Metrics, Dashboard analytics, or Audit Bundle summaries
- `unavailable`: the diagnostics layer cannot read required safe metadata

Fail-closed behavior means reporting `mismatch` or `unavailable` with safe
warning codes. It must not run repair commands, rebuild SQLite from the request
path, create files, or write research artifacts.

## Safety Boundaries

Phase 15B must preserve:

- read-only Web behavior
- ratio-only payloads
- current-only source resolution through `latest_index.modules`
- ResearchFirst neutrality
- OpenAPI GET-only
- no automatic trading
- no QMT write adapter
- no action-plan or target-allocation generation
- no SQLite writes from request handling
- no runtime, temp, cache, ZIP, log, build, or dist artifacts in Git

## Acceptance Commands

Phase 15A design acceptance:

```bash
python scripts/check_hidden_unicode.py
python -m pytest web/backend/tests -q -W error
python scripts/web_check.py
python scripts/project_check.py --current-only
```

Phase 15B implementation should also add focused tests for:

- all required Historical Metrics inputs present
- optional history snapshot absent but degraded, not failed
- missing required input
- cross-service count mismatch
- diagnostics endpoint GET response safety
- Audit Bundle integration safety
- OpenAPI still GET-only

## Rollback Strategy

Because Phase 15A is documentation only, rollback is a doc-only revert. Phase
15B must remain similarly narrow: if implementation introduces regressions,
remove the new diagnostics endpoint and audit integration without changing
current Historical Metrics, Audit Bundle, or research generation behavior.
