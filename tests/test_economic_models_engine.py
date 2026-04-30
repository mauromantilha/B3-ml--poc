from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.api.main import app
from b3_quant_platform.economic_models_engine import (
    AptMultiFactorModel,
    ArimaSarimaModel,
    CapmModel,
    DiscountedCashFlowModel,
    GarchEgarchModel,
    RelativeValuationModel,
)
from b3_quant_platform.models.entities import CapmMetric, FeatureStoreSnapshot, IntrinsicValueEstimate, ValuationMetric
from b3_quant_platform.models.enums import EconomicModelWindow
from b3_quant_platform.schemas.economic_models import EconomicModelsJobRequest
from b3_quant_platform.schemas.portfolio import PortfolioInstanceCreate
from b3_quant_platform.services.economic_models_engine import EconomicModelsEngineService
from b3_quant_platform.services.portfolio_factory import PortfolioFactoryService


def _create_portfolio(db_session):
    portfolio_service = PortfolioFactoryService()
    portfolio_service.seed_default_templates(db_session)
    template = portfolio_service.list_templates(db_session)[0]
    return portfolio_service.create_instance(
        db_session,
        PortfolioInstanceCreate(
            template_id=template.id,
            name="Economic Models Book",
            reference_date=date(2026, 4, 28),
            seed_capital=Decimal("100000.00"),
            positions=[
                {
                    "ticker": "VALE3",
                    "market": "equities",
                    "target_weight": "1.0",
                    "quantity": "100",
                    "close_price": "60.00",
                    "signal": {},
                }
            ],
        ),
    )


def test_capm_recovers_alpha_and_beta() -> None:
    market_returns = [-0.02, -0.01, 0.0, 0.01, 0.02, 0.03]
    risk_free_rate = 0.001
    asset_returns = [risk_free_rate + 0.002 + (1.2 * (value - risk_free_rate)) for value in market_returns]
    model = CapmModel(window=EconomicModelWindow.SHORT_TERM)

    fit = model.fit(
        {
            "asset_identifier": "VALE3",
            "market_identifier": "IBOV",
            "asset_returns": asset_returns,
            "market_returns": market_returns,
            "risk_free_rate": risk_free_rate,
        }
    )
    prediction = model.predict({"forecast_market_return": 0.015, "forecast_risk_free_rate": risk_free_rate})

    assert abs(fit.parameters["beta"] - 1.2) < 0.05
    assert abs(fit.parameters["alpha"] - 0.002) < 0.01
    assert prediction.outputs["expected_return"] > 0


def test_apt_recovers_multifactor_loadings() -> None:
    factor_market = [0.01, -0.01, 0.02, -0.015, 0.018, 0.012]
    factor_value = [0.005, 0.001, -0.004, 0.002, 0.006, -0.003]
    asset_returns = [0.001 + (0.7 * factor_market[index]) + (0.3 * factor_value[index]) for index in range(len(factor_market))]
    model = AptMultiFactorModel(window=EconomicModelWindow.SHORT_TERM)

    fit = model.fit(
        {
            "asset_identifier": "VALE3",
            "asset_returns": asset_returns,
            "factor_returns": {"market": factor_market, "value": factor_value},
        }
    )

    assert abs(fit.parameters["factor_loadings"]["market"] - 0.7) < 0.1
    assert abs(fit.parameters["factor_loadings"]["value"] - 0.3) < 0.1


def test_arima_generates_requested_steps() -> None:
    pytest.importorskip("statsmodels")
    series = [0.012, 0.011, 0.013, 0.0125, 0.0135, 0.013, 0.014, 0.0138]
    model = ArimaSarimaModel(window=EconomicModelWindow.SHORT_TERM)

    fit = model.fit({"series_name": "VALE3", "time_series": series, "order": (1, 0, 0), "forecast_horizon": 3})
    prediction = model.predict({"forecast_horizon": 3})

    assert fit.parameters["order"] == (1, 0, 0)
    assert len(prediction.outputs["forecasts"]) == 3
    assert prediction.outputs["forecasts"][0]["lower_ci"] <= prediction.outputs["forecasts"][0]["forecast_mean"]
    assert prediction.outputs["forecasts"][0]["forecast_mean"] <= prediction.outputs["forecasts"][0]["upper_ci"]


def test_garch_forecast_returns_positive_volatility() -> None:
    pytest.importorskip("arch")
    returns = [0.01, -0.02, 0.015, -0.018, 0.022, -0.011, 0.009, -0.014, 0.02, -0.017]
    model = GarchEgarchModel(window=EconomicModelWindow.SHORT_TERM)

    model.fit({"series_name": "VALE3", "returns": returns, "model_family": "garch", "forecast_horizon": 2})
    prediction = model.predict({"forecast_horizon": 2})

    assert len(prediction.outputs["volatility_forecast"]) == 2
    assert all(row["conditional_volatility"] > 0 for row in prediction.outputs["volatility_forecast"])


