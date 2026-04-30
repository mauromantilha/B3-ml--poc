from __future__ import annotations

from typing import Any


class HistoricalDeduplicator:
    deduplication_rule = (
        "Keep the record with the highest trade_count, then highest trade_volume, then the latest source_line_number "
        "for the same reference_date, market_type, ticker and isin."
    )

    def deduplicate(self, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        deduplicated: dict[tuple[Any, ...], dict[str, Any]] = {}
        duplicate_count = 0
        for record in records:
            key = (
                record["reference_date"],
                record["market_type"],
                record["ticker"],
                record.get("isin") or "",
            )
            current = deduplicated.get(key)
            if current is None:
                deduplicated[key] = record
                continue
            duplicate_count += 1
            if self._is_preferred(record, current):
                deduplicated[key] = record

        ordered = sorted(
            deduplicated.values(),
            key=lambda item: (item["reference_date"], item["market_type"], item["ticker"]),
        )
        return ordered, duplicate_count

    def build_instrument_rows(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        instruments: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            key = (record["ticker"], record.get("isin") or "", record["asset_type"], record["segment"])
            instrument = instruments.get(key)
            if instrument is None:
                instruments[key] = {
                    "ticker": record["ticker"],
                    "isin": record.get("isin"),
                    "asset_type": record["asset_type"],
                    "segment": record["segment"],
                    "market_type": record["market_type"],
                    "instrument_name": record["instrument_name"],
                    "specification_code": record["specification_code"],
                    "first_reference_date": record["reference_date"],
                    "last_reference_date": record["reference_date"],
                    "last_processing_date": record["processing_date"],
                    "source_checksum": record["source_checksum"],
                }
                continue
            if record["reference_date"] < instrument["first_reference_date"]:
                instrument["first_reference_date"] = record["reference_date"]
            if record["reference_date"] > instrument["last_reference_date"]:
                instrument["last_reference_date"] = record["reference_date"]
            instrument["last_processing_date"] = record["processing_date"]
            instrument["source_checksum"] = record["source_checksum"]
        return sorted(instruments.values(), key=lambda item: item["ticker"])

    def _is_preferred(self, candidate: dict[str, Any], current: dict[str, Any]) -> bool:
        candidate_rank = (
            candidate["trade_count"],
            candidate["trade_volume"],
            candidate["source_line_number"],
        )
        current_rank = (
            current["trade_count"],
            current["trade_volume"],
            current["source_line_number"],
        )
        return candidate_rank > current_rank