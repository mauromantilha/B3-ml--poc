from __future__ import annotations

from typing import Any

from b3_quant_platform.economic_models_engine.base import BaseEconomicModel, EconomicModelFitResult, EconomicModelPrediction
from b3_quant_platform.economic_models_engine.utils import as_series, json_ready, require_sarimax, scalar
from b3_quant_platform.models.enums import EconomicModelName


class ArimaSarimaModel(BaseEconomicModel):
    model_name = EconomicModelName.ARIMA

    def __init__(self, *, window, config: dict[str, Any] | None = None) -> None:
        super().__init__(window=window, config=config)
        self._result: Any | None = None

    def fit(self, inputs: dict[str, Any]) -> EconomicModelFitResult:
        series = as_series("time_series", inputs["time_series"])
        order = tuple(inputs.get("order", self.config.get("order", (1, 0, 0))))
        seasonal_order = tuple(inputs.get("seasonal_order", self.config.get("seasonal_order", (0, 0, 0, 0))))
        sarimax = require_sarimax()
        model = sarimax.SARIMAX(
            series,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        result = model.fit(disp=False)
        self._result = result
        self.model_name = EconomicModelName.SARIMA if seasonal_order[-1] else EconomicModelName.ARIMA
        explanation = {
            "inputs": {
                "time_series": "ordered return, spread or valuation series",
                "order": "(p, d, q) short-memory structure",
                "seasonal_order": "(P, D, Q, s) seasonal structure for SARIMA",
            },
            "outputs": {
                "forecast_mean": "point forecast for the requested steps",
                "confidence_interval": "forecast interval around the point estimate",
                "aic": "information criterion for model selection",
            },
        }
        return self._set_fit_result(
            sample_size=len(series),
            parameters={
                "order": order,
                "seasonal_order": seasonal_order,
                "params": {name: scalar(value) for name, value in result.params.items()},
            },
            diagnostics={
                "aic": scalar(result.aic),
                "bic": scalar(result.bic),
                "sigma2": scalar(result.params.get("sigma2", 0.0)),
            },
            state={
                "order": order,
                "seasonal_order": seasonal_order,
                "params": {name: scalar(value) for name, value in result.params.items()},
                "last_value": scalar(series.iloc[-1]),
                "aic": scalar(result.aic),
                "bic": scalar(result.bic),
            },
            explanation=explanation,
        )

    def predict(self, inputs: dict[str, Any]) -> EconomicModelPrediction:
        self._require_fitted()
        if self._result is None:
            raise RuntimeError("arima/sarima fitted state is unavailable for prediction")
        result = self._result
        horizon = int(inputs.get("forecast_horizon", self.config.get("forecast_horizon", 5)))
        forecast_result = result.get_forecast(steps=horizon)
        confidence_interval = forecast_result.conf_int(alpha=inputs.get("alpha", 0.05))
        rows = []
        for step in range(horizon):
            rows.append(
                {
                    "forecast_step": step + 1,
                    "forecast_mean": scalar(forecast_result.predicted_mean.iloc[step]),
                    "lower_ci": scalar(confidence_interval.iloc[step, 0]),
                    "upper_ci": scalar(confidence_interval.iloc[step, 1]),
                }
            )
        return EconomicModelPrediction(
            model_name=self.model_name,
            window=self.window,
            outputs={
                "series_name": inputs.get("series_name", "time_series"),
                "forecasts": rows,
            },
            diagnostics={
                "aic": self._serialized_state["aic"],
                "bic": self._serialized_state["bic"],
            },
        )

    def explain(self) -> dict[str, Any]:
        self._require_fitted()
        return json_ready(self._explanation)