from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from b3_quant_platform.models.enums import EconomicModelName, EconomicModelWindow


@dataclass(slots=True)
class EconomicModelFitResult:
    model_name: EconomicModelName
    window: EconomicModelWindow
    sample_size: int
    parameters: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["model_name"] = self.model_name.value
        payload["window"] = self.window.value
        return payload


@dataclass(slots=True)
class EconomicModelPrediction:
    model_name: EconomicModelName
    window: EconomicModelWindow
    outputs: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["model_name"] = self.model_name.value
        payload["window"] = self.window.value
        return payload


class BaseEconomicModel(ABC):
    model_name: EconomicModelName

    def __init__(
        self,
        *,
        window: EconomicModelWindow = EconomicModelWindow.SHORT_TERM,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.window = window
        self.config = config or {}
        self._fit_result: EconomicModelFitResult | None = None
        self._explanation: dict[str, Any] = {}
        self._serialized_state: dict[str, Any] = {}

    @property
    def is_fitted(self) -> bool:
        return self._fit_result is not None

    @abstractmethod
    def fit(self, inputs: dict[str, Any]) -> EconomicModelFitResult:
        raise NotImplementedError

    @abstractmethod
    def predict(self, inputs: dict[str, Any]) -> EconomicModelPrediction:
        raise NotImplementedError

    @abstractmethod
    def explain(self) -> dict[str, Any]:
        raise NotImplementedError

    def serialize(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name.value,
            "window": self.window.value,
            "config": self.config,
            "fit_result": self._fit_result.to_dict() if self._fit_result is not None else None,
            "state": self._serialized_state,
            "explanation": self._explanation,
        }

    def _require_fitted(self) -> None:
        if not self.is_fitted:
            raise RuntimeError(f"{self.model_name.value} must be fitted before prediction")

    def _set_fit_result(
        self,
        *,
        sample_size: int,
        parameters: dict[str, Any] | None = None,
        diagnostics: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
        explanation: dict[str, Any] | None = None,
    ) -> EconomicModelFitResult:
        self._fit_result = EconomicModelFitResult(
            model_name=self.model_name,
            window=self.window,
            sample_size=sample_size,
            parameters=parameters or {},
            diagnostics=diagnostics or {},
        )
        self._serialized_state = state or {}
        self._explanation = explanation or {}
        return self._fit_result