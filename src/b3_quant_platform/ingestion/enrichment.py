from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from b3_quant_platform.ingestion.models import ParsedHistoricalRecord


MARKET_TYPE_NAMES: dict[int, str] = {
    10: "spot",
    12: "exercise_call",
    13: "exercise_put",
    17: "auction",
    20: "fractional",
    30: "term",
    50: "future",
    60: "call_option",
    70: "put_option",
    80: "debt",
}


class HistoricalRecordEnricher:
    def enrich(
        self,
        record: ParsedHistoricalRecord,
        *,
        dataset_type: str,
        processing_date: date,
        source_checksum: str,
        source_name: str,
    ) -> dict[str, Any]:
        market_type = MARKET_TYPE_NAMES.get(record.market_type_code, f"market_{record.market_type_code}")
        asset_type = self._infer_asset_type(record, market_type)
        segment = self._infer_segment(record, asset_type, market_type)
        has_trades = record.trade_count > 0 and record.trade_quantity > 0
        is_liquid = record.trade_count >= 20 and record.trade_volume >= Decimal("100000")
        is_high_liquidity = record.trade_count >= 100 and record.trade_volume >= Decimal("1000000")
        is_fractional = market_type == "fractional" or record.ticker.endswith("F")
        return {
            "dataset_type": dataset_type,
            "reference_date": record.reference_date,
            "processing_date": processing_date,
            "source_name": source_name,
            "source_checksum": source_checksum,
            "source_line_number": record.source_line_number,
            "bdi_code": record.bdi_code,
            "ticker": record.ticker,
            "isin": record.isin,
            "market_type": market_type,
            "market_type_code": record.market_type_code,
            "asset_type": asset_type,
            "segment": segment,
            "instrument_name": record.instrument_name,
            "specification_code": record.specification_code,
            "term_days": record.term_days,
            "currency": record.currency,
            "open_price": record.open_price,
            "high_price": record.high_price,
            "low_price": record.low_price,
            "average_price": record.average_price,
            "close_price": record.close_price,
            "adjusted_close": record.close_price,
            "best_bid_price": record.best_bid_price,
            "best_ask_price": record.best_ask_price,
            "trade_count": record.trade_count,
            "trade_quantity": record.trade_quantity,
            "trade_volume": record.trade_volume,
            "exercise_price": record.exercise_price,
            "option_indicator": record.option_indicator,
            "expiration_date": record.expiration_date,
            "price_factor": record.price_factor,
            "strike_points": record.strike_points,
            "distribution_number": record.distribution_number,
            "has_trades": has_trades,
            "is_liquid": is_liquid,
            "is_high_liquidity": is_high_liquidity,
            "is_fractional": is_fractional,
            "liquidity_flags": {
                "has_trades": has_trades,
                "is_liquid": is_liquid,
                "is_high_liquidity": is_high_liquidity,
                "is_fractional": is_fractional,
            },
        }

    def _infer_asset_type(self, record: ParsedHistoricalRecord, market_type: str) -> str:
        specification = record.specification_code.upper()
        instrument_name = record.instrument_name.upper()
        ticker = record.ticker.upper()
        if market_type in {"call_option", "put_option", "exercise_call", "exercise_put"}:
            return "option"
        if market_type == "future":
            return "future"
        if "ETF" in specification or "ETF" in instrument_name:
            return "etf"
        if "FII" in specification or "IMOB" in instrument_name:
            return "fund"
        if "BDR" in specification:
            return "bdr"
        if specification in {"UNT", "UNIT"} or ticker.endswith("11"):
            return "unit"
        if specification in {"ON", "PN", "PNA", "PNB", "PNC", "PND"}:
            return "equity"
        if market_type == "debt":
            return "debt"
        return "other"

    def _infer_segment(self, record: ParsedHistoricalRecord, asset_type: str, market_type: str) -> str:
        if market_type == "fractional":
            return "fractional"
        if asset_type in {"option", "future"}:
            return "derivatives"
        if asset_type in {"fund", "etf"}:
            return "funds"
        if asset_type == "bdr":
            return "bdr"
        if asset_type == "debt":
            return "debt"
        if record.bdi_code == "02":
            return "cash_equities"
        return "other"