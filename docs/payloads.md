# Exemplos de payload

## Criar template de portfólio
```json
{
  "slug": "quality-income",
  "name": "Quality Income Brazil",
  "objective": "income",
  "benchmark_ticker": "IDIV",
  "risk_budget_bps": 400,
  "rebalance_rule": {
    "cadence": "monthly",
    "trigger": "valuation-spread"
  },
  "constraints": {
    "max_single_name": 0.1,
    "min_dividend_yield": 0.04
  },
  "model_config": {
    "label": "quality_yield",
    "horizon_days": 5
  }
}
```

## Criar instância de portfólio
```json
{
  "template_id": "6a579914-a74f-4d3e-a8f5-84f88c3d8d5a",
  "name": "Income Sleeve BR",
  "reference_date": "2026-04-28",
  "seed_capital": 1000000,
  "base_currency": "BRL",
  "status": "active",
  "mandate": {
    "desk": "equities",
    "owner": "multi-portfolio-factory"
  },
  "positions": [
    {
      "ticker": "VALE3",
      "market": "equities",
      "target_weight": 0.35,
      "quantity": 1000,
      "close_price": 60.0,
      "signal": {
        "alpha": 0.11,
        "quality": 0.92
      }
    }
  ]
}
```

## Ingerir snapshots EOD
```json
{
  "reference_date": "2026-04-28",
  "snapshots": [
    {
      "ticker": "VALE3",
      "market": "equities",
      "open_price": 59.0,
      "high_price": 61.5,
      "low_price": 58.7,
      "close_price": 60.5,
      "adjusted_close": 60.5,
      "volume": 1000000,
      "source_version": "b3-eod-v1"
    }
  ]
}
```

## Criar cenário
```json
{
  "slug": "election-stress",
  "name": "Election Stress",
  "description": "abertura de curva, desvalorização cambial e queda de commodities",
  "scenario_type": "stress",
  "shock_vector": {
    "default_price_shock_pct": -0.08,
    "ticker_overrides": {
      "VALE3": -0.12,
      "PETR4": -0.1
    }
  },
  "active": true
}
```

## Criar evento exógeno
```json
{
  "code": "election-2026",
  "name": "Election 2026",
  "description": "choque político doméstico com abertura de curva e aumento de volatilidade",
  "event_type": "eleicao",
  "event_date": "2026-04-28",
  "scope": "brasil",
  "scope_reference": "BR",
  "severity": 4,
  "expected_duration_days": 30,
  "confidence": 0.84,
  "macro_factors": [
    {
      "factor": "juros",
      "shock_bps": 80
    },
    {
      "factor": "cambio",
      "shock_pct": 0.04
    }
  ],
  "affected_assets": [
    {
      "asset_identifier": "IBOV",
      "asset_name": "Ibovespa",
      "asset_type": "index",
      "mapping_scope": "indice",
      "weight": 1.0,
      "is_primary": true
    }
  ]
}
```

## Criar cenário a partir de evento
```json
{
  "event_id": "8b0c8436-5e5f-4a19-b2eb-e2a228f3f9d8",
  "impact_profile_id": "dc905a16-0e84-4cf2-b44f-648cc81285e6",
  "scenario_type": "counterfactual",
  "assumptions": {
    "shock_multiplier": 1.1
  }
}
```

## Rodar contrafactual
```json
{
  "portfolio_id": "f489f959-b66e-4bfe-9253-724cc79f9f4a",
  "reference_date": "2026-04-28",
  "scenario_slug": "election-2026-counterfactual",
  "assumptions": {
    "shock_multiplier": 1.05
  }
}
```

## Rodar cenário
```json
{
  "portfolio_id": "f489f959-b66e-4bfe-9253-724cc79f9f4a",
  "reference_date": "2026-04-28",
  "scenario_slug": "election-stress"
}
```

## Job de comparação EOD
```json
{
  "reference_date": "2026-04-28",
  "portfolio_id": "f489f959-b66e-4bfe-9253-724cc79f9f4a",
  "scenario_slug": "baseline",
  "expected_prices": [
    {
      "ticker": "VALE3",
      "expected_close": 60.0
    },
    {
      "ticker": "PETR4",
      "expected_close": 35.5
    }
  ]
}
```

## Job de mirror analítico
```json
{
  "processing_date": "2026-04-29",
  "dataset_name": "quotes",
  "source_prefix": "b3/silver/quotes/",
  "table_name": "quotes",
  "materialization_strategy": "external_and_native",
  "partition_field": "reference_date",
  "cluster_fields": [
    "market_type",
    "ticker"
  ]
}
```

## Job de ingestão histórica B3
```json
{
  "dataset_type": "eod",
  "processing_date": "2026-04-29",
  "reference_date": "2026-04-28",
  "source_name": "quotes.csv",
  "content_base64": "<base64>",
  "encoding": "latin-1",
  "delimiter": ";"
}
```

## Job de treino TensorFlow
```json
{
  "reference_date": "2026-04-28",
  "portfolio_id": "f489f959-b66e-4bfe-9253-724cc79f9f4a",
  "model_name": "close-price-baseline",
  "version": "2026.04.28",
  "objective": "predict_expected_close",
  "epochs": 10,
  "rows": [
    {
      "features": {
        "momentum_5d": 0.04,
        "volatility_10d": 0.12,
        "volume_zscore": 1.8
      },
      "target": 60.7
    }
  ]
}
```

## Job do economic models engine
```json
{
  "portfolio_id": "f489f959-b66e-4bfe-9253-724cc79f9f4a",
  "reference_date": "2026-04-28",
  "window": "short_term",
  "capm": {
    "asset_identifier": "VALE3",
    "market_identifier": "IBOV",
    "asset_returns": [0.01, 0.012, 0.011, 0.013, 0.014, 0.012],
    "market_returns": [0.008, 0.009, 0.007, 0.01, 0.011, 0.009],
    "risk_free_rate": 0.001
  },
  "apt": {
    "asset_identifier": "VALE3",
    "asset_returns": [0.01, 0.012, 0.011, 0.013, 0.014, 0.012],
    "factor_returns": {
      "market": [0.008, 0.009, 0.007, 0.01, 0.011, 0.009],
      "value": [0.003, 0.002, -0.001, 0.004, 0.003, 0.002]
    }
  },
  "arima": {
    "series_name": "VALE3",
    "time_series": [0.011, 0.01, 0.012, 0.013, 0.012, 0.014, 0.013, 0.014],
    "order": [1, 0, 0],
    "forecast_horizon": 3
  },
  "garch": {
    "series_name": "VALE3",
    "returns": [0.01, -0.02, 0.015, -0.018, 0.022, -0.011, 0.009, -0.014],
    "model_family": "garch",
    "forecast_horizon": 3
  },
  "multiples": {
    "asset_identifier": "VALE3",
    "comparables": [
      {"ev_ebitda": 8.2, "pe": 12.5},
      {"ev_ebitda": 9.0, "pe": 13.4}
    ],
    "fundamentals": {
      "ebitda": 100.0,
      "net_income": 45.0
    },
    "net_debt": 120.0,
    "shares_outstanding": 10.0
  },
  "dcf": {
    "asset_identifier": "VALE3",
    "projected_cash_flows": [18.0, 21.0, 24.0, 27.0, 29.0],
    "discount_rate": 0.10,
    "terminal_growth_rate": 0.03,
    "net_debt": 50.0,
    "shares_outstanding": 10.0
  }
}
```
