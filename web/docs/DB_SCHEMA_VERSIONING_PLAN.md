# DB Schema Versioning Plan

Phase 14A is a design-only phase for Web SQLite read-model schema
versioning. It does not implement a migration, write SQLite, change ingest,
add a table, add an API, or change Web behavior.

## Scope

The Web SQLite database is a current-only, ratio-only read model generated from
`research/latest_index.json` `modules` pointers. The database lives under
`temp/web_db/myinvest.sqlite`, is ignored by Git, and is not a source of
official research state.

The current schema contract is documented in `web/docs/DATABASE_SCHEMA.md`.
Phase 14A treats that contract as the initial read-model baseline for future
version checks.

Out of scope for Phase 14A:

- modifying `scripts/ingest_current_state.py`
- modifying `scripts/ingest_current_state_to_web_db.py`
- modifying `DatabaseService`, repositories, routers, templates, or static JS
- creating or writing a `schema_version` table
- adding Alembic or any other migration framework
- writing SQLite or research artifacts
- adding API endpoints
- changing target-allocation or action-plan generation

## Versioning Goal

The goal is to make future Web startup and validation detect whether
`temp/web_db/myinvest.sqlite` matches the schema expected by the current code.
The guard should prevent stale or incompatible local read-model databases from
being treated as valid current state.

The initial proposed schema identity for a later implementation is:

```text
schema_name: web_sqlite_read_model
schema_version: web_read_model_v1
schema_source: web/docs/DATABASE_SCHEMA.md
```

`web_read_model_v1` means the current Phase 5A schema plus later read-only
Workbench tables and repository access boundaries documented through Phase 13C.
Phase 14A records this name only as a proposal; no runtime value is written.

## Candidate Table Design

Two minimal designs are acceptable for a later audited implementation. Phase 14B
should choose one and implement it in a separate PR.

### Option A: Single-Row `schema_version`

```sql
CREATE TABLE schema_version (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  schema_name TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  schema_fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source TEXT NOT NULL
);
```

Expected behavior:

- exactly one row with `id = 1`
- `schema_name` is `web_sqlite_read_model`
- `schema_version` is the expected version string
- `schema_fingerprint` is a deterministic fingerprint of the expected table and
  column contract
- `source` is a repo-relative reference such as
  `web/docs/DATABASE_SCHEMA.md`

Benefits:

- small and easy to check with one read-only query
- clear fail-closed behavior when missing or mismatched
- avoids flexible key names that could drift over time

Tradeoff:

- new metadata fields require an explicit table alteration in a later phase

### Option B: Key-Value `schema_metadata`

```sql
CREATE TABLE schema_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source TEXT NOT NULL
);
```

Required keys:

- `schema_name`
- `schema_version`
- `schema_fingerprint`
- `schema_source`

Benefits:

- flexible for future metadata without table alteration
- easy to add non-sensitive schema descriptors later

Tradeoff:

- guard code must validate required keys and reject partial metadata

## Recommended Choice

Phase 14A recommends Option A for the first implementation because the Web read
model has a single current schema contract. A single-row table gives simpler
validation and fewer partial-state cases.

Option B should be considered only if a future migration framework needs more
extensible metadata.

## Why Phase 14A Is Design-Only

Schema versioning touches the local database lifecycle. Implementing it safely
requires coordinated changes to ingest, test setup, `web_check.py`, and
`DatabaseService` guard behavior. Combining that with design would make the
review boundary too broad.

Phase 14A therefore creates only durable documentation. Phase 14B implements the
read-only guard skeleton without changing ingest, migrations, or SQLite write
behavior.

## Phase 14B Read-Only Guard Interface

Phase 14B adds a narrow guard service and repository:

- `web/backend/app/services/schema_guard.py`
- `web/backend/app/repositories/schema_guard_repo.py`
- `GET /api/diagnostics/schema`

The guard returns a small status object under the normal API envelope:

```text
data.schema_guard -> {
  "ok": bool,
  "status": "ok" | "degraded" | "mismatch" | "unavailable",
  "expected_schema_name": "web_sqlite_read_model",
  "expected_schema_version": "web_read_model_v1",
  "observed_schema_name": string | null,
  "observed_schema_version": string | null,
  "schema_version_table_present": bool,
  "required_tables_present": bool,
  "missing_required_tables": string[],
  "checked_at": string,
  "diagnostics_warnings": string[]
}
```

Guard requirements:

- read schema metadata using read-only `SELECT` and safe table-info
  introspection
- use `SchemaGuardRepository`, which delegates to `DatabaseService`
- return only safe status strings and version identifiers
- expose no local absolute paths, SQLite contents, credentials, account context,
  order records, or runtime data
- integrate with `scripts/web_check.py`
- keep OpenAPI GET-only through `GET /api/diagnostics/schema`

Phase 14B does not auto-create, alter, drop, or migrate tables from the read
path. Any future write needed to seed schema metadata belongs to the ingest path
and must be reviewed separately from read-time guard behavior.

