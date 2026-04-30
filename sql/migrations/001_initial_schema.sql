BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_auth_id VARCHAR(128) UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(160),
    role VARCHAR(24) NOT NULL DEFAULT 'analyst' CHECK (role IN ('admin', 'analyst', 'viewer', 'service')),
    timezone_name VARCHAR(50) NOT NULL DEFAULT 'UTC',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    preferences_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio_families (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES users(id),
    slug VARCHAR(80) NOT NULL,
    name VARCHAR(120) NOT NULL,
    objective VARCHAR(32) NOT NULL CHECK (objective IN ('income', 'growth', 'defensive', 'hedge', 'factor')),
    description TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portfolio_family_owner_slug UNIQUE (owner_user_id, slug)
);

CREATE TABLE IF NOT EXISTS portfolio_strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES portfolio_families(id),
    created_by_user_id UUID REFERENCES users(id),
    slug VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    objective VARCHAR(32) NOT NULL CHECK (objective IN ('income', 'growth', 'defensive', 'hedge', 'factor')),
    benchmark_ticker VARCHAR(24) NOT NULL,
    risk_budget_bps INTEGER NOT NULL CHECK (risk_budget_bps >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    rebalance_rule_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    constraints_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    archived_at DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolio_constraints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES portfolio_strategies(id) ON DELETE CASCADE,
    constraint_key VARCHAR(80) NOT NULL,
    constraint_type VARCHAR(24) NOT NULL DEFAULT 'custom' CHECK (constraint_type IN ('hard_limit', 'soft_limit', 'liquidity', 'exposure', 'custom')),
    hard_constraint BOOLEAN NOT NULL DEFAULT TRUE,
    rule_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    active_from DATE NOT NULL DEFAULT CURRENT_DATE,
    active_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portfolio_constraints_strategy_key_from UNIQUE (strategy_id, constraint_key, active_from),
    CONSTRAINT ck_portfolio_constraints_range CHECK (active_to IS NULL OR active_to >= active_from)
);

CREATE TABLE IF NOT EXISTS portfolio_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES portfolio_strategies(id),
    portfolio_family_id UUID REFERENCES portfolio_families(id),
    owner_user_id UUID REFERENCES users(id),
    name VARCHAR(120) NOT NULL,
    reference_date DATE NOT NULL,
    base_currency VARCHAR(8) NOT NULL DEFAULT 'BRL',
    seed_capital NUMERIC(18, 2) NOT NULL CHECK (seed_capital >= 0),
    status VARCHAR(32) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    mandate_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portfolio_instance UNIQUE (strategy_id, name, reference_date)
);

CREATE TABLE IF NOT EXISTS portfolio_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID NOT NULL REFERENCES portfolio_instances(id) ON DELETE CASCADE,
    reference_date DATE NOT NULL,
    ticker VARCHAR(24) NOT NULL,
    market VARCHAR(24) NOT NULL,
    target_weight NUMERIC(12, 6) NOT NULL CHECK (target_weight >= -5 AND target_weight <= 5),
    quantity NUMERIC(18, 6) NOT NULL,
    close_price NUMERIC(18, 6) NOT NULL CHECK (close_price >= 0),
    signal_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    allocation_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_snapshot_key VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portfolio_position UNIQUE (portfolio_instance_id, reference_date, ticker)
);

CREATE TABLE IF NOT EXISTS portfolio_valuations_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID NOT NULL REFERENCES portfolio_instances(id) ON DELETE CASCADE,
    reference_date DATE NOT NULL,
    nav NUMERIC(18, 6) NOT NULL,
    gross_exposure NUMERIC(18, 6) NOT NULL DEFAULT 0,
    net_exposure NUMERIC(18, 6) NOT NULL DEFAULT 0,
    cash_balance NUMERIC(18, 6) NOT NULL DEFAULT 0,
    pnl_daily NUMERIC(18, 6) NOT NULL DEFAULT 0,
    drawdown_pct NUMERIC(12, 6) NOT NULL DEFAULT 0,
    valuation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_portfolio_valuations_daily UNIQUE (portfolio_instance_id, reference_date)
);

