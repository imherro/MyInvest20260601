CREATE VIEW IF NOT EXISTS v_valuation_history AS
SELECT
  s.ts_code,
  s.code_short,
  s.name,
  rr.generated_at,
  vr.basis_date,
  vr.price_date,
  vr.asset_type,
  vr.current_value,
  vr.comparable_current_value,
  vr.current_zone_key,
  vr.current_zone_label,
  vr.stance_label,
  MAX(CASE WHEN vz.zone_key = 'undervalued_observe' THEN vz.min_value END) AS undervalued_min,
  MAX(CASE WHEN vz.zone_key = 'undervalued_observe' THEN vz.max_value END) AS undervalued_max,
  MAX(CASE WHEN vz.zone_key = 'reasonable_allocation' THEN vz.min_value END) AS reasonable_min,
  MAX(CASE WHEN vz.zone_key = 'reasonable_allocation' THEN vz.max_value END) AS reasonable_max,
  MAX(CASE WHEN vz.zone_key = 'expensive' THEN vz.min_value END) AS expensive_min,
  MAX(CASE WHEN vz.zone_key = 'expensive' THEN vz.max_value END) AS expensive_max,
  MAX(CASE WHEN vz.zone_key = 'crowded_risk' THEN vz.min_value END) AS crowded_min,
  MAX(CASE WHEN vz.zone_key = 'crowded_risk' THEN vz.max_value END) AS crowded_max,
  vr.valuation_basis,
  vr.confidence,
  vr.not_portfolio_action,
  a.path AS artifact_path,
  vr.valuation_id
FROM valuation_reports vr
JOIN research_runs rr ON rr.run_id = vr.run_id
JOIN securities s ON s.security_id = vr.security_id
LEFT JOIN valuation_zones vz ON vz.valuation_id = vr.valuation_id
LEFT JOIN artifacts a ON a.run_id = vr.run_id AND a.artifact_type = 'json'
GROUP BY vr.valuation_id;

CREATE VIEW IF NOT EXISTS v_valuation_zone_drift AS
SELECT
  h.*,
  CASE
    WHEN h.reasonable_min IS NOT NULL AND h.reasonable_max IS NOT NULL
    THEN (h.reasonable_min + h.reasonable_max) / 2.0
  END AS reasonable_mid,
  CASE
    WHEN h.reasonable_min IS NOT NULL AND h.reasonable_max IS NOT NULL
         AND (h.reasonable_min + h.reasonable_max) != 0
    THEN (h.current_value / ((h.reasonable_min + h.reasonable_max) / 2.0) - 1.0) * 100.0
  END AS current_vs_reasonable_mid_pct,
  LAG(h.reasonable_min) OVER (PARTITION BY h.ts_code ORDER BY h.generated_at) AS prev_reasonable_min,
  LAG(h.reasonable_max) OVER (PARTITION BY h.ts_code ORDER BY h.generated_at) AS prev_reasonable_max,
  LAG(h.crowded_min) OVER (PARTITION BY h.ts_code ORDER BY h.generated_at) AS prev_crowded_min,
  LAG(h.current_zone_key) OVER (PARTITION BY h.ts_code ORDER BY h.generated_at) AS prev_current_zone_key
FROM v_valuation_history h;

CREATE VIEW IF NOT EXISTS v_market_position_history AS
SELECT
  rr.run_id,
  rr.generated_at,
  rr.basis_trade_date,
  ms.market_state,
  ms.opportunity_score,
  ms.crowding_penalty_score,
  ms.market_position_score,
  ms.equity_range_low_pct,
  ms.equity_range_high_pct,
  ms.bond_cash_range_low_pct,
  ms.bond_cash_range_high_pct,
  ms.offensive_bucket_status,
  ms.one_line_conclusion,
  a.path AS artifact_path
FROM market_score_runs ms
JOIN research_runs rr ON rr.run_id = ms.run_id
LEFT JOIN artifacts a ON a.run_id = rr.run_id AND a.artifact_type = 'json';

CREATE VIEW IF NOT EXISTS v_position_slot_history AS
SELECT
  ps.slot_code,
  s.ts_code,
  s.code_short,
  COALESCE(s.name, pp.name_raw) AS name,
  ps.bucket_key AS slot_bucket_key,
  pp.allocation_bucket AS snapshot_bucket_key,
  pp.category,
  rr.generated_at AS snapshot_at,
  rr.basis_trade_date,
  pp.weight_pct,
  pp.day_change_pct,
  pp.reference_pnl_pct,
  ps.lifecycle_status,
  pf.snapshot_id
FROM portfolio_positions pp
JOIN portfolio_snapshots pf ON pf.snapshot_id = pp.snapshot_id
JOIN research_runs rr ON rr.run_id = pf.run_id
LEFT JOIN position_slots ps ON ps.position_slot_id = pp.position_slot_id
LEFT JOIN securities s ON s.security_id = pp.security_id;

CREATE VIEW IF NOT EXISTS v_action_history AS
SELECT
  rr.generated_at,
  rr.basis_trade_date,
  ap.session,
  ap.action_state,
  ai.priority,
  ai.action_type,
  ai.subject_type,
  ai.subject_code,
  ai.subject_name,
  ai.bucket_key,
  ps.slot_code,
  ai.current_position_text,
  ai.suggested_change_text,
  ai.suggested_change_low_pp,
  ai.suggested_change_high_pp,
  ai.target_position_text,
  ai.recommendation_strength,
  ai.needs_manual_confirmation,
  ap.one_line_conclusion,
  a.path AS artifact_path
FROM action_items ai
JOIN action_plans ap ON ap.action_plan_id = ai.action_plan_id
JOIN research_runs rr ON rr.run_id = ap.run_id
LEFT JOIN position_slots ps ON ps.position_slot_id = ai.position_slot_id
LEFT JOIN artifacts a ON a.run_id = rr.run_id AND a.artifact_type = 'json';
