# Events Catalog

## Objetivo
Representar eventos exógenos reais e sintéticos, mapear ativos e fatores macro afetados, derivar cenários e executar runs contrafactuais sobre carteiras.

## Entidades
- `events_catalog`
- `event_asset_mapping`
- `event_impact_profiles`
- `event_scenarios`
- `counterfactual_runs`

## Escopo
- `empresa`: choque concentrado em tickers e ativos mapeados.
- `setor`: choque propagado para setor e ativos associados.
- `indice`: choque direcionado a benchmarks e índices mapeados.
- `brasil`: choque sistêmico doméstico com `default_price_shock_pct` e fatores macro locais.
- `global`: choque sistêmico global com multiplicador adicional de severidade.

## Endpoints REST
- `GET /v1/events`
- `GET /v1/events/{event_id}`
- `POST /v1/events`
- `POST /v1/events/{event_id}/assets`
- `POST /v1/events/{event_id}/impact-profiles`
- `GET /v1/events/{event_id}/shock-vector`
- `POST /v1/scenarios/from-event`
- `POST /v1/scenarios/counterfactual-run`

## Regras do vetor de choque
- Severidade define a base do choque quando o perfil não informa `default_price_shock_pct`.
- `empresa`, `setor` e `indice` priorizam overrides explícitos por ativo, setor ou benchmark.
- `brasil` e `global` aplicam `default_price_shock_pct` ao portfólio e complementam com ativos mapeados.
- Fatores macro afetados entram serializados em `macro_factor_shocks` com `shock_bps` ou `shock_pct`.

## Seeds históricos
- Brumadinho 2019
- Eleição Brasil 2022
- Americanas 2023
- Copom Hike 2021