CREATE TABLE IF NOT EXISTS market_eod_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_date DATE NOT NULL,
    market VARCHAR(24) NOT NULL,
    ticker VARCHAR(24) NOT NULL,
    open_price NUMERIC(18, 6) NOT NULL CHECK (open_price >= 0),
    high_price NUMERIC(18, 6) NOT NULL CHECK (high_price >= 0),
    low_price NUMERIC(18, 6) NOT NULL CHECK (low_price >= 0),
    close_price NUMERIC(18, 6) NOT NULL CHECK (close_price >= 0),
    adjusted_close NUMERIC(18, 6) NOT NULL CHECK (adjusted_close >= 0),
    volume BIGINT NOT NULL CHECK (volume >= 0),
    source_version VARCHAR(48) NOT NULL,
    ingest_hash VARCHAR(64) NOT NULL,
    raw_partition_uri TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_market_snapshot UNIQUE (reference_date, market, ticker)
);

CREATE TABLE IF NOT EXISTS events_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(160) NOT NULL,
    event_type VARCHAR(24) NOT NULL CHECK (event_type IN ('macro', 'market', 'corporate', 'policy')),
    event_date DATE NOT NULL,
    market_scope VARCHAR(48) NOT NULL DEFAULT 'b3',
    severity INTEGER NOT NULL DEFAULT 3 CHECK (severity BETWEEN 1 AND 5),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_scenarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events_catalog(id) ON DELETE SET NULL,
    slug VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(500) NOT NULL,
    scenario_type VARCHAR(32) NOT NULL CHECK (scenario_type IN ('exogenous', 'counterfactual', 'stress', 'regime')),
    shock_vector_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    assumptions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_scenario_id UUID NOT NULL REFERENCES event_scenarios(id),
    portfolio_instance_id UUID NOT NULL REFERENCES portfolio_instances(id),
    reference_date DATE NOT NULL,
    run_status VARCHAR(32) NOT NULL CHECK (run_status IN ('pending', 'running', 'succeeded', 'failed')),
    input_hash VARCHAR(64) NOT NULL DEFAULT '',
    engine_version VARCHAR(48) NOT NULL DEFAULT 'v1',
    result_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_simulation_run UNIQUE (event_scenario_id, portfolio_instance_id, reference_date)
);

CREATE TABLE IF NOT EXISTS model_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_strategy_id UUID REFERENCES portfolio_strategies(id),
    created_by_user_id UUID REFERENCES users(id),
    model_name VARCHAR(120) NOT NULL,
    version VARCHAR(32) NOT NULL,
    framework VARCHAR(32) NOT NULL DEFAULT 'tensorflow',
    objective VARCHAR(64) NOT NULL,
    artifact_uri VARCHAR(255) NOT NULL,
    metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_model_registry_name_version UNIQUE (model_name, version)
);

CREATE TABLE IF NOT EXISTS training_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES model_registry(id),
    portfolio_strategy_id UUID REFERENCES portfolio_strategies(id),
    reference_date DATE NOT NULL,
    dataset_fingerprint VARCHAR(64) NOT NULL,
    feature_set_version VARCHAR(32) NOT NULL DEFAULT 'v1',
    run_status VARCHAR(32) NOT NULL CHECK (run_status IN ('pending', 'running', 'succeeded', 'failed')),
    parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_uri VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_training_runs_dataset_fingerprint UNIQUE (model_id, reference_date, dataset_fingerprint)
);

CREATE TABLE IF NOT EXISTS prediction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES model_registry(id),
    training_run_id UUID REFERENCES training_runs(id),
    portfolio_instance_id UUID NOT NULL REFERENCES portfolio_instances(id),
    reference_date DATE NOT NULL,
    horizon_days INTEGER NOT NULL CHECK (horizon_days > 0),
    status VARCHAR(32) NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    predictions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_model_run UNIQUE (model_id, portfolio_instance_id, reference_date, horizon_days)
);

