from __future__ import annotations

from datetime import date
from decimal import Decimal

from b3_quant_platform.schemas.portfolio import PortfolioInstanceCreate
from b3_quant_platform.services.portfolio_factory import PortfolioFactoryService


def test_seed_templates_and_create_portfolio(db_session) -> None:
    service = PortfolioFactoryService()
    created, skipped, _ = service.seed_default_templates(db_session)
    templates = service.list_templates(db_session)

    assert created >= 1 or skipped >= 1
    assert len(templates) >= 4

    template = templates[0]
    portfolio = service.create_instance(
        db_session,
        PortfolioInstanceCreate(
            template_id=template.id,
            name="Income Sleeve BR",
            reference_date=date(2026, 4, 28),
            seed_capital=Decimal("100000.00"),
            positions=[
                {
                    "ticker": "VALE3",
                    "market": "equities",
                    "target_weight": "0.40",
                    "quantity": "100",
                    "close_price": "60.00",
                    "signal": {"alpha": 0.12},
                },
                {
                    "ticker": "PETR4",
                    "market": "equities",
                    "target_weight": "0.60",
                    "quantity": "150",
                    "close_price": "35.00",
                    "signal": {"alpha": 0.09},
                },
            ],
        ),
    )

    assert portfolio.name == "Income Sleeve BR"
    assert len(portfolio.positions) == 2
