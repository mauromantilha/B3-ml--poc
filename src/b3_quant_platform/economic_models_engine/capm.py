from __future__ import annotations

from typing import Any

from b3_quant_platform.economic_models_engine.base import BaseEconomicModel, EconomicModelFitResult, EconomicModelPrediction
from b3_quant_platform.economic_models_engine.utils import align_series, json_ready, require_statsmodels, scalar
from b3_quant_platform.models.enums import EconomicModelName


class CapmModel(BaseEconomicModel):
    model_name = EconomicModelName.CAPM

    def fit(self, inputs: dict[str, Any]) -> EconomicModelFitResult:
        risk_free_rate = inputs.get("risk_free_rate", 0.0)
        if isinstance(risk_free_rate, (int, float)):
            risk_free_rate = [float(risk_free_rate)] * len(inputs["asset_returns"])
        frame = align_series(
            asset_returns=inputs["asset_returns"],
            market_returns=inputs["market_returns"],
            risk_free_rate=risk_free_rate,
        )
        asset_excess = frame["asset_returns"] - frame["risk_free_rate"]
        market_excess = frame["market_returns"] - frame["risk_free_rate"]
        statsmodels = require_statsmodels()
        regression = statsmodels.OLS(asset_excess, statsmodels.add_constant(market_excess)).fit()
        alpha = scalar(regression.params.iloc[0])
        beta = scalar(regression.params.iloc[1])
        expected_market_return = scalar(frame["market_returns"].mean())
        expected_risk_free_rate = scalar(frame["risk_free_rate"].mean())
        expected_return = expected_risk_free_rate + alpha + beta * (expected_market_return - expected_risk_free_rate)
        explanation = {
            "inputs": {
                "asset_returns": "historical asset return series",
                "market_returns": "historical market benchmark return series",
                "risk_free_rate": "historical or constant risk free rate series",
            },
            "outputs": {
                "alpha": "risk-adjusted excess return unexplained by the market",
                "beta": "systematic sensitivity to the benchmark",
                "expected_return": "CAPM-implied return for the selected horizon",
            },
        }
        return self._set_fit_result(
            sample_size=len(frame),
            parameters={
                "alpha": alpha,
                "beta": beta,
                "expected_return": expected_return,
                "market_identifier": inputs.get("market_identifier", "market"),
            },
            diagnostics={
                "r_squared": scalar(regression.rsquared),
                "adjusted_r_squared": scalar(regression.rsquared_adj),
                "residual_volatility": scalar(regression.resid.std(ddof=1)),
                "alpha_t_stat": scalar(regression.tvalues.iloc[0]),
                "beta_t_stat": scalar(regression.tvalues.iloc[1]),
            },
            state={
                "alpha": alpha,
                "beta": beta,
                "expected_return": expected_return,
                "market_excess_mean": scalar(market_excess.mean()),
                "risk_free_rate_mean": expected_risk_free_rate,
            },
            explanation=explanation,
        )

    def predict(self, inputs: dict[str, Any]) -> EconomicModelPrediction:
        self._require_fitted()
        forecast_market_return = scalar(inputs.get("forecast_market_return", self._serialized_state["market_excess_mean"]))
        forecast_risk_free_rate = scalar(inputs.get("forecast_risk_free_rate", self._serialized_state["risk_free_rate_mean"]))
        expected_excess_return = self._serialized_state["alpha"] + self._serialized_state["beta"] * forecast_market_return
        expected_return = forecast_risk_free_rate + expected_excess_return
        return EconomicModelPrediction(
            model_name=self.model_name,
            window=self.window,
            outputs={
                "expected_return": expected_return,
                "expected_excess_return": expected_excess_return,
                "alpha": self._serialized_state["alpha"],
                "beta": self._serialized_state["beta"],
            },
            diagnostics=json_ready(self._fit_result.diagnostics if self._fit_result is not None else {}),
        )

    def explain(self) -> dict[str, Any]:
        self._require_fitted()
        return json_ready(self._explanation)