CREATE TABLE IF NOT EXISTS eod_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID NOT NULL REFERENCES portfolio_instances(id),
    prediction_run_id UUID REFERENCES prediction_runs(id),
    reference_date DATE NOT NULL,
    ticker VARCHAR(24) NOT NULL,
    scenario_slug VARCHAR(80) NOT NULL DEFAULT 'baseline',
    expected_close NUMERIC(18, 6) NOT NULL CHECK (expected_close >= 0),
    actual_close NUMERIC(18, 6) NOT NULL CHECK (actual_close >= 0),
    tracking_error_bps NUMERIC(18, 6) NOT NULL,
    verdict VARCHAR(32) NOT NULL CHECK (verdict IN ('outperformed', 'underperformed', 'inline')),
    comparison_details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_eod_comparison UNIQUE (portfolio_instance_id, reference_date, ticker, scenario_slug)
);

CREATE TABLE IF NOT EXISTS system_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name VARCHAR(120) NOT NULL UNIQUE,
    service_name VARCHAR(64) NOT NULL CHECK (service_name IN ('api', 'worker-ingestion', 'worker-feature-store', 'worker-forecast', 'worker-simulation', 'worker-eod', 'dashboard-streamlit')),
    schedule_cron VARCHAR(64),
    idempotency_scope VARCHAR(32) NOT NULL DEFAULT 'reference_date',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_job_id UUID REFERENCES system_jobs(id),
    job_name VARCHAR(120) NOT NULL,
    reference_date DATE NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(32) NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_uri VARCHAR(255),
    qstash_message_id VARCHAR(96),
    attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number >= 1),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id UUID,
    action VARCHAR(80) NOT NULL,
    request_id VARCHAR(96),
    trace_id VARCHAR(96),
    before_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    after_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_role_active ON users (role, is_active);
CREATE INDEX IF NOT EXISTS ix_portfolio_families_owner_active ON portfolio_families (owner_user_id, is_active);
CREATE INDEX IF NOT EXISTS ix_portfolio_strategies_family_active ON portfolio_strategies (family_id, is_active);
CREATE INDEX IF NOT EXISTS ix_portfolio_constraints_strategy_active ON portfolio_constraints (strategy_id, active_from, active_to);
CREATE INDEX IF NOT EXISTS ix_portfolio_instances_family_date ON portfolio_instances (portfolio_family_id, reference_date);
CREATE INDEX IF NOT EXISTS ix_portfolio_instances_status_date ON portfolio_instances (status, reference_date);
CREATE INDEX IF NOT EXISTS ix_portfolio_positions_portfolio_date ON portfolio_positions (portfolio_instance_id, reference_date);
CREATE INDEX IF NOT EXISTS ix_portfolio_positions_market_ticker_date ON portfolio_positions (market, ticker, reference_date);
CREATE INDEX IF NOT EXISTS ix_portfolio_valuations_reference_date ON portfolio_valuations_daily (reference_date, portfolio_instance_id);
CREATE INDEX IF NOT EXISTS ix_market_eod_snapshots_date_ticker ON market_eod_snapshots (reference_date, ticker);
CREATE INDEX IF NOT EXISTS ix_market_eod_snapshots_market_date ON market_eod_snapshots (market, reference_date);
CREATE INDEX IF NOT EXISTS ix_events_catalog_date_type ON events_catalog (event_date, event_type);
CREATE INDEX IF NOT EXISTS ix_event_scenarios_event_active ON event_scenarios (event_id, active);
CREATE INDEX IF NOT EXISTS ix_simulation_runs_reference_date ON simulation_runs (reference_date, run_status);
CREATE INDEX IF NOT EXISTS ix_model_registry_active ON model_registry (active, framework);
CREATE INDEX IF NOT EXISTS ix_training_runs_reference_date ON training_runs (reference_date, run_status);
CREATE INDEX IF NOT EXISTS ix_prediction_runs_portfolio_reference ON prediction_runs (portfolio_instance_id, reference_date);
CREATE INDEX IF NOT EXISTS ix_eod_comparisons_date_portfolio ON eod_comparisons (reference_date, portfolio_instance_id);
CREATE INDEX IF NOT EXISTS ix_system_jobs_target_active ON system_jobs (service_name, active);
CREATE INDEX IF NOT EXISTS ix_job_executions_job_date ON job_executions (job_name, reference_date);
CREATE INDEX IF NOT EXISTS ix_job_executions_system_job_status ON job_executions (system_job_id, status);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_request ON audit_logs (request_id, created_at);

