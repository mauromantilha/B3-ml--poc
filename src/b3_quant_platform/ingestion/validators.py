from __future__ import annotations

from typing import Iterable

from b3_quant_platform.ingestion.models import ParsedHistoricalFile, ParsedHistoricalRecord, ValidationIssue


class HistoricalIngestionValidationError(Exception):
    def __init__(self, issues: Iterable[ValidationIssue]) -> None:
        self.issues = list(issues)
        super().__init__(f"Historical ingestion validation failed with {len(self.issues)} issue(s)")


class HistoricalFileValidator:
    def validate(self, parsed_file: ParsedHistoricalFile) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not parsed_file.records:
            issues.append(ValidationIssue(line_number=0, code="empty_file", message="No quote records found"))
            return issues

        for record in parsed_file.records:
            issues.extend(self._validate_record(record))
        return issues

    def assert_valid(self, parsed_file: ParsedHistoricalFile) -> list[ValidationIssue]:
        issues = self.validate(parsed_file)
        if issues:
            raise HistoricalIngestionValidationError(issues)
        return issues

    def _validate_record(self, record: ParsedHistoricalRecord) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not record.ticker:
            issues.append(
                ValidationIssue(
                    line_number=record.source_line_number,
                    code="missing_ticker",
                    message="Ticker is required",
                )
            )
        if record.close_price < 0 or record.open_price < 0 or record.high_price < 0 or record.low_price < 0:
            issues.append(
                ValidationIssue(
                    line_number=record.source_line_number,
                    code="negative_price",
                    message="Price columns must be non-negative",
                )
            )
        if record.high_price < max(record.open_price, record.close_price, record.low_price):
            issues.append(
                ValidationIssue(
                    line_number=record.source_line_number,
                    code="invalid_high_price",
                    message="High price must be greater than or equal to open, close and low",
                )
            )
        if record.low_price > min(record.open_price, record.close_price, record.high_price):
            issues.append(
                ValidationIssue(
                    line_number=record.source_line_number,
                    code="invalid_low_price",
                    message="Low price must be lower than or equal to open, close and high",
                )
            )
        if record.trade_count < 0 or record.trade_quantity < 0 or record.trade_volume < 0:
            issues.append(
                ValidationIssue(
                    line_number=record.source_line_number,
                    code="negative_liquidity_metric",
                    message="Trade metrics must be non-negative",
                )
            )
        return issues