from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.api.main import app
from b3_quant_platform.models.enums import EventScope, EventType, MacroFactor, ScenarioType
from b3_quant_platform.schemas.portfolio import PortfolioInstanceCreate
from b3_quant_platform.schemas.scenario import CounterfactualRunRequest, EventCatalogCreate, EventImpactProfileCreate, EventScenarioFromEventCreate
from b3_quant_platform.services.event_catalog import EventCatalogService
from b3_quant_platform.services.portfolio_factory import PortfolioFactoryService


def _create_portfolio(db_session):
    portfolio_service = PortfolioFactoryService()
    portfolio_service.seed_default_templates(db_session)
    template = portfolio_service.list_templates(db_session)[0]
    return portfolio_service.create_instance(
        db_session,
        PortfolioInstanceCreate(
            template_id=template.id,
            name="Event Book",
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


def test_event_to_shock_vector_respects_company_scope(db_session) -> None:
    service = EventCatalogService()
    event = service.create_event(
        db_session,
        EventCatalogCreate(
            code="americanas-credit-2023",
            name="Americanas Credit 2023",
            description="Stress de crédito após evento corporativo.",
            event_type=EventType.REBAIXAMENTO_RATING,
            event_date=date(2023, 1, 12),
            scope=EventScope.EMPRESA,
            scope_reference="AMER3",
            severity=5,
            expected_duration_days=90,
            confidence=Decimal("0.92"),
            macro_factors=[{"factor": MacroFactor.CREDITO, "shock_bps": Decimal("250")}],
            affected_assets=[{"asset_identifier": "AMER3", "asset_type": "equity", "mapping_scope": EventScope.EMPRESA, "is_primary": True}],
        ),
    )
    profile = service.add_impact_profile(
        db_session,
        event.id,
        EventImpactProfileCreate(
            profile_name="credit-shock",
            shock_template={"default_price_shock_pct": -0.15, "ticker_overrides": {"AMER3": -0.35}},
            macro_factors=[{"factor": MacroFactor.CREDITO, "shock_bps": Decimal("300")}],
            confidence=Decimal("0.95"),
            expected_duration_days=120,
        ),
    )

    shock = service.event_to_shock_vector(db_session, event.id, impact_profile_id=profile.id)

    assert shock["scope"] == EventScope.EMPRESA
    assert shock["shock_vector"]["default_price_shock_pct"] == 0.0
    assert shock["shock_vector"]["ticker_overrides"]["AMER3"] == -0.35
    assert "credito" in shock["shock_vector"]["macro_factor_shocks"]


def test_create_scenario_from_event_and_run_counterfactual(db_session) -> None:
    portfolio = _create_portfolio(db_session)
    service = EventCatalogService()
    event = service.create_event(
        db_session,
        EventCatalogCreate(
            code="vale-accident",
            name="Vale Accident",
            description="Choque operacional em mineração.",
            event_type=EventType.ACIDENTE_CORPORATIVO,
            event_date=date(2026, 4, 28),
            scope=EventScope.EMPRESA,
            scope_reference="VALE3",
            severity=4,
            expected_duration_days=45,
            confidence=Decimal("0.88"),
            macro_factors=[{"factor": MacroFactor.COMMODITIES, "shock_pct": Decimal("-0.07")}],
            affected_assets=[{"asset_identifier": "VALE3", "asset_type": "equity", "mapping_scope": EventScope.EMPRESA, "is_primary": True}],
        ),
    )
    profile = service.add_impact_profile(
        db_session,
        event.id,
        EventImpactProfileCreate(
            profile_name="operational",
            shock_template={"ticker_overrides": {"VALE3": -0.2}},
            confidence=Decimal("0.9"),
            expected_duration_days=60,
        ),
    )
    scenario = service.create_scenario_from_event(
        db_session,
        EventScenarioFromEventCreate(
            event_id=event.id,
            impact_profile_id=profile.id,
            scenario_type=ScenarioType.CONTRAFACTUAL,
            assumptions={"recovery_window_days": 30},
        ),
    )
    run = service.run_counterfactual(
        db_session,
        CounterfactualRunRequest(
            portfolio_id=portfolio.id,
            reference_date=date(2026, 4, 28),
            scenario_slug=scenario.slug,
            assumptions={"shock_multiplier": 1.1},
        ),
    )

    assert scenario.scope == EventScope.EMPRESA
    assert run.counterfactual_nav < run.baseline_nav
    assert run.result_summary_json["position_impacts"][0]["ticker"] == "VALE3"


def test_event_routes_create_event_and_counterfactual_run(db_session) -> None:
    portfolio = _create_portfolio(db_session)

    def override_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    try:
        create_event = client.post(
            "/v1/events",
            json={
                "code": "election-2026",
                "name": "Election 2026",
                "description": "Choque político doméstico.",
                "event_type": "eleicao",
                "event_date": "2026-04-28",
                "scope": "brasil",
                "scope_reference": "BR",
                "severity": 4,
                "expected_duration_days": 30,
                "confidence": 0.84,
                "macro_factors": [{"factor": "juros", "shock_bps": 80}],
                "affected_assets": [{"asset_identifier": "VALE3", "asset_type": "equity", "mapping_scope": "empresa", "is_primary": True}],
            },
        )
        event_id = create_event.json()["id"]
        add_profile = client.post(
            f"/v1/events/{event_id}/impact-profiles",
            json={
                "profile_name": "base-election",
                "shock_template": {"default_price_shock_pct": -0.08, "ticker_overrides": {"VALE3": -0.12}},
                "macro_factors": [{"factor": "juros", "shock_bps": 100}],
                "confidence": 0.88,
                "expected_duration_days": 45,
            },
        )
        profile_id = add_profile.json()["id"]
        shock_vector = client.get(f"/v1/events/{event_id}/shock-vector", params={"impact_profile_id": profile_id})
        create_scenario = client.post(
            "/v1/scenarios/from-event",
            json={
                "event_id": event_id,
                "impact_profile_id": profile_id,
                "scenario_type": "counterfactual",
                "assumptions": {"second_round": True},
            },
        )
        scenario_slug = create_scenario.json()["slug"]
        counterfactual = client.post(
            "/v1/scenarios/counterfactual-run",
            json={
                "portfolio_id": str(portfolio.id),
                "reference_date": "2026-04-28",
                "scenario_slug": scenario_slug,
                "assumptions": {"shock_multiplier": 1.05},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert create_event.status_code == 201
    assert add_profile.status_code == 201
    assert shock_vector.status_code == 200
    assert create_scenario.status_code == 201
    assert counterfactual.status_code == 202
    assert Decimal(counterfactual.json()["delta_pnl"]) < 0