BEGIN;

CREATE TABLE IF NOT EXISTS capm_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID REFERENCES portfolio_instances(id) ON DELETE SET NULL,
    model_name VARCHAR(48) NOT NULL DEFAULT 'capm' CHECK (model_name = 'capm'),
    window VARCHAR(24) NOT NULL CHECK (window IN ('short_term', 'medium_term', 'long_term')),
    asset_identifier VARCHAR(64) NOT NULL,
    market_identifier VARCHAR(64) NOT NULL,
    reference_date DATE NOT NULL,
    risk_free_rate NUMERIC(18, 6) NOT NULL,
    alpha NUMERIC(18, 6) NOT NULL,
    beta NUMERIC(18, 6) NOT NULL,
    expected_return NUMERIC(18, 6) NOT NULL,
    actual_return NUMERIC(18, 6) NOT NULL,
    r_squared NUMERIC(18, 6) NOT NULL,
    residual_volatility NUMERIC(18, 6) NOT NULL,
    inputs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_capm_metrics_scope UNIQUE (portfolio_instance_id, asset_identifier, market_identifier, reference_date, window)
);

CREATE TABLE IF NOT EXISTS apt_factor_loadings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID REFERENCES portfolio_instances(id) ON DELETE SET NULL,
    model_name VARCHAR(48) NOT NULL DEFAULT 'apt_multifactor' CHECK (model_name = 'apt_multifactor'),
    window VARCHAR(24) NOT NULL CHECK (window IN ('short_term', 'medium_term', 'long_term')),
    asset_identifier VARCHAR(64) NOT NULL,
    factor_name VARCHAR(64) NOT NULL,
    reference_date DATE NOT NULL,
    factor_loading NUMERIC(18, 6) NOT NULL,
    factor_premium NUMERIC(18, 6) NOT NULL,
    intercept_alpha NUMERIC(18, 6) NOT NULL,
    implied_return NUMERIC(18, 6) NOT NULL,
    t_stat NUMERIC(18, 6),
    p_value NUMERIC(18, 6),
    residual_volatility NUMERIC(18, 6) NOT NULL,
    inputs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_apt_factor_loadings_scope UNIQUE (portfolio_instance_id, asset_identifier, factor_name, reference_date, window)
);

CREATE TABLE IF NOT EXISTS arima_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID REFERENCES portfolio_instances(id) ON DELETE SET NULL,
    model_name VARCHAR(48) NOT NULL CHECK (model_name IN ('arima', 'sarima')),
    window VARCHAR(24) NOT NULL CHECK (window IN ('short_term', 'medium_term', 'long_term')),
    series_name VARCHAR(64) NOT NULL,
    reference_date DATE NOT NULL,
    forecast_step INTEGER NOT NULL CHECK (forecast_step >= 1),
    predicted_value NUMERIC(18, 6) NOT NULL,
    lower_ci NUMERIC(18, 6) NOT NULL,
    upper_ci NUMERIC(18, 6) NOT NULL,
    order_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_arima_forecasts_scope UNIQUE (portfolio_instance_id, series_name, reference_date, window, forecast_step, model_name)
);

CREATE TABLE IF NOT EXISTS garch_volatility (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID REFERENCES portfolio_instances(id) ON DELETE SET NULL,
    model_name VARCHAR(48) NOT NULL CHECK (model_name IN ('garch', 'egarch')),
    window VARCHAR(24) NOT NULL CHECK (window IN ('short_term', 'medium_term', 'long_term')),
    series_name VARCHAR(64) NOT NULL,
    reference_date DATE NOT NULL,
    forecast_step INTEGER NOT NULL CHECK (forecast_step >= 1),
    conditional_volatility NUMERIC(18, 6) NOT NULL,
    variance NUMERIC(18, 6) NOT NULL,
    persistence NUMERIC(18, 6) NOT NULL,
    leverage_term NUMERIC(18, 6) NOT NULL,
    diagnostics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_garch_volatility_scope UNIQUE (portfolio_instance_id, series_name, reference_date, window, forecast_step, model_name)
);