def test_valuation_models_generate_intrinsic_values() -> None:
    multiples_model = RelativeValuationModel(window=EconomicModelWindow.MEDIUM_TERM)
    multiples_model.fit(
        {
            "asset_identifier": "VALE3",
            "comparables": [{"ev_ebitda": 8.0, "pe": 12.0}, {"ev_ebitda": 10.0, "pe": 14.0}],
            "fundamentals": {"ebitda": 100.0, "net_income": 40.0},
            "net_debt": 120.0,
            "shares_outstanding": 10.0,
        }
    )
    multiples_prediction = multiples_model.predict(
        {
            "fundamentals": {"ebitda": 100.0, "net_income": 40.0},
            "net_debt": 120.0,
            "shares_outstanding": 10.0,
        }
    )
    dcf_model = DiscountedCashFlowModel(window=EconomicModelWindow.LONG_TERM)
    dcf_model.fit(
        {
            "asset_identifier": "VALE3",
            "projected_cash_flows": [20.0, 24.0, 28.0, 31.0, 33.0],
            "discount_rate": 0.1,
            "terminal_growth_rate": 0.03,
        }
    )
    dcf_prediction = dcf_model.predict(
        {
            "net_debt": 50.0,
            "shares_outstanding": 10.0,
        }
    )

    assert multiples_prediction.outputs["aggregate"]["intrinsic_value_per_share"] > 0
    assert dcf_prediction.outputs["enterprise_value"] > dcf_prediction.outputs["equity_value"]
    assert dcf_prediction.outputs["intrinsic_value_per_share"] > 0


def test_economic_models_engine_persists_outputs_and_builds_optimizer_overlay(db_session) -> None:
    portfolio = _create_portfolio(db_session)
    service = EconomicModelsEngineService()
    payload = EconomicModelsJobRequest.model_validate(
        {
            "portfolio_id": str(portfolio.id),
            "reference_date": "2026-04-28",
            "window": "short_term",
            "capm": {
                "asset_identifier": "VALE3",
                "market_identifier": "IBOV",
                "asset_returns": [0.01, 0.012, 0.011, 0.013, 0.014, 0.012],
                "market_returns": [0.008, 0.009, 0.007, 0.01, 0.011, 0.009],
                "risk_free_rate": 0.001
            },
            "multiples": {
                "asset_identifier": "VALE3",
                "comparables": [{"ev_ebitda": 8.0, "pe": 12.0}, {"ev_ebitda": 9.0, "pe": 13.0}],
                "fundamentals": {"ebitda": 100.0, "net_income": 45.0},
                "net_debt": 120.0,
                "shares_outstanding": 10.0
            },
            "dcf": {
                "asset_identifier": "VALE3",
                "projected_cash_flows": [18.0, 21.0, 24.0, 27.0, 29.0],
                "discount_rate": 0.1,
                "terminal_growth_rate": 0.03,
                "net_debt": 50.0,
                "shares_outstanding": 10.0
            }
        }
    )

    result = service.run(db_session, payload)

    assert result.output_counts["capm_metrics"] == 1
    assert result.output_counts["valuation_metrics"] >= 1
    assert result.output_counts["intrinsic_value_estimates"] == 1
    assert result.feature_store_snapshot_id is not None
    assert result.portfolio_optimizer_overlay is not None
    assert result.portfolio_optimizer_overlay["overlays"][0]["ticker"] == "VALE3"

    assert db_session.scalar(select(CapmMetric)) is not None
    assert db_session.scalar(select(ValuationMetric)) is not None
    assert db_session.scalar(select(IntrinsicValueEstimate)) is not None
    assert db_session.scalar(select(FeatureStoreSnapshot)) is not None


def test_economic_models_job_route_is_idempotent(db_session) -> None:
    portfolio = _create_portfolio(db_session)

    def override_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    payload = {
        "portfolio_id": str(portfolio.id),
        "reference_date": "2026-04-28",
        "window": "short_term",
        "capm": {
            "asset_identifier": "VALE3",
            "market_identifier": "IBOV",
            "asset_returns": [0.01, 0.012, 0.011, 0.013, 0.014, 0.012],
            "market_returns": [0.008, 0.009, 0.007, 0.01, 0.011, 0.009],
            "risk_free_rate": 0.001
        },
        "multiples": {
            "asset_identifier": "VALE3",
            "comparables": [{"ev_ebitda": 8.0, "pe": 12.0}, {"ev_ebitda": 9.0, "pe": 13.0}],
            "fundamentals": {"ebitda": 100.0, "net_income": 45.0},
            "net_debt": 120.0,
            "shares_outstanding": 10.0
        },
        "dcf": {
            "asset_identifier": "VALE3",
            "projected_cash_flows": [18.0, 21.0, 24.0, 27.0, 29.0],
            "discount_rate": 0.1,
            "terminal_growth_rate": 0.03,
            "net_debt": 50.0,
            "shares_outstanding": 10.0
        }
    }

    try:
        first = client.post("/v1/jobs/economic-models", json=payload)
        second = client.post("/v1/jobs/economic-models", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["details"]["reused"] is False
    assert first.json()["details"]["output_counts"]["capm_metrics"] == 1
    assert second.json()["details"]["reused"] is True