from __future__ import annotations

from typing import Any

from b3_quant_platform.economic_models_engine.base import BaseEconomicModel, EconomicModelFitResult, EconomicModelPrediction
from b3_quant_platform.economic_models_engine.utils import as_series, json_ready, require_arch_model, scalar
from b3_quant_platform.models.enums import EconomicModelName


class GarchEgarchModel(BaseEconomicModel):
    model_name = EconomicModelName.GARCH

    def __init__(self, *, window, config: dict[str, Any] | None = None) -> None:
        super().__init__(window=window, config=config)
        self._result: Any | None = None

    def fit(self, inputs: dict[str, Any]) -> EconomicModelFitResult:
        returns = as_series("returns", inputs["returns"]) * 100.0
        model_family = str(inputs.get("model_family", self.config.get("model_family", "garch"))).lower()
        p_order = int(inputs.get("p_order", self.config.get("p_order", 1)))
        q_order = int(inputs.get("q_order", self.config.get("q_order", 1)))
        distribution = str(inputs.get("distribution", self.config.get("distribution", "normal"))).lower()
        model_name = EconomicModelName.EGARCH if model_family == "egarch" else EconomicModelName.GARCH
        arch_model = require_arch_model()
        if model_family == "egarch":
            model = arch_model(returns, vol="EGARCH", p=p_order, q=q_order, dist=distribution)
        else:
            model = arch_model(returns, vol="GARCH", p=p_order, q=q_order, dist=distribution)
        result = model.fit(disp="off")
        self._result = result
        params = {key: scalar(value) for key, value in result.params.items()}
        persistence = params.get("alpha[1]", 0.0) + params.get("beta[1]", 0.0)
        explanation = {
            "inputs": {
                "returns": "historical return series in decimal form",
                "model_family": "garch or egarch to model volatility clustering and leverage",
            },
            "outputs": {
                "conditional_volatility": "forecasted sigma for each forward step",
                "persistence": "sum of ARCH and GARCH terms as a proxy for volatility memory",
                "leverage_term": "asymmetric volatility response captured by EGARCH gamma",
            },
        }
        self.model_name = model_name
        return self._set_fit_result(
            sample_size=len(returns),
            parameters={
                "model_family": model_name.value,
                "params": params,
            },
            diagnostics={
                "aic": scalar(result.aic),
                "bic": scalar(result.bic),
                "persistence": persistence,
                "leverage_term": params.get("gamma[1]", 0.0),
            },
            state={
                "model_family": model_name.value,
                "params": params,
                "persistence": persistence,
                "leverage_term": params.get("gamma[1]", 0.0),
            },
            explanation=explanation,
        )

    def predict(self, inputs: dict[str, Any]) -> EconomicModelPrediction:
        self._require_fitted()
        if self._result is None:
            raise RuntimeError("garch/egarch fitted state is unavailable for prediction")
        result = self._result
        horizon = int(inputs.get("forecast_horizon", self.config.get("forecast_horizon", 5)))
        forecast = result.forecast(horizon=horizon, reindex=False)
        variance_row = forecast.variance.iloc[-1]
        rows = []
        for step in range(horizon):
            variance = scalar(variance_row.iloc[step])
            rows.append(
                {
                    "forecast_step": step + 1,
                    "conditional_volatility": variance ** 0.5 / 100.0,
                    "variance": variance / 10000.0,
                }
            )
        return EconomicModelPrediction(
            model_name=self.model_name,
            window=self.window,
            outputs={
                "model_family": self._serialized_state["model_family"],
                "volatility_forecast": rows,
                "persistence": self._serialized_state["persistence"],
                "leverage_term": self._serialized_state["leverage_term"],
            },
            diagnostics=json_ready(self._fit_result.diagnostics if self._fit_result is not None else {}),
        )

    def explain(self) -> dict[str, Any]:
        self._require_fitted()
        return json_ready(self._explanation)