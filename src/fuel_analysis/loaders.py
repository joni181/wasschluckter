"""CSV loading functions for fuel and odometer datasets.

Loads raw CSV data into dictionaries, then delegates to validators
for parsing into typed records. Raw data is never modified.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from .config import CsvConfig, PathConfig, ValidationConfig
from .models import FuelRecord, OdometerRecord
from .validators import (
    ValidationResult,
    validate_fuel_dataset,
    validate_odometer_dataset,
)


FUEL_REQUIRED_COLUMNS = {
    "datetime", "amount_eur", "liters", "price_per_liter_eur",
    "fuel_type", "is_full_tank", "station_name", "city", "country", "notes",
}

ODOMETER_REQUIRED_COLUMNS = {
    "datetime", "odometer_km", "notes",
}


def _read_csv(
    path: Path,
    required_columns: set[str],
    csv_config: CsvConfig,
) -> tuple[list[dict[str, str]], ValidationResult]:
    """Read a CSV file and check for required columns.

    Returns (rows_as_dicts, validation_result).
    """
    result = ValidationResult()

    if not path.exists():
        result.add_error(f"File not found: {path}")
        return [], result

    with open(path, encoding=csv_config.encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=csv_config.delimiter, quotechar=csv_config.quotechar)
        if reader.fieldnames is None:
            result.add_error(f"Empty or malformed CSV: {path}")
            return [], result

        actual_columns = set(reader.fieldnames)
        missing = required_columns - actual_columns
        if missing:
            result.add_error(f"Missing required columns: {sorted(missing)}")
            return [], result

        rows = list(reader)

    return rows, result


def load_fuel_data(
    path: Optional[Path] = None,
    csv_config: Optional[CsvConfig] = None,
    validation_config: Optional[ValidationConfig] = None,
) -> tuple[list[FuelRecord], ValidationResult]:
    """Load and validate fuel log data from CSV.

    Returns (valid_records, validation_result).
    """
    if path is None:
        path = PathConfig().fuel_log
    if csv_config is None:
        csv_config = CsvConfig()

    rows, result = _read_csv(path, FUEL_REQUIRED_COLUMNS, csv_config)
    if not result.is_valid:
        return [], result

    records, val_result = validate_fuel_dataset(rows, validation_config)
    result.issues.extend(val_result.issues)
    return records, result


def load_odometer_data(
    path: Optional[Path] = None,
    csv_config: Optional[CsvConfig] = None,
) -> tuple[list[OdometerRecord], ValidationResult]:
    """Load and validate odometer log data from CSV.

    Returns (valid_records, validation_result).
    """
    if path is None:
        path = PathConfig().odometer_log
    if csv_config is None:
        csv_config = CsvConfig()

    rows, result = _read_csv(path, ODOMETER_REQUIRED_COLUMNS, csv_config)
    if not result.is_valid:
        return [], result

    records, val_result = validate_odometer_dataset(rows)
    result.issues.extend(val_result.issues)
    return records, result
