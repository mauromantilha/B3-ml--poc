-- Example inserts for the Supabase OLTP module.

INSERT INTO users (email, full_name, role, timezone_name, is_active, preferences_json)
VALUES (
  'ana.silva@example.com',
  'Ana Silva',
  'analyst',
  'UTC',
  TRUE,
  '{"desk": "research"}'::jsonb
)
ON CONFLICT (email) DO NOTHING;

INSERT INTO portfolio_families (owner_user_id, slug, name, objective, description, metadata_json, is_active)
SELECT id, 'alpha-core', 'Alpha Core', 'growth', 'Família principal de carteiras quantitativas.', '{"region": "BR"}'::jsonb, TRUE
FROM users
WHERE email = 'ana.silva@example.com'
ON CONFLICT (owner_user_id, slug) DO NOTHING;

INSERT INTO portfolio_strategies (
  family_id,
  created_by_user_id,
  slug,
  name,
  objective,
  benchmark_ticker,
  risk_budget_bps,
  rebalance_rule_json,
  constraints_json,
  model_config_json,
  tags_json,
  is_active
)
SELECT
  family.id,
  analyst.id,
  'quality-carry',
  'Quality Carry Brazil',
  'growth',
  'IBOV',
  500,
  '{"cadence": "weekly"}'::jsonb,
  '{"max_single_name": 0.10, "min_liquidity_brl": 20000000}'::jsonb,
  '{"label": "expected_close"}'::jsonb,
  '["quality", "carry"]'::jsonb,
  TRUE
FROM portfolio_families AS family
JOIN users AS analyst ON analyst.email = 'ana.silva@example.com'
WHERE family.slug = 'alpha-core'
ON CONFLICT (slug) DO NOTHING;

INSERT INTO portfolio_constraints (strategy_id, constraint_key, constraint_type, hard_constraint, rule_json, active_from)
SELECT id, 'max_single_name', 'hard_limit', TRUE, '{"value": 0.10}'::jsonb, CURRENT_DATE
FROM portfolio_strategies
WHERE slug = 'quality-carry'
ON CONFLICT (strategy_id, constraint_key, active_from) DO NOTHING;

INSERT INTO portfolio_instances (
  strategy_id,
  portfolio_family_id,
  owner_user_id,
  name,
  reference_date,
  base_currency,
  seed_capital,
  status,
  mandate_json,
  notes_json
)
SELECT
  strategy.id,
  family.id,
  analyst.id,
  'Quality Carry Sleeve',
  DATE '2026-04-28',
  'BRL',
  1000000,
  'active',
  '{"desk": "equities"}'::jsonb,
  '{}'::jsonb
FROM portfolio_strategies AS strategy
JOIN portfolio_families AS family ON family.id = strategy.family_id
JOIN users AS analyst ON analyst.email = 'ana.silva@example.com'
WHERE strategy.slug = 'quality-carry'
ON CONFLICT (strategy_id, name, reference_date) DO NOTHING;

INSERT INTO portfolio_positions (
  portfolio_instance_id,
  reference_date,
  ticker,
  market,
  target_weight,
  quantity,
  close_price,
  signal_json,
  allocation_metadata_json
)
SELECT
  instance.id,
  DATE '2026-04-28',
  'VALE3',
  'equities',
  0.35,
  1000,
  60.50,
  '{"alpha": 0.11}'::jsonb,
  '{"bucket": "miners"}'::jsonb
FROM portfolio_instances AS instance
WHERE instance.name = 'Quality Carry Sleeve'
ON CONFLICT (portfolio_instance_id, reference_date, ticker) DO NOTHING;

INSERT INTO portfolio_valuations_daily (
  portfolio_instance_id,
  reference_date,
  nav,
  gross_exposure,
  net_exposure,
  cash_balance,
  pnl_daily,
  drawdown_pct,
  valuation_json
)
SELECT
  instance.id,
  DATE '2026-04-28',
  1005400,
  1.00,
  1.00,
  12000,
  5400,
  0.012,
  '{"turnover": 0.08}'::jsonb
FROM portfolio_instances AS instance
WHERE instance.name = 'Quality Carry Sleeve'
ON CONFLICT (portfolio_instance_id, reference_date) DO NOTHING;

