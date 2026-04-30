from __future__ import annotations

from typing import Any

from b3_quant_platform.economic_models_engine.base import BaseEconomicModel, EconomicModelFitResult, EconomicModelPrediction
from b3_quant_platform.economic_models_engine.utils import json_ready, scalar
from b3_quant_platform.models.enums import EconomicModelName


class DiscountedCashFlowModel(BaseEconomicModel):
    model_name = EconomicModelName.DISCOUNTED_CASH_FLOW

    def fit(self, inputs: dict[str, Any]) -> EconomicModelFitResult:
        projected_cash_flows = [scalar(value) for value in inputs["projected_cash_flows"]]
        if not projected_cash_flows:
            raise ValueError("projected_cash_flows cannot be empty")
        discount_rate = scalar(inputs["discount_rate"])
        terminal_growth_rate = scalar(inputs.get("terminal_growth_rate", 0.0))
        if discount_rate <= terminal_growth_rate:
            raise ValueError("discount_rate must be greater than terminal_growth_rate")
        explanation = {
            "inputs": {
                "projected_cash_flows": "explicit short, medium and long-term forecast cash flows",
                "discount_rate": "WACC or required return used to discount future cash flows",
                "terminal_growth_rate": "perpetual growth applied after the explicit horizon",
            },
            "outputs": {
                "enterprise_value": "present value of explicit and terminal cash flows",
                "equity_value": "enterprise value adjusted for net debt and non-operating items",
                "intrinsic_value_per_share": "equity value divided by diluted shares outstanding",
            },
        }
        return self._set_fit_result(
            sample_size=len(projected_cash_flows),
            parameters={
                "discount_rate": discount_rate,
                "terminal_growth_rate": terminal_growth_rate,
                "projected_cash_flows": projected_cash_flows,
            },
            diagnostics={"projection_years": len(projected_cash_flows)},
            state={
                "discount_rate": discount_rate,
                "terminal_growth_rate": terminal_growth_rate,
                "projected_cash_flows": projected_cash_flows,
            },
            explanation=explanation,
        )

    def predict(self, inputs: dict[str, Any]) -> EconomicModelPrediction:
        self._require_fitted()
        projected_cash_flows = [scalar(value) for value in inputs.get("projected_cash_flows", self._serialized_state["projected_cash_flows"])]
        discount_rate = scalar(inputs.get("discount_rate", self._serialized_state["discount_rate"]))
        terminal_growth_rate = scalar(inputs.get("terminal_growth_rate", self._serialized_state["terminal_growth_rate"]))
        net_debt = scalar(inputs.get("net_debt", 0.0))
        shares_outstanding = scalar(inputs.get("shares_outstanding", 1.0))

        present_values = []
        for index, cash_flow in enumerate(projected_cash_flows, start=1):
            present_values.append(cash_flow / ((1.0 + discount_rate) ** index))

        terminal_cash_flow = projected_cash_flows[-1] * (1.0 + terminal_growth_rate)
        terminal_value = terminal_cash_flow / (discount_rate - terminal_growth_rate)
        terminal_present_value = terminal_value / ((1.0 + discount_rate) ** len(projected_cash_flows))
        enterprise_value = sum(present_values) + terminal_present_value
        equity_value = enterprise_value - net_debt
        intrinsic_value_per_share = equity_value / shares_outstanding

        return EconomicModelPrediction(
            model_name=self.model_name,
            window=self.window,
            outputs={
                "present_value_schedule": present_values,
                "terminal_value": terminal_value,
                "terminal_present_value": terminal_present_value,
                "enterprise_value": enterprise_value,
                "equity_value": equity_value,
                "intrinsic_value_per_share": intrinsic_value_per_share,
            },
            diagnostics=json_ready(self._fit_result.diagnostics if self._fit_result is not None else {}),
        )

    def explain(self) -> dict[str, Any]:
        self._require_fitted()
        return json_ready(self._explanation)