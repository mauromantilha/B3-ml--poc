from __future__ import annotations

from statistics import median
from typing import Any

from b3_quant_platform.economic_models_engine.base import BaseEconomicModel, EconomicModelFitResult, EconomicModelPrediction
from b3_quant_platform.economic_models_engine.utils import json_ready, scalar
from b3_quant_platform.models.enums import EconomicModelName


class RelativeValuationModel(BaseEconomicModel):
    model_name = EconomicModelName.MULTIPLES

    FUNDAMENTAL_FIELDS = {
        "ev_ebitda": "ebitda",
        "ev_sales": "revenue",
        "pe": "net_income",
        "pb": "book_value",
    }

    def fit(self, inputs: dict[str, Any]) -> EconomicModelFitResult:
        comparables = list(inputs["comparables"])
        if not comparables:
            raise ValueError("comparables cannot be empty for multiples valuation")
        multiples_by_metric: dict[str, list[float]] = {}
        for comparable in comparables:
            for metric_name, metric_value in comparable.items():
                multiples_by_metric.setdefault(metric_name, []).append(scalar(metric_value))
        median_multiples = {
            metric_name: float(median(values)) for metric_name, values in multiples_by_metric.items() if values
        }
        explanation = {
            "inputs": {
                "comparables": "peer group trading multiples",
                "fundamentals": "issuer fundamentals aligned with each multiple denominator",
            },
            "outputs": {
                "median_multiples": "central peer multiples used as baseline",
                "implied_enterprise_value": "enterprise value implied by EV-based multiples",
                "implied_equity_value": "equity value implied after debt and cash adjustments",
            },
        }
        return self._set_fit_result(
            sample_size=len(comparables),
            parameters={"median_multiples": median_multiples},
            diagnostics={"peer_count": len(comparables)},
            state={"median_multiples": median_multiples},
            explanation=explanation,
        )

    def predict(self, inputs: dict[str, Any]) -> EconomicModelPrediction:
        self._require_fitted()
        fundamentals = dict(inputs["fundamentals"])
        net_debt = scalar(inputs.get("net_debt", 0.0))
        shares_outstanding = scalar(inputs.get("shares_outstanding", 1.0))
        rows = []
        enterprise_value_estimates: list[float] = []
        equity_value_estimates: list[float] = []
        per_share_estimates: list[float] = []

        for metric_name, multiple in self._serialized_state["median_multiples"].items():
            denominator_key = self.FUNDAMENTAL_FIELDS.get(metric_name)
            if denominator_key is None or denominator_key not in fundamentals:
                continue
            denominator_value = scalar(fundamentals[denominator_key])
            implied_metric_value = multiple * denominator_value
            if metric_name.startswith("ev_"):
                enterprise_value = implied_metric_value
                equity_value = enterprise_value - net_debt
            else:
                equity_value = implied_metric_value
                enterprise_value = equity_value + net_debt
            intrinsic_per_share = equity_value / shares_outstanding
            enterprise_value_estimates.append(enterprise_value)
            equity_value_estimates.append(equity_value)
            per_share_estimates.append(intrinsic_per_share)
            rows.append(
                {
                    "metric_name": metric_name,
                    "applied_multiple": multiple,
                    "denominator_key": denominator_key,
                    "denominator_value": denominator_value,
                    "implied_enterprise_value": enterprise_value,
                    "implied_equity_value": equity_value,
                    "intrinsic_value_per_share": intrinsic_per_share,
                }
            )

        aggregate = {
            "enterprise_value": sum(enterprise_value_estimates) / len(enterprise_value_estimates) if enterprise_value_estimates else 0.0,
            "equity_value": sum(equity_value_estimates) / len(equity_value_estimates) if equity_value_estimates else 0.0,
            "intrinsic_value_per_share": sum(per_share_estimates) / len(per_share_estimates) if per_share_estimates else 0.0,
        }
        return EconomicModelPrediction(
            model_name=self.model_name,
            window=self.window,
            outputs={
                "valuation_rows": rows,
                "aggregate": aggregate,
            },
            diagnostics=json_ready(self._fit_result.diagnostics if self._fit_result is not None else {}),
        )

    def explain(self) -> dict[str, Any]:
        self._require_fitted()
        return json_ready(self._explanation)