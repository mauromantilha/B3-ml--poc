from __future__ import annotations

from enum import StrEnum


class PortfolioObjective(StrEnum):
    INCOME = "income"
    GROWTH = "growth"
    DEFENSIVE = "defensive"
    HEDGE = "hedge"
    FACTOR = "factor"


class PortfolioStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ScenarioType(StrEnum):
    EXOGENOUS = "exogenous"
    CONTRAFACTUAL = "counterfactual"
    STRESS = "stress"
    REGIME = "regime"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ComparisonVerdict(StrEnum):
    OUTPERFORMED = "outperformed"
    UNDERPERFORMED = "underperformed"
    INLINE = "inline"


class UserRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    SERVICE = "service"


class ConstraintType(StrEnum):
    HARD_LIMIT = "hard_limit"
    SOFT_LIMIT = "soft_limit"
    LIQUIDITY = "liquidity"
    EXPOSURE = "exposure"
    CUSTOM = "custom"


class EventType(StrEnum):
    CRISE_BANCARIA = "crise_bancaria"
    ACIDENTE_CORPORATIVO = "acidente_corporativo"
    CHOQUE_POLITICO = "choque_politico"
    ELEICAO = "eleicao"
    MUDANCA_REGULATORIA = "mudanca_regulatoria"
    REBAIXAMENTO_RATING = "rebaixamento_rating"
    DESASTRE_OPERACIONAL = "desastre_operacional"
    CHOQUE_JUROS = "choque_juros"
    CHOQUE_CAMBIAL = "choque_cambial"
    CHOQUE_SETORIAL = "choque_setorial"
    MACRO = "macro"
    MARKET = "market"
    CORPORATE = "corporate"
    POLICY = "policy"


class EventScope(StrEnum):
    EMPRESA = "empresa"
    SETOR = "setor"
    INDICE = "indice"
    BRASIL = "brasil"
    GLOBAL = "global"


class MacroFactor(StrEnum):
    JUROS = "juros"
    CAMBIO = "cambio"
    INFLACAO = "inflacao"
    RISCO_PAIS = "risco_pais"
    LIQUIDEZ = "liquidez"
    CREDITO = "credito"
    COMMODITIES = "commodities"
    EQUITY_RISK = "equity_risk"


class JobTarget(StrEnum):
    API = "api"
    WORKER_INGESTION = "worker-ingestion"
    WORKER_FEATURE_STORE = "worker-feature-store"
    WORKER_FORECAST = "worker-forecast"
    WORKER_SIMULATION = "worker-simulation"
    WORKER_EOD = "worker-eod"
    DASHBOARD_STREAMLIT = "dashboard-streamlit"


class EconomicModelName(StrEnum):
    CAPM = "capm"
    APT_MULTIFACTOR = "apt_multifactor"
    ARIMA = "arima"
    SARIMA = "sarima"
    GARCH = "garch"
    EGARCH = "egarch"
    MULTIPLES = "valuation_multiples"
    DISCOUNTED_CASH_FLOW = "discounted_cash_flow"


class EconomicModelWindow(StrEnum):
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
