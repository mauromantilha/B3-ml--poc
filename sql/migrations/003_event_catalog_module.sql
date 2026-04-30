BEGIN;

ALTER TABLE IF EXISTS events_catalog
    DROP CONSTRAINT IF EXISTS events_catalog_event_type_check,
    DROP CONSTRAINT IF EXISTS ck_events_catalog_event_type,
    DROP CONSTRAINT IF EXISTS ck_events_catalog_scope,
    DROP CONSTRAINT IF EXISTS ck_events_catalog_severity,
    DROP CONSTRAINT IF EXISTS ck_events_catalog_expected_duration_days,
    DROP CONSTRAINT IF EXISTS ck_events_catalog_confidence;

ALTER TABLE IF EXISTS events_catalog
    ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT 'event without description',
    ADD COLUMN IF NOT EXISTS scope VARCHAR(24) NOT NULL DEFAULT 'brasil',
    ADD COLUMN IF NOT EXISTS scope_reference VARCHAR(80),
    ADD COLUMN IF NOT EXISTS expected_duration_days INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.7500,
    ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source_reference VARCHAR(255),
    ADD COLUMN IF NOT EXISTS macro_factors_json JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE IF EXISTS events_catalog
    ADD CONSTRAINT ck_events_catalog_event_type CHECK (
        event_type IN (
            'crise_bancaria', 'acidente_corporativo', 'choque_politico', 'eleicao',
            'mudanca_regulatoria', 'rebaixamento_rating', 'desastre_operacional',
            'choque_juros', 'choque_cambial', 'choque_setorial',
            'macro', 'market', 'corporate', 'policy'
        )
    ),
    ADD CONSTRAINT ck_events_catalog_scope CHECK (scope IN ('empresa', 'setor', 'indice', 'brasil', 'global')),
    ADD CONSTRAINT ck_events_catalog_severity CHECK (severity BETWEEN 1 AND 5),
    ADD CONSTRAINT ck_events_catalog_expected_duration_days CHECK (expected_duration_days >= 1),
    ADD CONSTRAINT ck_events_catalog_confidence CHECK (confidence >= 0 AND confidence <= 1);

CREATE TABLE IF NOT EXISTS event_asset_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events_catalog(id) ON DELETE CASCADE,
    asset_identifier VARCHAR(64) NOT NULL,
    asset_name VARCHAR(160),
    asset_type VARCHAR(32) NOT NULL,
    mapping_scope VARCHAR(24) NOT NULL CHECK (mapping_scope IN ('empresa', 'setor', 'indice', 'brasil', 'global')),
    sector VARCHAR(64),
    weight NUMERIC(10, 4) NOT NULL DEFAULT 1.0000 CHECK (weight >= 0),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_event_asset_mapping_event_asset UNIQUE (event_id, asset_identifier, asset_type)
);

CREATE TABLE IF NOT EXISTS event_impact_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events_catalog(id) ON DELETE CASCADE,
    profile_name VARCHAR(80) NOT NULL,
    shock_template_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    macro_factors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_duration_days INTEGER NOT NULL DEFAULT 5 CHECK (expected_duration_days >= 1),
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.7500 CHECK (confidence >= 0 AND confidence <= 1),
    transmission_lag_days INTEGER NOT NULL DEFAULT 0 CHECK (transmission_lag_days >= 0),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_event_impact_profiles_event_profile UNIQUE (event_id, profile_name)
);

ALTER TABLE IF EXISTS event_scenarios
    DROP CONSTRAINT IF EXISTS ck_event_scenarios_scope,
    DROP CONSTRAINT IF EXISTS ck_event_scenarios_severity,
    DROP CONSTRAINT IF EXISTS ck_event_scenarios_expected_duration_days,
    DROP CONSTRAINT IF EXISTS ck_event_scenarios_confidence;

ALTER TABLE IF EXISTS event_scenarios
    ADD COLUMN IF NOT EXISTS impact_profile_id UUID REFERENCES event_impact_profiles(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS scope VARCHAR(24) NOT NULL DEFAULT 'brasil',
    ADD COLUMN IF NOT EXISTS severity INTEGER NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS expected_duration_days INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.7500,
    ADD COLUMN IF NOT EXISTS affected_assets_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS macro_factors_json JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE IF EXISTS event_scenarios
    ADD CONSTRAINT ck_event_scenarios_scope CHECK (scope IN ('empresa', 'setor', 'indice', 'brasil', 'global')),
    ADD CONSTRAINT ck_event_scenarios_severity CHECK (severity BETWEEN 1 AND 5),
    ADD CONSTRAINT ck_event_scenarios_expected_duration_days CHECK (expected_duration_days >= 1),
    ADD CONSTRAINT ck_event_scenarios_confidence CHECK (confidence >= 0 AND confidence <= 1);

CREATE TABLE IF NOT EXISTS counterfactual_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES events_catalog(id) ON DELETE SET NULL,
    event_scenario_id UUID NOT NULL REFERENCES event_scenarios(id),
    portfolio_instance_id UUID NOT NULL REFERENCES portfolio_instances(id),
    reference_date DATE NOT NULL,
    run_status VARCHAR(32) NOT NULL CHECK (run_status IN ('pending', 'running', 'succeeded', 'failed')),
    input_hash VARCHAR(64) NOT NULL DEFAULT '',
    engine_version VARCHAR(48) NOT NULL DEFAULT 'v1',
    baseline_nav NUMERIC(18, 6) NOT NULL,
    counterfactual_nav NUMERIC(18, 6) NOT NULL,
    delta_pnl NUMERIC(18, 6) NOT NULL,
    shock_vector_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    assumptions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_counterfactual_run UNIQUE (event_scenario_id, portfolio_instance_id, reference_date)
);

CREATE INDEX IF NOT EXISTS ix_events_catalog_scope_active ON events_catalog (scope, is_active);
CREATE INDEX IF NOT EXISTS ix_event_asset_mapping_event_primary ON event_asset_mapping (event_id, is_primary);
CREATE INDEX IF NOT EXISTS ix_event_impact_profiles_event_confidence ON event_impact_profiles (event_id, confidence);
CREATE INDEX IF NOT EXISTS ix_event_scenarios_scope_active ON event_scenarios (scope, active);
CREATE INDEX IF NOT EXISTS ix_counterfactual_runs_reference_date ON counterfactual_runs (reference_date, run_status);

DROP TRIGGER IF EXISTS trg_event_asset_mapping_set_updated_at ON event_asset_mapping;
CREATE TRIGGER trg_event_asset_mapping_set_updated_at BEFORE UPDATE ON event_asset_mapping FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_event_impact_profiles_set_updated_at ON event_impact_profiles;
CREATE TRIGGER trg_event_impact_profiles_set_updated_at BEFORE UPDATE ON event_impact_profiles FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_counterfactual_runs_set_updated_at ON counterfactual_runs;
CREATE TRIGGER trg_counterfactual_runs_set_updated_at BEFORE UPDATE ON counterfactual_runs FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;