DROP TRIGGER IF EXISTS trg_users_set_updated_at ON users;
CREATE TRIGGER trg_users_set_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_portfolio_families_set_updated_at ON portfolio_families;
CREATE TRIGGER trg_portfolio_families_set_updated_at BEFORE UPDATE ON portfolio_families FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_portfolio_strategies_set_updated_at ON portfolio_strategies;
CREATE TRIGGER trg_portfolio_strategies_set_updated_at BEFORE UPDATE ON portfolio_strategies FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_portfolio_constraints_set_updated_at ON portfolio_constraints;
CREATE TRIGGER trg_portfolio_constraints_set_updated_at BEFORE UPDATE ON portfolio_constraints FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_portfolio_instances_set_updated_at ON portfolio_instances;
CREATE TRIGGER trg_portfolio_instances_set_updated_at BEFORE UPDATE ON portfolio_instances FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_portfolio_positions_set_updated_at ON portfolio_positions;
CREATE TRIGGER trg_portfolio_positions_set_updated_at BEFORE UPDATE ON portfolio_positions FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_portfolio_valuations_daily_set_updated_at ON portfolio_valuations_daily;
CREATE TRIGGER trg_portfolio_valuations_daily_set_updated_at BEFORE UPDATE ON portfolio_valuations_daily FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_market_eod_snapshots_set_updated_at ON market_eod_snapshots;
CREATE TRIGGER trg_market_eod_snapshots_set_updated_at BEFORE UPDATE ON market_eod_snapshots FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_events_catalog_set_updated_at ON events_catalog;
CREATE TRIGGER trg_events_catalog_set_updated_at BEFORE UPDATE ON events_catalog FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_event_scenarios_set_updated_at ON event_scenarios;
CREATE TRIGGER trg_event_scenarios_set_updated_at BEFORE UPDATE ON event_scenarios FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_simulation_runs_set_updated_at ON simulation_runs;
CREATE TRIGGER trg_simulation_runs_set_updated_at BEFORE UPDATE ON simulation_runs FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_model_registry_set_updated_at ON model_registry;
CREATE TRIGGER trg_model_registry_set_updated_at BEFORE UPDATE ON model_registry FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_training_runs_set_updated_at ON training_runs;
CREATE TRIGGER trg_training_runs_set_updated_at BEFORE UPDATE ON training_runs FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_prediction_runs_set_updated_at ON prediction_runs;
CREATE TRIGGER trg_prediction_runs_set_updated_at BEFORE UPDATE ON prediction_runs FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_eod_comparisons_set_updated_at ON eod_comparisons;
CREATE TRIGGER trg_eod_comparisons_set_updated_at BEFORE UPDATE ON eod_comparisons FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_system_jobs_set_updated_at ON system_jobs;
CREATE TRIGGER trg_system_jobs_set_updated_at BEFORE UPDATE ON system_jobs FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_job_executions_set_updated_at ON job_executions;
CREATE TRIGGER trg_job_executions_set_updated_at BEFORE UPDATE ON job_executions FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_audit_logs_set_updated_at ON audit_logs;
CREATE TRIGGER trg_audit_logs_set_updated_at BEFORE UPDATE ON audit_logs FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
