from __future__ import annotations

from datetime import date
from decimal import Decimal

from b3_quant_platform.models.enums import ScenarioType
from b3_quant_platform.schemas.portfolio import PortfolioInstanceCreate
from b3_quant_platform.schemas.scenario import ScenarioDefinitionCreate, ScenarioRunRequest
from b3_quant_platform.services.portfolio_factory import PortfolioFactoryService
from b3_quant_platform.services.scenario_lab import ScenarioLabService


def test_run_stress_scenario_returns_projection(db_session) -> None:
    portfolio_service = PortfolioFactoryService()
    portfolio_service.seed_default_templates(db_session)
    template = portfolio_service.list_templates(db_session)[0]
    portfolio = portfolio_service.create_instance(
        db_session,
        PortfolioInstanceCreate(
            template_id=template.id,
            name="Stress Book",
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

    scenario_service = ScenarioLabService()
    scenario = scenario_service.create_scenario(
        db_session,
        ScenarioDefinitionCreate(
            slug="commodity-stress",
            name="Commodity stress",
            description="queda abrupta de minério e petróleo",
            scenario_type=ScenarioType.STRESS,
            shock_vector={"default_price_shock_pct": -0.1},
        ),
    )
    run = scenario_service.run_scenario(
        db_session,
        ScenarioRunRequest(
            portfolio_id=portfolio.id,
            reference_date=date(2026, 4, 28),
            scenario_slug=scenario.slug,
        ),
    )

    assert run.status.value == "succeeded"
    assert run.result_summary_json["projected_nav"] < 100000.0
