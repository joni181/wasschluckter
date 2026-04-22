"""Validation logic for fuel and odometer records.

Validation policy:
- Hard errors: data that cannot be loaded or is structurally invalid.
  Examples: unparsable datetime, negative amounts, invalid fuel_type,
  invalid country code, missing required columns.
- Soft warnings: data that is loadable but suspicious.
  Examples: suspiciously high/low derived price per liter, odometer
  monotonicity violations, potential duplicate entries (based on datetime
  proximity + values).

Hard errors prevent the record from being included in analysis.
Warnings are collected and reported but do not block loading.

Duplicate detection: instead of requiring manually maintained unique IDs,
duplicates are detected by comparing datetime proximity (±20 minutes for
fuel events) combined with matching liters values. For odometer events,
datetime proximity (±20 minutes) combined with matching odometer_km is used.

price_per_liter_eur: not a stored field. Always derived from
amount_eur / liters. Suspicious-price warnings use this derived value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
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

DUPLICATE_TIME_TOLERANCE = timedelta(minutes=20)


@dataclass
class ValidationIssue:
    severity: str  # "error" or "warning"
    row: Optional[int]
    field: Optional[str]
    message: str


@dataclass
class ValidationResult:
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
        field: Optional[str] = None,
    ) -> None:
        self.issues.append(ValidationIssue("error", row, field, message))

    def add_warning(
        self,
        message: str,
        row: Optional[int] = None,
        field: Optional[str] = None,
    ) -> None:
        self.issues.append(ValidationIssue("warning", row, field, message))

    def summary(self) -> str:
        lines = [
            f"Validation: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        ]
        for issue in self.issues:
            prefix = "ERROR" if issue.severity == "error" else "WARN"
            loc = f"row {issue.row}" if issue.row else "dataset"
            lines.append(f"  [{prefix}] {loc}: {issue.message}")
        return "\n".join(lines)


def _parse_datetime(value: str, row: int, result: ValidationResult):
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        result.add_error(
            f"Unparsable datetime: '{value}'",
            row=row, field="datetime",
        )
        return None


def _parse_positive_float(
    value: str, field_name: str, row: int, result: ValidationResult
) -> Optional[float]:
    try:
        num = float(value.strip())
    except (ValueError, TypeError):
        result.add_error(
            f"Invalid numeric value for {field_name}: '{value}'",
            row=row, field=field_name,
        )
        return None
    if num <= 0:
        result.add_error(
            f"{field_name} must be positive, got {num}",
            row=row, field=field_name,
        )
        return None
    return num


def _parse_non_negative_float(
    value: str, field_name: str, row: int, result: ValidationResult
) -> Optional[float]:
    try:
        num = float(value.strip())
    except (ValueError, TypeError):
        result.add_error(
            f"Invalid numeric value for {field_name}: '{value}'",
            row=row, field=field_name,
        )
        return None
    if num < 0:
        result.add_error(
            f"{field_name} must be non-negative, got {num}",
            row=row, field=field_name,
        )
        return None
    return num


def validate_fuel_row(
    row_data: dict[str, str],
    row_number: int,
    config: ValidationConfig,
    result: ValidationResult,
) -> Optional[FuelRecord]:
    """Validate and parse a single fuel log row."""
    dt = _parse_datetime(row_data.get("datetime", ""), row_number, result)
    amount = _parse_positive_float(
        row_data.get("amount_eur", ""), "amount_eur", row_number, result
    )
    liters = _parse_positive_float(
        row_data.get("liters", ""), "liters", row_number, result
    )

    fuel_type_str = row_data.get("fuel_type", "").strip()
    fuel_type: Optional[FuelType] = None
    if fuel_type_str not in ALLOWED_FUEL_TYPES:
        result.add_error(
            f"Invalid fuel_type: '{fuel_type_str}'. Allowed: {sorted(ALLOWED_FUEL_TYPES)}",
            row=row_number, field="fuel_type",
        )
    else:
        fuel_type = FuelType(fuel_type_str)

    is_full_tank_str = row_data.get("is_full_tank", "")
    try:
        is_full_tank = FullTankStatus.from_csv_value(is_full_tank_str)
    except ValueError as e:
        result.add_error(str(e), row=row_number, field="is_full_tank")
        return None

    station_name = row_data.get("station_name", "").strip()
    if not station_name:
        result.add_error(
            "Missing station_name",
            row=row_number, field="station_name",
        )

    city = row_data.get("city", "").strip()
    if not city:
        result.add_warning(
            "Missing city value",
            row=row_number, field="city",
        )

    country = row_data.get("country", "").strip()
    if not COUNTRY_CODE_PATTERN.match(country):
        result.add_error(
            f"Invalid country code format: '{country}'. Expected 2-letter ISO code.",
            row=row_number, field="country",
        )
        country = ""
    elif country not in REQUIRED_COUNTRY_CODES:
        result.add_warning(
            f"Country '{country}' is not in the primary set {sorted(REQUIRED_COUNTRY_CODES)}",
            row=row_number, field="country",
        )

    notes = row_data.get("notes", "").strip()

    if dt is None or amount is None or liters is None or fuel_type is None:
        return None
    if not station_name or not country:
        return None

    # Derived price per liter — always amount / liters.
    derived_price = amount / liters
    if derived_price < config.price_per_liter_min_warn:
        result.add_warning(
            f"Suspiciously low derived price per liter: {derived_price:.3f} EUR",
            row=row_number, field="amount_eur",
        )
    if derived_price > config.price_per_liter_max_warn:
        result.add_warning(
            f"Suspiciously high derived price per liter: {derived_price:.3f} EUR",
            row=row_number, field="amount_eur",
        )

    return FuelRecord(
        datetime=dt,
        amount_eur=amount,
        liters=liters,
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
    dt = _parse_datetime(row_data.get("datetime", ""), row_number, result)
    odometer_km = _parse_non_negative_float(
        row_data.get("odometer_km", ""), "odometer_km", row_number, result
    )
    notes = row_data.get("notes", "").strip()

    if dt is None or odometer_km is None:
        return None

    return OdometerRecord(
        datetime=dt,
        odometer_km=odometer_km,
        notes=notes,
    )


def validate_fuel_dataset(
    rows: list[dict[str, str]],
    config: Optional[ValidationConfig] = None,
) -> tuple[list[FuelRecord], ValidationResult]:
    if config is None:
        config = ValidationConfig()

    result = ValidationResult()
    records: list[FuelRecord] = []

    for i, row_data in enumerate(rows):
        row_number = i + 2
        record = validate_fuel_row(row_data, row_number, config, result)
        if record is not None:
            records.append(record)

    for i, r1 in enumerate(records):
        for r2 in records[i + 1:]:
            time_diff = abs(r1.datetime - r2.datetime)
            if time_diff <= DUPLICATE_TIME_TOLERANCE and r1.liters == r2.liters:
                result.add_warning(
                    f"Potential duplicate: rows with {r1.liters}L at "
                    f"{r1.datetime} and {r2.datetime} "
                    f"(within {DUPLICATE_TIME_TOLERANCE})",
                )

    return records, result


def validate_odometer_dataset(
    rows: list[dict[str, str]],
) -> tuple[list[OdometerRecord], ValidationResult]:
    result = ValidationResult()
    records: list[OdometerRecord] = []

    for i, row_data in enumerate(rows):
        row_number = i + 2
        record = validate_odometer_row(row_data, row_number, result)
        if record is not None:
            records.append(record)

    sorted_records = sorted(records, key=lambda r: r.datetime)
    for i in range(1, len(sorted_records)):
        prev = sorted_records[i - 1]
        curr = sorted_records[i]
        if curr.odometer_km < prev.odometer_km:
            result.add_warning(
                f"Odometer monotonicity violation: "
                f"{curr.odometer_km} km at {curr.datetime} is less than "
                f"{prev.odometer_km} km at {prev.datetime}",
                field="odometer_km",
            )

    for i, r1 in enumerate(sorted_records):
        for r2 in sorted_records[i + 1:]:
            time_diff = abs(r1.datetime - r2.datetime)
            if time_diff > DUPLICATE_TIME_TOLERANCE:
                break
            if r1.odometer_km == r2.odometer_km:
                result.add_warning(
                    f"Potential duplicate: odometer readings of "
                    f"{r1.odometer_km} km at {r1.datetime} and {r2.datetime} "
                    f"(within {DUPLICATE_TIME_TOLERANCE})",
                )

    return records, result
