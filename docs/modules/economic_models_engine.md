# Economic Models Engine

## Objetivo
Adicionar uma camada híbrida explicativa e preditiva com modelos aceitos pelo mercado para retornos, risco e valuation, servindo ao mesmo tempo como baseline e como gerador de features para ML.

## Modelos implementados
- `CAPM`
- `APT multifatorial`
- `ARIMA/SARIMA`
- `GARCH/EGARCH`
- `valuation por múltiplos`
- `valuation por fluxo de caixa descontado`

## Interface comum
Todos os modelos expõem:
- `fit(inputs)`
- `predict(inputs)`
- `explain()`
- `serialize()`

## Janelas
- `short_term`: sinais e risco de curto prazo.
- `medium_term`: premissas e valuation relativo intermediário.
- `long_term`: valuation intrínseco e cenários estruturais.

## Inputs por modelo
- `CAPM`: `asset_returns`, `market_returns`, `risk_free_rate`, `asset_identifier`, `market_identifier`.
- `APT`: `asset_returns`, `factor_returns`, `factor_projection`, `asset_identifier`.
- `ARIMA/SARIMA`: `time_series`, `order`, `seasonal_order`, `forecast_horizon`, `series_name`.
- `GARCH/EGARCH`: `returns`, `model_family`, `p_order`, `q_order`, `forecast_horizon`, `series_name`.
- `valuation por múltiplos`: `comparables`, `fundamentals`, `net_debt`, `shares_outstanding`, `asset_identifier`.
- `DCF`: `projected_cash_flows`, `discount_rate`, `terminal_growth_rate`, `net_debt`, `shares_outstanding`, `asset_identifier`.

## Outputs principais
- `capm_metrics`: alpha, beta, retorno esperado, $R^2$ e volatilidade residual.
- `apt_factor_loadings`: carga por fator, prêmio do fator, alpha e retorno implícito.
- `arima_forecasts`: previsão por passo com intervalo de confiança.
- `garch_volatility`: volatilidade condicional prevista, persistência e assimetria.
- `valuation_metrics`: estimativas por múltiplo e preço implícito por ação.
- `intrinsic_value_estimates`: enterprise value, equity value e valor intrínseco por ação.

## Jobs
- CLI: `b3-jobs economic-models --file examples/economic_models_engine_job.json`
- HTTP: `POST /v1/jobs/economic-models`

## Integração com feature store
- O job consolida `capm_expected_return`, contribuições do APT, `arima_forecast_step_1`, `garch_volatility_step_1`, `multiples_intrinsic_value_per_share` e `dcf_intrinsic_value_per_share`.
- As features são persistidas em `feature_store_snapshots` com namespace `economic_models_engine`.

## Integração com portfolio optimizer
- O optimizer lê métricas econômicas persistidas e monta overlays por ticker com:
  - `expected_return`
  - `valuation_upside`
  - `risk_proxy`
  - `optimizer_score`

## Critérios de aceite
- Saídas persistidas nas seis tabelas obrigatórias.
- Feature store atualizado a cada execução quando solicitado.
- Overlay do optimizer calculado para os tickers do portfólio.
- Cada modelo documenta claramente seus inputs e outputs.