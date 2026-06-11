CREATE TABLE IF NOT EXISTS market_score_runs (
  market_score_run_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  market_state TEXT,
  opportunity_score REAL,
  crowding_penalty_score REAL,
  market_position_score REAL,
  equity_range_low_pct REAL,
  equity_range_high_pct REAL,
  bond_cash_range_low_pct REAL,
  bond_cash_range_high_pct REAL,
  offensive_bucket_status TEXT,
  one_line_conclusion TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS market_score_components (
  component_id TEXT PRIMARY KEY,
  market_score_run_id TEXT NOT NULL,
  component_key TEXT NOT NULL,
  score REAL,
  weight REAL,
  evidence_json TEXT,
  FOREIGN KEY (market_score_run_id) REFERENCES market_score_runs(market_score_run_id)
);

CREATE TABLE IF NOT EXISTS market_allocation_ranges (
  range_id TEXT PRIMARY KEY,
  market_score_run_id TEXT NOT NULL,
  allocation_key TEXT NOT NULL,
  low_pct REAL,
  high_pct REAL,
  reason TEXT,
  FOREIGN KEY (market_score_run_id) REFERENCES market_score_runs(market_score_run_id)
);

CREATE TABLE IF NOT EXISTS market_hard_constraints (
  constraint_id TEXT PRIMARY KEY,
  market_score_run_id TEXT NOT NULL,
  constraint_key TEXT,
  status TEXT,
  reason TEXT,
  raw_json TEXT,
  FOREIGN KEY (market_score_run_id) REFERENCES market_score_runs(market_score_run_id)
);

CREATE TABLE IF NOT EXISTS market_trigger_adjustments (
  adjustment_id TEXT PRIMARY KEY,
  market_score_run_id TEXT NOT NULL,
  trigger_key TEXT,
  adjustment_pp REAL,
  reason TEXT,
  raw_json TEXT,
  FOREIGN KEY (market_score_run_id) REFERENCES market_score_runs(market_score_run_id)
);

CREATE TABLE IF NOT EXISTS themes (
  theme_id TEXT PRIMARY KEY,
  theme_key TEXT UNIQUE NOT NULL,
  theme_name TEXT,
  active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS theme_review_runs (
  theme_review_run_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  summary TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS theme_review_items (
  theme_review_item_id TEXT PRIMARY KEY,
  theme_review_run_id TEXT NOT NULL,
  theme_id TEXT,
  theme_key TEXT,
  theme_name TEXT,
  strategic_rating TEXT,
  trading_rating TEXT,
  phase TEXT,
  prior_rating TEXT,
  rating_change_reason TEXT,
  target_position_range TEXT,
  target_low_pct REAL,
  target_high_pct REAL,
  evidence_json TEXT,
  FOREIGN KEY (theme_review_run_id) REFERENCES theme_review_runs(theme_review_run_id),
  FOREIGN KEY (theme_id) REFERENCES themes(theme_id)
);

CREATE TABLE IF NOT EXISTS theme_security_links (
  link_id TEXT PRIMARY KEY,
  theme_review_item_id TEXT NOT NULL,
  security_id TEXT,
  code TEXT,
  name TEXT,
  link_role TEXT,
  FOREIGN KEY (theme_review_item_id) REFERENCES theme_review_items(theme_review_item_id),
  FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE TABLE IF NOT EXISTS security_profile_runs (
  security_profile_run_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  security_id TEXT,
  profile_type TEXT,
  action_rating TEXT,
  overall_score REAL,
  target_position_range TEXT,
  target_low_pct REAL,
  target_high_pct REAL,
  research_first_status TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id),
  FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE TABLE IF NOT EXISTS security_profile_scores (
  score_id TEXT PRIMARY KEY,
  security_profile_run_id TEXT NOT NULL,
  score_key TEXT NOT NULL,
  score REAL,
  weight REAL,
  evidence TEXT,
  FOREIGN KEY (security_profile_run_id) REFERENCES security_profile_runs(security_profile_run_id)
);

CREATE TABLE IF NOT EXISTS security_operation_conditions (
  condition_id TEXT PRIMARY KEY,
  security_profile_run_id TEXT NOT NULL,
  condition_type TEXT NOT NULL,
  condition_text TEXT NOT NULL,
  FOREIGN KEY (security_profile_run_id) REFERENCES security_profile_runs(security_profile_run_id)
);

CREATE TABLE IF NOT EXISTS security_risk_items (
  risk_item_id TEXT PRIMARY KEY,
  security_profile_run_id TEXT NOT NULL,
  risk_key TEXT,
  risk_text TEXT NOT NULL,
  severity TEXT,
  FOREIGN KEY (security_profile_run_id) REFERENCES security_profile_runs(security_profile_run_id)
);

CREATE TABLE IF NOT EXISTS valuation_reports (
  valuation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  security_id TEXT NOT NULL,
  basis_date TEXT,
  price_date TEXT,
  asset_type TEXT,
  current_value REAL,
  comparable_current_value REAL,
  current_zone_key TEXT,
  current_zone_label TEXT,
  stance_label TEXT,
  valuation_basis TEXT,
  confidence TEXT,
  not_portfolio_action INTEGER DEFAULT 1,
  source_json TEXT,
  price_series_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id),
  FOREIGN KEY (security_id) REFERENCES securities(security_id)
);

CREATE TABLE IF NOT EXISTS valuation_zones (
  valuation_zone_id TEXT PRIMARY KEY,
  valuation_id TEXT NOT NULL,
  zone_key TEXT NOT NULL,
  zone_label TEXT,
  min_value REAL,
  max_value REAL,
  display_order INTEGER,
  raw_json TEXT,
  UNIQUE(valuation_id, zone_key),
  FOREIGN KEY (valuation_id) REFERENCES valuation_reports(valuation_id)
);

CREATE TABLE IF NOT EXISTS valuation_metrics (
  valuation_metric_id TEXT PRIMARY KEY,
  valuation_id TEXT NOT NULL,
  metric_key TEXT NOT NULL,
  metric_value REAL,
  metric_text TEXT,
  unit TEXT,
  raw_json TEXT,
  FOREIGN KEY (valuation_id) REFERENCES valuation_reports(valuation_id)
);

CREATE TABLE IF NOT EXISTS valuation_reference_metrics (
  reference_metric_id TEXT PRIMARY KEY,
  valuation_id TEXT NOT NULL,
  metric_key TEXT NOT NULL,
  metric_value REAL,
  metric_text TEXT,
  unit TEXT,
  raw_json TEXT,
  FOREIGN KEY (valuation_id) REFERENCES valuation_reports(valuation_id)
);

CREATE TABLE IF NOT EXISTS valuation_data_gaps (
  data_gap_id TEXT PRIMARY KEY,
  valuation_id TEXT NOT NULL,
  gap_key TEXT,
  severity TEXT,
  description TEXT NOT NULL,
  FOREIGN KEY (valuation_id) REFERENCES valuation_reports(valuation_id)
);

CREATE TABLE IF NOT EXISTS position_slots (
  position_slot_id TEXT PRIMARY KEY,
  security_id TEXT,
  slot_code TEXT NOT NULL UNIQUE,
  bucket_key TEXT,
  lifecycle_status TEXT DEFAULT 'active',
  created_run_id TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d_%H%M%S','now','localtime')),
  FOREIGN KEY (security_id) REFERENCES securities(security_id),
  FOREIGN KEY (bucket_key) REFERENCES buckets(bucket_key),
  FOREIGN KEY (created_run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  basis_trade_date TEXT,
  equity_weight_pct REAL,
  bond_cash_weight_pct REAL,
  cash_uninvested_pct REAL,
  weight_sum_pct REAL,
  privacy_policy TEXT,
  package_redaction_json TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS portfolio_positions (
  position_id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  security_id TEXT,
  position_slot_id TEXT,
  code_raw TEXT,
  name_raw TEXT,
  allocation_bucket TEXT,
  category TEXT,
  weight_pct REAL,
  day_change_pct REAL,
  reference_pnl_pct REAL,
  research_status TEXT,
  raw_json TEXT,
  FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(snapshot_id),
  FOREIGN KEY (security_id) REFERENCES securities(security_id),
  FOREIGN KEY (position_slot_id) REFERENCES position_slots(position_slot_id)
);

CREATE TABLE IF NOT EXISTS portfolio_bucket_exposures (
  bucket_exposure_id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  bucket_key TEXT NOT NULL,
  weight_pct REAL,
  target_low_pct REAL,
  target_high_pct REAL,
  gap_pct REAL,
  FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS portfolio_category_exposures (
  category_exposure_id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  category TEXT NOT NULL,
  weight_pct REAL,
  FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS target_allocation_runs (
  target_allocation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  basis_trade_date TEXT,
  equity_target_low_pct REAL,
  equity_target_high_pct REAL,
  bond_cash_target_low_pct REAL,
  bond_cash_target_high_pct REAL,
  one_line_conclusion TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS target_allocation_buckets (
  target_bucket_id TEXT PRIMARY KEY,
  target_allocation_id TEXT NOT NULL,
  bucket_key TEXT NOT NULL,
  target_low_pct REAL,
  target_high_pct REAL,
  target_center_pct REAL,
  actual_pct REAL,
  gap_pct REAL,
  raw_json TEXT,
  FOREIGN KEY (target_allocation_id) REFERENCES target_allocation_runs(target_allocation_id)
);

CREATE TABLE IF NOT EXISTS target_transition_targets (
  transition_target_id TEXT PRIMARY KEY,
  target_allocation_id TEXT NOT NULL,
  subject_code TEXT,
  subject_name TEXT,
  bucket_key TEXT,
  target_low_pct REAL,
  target_high_pct REAL,
  reason TEXT,
  FOREIGN KEY (target_allocation_id) REFERENCES target_allocation_runs(target_allocation_id)
);

CREATE TABLE IF NOT EXISTS action_plans (
  action_plan_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  session TEXT,
  action_state TEXT,
  recommendation_strength TEXT,
  market_conclusion TEXT,
  valuation_conclusion TEXT,
  portfolio_conclusion TEXT,
  research_first_conclusion TEXT,
  one_line_conclusion TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS action_items (
  action_item_id TEXT PRIMARY KEY,
  action_plan_id TEXT NOT NULL,
  security_id TEXT,
  position_slot_id TEXT,
  priority TEXT,
  action_type TEXT,
  subject_type TEXT,
  subject_code TEXT,
  subject_name TEXT,
  bucket_key TEXT,
  current_position_text TEXT,
  current_position_pct REAL,
  suggested_change_text TEXT,
  suggested_change_low_pp REAL,
  suggested_change_high_pp REAL,
  target_position_text TEXT,
  target_position_low_pct REAL,
  target_position_high_pct REAL,
  recommendation_strength TEXT,
  needs_manual_confirmation INTEGER DEFAULT 1,
  raw_json TEXT,
  FOREIGN KEY (action_plan_id) REFERENCES action_plans(action_plan_id),
  FOREIGN KEY (security_id) REFERENCES securities(security_id),
  FOREIGN KEY (position_slot_id) REFERENCES position_slots(position_slot_id)
);

CREATE TABLE IF NOT EXISTS action_item_evidence (
  evidence_id TEXT PRIMARY KEY,
  action_item_id TEXT NOT NULL,
  evidence_type TEXT,
  evidence_text TEXT,
  artifact_id TEXT,
  FOREIGN KEY (action_item_id) REFERENCES action_items(action_item_id),
  FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS action_item_conditions (
  condition_id TEXT PRIMARY KEY,
  action_item_id TEXT NOT NULL,
  condition_type TEXT NOT NULL,
  condition_text TEXT NOT NULL,
  FOREIGN KEY (action_item_id) REFERENCES action_items(action_item_id)
);

CREATE TABLE IF NOT EXISTS research_first_blocks (
  research_first_block_id TEXT PRIMARY KEY,
  action_plan_id TEXT NOT NULL,
  subject_code TEXT,
  subject_name TEXT,
  subject_type TEXT,
  blocker_reason TEXT,
  required_research TEXT,
  status TEXT DEFAULT 'blocked',
  FOREIGN KEY (action_plan_id) REFERENCES action_plans(action_plan_id)
);

CREATE TABLE IF NOT EXISTS strategy_briefings (
  strategy_briefing_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  basis_trade_date TEXT,
  market_view TEXT,
  focus_directions TEXT,
  risk_notes TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS premarket_checks (
  premarket_check_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  basis_trade_date TEXT,
  gate_status TEXT,
  allowed_actions TEXT,
  blocked_actions TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS intraday_rule_sets (
  intraday_rule_set_id TEXT PRIMARY KEY,
  run_id TEXT,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  basis_trade_date TEXT,
  raw_json TEXT,
  UNIQUE(path, sha256),
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS intraday_alerts (
  intraday_alert_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  basis_trade_date TEXT,
  alert_status TEXT,
  trigger_count INTEGER,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE TABLE IF NOT EXISTS post_market_reviews (
  post_market_review_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL UNIQUE,
  basis_trade_date TEXT,
  review_status TEXT,
  execution_deviation TEXT,
  second_day_watch_points TEXT,
  source_json TEXT,
  FOREIGN KEY (run_id) REFERENCES research_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_valuation_security_basis
  ON valuation_reports(security_id, basis_date);

CREATE INDEX IF NOT EXISTS idx_valuation_current_zone
  ON valuation_reports(current_zone_key);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshot_run
  ON portfolio_snapshots(run_id);

CREATE INDEX IF NOT EXISTS idx_portfolio_positions_security
  ON portfolio_positions(security_id);

CREATE INDEX IF NOT EXISTS idx_position_slots_security
  ON position_slots(security_id);

CREATE INDEX IF NOT EXISTS idx_action_items_subject
  ON action_items(subject_code, action_type);

CREATE INDEX IF NOT EXISTS idx_theme_items_theme
  ON theme_review_items(theme_key);
