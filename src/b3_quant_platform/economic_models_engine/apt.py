from __future__ import annotations

from typing import Any

from b3_quant_platform.economic_models_engine.base import BaseEconomicModel, EconomicModelFitResult, EconomicModelPrediction
from b3_quant_platform.economic_models_engine.utils import as_frame, as_series, json_ready, require_statsmodels, scalar
from b3_quant_platform.models.enums import EconomicModelName


class AptMultiFactorModel(BaseEconomicModel):
    model_name = EconomicModelName.APT_MULTIFACTOR

    def fit(self, inputs: dict[str, Any]) -> EconomicModelFitResult:
        asset_returns = as_series("asset_returns", inputs["asset_returns"])
        factor_frame = as_frame(inputs["factor_returns"])
        frame = factor_frame.copy()
        frame["asset_returns"] = asset_returns.iloc[: len(factor_frame)].reset_index(drop=True)
        frame = frame.dropna(axis=0, how="any").reset_index(drop=True)
        if frame.empty:
            raise ValueError("factor returns and asset returns must overlap")
        y = frame.pop("asset_returns")
        statsmodels = require_statsmodels()
        regression = statsmodels.OLS(y, statsmodels.add_constant(frame)).fit()
        factor_loadings = {name: scalar(value) for name, value in regression.params.items() if name != "const"}
        factor_premia = {name: scalar(frame[name].mean()) for name in frame.columns}
        expected_return = scalar(regression.params.loc["const"]) + sum(
            factor_loadings[name] * factor_premia[name] for name in factor_loadings
        )
        explanation = {
            "inputs": {
                "asset_returns": "historical asset return series",
                "factor_returns": "dictionary of factor return series such as market, size, value or macro shocks",
            },
            "outputs": {
                "factor_loadings": "estimated exposure of the asset to each factor",
                "factor_premia": "mean premium contributed by each factor in the selected window",
                "expected_return": "APT-implied return built from alpha plus factor premia",
            },
        }
        return self._set_fit_result(
            sample_size=len(frame),
            parameters={
                "alpha": scalar(regression.params.loc["const"]),
                "factor_loadings": factor_loadings,
                "factor_premia": factor_premia,
                "expected_return": expected_return,
            },
            diagnostics={
                "r_squared": scalar(regression.rsquared),
                "adjusted_r_squared": scalar(regression.rsquared_adj),
                "residual_volatility": scalar(regression.resid.std(ddof=1)),
                "factor_t_stats": {name: scalar(value) for name, value in regression.tvalues.items() if name != "const"},
            },
            state={
                "alpha": scalar(regression.params.loc["const"]),
                "factor_loadings": factor_loadings,
                "factor_premia": factor_premia,
            },
            explanation=explanation,
        )

    def predict(self, inputs: dict[str, Any]) -> EconomicModelPrediction:
        self._require_fitted()
        factor_projection = inputs.get("factor_projection", self._serialized_state["factor_premia"])
        expected_return = self._serialized_state["alpha"]
        contributions: dict[str, float] = {}
        for factor_name, loading in self._serialized_state["factor_loadings"].items():
            premium = scalar(factor_projection.get(factor_name, 0.0))
            contribution = loading * premium
            expected_return += contribution
            contributions[factor_name] = contribution
        return EconomicModelPrediction(
            model_name=self.model_name,
            window=self.window,
            outputs={
                "expected_return": expected_return,
                "alpha": self._serialized_state["alpha"],
                "factor_contributions": contributions,
                "factor_loadings": self._serialized_state["factor_loadings"],
            },
            diagnostics=json_ready(self._fit_result.diagnostics if self._fit_result is not None else {}),
        )

    def explain(self) -> dict[str, Any]:
        self._require_fitted()
        return json_ready(self._explanation)