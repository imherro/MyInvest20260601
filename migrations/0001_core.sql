CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime')),
  checksum TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime'))
);

CREATE TABLE IF NOT EXISTS research_runs (
  run_id TEXT PRIMARY KEY,
  module TEXT NOT NULL,
  version TEXT,
  run_type TEXT,
  session TEXT,
  status TEXT NOT NULL DEFAULT 'completed',
  generated_at TEXT NOT NULL,
  basis_date TEXT,
  basis_trade_date TEXT,
  command TEXT,
  created_by TEXT DEFAULT 'codex_or_script',
  notes TEXT,
  raw_summary TEXT,
  quality_status TEXT,
  staleness_status TEXT,
  privacy_policy TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime'))
);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT,
  module TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  generated_at TEXT,
  basis_date TEXT,
  basis_trade_date TEXT,
  code TEXT,
  name TEXT,
  raw_json TEXT,
  raw_text TEXT,
  quality_status TEXT,
  staleness_status TEXT,
  ingested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime')),
  UNIQUE(path, sha256),
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS artifact_dependencies (
  artifact_id TEXT NOT NULL,
  depends_on_artifact_id TEXT,
  dependency_path TEXT NOT NULL,
  dependency_role TEXT,
  dependency_sha256 TEXT,
  required INTEGER DEFAULT 1,
  status TEXT DEFAULT 'unknown',
  PRIMARY KEY (artifact_id, dependency_path),
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (depends_on_artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS run_dependencies (
  run_id TEXT NOT NULL,
  depends_on_run_id TEXT,
  dependency_module TEXT,
  dependency_role TEXT,
  dependency_path TEXT,
  status TEXT DEFAULT 'unknown',
  PRIMARY KEY (run_id, dependency_role, dependency_path),
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id),
  FOREIGN KEY (depends_on_run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS securities (
  security_id TEXT PRIMARY KEY,
  ts_code TEXT UNIQUE,
  code_short TEXT NOT NULL,
  exchange TEXT,
  name TEXT,
  asset_type TEXT,
  market TEXT DEFAULT 'CN',
  first_seen_at TEXT,
  last_seen_at TEXT,
  active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS security_aliases (
  alias TEXT PRIMARY KEY,
  security_id TEXT NOT NULL,
  alias_type TEXT,
  FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE TABLE IF NOT EXISTS buckets (
  bucket_key TEXT PRIMARY KEY,
  bucket_label TEXT,
  bucket_type TEXT,
  risk_level TEXT,
  display_order INTEGER,
  active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS bucket_assignment_history (
  assignment_id TEXT PRIMARY KEY,
  security_id TEXT NOT NULL,
  bucket_key TEXT NOT NULL,
  run_id TEXT,
  effective_at TEXT NOT NULL,
  reason TEXT,
  source_artifact_id TEXT,
  FOREIGN KEY (security_id) REFERENCES securities(security_id),
  FOREIGN KEY (bucket_key) REFERENCES buckets(bucket_key),
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id),
  FOREIGN KEY (source_artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS config_snapshots (
  config_snapshot_id TEXT PRIMARY KEY,
  run_id TEXT,
  config_key TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  raw_json TEXT,
  captured_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime')),
  UNIQUE(path, sha256),
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS decision_events (
  decision_event_id TEXT PRIMARY KEY,
  run_id TEXT,
  event_at TEXT NOT NULL,
  module TEXT,
  subject_code TEXT,
  subject_name TEXT,
  event_type TEXT,
  summary TEXT,
  raw_text TEXT,
  artifact_id TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id),
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS quality_checks (
  quality_check_id TEXT PRIMARY KEY,
  run_id TEXT,
  check_name TEXT NOT NULL,
  status TEXT NOT NULL,
  checked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime')),
  summary TEXT,
  raw_output TEXT,
  artifact_id TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id),
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS privacy_scan_results (
  privacy_scan_id TEXT PRIMARY KEY,
  artifact_id TEXT,
  run_id TEXT,
  scanner_version TEXT,
  status TEXT NOT NULL,
  finding_count INTEGER DEFAULT 0,
  findings_json TEXT,
  scanned_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime')),
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id),
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_research_runs_module_generated
  ON research_runs(module, generated_at);

CREATE INDEX IF NOT EXISTS idx_artifacts_module_generated
  ON artifacts(module, generated_at);

CREATE INDEX IF NOT EXISTS idx_artifacts_path
  ON artifacts(path);

CREATE INDEX IF NOT EXISTS idx_securities_code
  ON securities(ts_code, code_short);
