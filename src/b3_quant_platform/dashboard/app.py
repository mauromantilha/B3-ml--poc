from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

import httpx
import pandas as pd
import streamlit as st

API_BASE_URL = os.getenv("B3_CLOUD_RUN_BASE_URL", "http://localhost:8080")
API_PREFIX = os.getenv("B3_API_PREFIX", "/v1")
TIMEOUT = 30.0


def api_request(method: str, path: str, *, json_body: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    response = httpx.request(method, url, json=json_body, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=60)
def load_templates() -> list[dict[str, Any]]:
    return api_request("GET", f"{API_PREFIX}/templates")


@st.cache_data(ttl=60)
def load_portfolios() -> list[dict[str, Any]]:
    return api_request("GET", f"{API_PREFIX}/portfolios")


def main() -> None:
    st.set_page_config(page_title="B3 Multi-Portfolio Lab", layout="wide")
    st.title("B3 Multi-Portfolio Lab")
    st.caption("Factory de carteiras, laboratório de cenários e comparação EOD")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("API", API_BASE_URL)
    with col2:
        st.metric("Templates", len(load_templates()))
    with col3:
        st.metric("Portfólios", len(load_portfolios()))

    overview_tab, reconcile_tab, scenario_tab = st.tabs(["Overview", "EOD", "Cenários"])

    with overview_tab:
        if st.button("Seed default templates"):
            result = api_request("POST", f"{API_PREFIX}/templates/seed")
            st.success(json.dumps(result, ensure_ascii=False))
            load_templates.clear()

        templates = load_templates()
        portfolios = load_portfolios()
        st.subheader("Templates")
        st.dataframe(pd.DataFrame(templates), use_container_width=True)
        st.subheader("Portfólios")
        st.dataframe(pd.DataFrame(portfolios), use_container_width=True)

    with reconcile_tab:
        st.subheader("Comparação EOD")
        reference_date = st.date_input("Data de referência", value=date.today())
        portfolio_id = st.text_input("Portfolio ID")
        expected_prices_text = st.text_area(
            "Expected prices JSON",
            value=json.dumps(
                [
                    {"ticker": "VALE3", "expected_close": 61.2},
                    {"ticker": "PETR4", "expected_close": 37.45},
                ],
                indent=2,
            ),
            height=180,
        )
        scenario_slug = st.text_input("Scenario slug", value="baseline")

        if st.button("Run EOD reconcile"):
            payload = {
                "reference_date": reference_date.isoformat(),
                "portfolio_id": portfolio_id,
                "scenario_slug": scenario_slug,
                "expected_prices": json.loads(expected_prices_text),
            }
            result = api_request("POST", f"{API_PREFIX}/jobs/eod-reconcile", json_body=payload)
            st.json(result)

        if portfolio_id:
            if st.button("Load comparisons"):
                comparisons = api_request(
                    "GET",
                    f"{API_PREFIX}/eod/comparisons",
                    params={
                        "reference_date": reference_date.isoformat(),
                        "portfolio_id": portfolio_id,
                        "scenario_slug": scenario_slug,
                    },
                )
                st.dataframe(pd.DataFrame(comparisons), use_container_width=True)

    with scenario_tab:
        st.subheader("Stress, exógenos e contrafactuais")
        scenario_name = st.text_input("Scenario name", value="Selic shock")
        scenario_slug_input = st.text_input("Scenario slug", value="selic-shock")
        description = st.text_area("Descrição", value="Abertura de curva e queda de commodities")
        default_shock_pct = st.number_input("Default price shock pct", value=-0.08, step=0.01)
        active_portfolio_id = st.text_input("Portfolio ID para execução")
        run_date = st.date_input("Data do cenário", value=date.today(), key="scenario_date")

        if st.button("Create scenario"):
            payload = {
                "slug": scenario_slug_input,
                "name": scenario_name,
                "description": description,
                "scenario_type": "stress",
                "shock_vector": {"default_price_shock_pct": default_shock_pct},
                "active": True,
            }
            st.json(api_request("POST", f"{API_PREFIX}/scenarios", json_body=payload))

        if st.button("Run scenario"):
            payload = {
                "portfolio_id": active_portfolio_id,
                "reference_date": run_date.isoformat(),
                "scenario_slug": scenario_slug_input,
            }
            st.json(api_request("POST", f"{API_PREFIX}/scenarios/run", json_body=payload))


if __name__ == "__main__":
    main()