INSERT INTO events_catalog (
  code,
  name,
  description,
  event_type,
  event_date,
  scope,
  scope_reference,
  market_scope,
  severity,
  expected_duration_days,
  confidence,
  macro_factors_json,
  metadata_json,
  is_active
)
VALUES (
  'copom-hawkish',
  'Copom Hawkish',
  'Choque de juros e compressão de múltiplos domésticos.',
  'choque_juros',
  DATE '2026-04-28',
  'brasil',
  'BR',
  'b3',
  4,
  30,
  0.88,
  '[{"factor":"juros","shock_bps":100}]'::jsonb,
  '{"source": "manual"}'::jsonb,
  TRUE
)
ON CONFLICT (code) DO NOTHING;

INSERT INTO event_asset_mapping (event_id, asset_identifier, asset_name, asset_type, mapping_scope, weight, is_primary, metadata_json)
SELECT event.id, 'IBOV', 'Ibovespa', 'index', 'indice', 1.0, TRUE, '{"role":"broad-market"}'::jsonb
FROM events_catalog AS event
WHERE event.code = 'copom-hawkish'
ON CONFLICT (event_id, asset_identifier, asset_type) DO NOTHING;

INSERT INTO event_impact_profiles (
  event_id,
  profile_name,
  shock_template_json,
  macro_factors_json,
  expected_duration_days,
  confidence,
  transmission_lag_days,
  metadata_json
)
SELECT
  event.id,
  'base-rates',
  '{"default_price_shock_pct": -0.05}'::jsonb,
  '[{"factor":"juros","shock_bps":100}]'::jsonb,
  30,
  0.88,
  0,
  '{"seed":true}'::jsonb
FROM events_catalog AS event
WHERE event.code = 'copom-hawkish'
ON CONFLICT (event_id, profile_name) DO NOTHING;

INSERT INTO event_scenarios (
  event_id,
  impact_profile_id,
  slug,
  name,
  description,
  scenario_type,
  scope,
  severity,
  expected_duration_days,
  confidence,
  affected_assets_json,
  macro_factors_json,
  shock_vector_json,
  assumptions_json,
  active
)
SELECT
  event.id,
  profile.id,
  'copom-hawkish-stress',
  'Copom Hawkish Stress',
  'Abertura de curva e compressão de múltiplos.',
  'stress',
  event.scope,
  event.severity,
  profile.expected_duration_days,
  profile.confidence,
  '[{"asset_identifier":"IBOV","asset_type":"index"}]'::jsonb,
  profile.macro_factors_json,
  '{"default_price_shock_pct": -0.05}'::jsonb,
  '{"ibov_beta_shock": -0.7}'::jsonb,
  TRUE
FROM events_catalog AS event
JOIN event_impact_profiles AS profile ON profile.event_id = event.id AND profile.profile_name = 'base-rates'
WHERE event.code = 'copom-hawkish'
ON CONFLICT (slug) DO NOTHING;

INSERT INTO simulation_runs (event_scenario_id, portfolio_instance_id, reference_date, run_status, input_hash, engine_version, result_summary_json)
SELECT
  scenario.id,
  instance.id,
  DATE '2026-04-28',
  'succeeded',
  'example-hash',
  'v1',
  '{"projected_nav": 972000}'::jsonb
FROM event_scenarios AS scenario
CROSS JOIN portfolio_instances AS instance
WHERE scenario.slug = 'copom-hawkish-stress'
  AND instance.name = 'Quality Carry Sleeve'
ON CONFLICT (event_scenario_id, portfolio_instance_id, reference_date) DO NOTHING;

INSERT INTO counterfactual_runs (
  event_id,
  event_scenario_id,
  portfolio_instance_id,
  reference_date,
  run_status,
  input_hash,
  engine_version,
  baseline_nav,
  counterfactual_nav,
  delta_pnl,
  shock_vector_json,
  assumptions_json,
  result_summary_json
)
SELECT
  event.id,
  scenario.id,
  instance.id,
  DATE '2026-04-28',
  'succeeded',
  'counterfactual-example-hash',
  'v1',
  1000000,
  972000,
  -28000,
  '{"default_price_shock_pct": -0.05}'::jsonb,
  '{"curve_steepening": true}'::jsonb,
  '{"projected_nav": 972000}'::jsonb
FROM events_catalog AS event
JOIN event_scenarios AS scenario ON scenario.event_id = event.id
CROSS JOIN portfolio_instances AS instance
WHERE event.code = 'copom-hawkish'
  AND scenario.slug = 'copom-hawkish-stress'
  AND instance.name = 'Quality Carry Sleeve'
ON CONFLICT (event_scenario_id, portfolio_instance_id, reference_date) DO NOTHING;

