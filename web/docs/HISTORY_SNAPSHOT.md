# History Snapshot

Phase 6 adds a read-only history snapshot for shadow, candidate, and controlled export audit artifacts. It consolidates temporary export results for review. It does not make any target allocation or action plan official.

## Inputs

The history snapshot scans JSON and ZIP artifacts under the existing ignored export scopes:

- controlled shadow export artifacts
- candidate simulation artifacts
- candidate audit artifacts

The service also builds a live current summary from the SQLite read model so the snapshot always includes the current shadow-vs-reference compare, candidate audit compare, replay fixture summary, promotion-mode status, provenance, and safety checks.

## Outputs

Read-only API:

```bash
GET /api/history/export
GET /api/history/export?format=json
GET /api/history/export?format=zip
```

CLI:

```bash
python scripts/export_history_snapshot.py --dry-run
python scripts/export_history_snapshot.py --format json
python scripts/export_history_snapshot.py --format zip
```

API exports are generated in memory. CLI exports write only to ignored temporary export folders and write a local history database only under ignored runtime storage.

The ZIP allowlist is:

- `manifest.json`
- `history_snapshot.json`
- `history_entries.json`
- `live_current_summary.json`
- `safety_checks.json`

## Safety Contract

The history snapshot must remain:

- ratio-only
- current-only for live current checks
- read-only for research state
- free of local absolute paths
- free of runtime paths inside exported JSON or ZIP payloads
- free of monetary amounts, share counts, account identifiers, order records, fill records, and QMT write behavior

The service must not:

- write `research/latest_index.json`
- write `research/allocation`
- write `research/actions`
- update `current_modules`
- generate official target allocation
- generate action plans
- create trading, order, fill, automatic execution, or QMT write interfaces

## Validation

Run direct tests:

```bash
python -m pytest web/backend/tests/test_history_snapshot.py
```

Run the full gate:

```bash
python scripts/web_check.py
```

The full gate verifies the history snapshot API, CLI dry-run, JSON export, ZIP export, ZIP allowlist, forbidden-field scan, runtime-term scan, replay summary, candidate audit compare, shadow compare, ResearchFirst, allocation consistency, and project check.

## Corrupt History Sources

If a temporary JSON or ZIP audit artifact is corrupt, the history snapshot must fail closed. The CLI returns a ratio-only JSON error and exits nonzero. The API returns a safe HTTP 500 detail. Neither path may print a traceback, leak a local absolute path, write the history database, or copy corrupt file content into an export.
