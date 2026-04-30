from __future__ import annotations

from datetime import date
from decimal import Decimal

from b3_quant_platform.models.enums import ComparisonVerdict, EventScope, EventType, JobTarget, PortfolioObjective, RunStatus, ScenarioType, UserRole
from b3_quant_platform.repositories.events import CounterfactualRunRepository, EventAssetMappingRepository, EventCatalogRepository, EventImpactProfileRepository, EventScenarioRepository, SimulationRunRepository
from b3_quant_platform.repositories.jobs import AuditLogRepository, JobExecutionRepository, SystemJobRepository
from b3_quant_platform.repositories.ml import EodComparisonRepository, ModelRegistryRepository, PredictionRunRepository, TrainingRunRepository
from b3_quant_platform.repositories.portfolio import PortfolioFamilyRepository, PortfolioInstanceRepository, PortfolioStrategyRepository
from b3_quant_platform.repositories.users import UserRepository


def create_portfolio_graph(db_session):
    user = UserRepository(db_session).create_user(
        email="integration@example.com",
        full_name="Integration User",
        role=UserRole.ADMIN,
    )
    family = PortfolioFamilyRepository(db_session).create_family(
        owner_user_id=user.id,
        slug="integration-family",
        name="Integration Family",
        objective=PortfolioObjective.GROWTH,
    )
    strategy = PortfolioStrategyRepository(db_session).create_strategy(
        family_id=family.id,
        created_by_user_id=user.id,
        slug="integration-strategy",
        name="Integration Strategy",
        objective=PortfolioObjective.GROWTH,
        benchmark_ticker="IBOV",
        risk_budget_bps=500,
        rebalance_rule={"cadence": "weekly"},
        constraints={"max_single_name": 0.1, "min_liquidity_brl": 20000000},
    )
    instance = PortfolioInstanceRepository(db_session).create_instance(
        template_id=strategy.id,
        family_id=family.id,
        name="Integration Portfolio",
        reference_date=date(2026, 4, 28),
        seed_capital=Decimal("1000000"),
        base_currency="BRL",
    )
    return user, family, strategy, instance


def test_portfolio_repositories_create_family_strategy_instance_and_valuation(db_session) -> None:
    _, family, strategy, instance = create_portfolio_graph(db_session)
    portfolio_repo = PortfolioInstanceRepository(db_session)

    position = portfolio_repo.upsert_position(
        portfolio_id=instance.id,
        reference_date=date(2026, 4, 28),
        ticker="VALE3",
        market="equities",
        target_weight=Decimal("0.35"),
        quantity=Decimal("1000"),
        close_price=Decimal("60.50"),
        signal_json={"alpha": 0.11},
    )
    valuation = portfolio_repo.upsert_daily_valuation(
        portfolio_id=instance.id,
        reference_date=date(2026, 4, 28),
        nav=Decimal("1005400"),
        gross_exposure=Decimal("1.0"),
        net_exposure=Decimal("1.0"),
        cash_balance=Decimal("12000"),
        pnl_daily=Decimal("5400"),
        drawdown_pct=Decimal("0.012"),
        valuation_json={"turnover": 0.08},
    )

    assert family.slug == "integration-family"
    assert strategy.slug == "integration-strategy"
    assert position.ticker == "VALE3"
    assert valuation.nav == Decimal("1005400")
    assert len(strategy.constraints) == 2


def test_event_and_simulation_repositories_link_to_portfolio_instance(db_session) -> None:
    _, _, _, instance = create_portfolio_graph(db_session)
    event_repo = EventCatalogRepository(db_session)
    mapping_repo = EventAssetMappingRepository(db_session)
    profile_repo = EventImpactProfileRepository(db_session)
    scenario_repo = EventScenarioRepository(db_session)
    simulation_repo = SimulationRunRepository(db_session)
    counterfactual_repo = CounterfactualRunRepository(db_session)

    event = event_repo.create_event(
        code="copom-hawkish",
        name="Copom Hawkish",
        description="Abertura de curva e compressão de múltiplos.",
        event_type=EventType.POLICY,
        event_date=date(2026, 4, 28),
        scope=EventScope.BRASIL,
        severity=4,
    )
    mapping = mapping_repo.create_mapping(
        event_id=event.id,
        asset_identifier="IBOV",
        asset_type="index",
        mapping_scope=EventScope.INDICE,
        weight=Decimal("1.0"),
        is_primary=True,
    )
    profile = profile_repo.create_profile(
        event_id=event.id,
        profile_name="hawkish-base",
        shock_template_json={"default_price_shock_pct": -0.05},
        macro_factors_json=[{"factor": "juros", "shock_bps": 100}],
    )
    scenario = scenario_repo.create_scenario(
        event_id=event.id,
        impact_profile_id=profile.id,
        slug="copom-hawkish-stress",
        name="Copom Hawkish Stress",
        description="Abertura de curva e compressão de múltiplos.",
        scenario_type=ScenarioType.STRESS,
        scope=EventScope.BRASIL,
        severity=4,
        expected_duration_days=15,
        confidence=Decimal("0.85"),
        affected_assets_json=[{"asset_identifier": "IBOV", "asset_type": "index"}],
        macro_factors_json=[{"factor": "juros", "shock_bps": 100}],
        shock_vector_json={"default_price_shock_pct": -0.05},
    )
    run = simulation_repo.create_run(
        scenario_id=scenario.id,
        portfolio_id=instance.id,
        reference_date=date(2026, 4, 28),
        status=RunStatus.SUCCEEDED,
        input_hash="integration-hash",
        result_summary_json={"projected_nav": 972000},
    )
    counterfactual = counterfactual_repo.create_run(
        event_id=event.id,
        scenario_id=scenario.id,
        portfolio_id=instance.id,
        reference_date=date(2026, 4, 28),
        status=RunStatus.SUCCEEDED,
        input_hash="integration-counterfactual-hash",
        baseline_nav=Decimal("1000000"),
        counterfactual_nav=Decimal("972000"),
        delta_pnl=Decimal("-28000"),
        shock_vector_json={"default_price_shock_pct": -0.05},
        result_summary_json={"projected_nav": 972000},
    )

    assert mapping.event_id == event.id
    assert profile.event_id == event.id
    assert scenario.event_id == event.id
    assert run.portfolio_id == instance.id
    assert run.status == RunStatus.SUCCEEDED
    assert counterfactual.event_id == event.id


