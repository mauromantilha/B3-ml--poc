from __future__ import annotations

from datetime import date

from b3_quant_platform.core.db import get_session_factory
from b3_quant_platform.schemas.economic_models import EconomicModelsJobRequest
from b3_quant_platform.services.economic_models_engine import EconomicModelsEngineService


def main() -> None:
    payload = EconomicModelsJobRequest.model_validate(
        {
            "reference_date": date(2026, 4, 28),
            "window": "medium_term",
            "capm": {
                "asset_identifier": "VALE3",
                "market_identifier": "IBOV",
                "asset_returns": [0.01, 0.012, 0.011, 0.013, 0.014, 0.012],
                "market_returns": [0.008, 0.009, 0.007, 0.01, 0.011, 0.009],
                "risk_free_rate": 0.001,
            },
            "multiples": {
                "asset_identifier": "VALE3",
                "comparables": [{"ev_ebitda": 8.0, "pe": 12.0}, {"ev_ebitda": 9.0, "pe": 13.0}],
                "fundamentals": {"ebitda": 100.0, "net_income": 45.0},
                "net_debt": 120.0,
                "shares_outstanding": 10.0,
            },
            "dcf": {
                "asset_identifier": "VALE3",
                "projected_cash_flows": [18.0, 21.0, 24.0, 27.0, 29.0],
                "discount_rate": 0.10,
                "terminal_growth_rate": 0.03,
                "net_debt": 50.0,
                "shares_outstanding": 10.0,
            },
        }
    )

    service = EconomicModelsEngineService()
    session = get_session_factory()()
    try:
        result = service.run(session, payload)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(result.model_dump(mode="json"))


if __name__ == "__main__":
    main()