INSERT INTO model_registry (portfolio_strategy_id, model_name, version, framework, objective, artifact_uri, metrics_json, tags_json, active)
SELECT
  strategy.id,
  'close-price-baseline',
  '2026.04.28',
  'tensorflow',
  'predict_expected_close',
  'r2://b3-poc/artifacts/model.keras',
  '{"mae": 0.82}'::jsonb,
  '["baseline"]'::jsonb,
  TRUE
FROM portfolio_strategies AS strategy
WHERE strategy.slug = 'quality-carry'
ON CONFLICT (model_name, version) DO NOTHING;

INSERT INTO training_runs (model_id, portfolio_strategy_id, reference_date, dataset_fingerprint, feature_set_version, run_status, parameters_json, metrics_json, artifact_uri)
SELECT
  model.id,
  model.portfolio_strategy_id,
  DATE '2026-04-28',
  'dataset-fingerprint-example',
  'v1',
  'succeeded',
  '{"epochs": 10}'::jsonb,
  '{"loss": 0.21, "mae": 0.82}'::jsonb,
  model.artifact_uri
FROM model_registry AS model
WHERE model.model_name = 'close-price-baseline'
  AND model.version = '2026.04.28'
ON CONFLICT (model_id, reference_date, dataset_fingerprint) DO NOTHING;

INSERT INTO prediction_runs (model_id, training_run_id, portfolio_instance_id, reference_date, horizon_days, status, metrics_json, predictions_json)
SELECT
  model.id,
  train.id,
  instance.id,
  DATE '2026-04-28',
  1,
  'succeeded',
  '{"mae": 0.82}'::jsonb,
  '{"VALE3": 61.20}'::jsonb
FROM model_registry AS model
JOIN training_runs AS train ON train.model_id = model.id
JOIN portfolio_instances AS instance ON instance.name = 'Quality Carry Sleeve'
WHERE model.model_name = 'close-price-baseline'
  AND model.version = '2026.04.28'
ON CONFLICT (model_id, portfolio_instance_id, reference_date, horizon_days) DO NOTHING;

INSERT INTO eod_comparisons (portfolio_instance_id, prediction_run_id, reference_date, ticker, scenario_slug, expected_close, actual_close, tracking_error_bps, verdict, comparison_details_json)
SELECT
  instance.id,
  prediction.id,
  DATE '2026-04-28',
  'VALE3',
  'baseline',
  61.20,
  60.50,
  -114.38,
  'underperformed',
  '{"abs_delta": 0.70}'::jsonb
FROM portfolio_instances AS instance
JOIN prediction_runs AS prediction ON prediction.portfolio_instance_id = instance.id
WHERE instance.name = 'Quality Carry Sleeve'
ON CONFLICT (portfolio_instance_id, reference_date, ticker, scenario_slug) DO NOTHING;

INSERT INTO system_jobs (job_name, service_name, schedule_cron, idempotency_scope, active, config_json)
VALUES ('eod-reconciliation', 'worker-eod', '50 18 * * 1-5', 'reference_date', TRUE, '{"stage": "curated"}'::jsonb)
ON CONFLICT (job_name) DO NOTHING;

INSERT INTO job_executions (system_job_id, job_name, reference_date, idempotency_key, status, payload_json, result_uri, qstash_message_id, attempt_number, error_json)
SELECT
  job.id,
  job.job_name,
  DATE '2026-04-28',
  'eod-2026-04-28-quality-carry',
  'succeeded',
  '{"portfolio": "Quality Carry Sleeve"}'::jsonb,
  'gs://b3quant-dev-gcs-curated/eod/2026-04-28.parquet',
  'msg-example-001',
  1,
  '{}'::jsonb
FROM system_jobs AS job
WHERE job.job_name = 'eod-reconciliation'
ON CONFLICT (idempotency_key) DO NOTHING;

INSERT INTO audit_logs (actor_user_id, entity_type, entity_id, action, request_id, trace_id, before_json, after_json, metadata_json)
SELECT
  analyst.id,
  'portfolio_instance',
  instance.id,
  'created',
  'req-001',
  'trace-001',
  '{}'::jsonb,
  '{"status": "active"}'::jsonb,
  '{"channel": "manual-example"}'::jsonb
FROM users AS analyst
JOIN portfolio_instances AS instance ON instance.name = 'Quality Carry Sleeve'
WHERE analyst.email = 'ana.silva@example.com';
