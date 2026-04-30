from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from typing import Any

from b3_quant_platform.ingestion.models import (
    HistoricalDatasetType,
    ParsedHistoricalFile,
    ParsedHistoricalRecord,
    SourceFileDescriptor,
)


class HistoricalB3Parser:
    def parse(
        self,
        payload: bytes,
        *,
        descriptor: SourceFileDescriptor,
        source_checksum: str,
    ) -> ParsedHistoricalFile:
        if descriptor.dataset_type == HistoricalDatasetType.COTAHIST:
            return self._parse_cotahist(payload, descriptor=descriptor, source_checksum=source_checksum)
        return self._parse_eod_csv(payload, descriptor=descriptor, source_checksum=source_checksum)

    def _parse_cotahist(
        self,
        payload: bytes,
        *,
        descriptor: SourceFileDescriptor,
        source_checksum: str,
    ) -> ParsedHistoricalFile:
        text = payload.decode(descriptor.encoding)
        lines = text.splitlines()
        records: list[ParsedHistoricalRecord] = []
        header_line = ""
        trailer_line = ""

        for line_number, line in enumerate(lines, start=1):
            if not line:
                continue
            record_type = line[0:2]
            if record_type == "00":
                header_line = line
                continue
            if record_type == "99":
                trailer_line = line
                continue
            if record_type != "01":
                continue
            records.append(self._parse_cotahist_line(line, line_number))

        reference_date = descriptor.reference_date or self._infer_reference_date(records)
        return ParsedHistoricalFile(
            dataset_type=descriptor.dataset_type,
            source_name=descriptor.path.name,
            source_system=descriptor.source_system,
            source_checksum=source_checksum,
            processing_date=descriptor.processing_date,
            reference_date=reference_date,
            records=records,
            metadata={
                "encoding": descriptor.encoding,
                "header_line": header_line,
                "trailer_line": trailer_line,
                "raw_line_count": len(lines),
                "quote_line_count": len(records),
            },
        )

    def _parse_eod_csv(
        self,
        payload: bytes,
        *,
        descriptor: SourceFileDescriptor,
        source_checksum: str,
    ) -> ParsedHistoricalFile:
        text = payload.decode(descriptor.encoding)
        delimiter = descriptor.delimiter or self._detect_delimiter(text)
        reader = csv.DictReader(StringIO(text), delimiter=delimiter)
        records: list[ParsedHistoricalRecord] = []
        for line_number, row in enumerate(reader, start=2):
            reference_date = self._parse_date_any(
                self._pick_first(row, "reference_date", "trade_date", "date")
            ) or descriptor.reference_date
            if reference_date is None:
                raise ValueError("EOD file requires a reference_date/date column or --reference-date")
            market_type_code = self._parse_int(self._pick_first(row, "market_type_code", "tpmerc") or "10")
            records.append(
                ParsedHistoricalRecord(
                    reference_date=reference_date,
                    bdi_code=(self._pick_first(row, "bdi_code", "codbdi") or "02").strip(),
                    ticker=(self._pick_first(row, "ticker", "symbol", "codneg") or "").strip(),
                    market_type_code=market_type_code,
                    instrument_name=(self._pick_first(row, "instrument_name", "name", "nomres") or "").strip(),
                    specification_code=(
                        self._pick_first(row, "specification_code", "specification", "especi") or ""
                    ).strip(),
                    term_days=(self._pick_first(row, "term_days", "prazot") or "").strip() or None,
                    currency=(self._pick_first(row, "currency", "modref") or "BRL").strip(),
                    open_price=self._parse_decimal_any(self._pick_first(row, "open_price", "preabe")),
                    high_price=self._parse_decimal_any(self._pick_first(row, "high_price", "premax")),
                    low_price=self._parse_decimal_any(self._pick_first(row, "low_price", "premin")),
                    average_price=self._parse_decimal_any(
                        self._pick_first(row, "average_price", "premed", "close_price", "preult")
                    ),
                    close_price=self._parse_decimal_any(self._pick_first(row, "close_price", "preult")),
                    best_bid_price=self._parse_decimal_any(self._pick_first(row, "best_bid_price", "preofc")),
                    best_ask_price=self._parse_decimal_any(self._pick_first(row, "best_ask_price", "preofv")),
                    trade_count=self._parse_int(self._pick_first(row, "trade_count", "totneg") or "0"),
                    trade_quantity=self._parse_int(
                        self._pick_first(row, "trade_quantity", "quatot") or "0"
                    ),
                    trade_volume=self._parse_decimal_any(
                        self._pick_first(row, "trade_volume", "voltot") or "0"
                    ),
                    exercise_price=self._parse_optional_decimal_any(
                        self._pick_first(row, "exercise_price", "preexe")
                    ),
                    option_indicator=(self._pick_first(row, "option_indicator", "indopc") or "").strip()
                    or None,
                    expiration_date=self._parse_date_any(self._pick_first(row, "expiration_date", "datven")),
                    price_factor=self._parse_int(self._pick_first(row, "price_factor", "fatcot") or "0"),
                    strike_points=self._parse_optional_decimal_any(
                        self._pick_first(row, "strike_points", "ptoexe")
                    ),
                    isin=(self._pick_first(row, "isin", "codisi") or "").strip() or None,
                    distribution_number=self._parse_optional_int(
                        self._pick_first(row, "distribution_number", "dismes")
                    ),
                    source_line_number=line_number,
                )
            )

        reference_date = descriptor.reference_date or self._infer_reference_date(records)
        return ParsedHistoricalFile(
            dataset_type=descriptor.dataset_type,
            source_name=descriptor.path.name,
            source_system=descriptor.source_system,
            source_checksum=source_checksum,
            processing_date=descriptor.processing_date,
            reference_date=reference_date,
            records=records,
            metadata={
                "encoding": descriptor.encoding,
                "delimiter": delimiter,
                "quote_line_count": len(records),
            },
        )

    def _parse_cotahist_line(self, line: str, line_number: int) -> ParsedHistoricalRecord:
        return ParsedHistoricalRecord(
            reference_date=datetime.strptime(line[2:10], "%Y%m%d").date(),
            bdi_code=line[10:12].strip(),
            ticker=line[12:24].strip(),
            market_type_code=self._parse_int(line[24:27]),
            instrument_name=line[27:39].strip(),
            specification_code=line[39:49].strip(),
            term_days=line[49:52].strip() or None,
            currency=line[52:56].strip() or "BRL",
            open_price=self._parse_implied_decimal(line[56:69]),
            high_price=self._parse_implied_decimal(line[69:82]),
            low_price=self._parse_implied_decimal(line[82:95]),
            average_price=self._parse_implied_decimal(line[95:108]),
            close_price=self._parse_implied_decimal(line[108:121]),
            best_bid_price=self._parse_implied_decimal(line[121:134]),
            best_ask_price=self._parse_implied_decimal(line[134:147]),
            trade_count=self._parse_int(line[147:152]),
            trade_quantity=self._parse_int(line[152:170]),
            trade_volume=self._parse_implied_decimal(line[170:188]),
            exercise_price=self._parse_optional_implied_decimal(line[188:201]),
            option_indicator=line[201:202].strip() or None,
            expiration_date=self._parse_date_any(line[202:210].strip()),
            price_factor=self._parse_int(line[210:217]),
            strike_points=self._parse_optional_implied_decimal(line[217:230]),
            isin=line[230:242].strip() or None,
            distribution_number=self._parse_optional_int(line[242:245]),
            source_line_number=line_number,
        )

    def _detect_delimiter(self, text: str) -> str:
        sample = text[:1024]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,")
            return dialect.delimiter
        except csv.Error:
            return ";"

    def _infer_reference_date(self, records: list[ParsedHistoricalRecord]) -> date | None:
        if not records:
            return None
        return min(record.reference_date for record in records)

    def _pick_first(self, row: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return None

    def _parse_date_any(self, value: str | None) -> date | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or cleaned == "00000000":
            return None
        for fmt in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unsupported date format: {cleaned}")

    def _parse_implied_decimal(self, value: str, *, scale: int = 2) -> Decimal:
        cleaned = value.strip() or "0"
        return Decimal(cleaned) / (Decimal(10) ** scale)

    def _parse_optional_implied_decimal(self, value: str, *, scale: int = 2) -> Decimal | None:
        cleaned = value.strip()
        if not cleaned or cleaned == "0" * len(cleaned):
            return None
        return self._parse_implied_decimal(cleaned, scale=scale)

    def _parse_decimal_any(self, value: str | None) -> Decimal:
        cleaned = (value or "0").strip().replace(" ", "")
        if not cleaned:
            return Decimal("0")
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return Decimal(cleaned)

    def _parse_optional_decimal_any(self, value: str | None) -> Decimal | None:
        if value is None or not value.strip():
            return None
        return self._parse_decimal_any(value)

    def _parse_int(self, value: str) -> int:
        cleaned = value.strip() or "0"
        return int(cleaned)

    def _parse_optional_int(self, value: str | None) -> int | None:
        if value is None or not value.strip():
            return None
        return self._parse_int(value)