Current Phase 14B behavior:

- if required read-model tables and columns exist but no version table exists,
  return `degraded` with `missing_version_table`
- if the future `schema_version` table exists, read row `id = 1` if possible
  and compare `schema_name` and `schema_version`
- if only the future `schema_metadata` table exists, read allowed metadata keys
  and compare safe schema name/version strings
- if required tables or columns are missing, return `mismatch`
- if introspection fails, return `unavailable`

## Phase 14C Read-Only Enforcement Reporting

Phase 14C extends the Phase 14B skeleton with full read-only enforcement
reporting. It still does not write SQLite, create metadata rows, modify ingest,
or introduce migration tooling.

Additional checks:

- compute a deterministic SHA-256 fingerprint from the required read-model
  table/column contract
- expose `expected_schema_fingerprint`
- read `schema_fingerprint` from `schema_version` or `schema_metadata` when
  those tables already exist
- require name, version, and fingerprint to match before returning `ok`
- return `mismatch` when required tables/columns, schema name, schema version,
  or schema fingerprint do not match
- return `degraded` only for the current safe missing-version-metadata state
  where required tables and columns are present
- return `unavailable` when read-only introspection cannot complete

Additional safe report fields:

```text
"schema_fingerprint_match": bool | null
"schema_contract": {
  "required_table_count": int,
  "observed_required_table_count": int,
  "missing_required_table_count": int,
  "required_column_count": int,
  "missing_required_column_count": int
}
"enforcement": {
  "mode": "read_only_schema_guard",
  "status": "ok" | "degraded" | "mismatch" | "unavailable",
  "fail_closed": bool,
  "web_smoke_compatible": bool,
  "read_model_usable": bool
}
```

The current no-version-table database remains `degraded` with
`web_smoke_compatible=true` and `fail_closed=false`. A structural mismatch,
version mismatch, fingerprint mismatch, or introspection failure reports
`fail_closed=true` while still returning a sanitized diagnostics payload.

## Schema Mismatch Safety Behavior

When schema metadata is mismatched, the guard should fail closed. Missing
version metadata is currently a controlled `degraded` state because the Phase
14A/14B/14C database has not yet written version metadata.

Required behavior:

- return a safe error status
- block Web checks that depend on the current SQLite read model
- avoid automatic destructive migration
- avoid automatic table creation from request handling
- avoid writing `research/latest_index.json`, `research/actions`,
  `research/allocation`, or other research artifacts
- avoid exposing local absolute paths or database internals

Recommended user-facing message shape:

```text
Web database schema mismatch. Rebuild the local read model with the reviewed
ingest flow after confirming the expected schema version.
```

The exact text may be refined in Phase 14B, but it must remain non-sensitive and
must not include local absolute paths.

## DatabaseService Boundary

The guard belongs at the Web database access boundary, not in feature services.
`DatabaseService` is the central read-only facade for current SQLite reads, so
future schema status checks should sit there or in a narrow repository used only
by `DatabaseService`.

Feature services should not open raw SQLite connections for schema checks.
Feature services should receive either a valid read model or a safe failure from
the shared access layer.

`HistorySnapshotRepository` remains the separate documented runtime DB
exception for `temp/web_runtime/history_snapshot.sqlite`. The schema versioning
plan applies to the main Web current read model under `temp/web_db/`, not to
history snapshot runtime storage.

## Current-Only, Ratio-Only, ResearchFirst, and GET-Only

Schema version metadata is operational metadata. It must not change investment
research behavior.

Boundaries:

- current-only: schema metadata validates the current SQLite read model loaded
  from `latest_index.modules`; it must not read `latest_index.files`
- ratio-only: metadata values are version/status strings only; no monetary
  amounts, share counts, order records, fill records, account identifiers, or
  local absolute paths
- ResearchFirst: schema checks must not create or change security-level
  conclusions
- GET-only: any future Web visibility must remain read-only and use GET only

## Acceptance Commands

Phase 14A documentation changes must pass:

```bash
python scripts/check_hidden_unicode.py
python -m pytest web/backend/tests -q -W error
python scripts/web_check.py
python scripts/project_check.py --current-only
```

Phase 14B implementation should also add focused tests for match, missing, and
mismatch status before integrating the guard with `web_check.py`.

## Rollback Strategy

For Phase 14A, rollback is a normal documentation revert because no runtime
behavior changes.

For a later Phase 14B implementation:

- revert the guard implementation PR if it blocks valid read models
- delete or regenerate only ignored local SQLite files under `temp/web_db/`
- do not alter committed research artifacts
- do not change tags as part of rollback unless a release manager explicitly
  requests it

## Future Migration Framework Review

Alembic or any other migration framework is not introduced by this plan. If a
future phase proposes a migration framework, it must be a separate PR with its
own audit scope, tests, rollback plan, and explicit review of local-only SQLite
write behavior.
