INSERT INTO users (
    email,
    full_name,
    role,
    timezone_name,
    is_active,
    preferences_json
)
VALUES (
    'system@b3quant.local',
    'B3 Quant Platform System',
    'service',
    'UTC',
    TRUE,
    '{"seeded_by": "002_seed_portfolio_templates.sql"}'::jsonb
)
ON CONFLICT (email) DO NOTHING;

INSERT INTO portfolio_families (
    owner_user_id,
    slug,
    name,
    objective,
    description,
    metadata_json,
    is_active
)
SELECT
    users.id,
    'multi-portfolio-factory',
    'Multi Portfolio Factory',
    'growth',
    'Família sistêmica para templates estratégicos padrão.',
    '{"seed": true}'::jsonb,
    TRUE
FROM users
WHERE users.email = 'system@b3quant.local'
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
    owner.id,
    payload.slug,
    payload.name,
    payload.objective,
    payload.benchmark_ticker,
    payload.risk_budget_bps,
    payload.rebalance_rule_json,
    payload.constraints_json,
    payload.model_config_json,
    payload.tags_json,
    TRUE
FROM (
    VALUES
        (
            'dividend-income',
            'Dividend Income Brazil',
            'income',
            'IDIV',
            450,
            '{"cadence": "monthly", "trigger": "yield-spread"}'::jsonb,
            '{"max_single_name": 0.12, "min_dividend_yield": 0.05}'::jsonb,
            '{"label": "yield_stability", "horizon_days": 5}'::jsonb,
            '["income", "equities"]'::jsonb
        ),
        (
            'factor-momentum',
            'Factor Momentum Brazil',
            'factor',
            'IBOV',
            650,
            '{"cadence": "weekly", "trigger": "relative-strength"}'::jsonb,
            '{"max_turnover": 0.18, "min_liquidity_brl": 10000000}'::jsonb,
            '{"label": "momentum_alpha", "horizon_days": 5}'::jsonb,
            '["factor", "momentum"]'::jsonb
        ),
        (
            'low-vol-defensive',
            'Low Vol Defensive Brazil',
            'defensive',
            'IBOV',
            300,
            '{"cadence": "monthly", "trigger": "volatility-regime"}'::jsonb,
            '{"max_beta": 0.85, "sector_cap": 0.28}'::jsonb,
            '{"label": "drawdown_control", "horizon_days": 5}'::jsonb,
            '["defensive", "risk-control"]'::jsonb
        ),
        (
            'macro-hedge',
            'Macro Hedge Overlay',
            'hedge',
            'DOL1!',
            250,
            '{"cadence": "event-driven", "trigger": "macro-shock"}'::jsonb,
            '{"max_net_exposure": 0.35, "max_gross_exposure": 1.2}'::jsonb,
            '{"label": "macro_overlay", "horizon_days": 1}'::jsonb,
            '["hedge", "macro"]'::jsonb
        )
) AS payload (
    slug,
    name,
    objective,
    benchmark_ticker,
    risk_budget_bps,
    rebalance_rule_json,
    constraints_json,
    model_config_json,
    tags_json
)
JOIN users AS owner ON owner.email = 'system@b3quant.local'
JOIN portfolio_families AS family
  ON family.owner_user_id = owner.id
 AND family.slug = 'multi-portfolio-factory'
ON CONFLICT (slug) DO NOTHING;

INSERT INTO portfolio_constraints (
    strategy_id,
    constraint_key,
    constraint_type,
    hard_constraint,
    rule_json,
    active_from
)
SELECT
    strategy.id,
    seed.constraint_key,
    seed.constraint_type,
    seed.hard_constraint,
    seed.rule_json,
    CURRENT_DATE
FROM (
    VALUES
        ('dividend-income', 'max_single_name', 'hard_limit', TRUE, '{"value": 0.12}'::jsonb),
        ('dividend-income', 'min_dividend_yield', 'hard_limit', TRUE, '{"value": 0.05}'::jsonb),
        ('factor-momentum', 'max_turnover', 'hard_limit', TRUE, '{"value": 0.18}'::jsonb),
        ('factor-momentum', 'min_liquidity_brl', 'liquidity', TRUE, '{"value": 10000000}'::jsonb),
        ('low-vol-defensive', 'max_beta', 'exposure', TRUE, '{"value": 0.85}'::jsonb),
        ('low-vol-defensive', 'sector_cap', 'hard_limit', TRUE, '{"value": 0.28}'::jsonb),
        ('macro-hedge', 'max_net_exposure', 'exposure', TRUE, '{"value": 0.35}'::jsonb),
        ('macro-hedge', 'max_gross_exposure', 'exposure', TRUE, '{"value": 1.2}'::jsonb)
) AS seed (strategy_slug, constraint_key, constraint_type, hard_constraint, rule_json)
JOIN portfolio_strategies AS strategy
  ON strategy.slug = seed.strategy_slug
ON CONFLICT (strategy_id, constraint_key, active_from) DO NOTHING;

INSERT INTO events_catalog (
    code,
    name,
    event_type,
    event_date,
    market_scope,
    severity,
    metadata_json,
    is_active
)
VALUES (
    'generic-macro-shock',
    'Generic Macro Shock',
    'macro',
    CURRENT_DATE,
    'b3',
    4,
    '{"seed": true, "note": "evento sistêmico base"}'::jsonb,
    TRUE
)
ON CONFLICT (code) DO NOTHING;

INSERT INTO event_scenarios (
    event_id,
    slug,
    name,
    description,
    scenario_type,
    shock_vector_json,
    assumptions_json,
    active
)
SELECT
    event.id,
    'baseline-stress',
    'Baseline Stress',
    'Cenário base para stress macro e contrafactual.',
    'stress',
    '{"default_price_shock_pct": -0.08}'::jsonb,
    '{"selic_shift_bps": 100}'::jsonb,
    TRUE
FROM events_catalog AS event
WHERE event.code = 'generic-macro-shock'
ON CONFLICT (slug) DO NOTHING;

INSERT INTO system_jobs (
    job_name,
    service_name,
    schedule_cron,
    idempotency_scope,
    active,
    config_json
)
VALUES
    ('ingestion-close', 'worker-ingestion', '10 18 * * 1-5', 'reference_date', TRUE, '{"stage": "raw"}'::jsonb),
    ('feature-store-refresh', 'worker-feature-store', '20 18 * * 1-5', 'reference_date', TRUE, '{"stage": "silver"}'::jsonb),
    ('forecast-run', 'worker-forecast', '30 18 * * 1-5', 'reference_date', TRUE, '{"stage": "forecasting"}'::jsonb),
    ('scenario-replay', 'worker-simulation', '40 18 * * 1-5', 'reference_date', TRUE, '{"stage": "simulation"}'::jsonb),
    ('eod-reconciliation', 'worker-eod', '50 18 * * 1-5', 'reference_date', TRUE, '{"stage": "curated"}'::jsonb)
ON CONFLICT (job_name) DO NOTHING;
