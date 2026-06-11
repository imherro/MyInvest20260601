CREATE INDEX IF NOT EXISTS idx_research_runs_module_generated
  ON research_runs(module, generated_at);

CREATE INDEX IF NOT EXISTS idx_artifacts_module_generated
  ON artifacts(module, generated_at);

CREATE INDEX IF NOT EXISTS idx_artifacts_path
  ON artifacts(path);

CREATE INDEX IF NOT EXISTS idx_artifact_dependencies_path
  ON artifact_dependencies(dependency_path);

CREATE INDEX IF NOT EXISTS idx_valuation_reports_basis
  ON valuation_reports(basis_date);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_basis
  ON portfolio_snapshots(basis_trade_date);

CREATE INDEX IF NOT EXISTS idx_portfolio_positions_security_snapshot
  ON portfolio_positions(security_id, snapshot_id);

CREATE INDEX IF NOT EXISTS idx_position_slots_bucket
  ON position_slots(bucket_key, security_id);

CREATE INDEX IF NOT EXISTS idx_action_items_action_type
  ON action_items(action_type);

CREATE INDEX IF NOT EXISTS idx_action_items_subject_bucket
  ON action_items(subject_code, bucket_key);

CREATE INDEX IF NOT EXISTS idx_market_score_runs_score
  ON market_score_runs(market_position_score);

CREATE INDEX IF NOT EXISTS idx_theme_review_runs_run
  ON theme_review_runs(run_id);

CREATE INDEX IF NOT EXISTS idx_security_profile_runs_security
  ON security_profile_runs(security_id);
