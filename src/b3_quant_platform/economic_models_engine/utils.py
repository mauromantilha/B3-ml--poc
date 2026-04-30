from __future__ import annotations

import importlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd


def as_series(name: str, values: Any) -> pd.Series:
    if isinstance(values, pd.Series):
        series = values.astype(float)
    else:
        series = pd.Series(list(values), name=name, dtype="float64")
    if series.empty:
        raise ValueError(f"{name} cannot be empty")
    return series.reset_index(drop=True)


def as_frame(values: dict[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame({key: as_series(key, series) for key, series in values.items()})
    if frame.empty:
        raise ValueError("factor matrix cannot be empty")
    return frame.dropna(axis=0, how="any").reset_index(drop=True)


def align_series(**series_map: Any) -> pd.DataFrame:
    frame = pd.DataFrame({name: as_series(name, values) for name, values in series_map.items()})
    frame = frame.dropna(axis=0, how="any").reset_index(drop=True)
    if frame.empty:
        raise ValueError("aligned series cannot be empty after removing missing values")
    return frame


def require_statsmodels() -> Any:
    try:
        return importlib.import_module("statsmodels.api")
    except ModuleNotFoundError as exc:
        raise RuntimeError("statsmodels is required for OLS and ARIMA/SARIMA models") from exc


def require_sarimax() -> Any:
    try:
        return importlib.import_module("statsmodels.tsa.statespace.sarimax")
    except ModuleNotFoundError as exc:
        raise RuntimeError("statsmodels is required for ARIMA/SARIMA models") from exc


def require_arch_model() -> Any:
    try:
        module = importlib.import_module("arch")
    except ModuleNotFoundError as exc:
        raise RuntimeError("arch is required for GARCH/EGARCH models") from exc
    return module.arch_model


def json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, pd.Series):
        return [json_ready(item) for item in value.tolist()]
    if isinstance(value, pd.DataFrame):
        return [{key: json_ready(item) for key, item in row.items()} for row in value.to_dict(orient="records")]
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if hasattr(value, "tolist"):
        return json_ready(value.tolist())
    return value


def scalar(value: Any) -> float:
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)