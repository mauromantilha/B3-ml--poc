BEGIN;

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
    is_synthetic,
    source_reference,
    macro_factors_json,
    metadata_json,
    is_active
)
VALUES
    (
        'brumadinho-2019',
        'Brumadinho 2019',
        'Desastre operacional com choque severo sobre VALE3 e contágio em mineração.',
        'desastre_operacional',
        DATE '2019-01-25',
        'empresa',
        'VALE3',
        'b3',
        5,
        180,
        0.97,
        FALSE,
        'historical-seed',
        '[{"factor":"commodities","shock_pct":-0.08},{"factor":"credito","shock_bps":-180}]'::jsonb,
        '{"origin":"historical","region":"BR"}'::jsonb,
        TRUE
    ),
    (
        'eleicao-br-2022',
        'Eleição Brasil 2022',
        'Choque político com abertura de curva, prêmio de risco e volatilidade sobre índices domésticos.',
        'eleicao',
        DATE '2022-10-30',
        'brasil',
        'BR',
        'b3',
        4,
        45,
        0.82,
        FALSE,
        'historical-seed',
        '[{"factor":"juros","shock_bps":120},{"factor":"cambio","shock_pct":0.05},{"factor":"risco_pais","shock_bps":95}]'::jsonb,
        '{"origin":"historical","region":"BR"}'::jsonb,
        TRUE
    ),
    (
        'americanas-2023-rating',
        'Americanas 2023',
        'Rebaixamento de rating e choque de crédito após evento contábil corporativo.',
        'rebaixamento_rating',
        DATE '2023-01-12',
        'empresa',
        'AMER3',
        'b3',
        5,
        90,
        0.95,
        FALSE,
        'historical-seed',
        '[{"factor":"credito","shock_bps":250},{"factor":"liquidez","shock_pct":-0.12}]'::jsonb,
        '{"origin":"historical","region":"BR"}'::jsonb,
        TRUE
    ),
    (
        'copom-hike-2021',
        'Copom Hike 2021',
        'Choque de juros com abertura de curva e compressão de múltiplos em ações domésticas.',
        'choque_juros',
        DATE '2021-03-17',
        'brasil',
        'BR',
        'b3',
        4,
        30,
        0.88,
        FALSE,
        'historical-seed',
        '[{"factor":"juros","shock_bps":150},{"factor":"equity_risk","shock_pct":-0.06}]'::jsonb,
        '{"origin":"historical","region":"BR"}'::jsonb,
        TRUE
    )
ON CONFLICT (code) DO NOTHING;