def test_job_execution_repository_is_idempotent_and_audited(db_session) -> None:
    user, _, _, instance = create_portfolio_graph(db_session)
    jobs_repo = SystemJobRepository(db_session)
    execution_repo = JobExecutionRepository(db_session)
    audit_repo = AuditLogRepository(db_session)

    job = jobs_repo.upsert_system_job(
        job_name="eod-reconciliation",
        service_name=JobTarget.WORKER_EOD,
        schedule_cron="50 18 * * 1-5",
        config_json={"stage": "curated"},
    )
    first = execution_repo.begin_execution(
        system_job_id=job.id,
        job_name=job.job_name,
        reference_date=date(2026, 4, 28),
        idempotency_key="job-2026-04-28",
        status=RunStatus.RUNNING,
        payload_json={"portfolio_id": str(instance.id)},
    )
    second = execution_repo.begin_execution(
        system_job_id=job.id,
        job_name=job.job_name,
        reference_date=date(2026, 4, 28),
        idempotency_key="job-2026-04-28",
        status=RunStatus.RUNNING,
        payload_json={"portfolio_id": str(instance.id)},
    )
    audit_entry = audit_repo.append_log(
        actor_user_id=user.id,
        entity_type="job_execution",
        entity_id=first.id,
        action="started",
        request_id="req-001",
        trace_id="trace-001",
        after_json={"status": "running"},
    )

    assert first.id == second.id
    assert audit_entry.entity_id == first.id
    assert first.system_job_id == job.id


def test_model_training_prediction_and_eod_repositories(db_session) -> None:
    _, _, strategy, instance = create_portfolio_graph(db_session)
    model_repo = ModelRegistryRepository(db_session)
    training_repo = TrainingRunRepository(db_session)
    prediction_repo = PredictionRunRepository(db_session)
    eod_repo = EodComparisonRepository(db_session)

    model = model_repo.upsert_model(
        model_name="close-price-baseline",
        version="2026.04.28",
        objective="predict_expected_close",
        artifact_uri="r2://b3-poc/artifacts/model.keras",
        strategy_id=strategy.id,
        metrics_json={"mae": 0.82},
    )
    training = training_repo.create_training_run(
        model_id=model.id,
        strategy_id=strategy.id,
        reference_date=date(2026, 4, 28),
        dataset_fingerprint="dataset-fingerprint-example",
        artifact_uri=model.artifact_uri,
        status=RunStatus.SUCCEEDED,
        parameters_json={"epochs": 10},
        metrics_json={"loss": 0.21},
    )
    prediction = prediction_repo.upsert_prediction_run(
        model_id=model.id,
        training_run_id=training.id,
        portfolio_id=instance.id,
        reference_date=date(2026, 4, 28),
        horizon_days=1,
        status=RunStatus.SUCCEEDED,
        predictions_json={"VALE3": 61.2},
    )
    comparison = eod_repo.upsert_comparison(
        portfolio_id=instance.id,
        prediction_run_id=prediction.id,
        reference_date=date(2026, 4, 28),
        ticker="VALE3",
        scenario_slug="baseline",
        expected_close=Decimal("61.20"),
        actual_close=Decimal("60.50"),
        tracking_error_bps=Decimal("-114.38"),
        verdict=ComparisonVerdict.UNDERPERFORMED,
        comparison_details_json={"abs_delta": 0.70},
    )

    assert model.strategy_id == strategy.id
    assert training.model_id == model.id
    assert prediction.training_run_id == training.id
    assert comparison.prediction_run_id == prediction.id