CREATE TABLE IF NOT EXISTS valuation_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID REFERENCES portfolio_instances(id) ON DELETE SET NULL,
    model_name VARCHAR(48) NOT NULL DEFAULT 'valuation_multiples' CHECK (model_name = 'valuation_multiples'),
    window VARCHAR(24) NOT NULL CHECK (window IN ('short_term', 'medium_term', 'long_term')),
    asset_identifier VARCHAR(64) NOT NULL,
    metric_name VARCHAR(64) NOT NULL,
    reference_date DATE NOT NULL,
    applied_multiple NUMERIC(18, 6) NOT NULL,
    denominator_key VARCHAR(64) NOT NULL,
    denominator_value NUMERIC(18, 6) NOT NULL,
    implied_enterprise_value NUMERIC(18, 6) NOT NULL,
    implied_equity_value NUMERIC(18, 6) NOT NULL,
    intrinsic_value_per_share NUMERIC(18, 6) NOT NULL,
    peer_count INTEGER NOT NULL CHECK (peer_count >= 0),
    inputs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_valuation_metrics_scope UNIQUE (portfolio_instance_id, asset_identifier, metric_name, reference_date, window)
);

CREATE TABLE IF NOT EXISTS intrinsic_value_estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID REFERENCES portfolio_instances(id) ON DELETE SET NULL,
    model_name VARCHAR(48) NOT NULL DEFAULT 'discounted_cash_flow' CHECK (model_name = 'discounted_cash_flow'),
    window VARCHAR(24) NOT NULL CHECK (window IN ('short_term', 'medium_term', 'long_term')),
    asset_identifier VARCHAR(64) NOT NULL,
    reference_date DATE NOT NULL,
    enterprise_value NUMERIC(18, 6) NOT NULL,
    equity_value NUMERIC(18, 6) NOT NULL,
    intrinsic_value_per_share NUMERIC(18, 6) NOT NULL,
    terminal_value NUMERIC(18, 6) NOT NULL,
    terminal_present_value NUMERIC(18, 6) NOT NULL,
    discount_rate NUMERIC(18, 6) NOT NULL,
    terminal_growth_rate NUMERIC(18, 6) NOT NULL,
    inputs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_intrinsic_value_estimates_scope UNIQUE (portfolio_instance_id, asset_identifier, reference_date, window)
);

CREATE TABLE IF NOT EXISTS feature_store_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_instance_id UUID REFERENCES portfolio_instances(id) ON DELETE SET NULL,
    entity_key VARCHAR(128) NOT NULL,
    feature_namespace VARCHAR(64) NOT NULL,
    window VARCHAR(24) NOT NULL CHECK (window IN ('short_term', 'medium_term', 'long_term')),
    reference_date DATE NOT NULL,
    source_models_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    features_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_feature_store_snapshots_scope UNIQUE (entity_key, feature_namespace, reference_date, window)
);

CREATE INDEX IF NOT EXISTS ix_capm_metrics_reference_window ON capm_metrics (reference_date, window);
CREATE INDEX IF NOT EXISTS ix_apt_factor_loadings_reference_window ON apt_factor_loadings (reference_date, window);
CREATE INDEX IF NOT EXISTS ix_arima_forecasts_reference_window ON arima_forecasts (reference_date, window);
CREATE INDEX IF NOT EXISTS ix_garch_volatility_reference_window ON garch_volatility (reference_date, window);
CREATE INDEX IF NOT EXISTS ix_valuation_metrics_reference_window ON valuation_metrics (reference_date, window);
CREATE INDEX IF NOT EXISTS ix_intrinsic_value_estimates_reference_window ON intrinsic_value_estimates (reference_date, window);
CREATE INDEX IF NOT EXISTS ix_feature_store_snapshots_reference_window ON feature_store_snapshots (reference_date, window);

DROP TRIGGER IF EXISTS trg_capm_metrics_set_updated_at ON capm_metrics;
CREATE TRIGGER trg_capm_metrics_set_updated_at BEFORE UPDATE ON capm_metrics FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_apt_factor_loadings_set_updated_at ON apt_factor_loadings;
CREATE TRIGGER trg_apt_factor_loadings_set_updated_at BEFORE UPDATE ON apt_factor_loadings FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_arima_forecasts_set_updated_at ON arima_forecasts;
CREATE TRIGGER trg_arima_forecasts_set_updated_at BEFORE UPDATE ON arima_forecasts FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_garch_volatility_set_updated_at ON garch_volatility;
CREATE TRIGGER trg_garch_volatility_set_updated_at BEFORE UPDATE ON garch_volatility FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_valuation_metrics_set_updated_at ON valuation_metrics;
CREATE TRIGGER trg_valuation_metrics_set_updated_at BEFORE UPDATE ON valuation_metrics FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_intrinsic_value_estimates_set_updated_at ON intrinsic_value_estimates;
CREATE TRIGGER trg_intrinsic_value_estimates_set_updated_at BEFORE UPDATE ON intrinsic_value_estimates FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_feature_store_snapshots_set_updated_at ON feature_store_snapshots;
CREATE TRIGGER trg_feature_store_snapshots_set_updated_at BEFORE UPDATE ON feature_store_snapshots FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;