INSERT INTO event_asset_mapping (
    event_id,
    asset_identifier,
    asset_name,
    asset_type,
    mapping_scope,
    sector,
    weight,
    is_primary,
    metadata_json
)
SELECT event.id, seed.asset_identifier, seed.asset_name, seed.asset_type, seed.mapping_scope, seed.sector, seed.weight, seed.is_primary, seed.metadata_json
FROM (
    VALUES
        ('brumadinho-2019', 'VALE3', 'Vale ON', 'equity', 'empresa', 'mineracao', 1.0, TRUE, '{"role":"primary"}'::jsonb),
        ('brumadinho-2019', 'IBOV', 'Ibovespa', 'index', 'indice', NULL, 0.35, FALSE, '{"role":"contagion"}'::jsonb),
        ('eleicao-br-2022', 'IBOV', 'Ibovespa', 'index', 'indice', NULL, 1.0, TRUE, '{"role":"broad-market"}'::jsonb),
        ('eleicao-br-2022', 'DOL1!', 'Dolar Futuro', 'fx', 'brasil', NULL, 0.55, FALSE, '{"role":"macro"}'::jsonb),
        ('americanas-2023-rating', 'AMER3', 'Americanas ON', 'equity', 'empresa', 'varejo', 1.0, TRUE, '{"role":"primary"}'::jsonb),
        ('copom-hike-2021', 'IDIV', 'Indice Dividendos', 'index', 'indice', NULL, 0.70, FALSE, '{"role":"rates-sensitive"}'::jsonb)
) AS seed (event_code, asset_identifier, asset_name, asset_type, mapping_scope, sector, weight, is_primary, metadata_json)
JOIN events_catalog AS event ON event.code = seed.event_code
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
SELECT event.id, seed.profile_name, seed.shock_template_json, seed.macro_factors_json, seed.expected_duration_days, seed.confidence, seed.transmission_lag_days, seed.metadata_json
FROM (
    VALUES
        (
            'brumadinho-2019',
            'base-operational',
            '{"default_price_shock_pct":-0.18,"ticker_overrides":{"VALE3":-0.24}}'::jsonb,
            '[{"factor":"commodities","shock_pct":-0.08},{"factor":"credito","shock_bps":-180}]'::jsonb,
            180,
            0.97,
            0,
            '{"seed":true}'::jsonb
        ),
        (
            'eleicao-br-2022',
            'base-election',
            '{"default_price_shock_pct":-0.07,"index_overrides":{"IBOV":-0.09}}'::jsonb,
            '[{"factor":"juros","shock_bps":120},{"factor":"cambio","shock_pct":0.05}]'::jsonb,
            45,
            0.82,
            0,
            '{"seed":true}'::jsonb
        ),
        (
            'americanas-2023-rating',
            'base-credit',
            '{"default_price_shock_pct":-0.15,"ticker_overrides":{"AMER3":-0.35}}'::jsonb,
            '[{"factor":"credito","shock_bps":250},{"factor":"liquidez","shock_pct":-0.12}]'::jsonb,
            90,
            0.95,
            1,
            '{"seed":true}'::jsonb
        ),
        (
            'copom-hike-2021',
            'base-rates',
            '{"default_price_shock_pct":-0.06}'::jsonb,
            '[{"factor":"juros","shock_bps":150},{"factor":"equity_risk","shock_pct":-0.06}]'::jsonb,
            30,
            0.88,
            0,
            '{"seed":true}'::jsonb
        )
) AS seed (event_code, profile_name, shock_template_json, macro_factors_json, expected_duration_days, confidence, transmission_lag_days, metadata_json)
JOIN events_catalog AS event ON event.code = seed.event_code
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
    seed.slug,
    seed.name,
    seed.description,
    seed.scenario_type,
    event.scope,
    event.severity,
    profile.expected_duration_days,
    profile.confidence,
    seed.affected_assets_json,
    profile.macro_factors_json,
    profile.shock_template_json,
    seed.assumptions_json,
    TRUE
FROM (
    VALUES
        ('brumadinho-2019', 'base-operational', 'brumadinho-counterfactual', 'Brumadinho Counterfactual', 'Cenário contrafactual para choque operacional de grande magnitude.', 'counterfactual', '[{"asset_identifier":"VALE3","asset_type":"equity"}]'::jsonb, '{"recovery_window_days":90}'::jsonb),
        ('eleicao-br-2022', 'base-election', 'eleicao-2022-stress', 'Eleicao 2022 Stress', 'Stress macro doméstico com abertura de curva e FX.', 'exogenous', '[{"asset_identifier":"IBOV","asset_type":"index"}]'::jsonb, '{"second_round":true}'::jsonb),
        ('americanas-2023-rating', 'base-credit', 'americanas-credit-stress', 'Americanas Credit Stress', 'Stress de crédito e liquidez sobre varejo alavancado.', 'counterfactual', '[{"asset_identifier":"AMER3","asset_type":"equity"}]'::jsonb, '{"liquidity_freeze":true}'::jsonb),
        ('copom-hike-2021', 'base-rates', 'copom-hike-stress', 'Copom Hike Stress', 'Choque de juros sobre Brasil e fatores de equity risk.', 'exogenous', '[{"asset_identifier":"IDIV","asset_type":"index"}]'::jsonb, '{"curve_steepening":true}'::jsonb)
) AS seed (event_code, profile_name, slug, name, description, scenario_type, affected_assets_json, assumptions_json)
JOIN events_catalog AS event ON event.code = seed.event_code
JOIN event_impact_profiles AS profile ON profile.event_id = event.id AND profile.profile_name = seed.profile_name
ON CONFLICT (slug) DO NOTHING;

COMMIT;