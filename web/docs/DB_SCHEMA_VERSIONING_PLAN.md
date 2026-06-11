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

Phase 14A therefore creates only durable documentation. Phase 14B may implement
the read-only guard after this plan is reviewed.

## Phase 14B Read-Only Guard Interface

A later Phase 14B implementation should add an internal read-only guard with a
small result object. The names below are suggested, not implemented in Phase
14A:

```text
DatabaseService.schema_status() -> {
  "ok": bool,
  "status": "match" | "missing" | "mismatch" | "unavailable",
  "expected_schema_name": "web_sqlite_read_model",
  "expected_schema_version": "web_read_model_v1",
  "actual_schema_name": string | null,
  "actual_schema_version": string | null,
  "message": string
}
```

Guard requirements:

- read schema metadata using a read-only `SELECT`
- use `DatabaseService` or a repository that delegates to `DatabaseService`
- return only safe status strings and version identifiers
- expose no local absolute paths, SQLite contents, credentials, account context,
  order records, or runtime data
- integrate with `scripts/web_check.py`
- optionally surface a sanitized status in existing local diagnostics such as
  `GET /api/environment/status`
- keep OpenAPI GET-only if a Web status surface is later added

Phase 14B must not auto-create, alter, drop, or migrate tables from the read
path. Any write needed to seed schema metadata must belong to the ingest path
and must be reviewed separately from read-time guard behavior if the scope grows.

## Schema Mismatch Safety Behavior

When schema metadata is missing or mismatched, the future guard should fail
closed.

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
