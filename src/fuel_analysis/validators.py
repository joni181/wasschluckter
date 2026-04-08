"""Validation logic for fuel and odometer records.

Validation policy:
- Hard errors: data that cannot be loaded or is structurally invalid.
  Examples: duplicate event_id, unparsable datetime, negative amounts,
  invalid fuel_type, invalid country code, missing required columns.
- Soft warnings: data that is loadable but suspicious.
  Examples: price consistency mismatch beyond tolerance, suspiciously
  high/low price per liter, odometer monotonicity violations,
  potential duplicate entries.

Hard errors prevent the record from being included in analysis.
Warnings are collected and reported but do not block loading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .config import (
    ALLOWED_FUEL_TYPES,
    REQUIRED_COUNTRY_CODES,
    ValidationConfig,
)
from .models import (
    COUNTRY_CODE_PATTERN,
    FuelRecord,
    FuelType,
    FullTankStatus,
    OdometerRecord,
)


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error" or "warning"
    row: Optional[int]  # 1-based row number in CSV (None for dataset-level)
    event_id: Optional[str]
    field: Optional[str]
    message: str


@dataclass
class ValidationResult:
    """Aggregated validation result for a dataset."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(
        self,
        message: str,
        row: Optional[int] = None,
        event_id: Optional[str] = None,
        field: Optional[str] = None,
    ) -> None:
        self.issues.append(ValidationIssue("error", row, event_id, field, message))

    def add_warning(
        self,
        message: str,
        row: Optional[int] = None,
        event_id: Optional[str] = None,
        field: Optional[str] = None,
    ) -> None:
        self.issues.append(ValidationIssue("warning", row, event_id, field, message))

    def summary(self) -> str:
        lines = [
            f"Validation: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        ]
        for issue in self.issues:
            prefix = "ERROR" if issue.severity == "error" else "WARN"
            loc = f"row {issue.row}" if issue.row else "dataset"
            lines.append(f"  [{prefix}] {loc}: {issue.message}")
        return "\n".join(lines)


def _parse_datetime(value: str, row: int, event_id: str, result: ValidationResult) -> Optional[datetime]:
    """Parse an ISO-like datetime string. Returns None on failure."""
    try:
        return datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        result.add_error(
            f"Unparsable datetime: '{value}'",
            row=row, event_id=event_id, field="datetime",
        )
        return None


def _parse_positive_float(
    value: str, field_name: str, row: int, event_id: str, result: ValidationResult
) -> Optional[float]:
    """Parse a positive float value. Returns None on failure."""
    try:
        num = float(value.strip())
    except (ValueError, TypeError):
        result.add_error(
            f"Invalid numeric value for {field_name}: '{value}'",
            row=row, event_id=event_id, field=field_name,
        )
        return None
    if num <= 0:
        result.add_error(
            f"{field_name} must be positive, got {num}",
            row=row, event_id=event_id, field=field_name,
        )
        return None
    return num


def _parse_non_negative_float(
    value: str, field_name: str, row: int, event_id: str, result: ValidationResult
) -> Optional[float]:
    """Parse a non-negative float value. Returns None on failure."""
    try:
        num = float(value.strip())
    except (ValueError, TypeError):
        result.add_error(
            f"Invalid numeric value for {field_name}: '{value}'",
            row=row, event_id=event_id, field=field_name,
        )
        return None
    if num < 0:
        result.add_error(
            f"{field_name} must be non-negative, got {num}",
            row=row, event_id=event_id, field=field_name,
        )
        return None
    return num


def validate_fuel_row(
    row_data: dict[str, str],
    row_number: int,
    config: ValidationConfig,
    result: ValidationResult,
) -> Optional[FuelRecord]:
    """Validate and parse a single fuel log row.

    Returns a FuelRecord on success, None if hard errors were found.
    """
    event_id = row_data.get("event_id", "").strip()
    if not event_id:
        result.add_error("Missing event_id", row=row_number, field="event_id")
        return None

    dt = _parse_datetime(row_data.get("datetime", ""), row_number, event_id, result)
    amount = _parse_positive_float(
        row_data.get("amount_eur", ""), "amount_eur", row_number, event_id, result
    )
    liters = _parse_positive_float(
        row_data.get("liters", ""), "liters", row_number, event_id, result
    )
    price = _parse_positive_float(
        row_data.get("price_per_liter_eur", ""), "price_per_liter_eur",
        row_number, event_id, result,
    )

    # Fuel type validation.
    fuel_type_str = row_data.get("fuel_type", "").strip()
    fuel_type: Optional[FuelType] = None
    if fuel_type_str not in ALLOWED_FUEL_TYPES:
        result.add_error(
            f"Invalid fuel_type: '{fuel_type_str}'. Allowed: {sorted(ALLOWED_FUEL_TYPES)}",
            row=row_number, event_id=event_id, field="fuel_type",
        )
    else:
        fuel_type = FuelType(fuel_type_str)

    # Full tank status.
    is_full_tank_str = row_data.get("is_full_tank", "")
    try:
        is_full_tank = FullTankStatus.from_csv_value(is_full_tank_str)
    except ValueError as e:
        result.add_error(str(e), row=row_number, event_id=event_id, field="is_full_tank")
        return None

    # Station name (required).
    station_name = row_data.get("station_name", "").strip()
    if not station_name:
        result.add_error(
            "Missing station_name",
            row=row_number, event_id=event_id, field="station_name",
        )

    # City (required, but allow empty with warning).
    city = row_data.get("city", "").strip()
    if not city:
        result.add_warning(
            "Missing city value",
            row=row_number, event_id=event_id, field="city",
        )

    # Country validation.
    country = row_data.get("country", "").strip()
    if not COUNTRY_CODE_PATTERN.match(country):
        result.add_error(
            f"Invalid country code format: '{country}'. Expected 2-letter ISO code.",
            row=row_number, event_id=event_id, field="country",
        )
        country = ""
    elif country not in REQUIRED_COUNTRY_CODES:
        # Accept valid ISO format but warn if not in primary set.
        result.add_warning(
            f"Country '{country}' is not in the primary set {sorted(REQUIRED_COUNTRY_CODES)}",
            row=row_number, event_id=event_id, field="country",
        )

    notes = row_data.get("notes", "").strip()

    # If any required field failed, return None.
    if dt is None or amount is None or liters is None or price is None or fuel_type is None:
        return None
    if not station_name or not country:
        return None

    # Price consistency warning.
    expected_amount = liters * price
    if abs(expected_amount - amount) / amount > config.price_consistency_tolerance:
        result.add_warning(
            f"Price inconsistency: amount_eur={amount:.2f} but "
            f"liters*price={expected_amount:.2f} "
            f"(diff={abs(expected_amount - amount):.2f})",
            row=row_number, event_id=event_id, field="amount_eur",
        )

    # Suspicious price warnings.
    if price < config.price_per_liter_min_warn:
        result.add_warning(
            f"Suspiciously low price per liter: {price:.3f} EUR",
            row=row_number, event_id=event_id, field="price_per_liter_eur",
        )
    if price > config.price_per_liter_max_warn:
        result.add_warning(
            f"Suspiciously high price per liter: {price:.3f} EUR",
            row=row_number, event_id=event_id, field="price_per_liter_eur",
        )

    return FuelRecord(
        event_id=event_id,
        datetime=dt,
        amount_eur=amount,
        liters=liters,
        price_per_liter_eur=price,
        fuel_type=fuel_type,
        is_full_tank=is_full_tank,
        station_name=station_name,
        city=city,
        country=country,
        notes=notes,
    )


def validate_odometer_row(
    row_data: dict[str, str],
    row_number: int,
    result: ValidationResult,
) -> Optional[OdometerRecord]:
    """Validate and parse a single odometer log row.

    Returns an OdometerRecord on success, None if hard errors were found.
    """
    event_id = row_data.get("event_id", "").strip()
    if not event_id:
        result.add_error("Missing event_id", row=row_number, field="event_id")
        return None

    dt = _parse_datetime(row_data.get("datetime", ""), row_number, event_id, result)
    odometer_km = _parse_non_negative_float(
        row_data.get("odometer_km", ""), "odometer_km", row_number, event_id, result
    )
    notes = row_data.get("notes", "").strip()

    if dt is None or odometer_km is None:
        return None

    return OdometerRecord(
        event_id=event_id,
        datetime=dt,
        odometer_km=odometer_km,
        notes=notes,
    )


def validate_fuel_dataset(
    rows: list[dict[str, str]],
    config: Optional[ValidationConfig] = None,
) -> tuple[list[FuelRecord], ValidationResult]:
    """Validate an entire fuel log dataset.

    Returns (valid_records, validation_result).
    """
    if config is None:
        config = ValidationConfig()

    result = ValidationResult()
    records: list[FuelRecord] = []
    seen_ids: set[str] = set()

    for i, row_data in enumerate(rows):
        row_number = i + 2  # 1-based, accounting for header row
        record = validate_fuel_row(row_data, row_number, config, result)
        if record is not None:
            if record.event_id in seen_ids:
                result.add_error(
                    f"Duplicate event_id: '{record.event_id}'",
                    row=row_number, event_id=record.event_id, field="event_id",
                )
            else:
                seen_ids.add(record.event_id)
                records.append(record)

    # Duplicate detection heuristic: same datetime and same station.
    for i, r1 in enumerate(records):
        for r2 in records[i + 1:]:
            if r1.datetime == r2.datetime and r1.station_name == r2.station_name:
                result.add_warning(
                    f"Potential duplicate: '{r1.event_id}' and '{r2.event_id}' "
                    f"have same datetime and station",
                )

    return records, result


def validate_odometer_dataset(
    rows: list[dict[str, str]],
) -> tuple[list[OdometerRecord], ValidationResult]:
    """Validate an entire odometer log dataset.

    Returns (valid_records, validation_result).

    Monotonicity policy: odometer readings should be monotonically increasing
    when sorted by datetime. Violations are reported as warnings, not errors,
    because a violation may indicate a data entry mistake rather than
    structurally invalid data. The raw data is never reordered or modified.
    """
    result = ValidationResult()
    records: list[OdometerRecord] = []
    seen_ids: set[str] = set()

    for i, row_data in enumerate(rows):
        row_number = i + 2
        record = validate_odometer_row(row_data, row_number, result)
        if record is not None:
            if record.event_id in seen_ids:
                result.add_error(
                    f"Duplicate event_id: '{record.event_id}'",
                    row=row_number, event_id=record.event_id, field="event_id",
                )
            else:
                seen_ids.add(record.event_id)
                records.append(record)

    # Chronological and monotonicity checks.
    sorted_records = sorted(records, key=lambda r: r.datetime)
    for i in range(1, len(sorted_records)):
        prev = sorted_records[i - 1]
        curr = sorted_records[i]
        if curr.odometer_km < prev.odometer_km:
            result.add_warning(
                f"Odometer monotonicity violation: '{curr.event_id}' "
                f"({curr.odometer_km} km at {curr.datetime}) is less than "
                f"'{prev.event_id}' ({prev.odometer_km} km at {prev.datetime})",
                event_id=curr.event_id, field="odometer_km",
            )
        if curr.datetime == prev.datetime:
            result.add_warning(
                f"Duplicate datetime: '{prev.event_id}' and '{curr.event_id}' "
                f"both at {curr.datetime}",
            )

    return records, result
