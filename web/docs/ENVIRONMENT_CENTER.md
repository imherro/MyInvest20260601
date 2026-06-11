# Workbench Environment Center

Phase 10A adds a read-only environment center for the local Web workbench.

## Surfaces

- Page: `GET /settings`
- Alias: `GET /environment`
- API: `GET /api/environment/status`

## Purpose

The environment center shows sanitized status metadata for local review:

- Git branch, commit, dirty state, baseline tag, and worktree status.
- Repo-relative runtime paths for `temp`, the Web SQLite database, runtime storage, and export folders.
- Web host/port contract, including the default `0.0.0.0:8000` runbook setting and the Phase 10 recommended development port `8010`.
- Read-only safety boundaries.
- Latest known check statuses. Unknown means the operator should run `python scripts/web_check.py` or the specific local gate.

## Safety Boundary

The feature is display-only. It must not:

- read `latest_index.files` as current state
- mutate `research/current`
- update `research/latest_index.json`
- write `research/actions` or `research/allocation`
- generate target-allocation or action-plan artifacts
- add trading, execution, automatic submission, or QMT write behavior
- expose local absolute paths, `.env` content, tokens, secrets, passwords, API keys, account context, trade records, runtime file contents, or SQLite file contents

All returned paths must be repo-relative, such as `temp/web_db/myinvest.sqlite`, or safe redacted labels.

## API Contract

`GET /api/environment/status` returns:

```json
{
  "module": "environment_status",
  "readonly": true,
  "read_only": true,
  "current_only": true,
  "ratio_only": true,
  "git": {
    "branch": "codex/phase-10-workbench-next",
    "commit": "<git commit>",
    "dirty": false,
    "dirty_status": "clean",
    "baseline_tag": "web-db-repository-readonly-baseline-v0.3.0",
    "worktree_path": ".",
    "is_worktree": true,
    "main_repo_path": "redacted:<main worktree name>"
  },
  "paths": {
    "project_root": ".",
    "temp_dir": "temp",
    "web_db_path": "temp/web_db/myinvest.sqlite",
    "web_runtime_dir": "temp/web_runtime",
    "web_exports_dir": "temp/web_exports",
    "candidate_exports_dir": "temp/candidate_exports",
    "history_exports_dir": "temp/history_exports"
  },
  "web": {
    "default_host": "0.0.0.0",
    "default_port": 8000,
    "current_host": "unknown",
    "current_port": "unknown",
    "phase10_recommended_port": 8010,
    "lan_mode_enabled": true,
    "readonly_mode": true
  },
  "safety": {
    "read_only": true,
    "no_trading": true,
    "no_qmt_write": true,
    "no_execution_generation": true,
    "ratio_only": true,
    "current_only": true,
    "research_first_gate_required": true,
    "research_current_mutation": false
  },
  "checks": {
    "hidden_unicode": "unknown",
    "ingest_status": "unknown",
    "web_check_status": "unknown",
    "ratio_only_status": "unknown",
    "research_first_status": "unknown",
    "allocation_consistency_status": "unknown",
    "project_check_status": "unknown"
  }
}
```

The `safety.no_execution_generation=true` key is an explicit negative safety declaration. It avoids forbidden wording in the API schema while still documenting that the Web workbench does not create execution artifacts.

## Validation

Run:

```bash
python scripts/check_hidden_unicode.py
python scripts/ingest_current_state.py
python -m pytest web/backend/tests -q
python scripts/web_check.py
python scripts/run_web.py --help
python scripts/check_ratio_only.py --path <latest_index.modules.action_plan.path>
python scripts/check_research_first_gate.py --path <latest_index.modules.action_plan.path>
python scripts/check_cross_file_allocation_consistency.py
python scripts/project_check.py --current-only
```

The action-plan path must be read dynamically from `research/latest_index.json` `modules.action_plan.path`.
