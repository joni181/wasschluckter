"""Tests for validation logic."""

import pytest
from datetime import datetime

from fuel_analysis.config import ValidationConfig
from fuel_analysis.validators import (
    ValidationResult,
    validate_fuel_row,
    validate_fuel_dataset,
    validate_odometer_row,
    validate_odometer_dataset,
)


def _fuel_row(**overrides) -> dict[str, str]:
    base = {
        "datetime": "2024-03-15 08:30:00",
        "amount_eur": "75.50",
        "liters": "42.50",
        "price_per_liter_eur": "1.776",
        "fuel_type": "E10",
        "is_full_tank": "true",
        "station_name": "Aral",
        "city": "Munich",
        "country": "DE",
        "notes": "",
    }
    base.update(overrides)
    return base


def _odo_row(**overrides) -> dict[str, str]:
    base = {
        "datetime": "2024-03-15 08:30:00",
        "odometer_km": "45000",
        "notes": "",
    }
    base.update(overrides)
    return base


class TestValidateFuelRowBasic:
    def test_valid_row(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(), 2, ValidationConfig(), result)
        assert record is not None
        assert result.is_valid
        assert record.liters == 42.50

    def test_unparsable_datetime(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(datetime="not-a-date"), 2, ValidationConfig(), result)
        assert record is None
        assert not result.is_valid

    def test_empty_datetime(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(datetime=""), 2, ValidationConfig(), result)
        assert record is None


class TestValidateFuelRowNumerics:
    def test_negative_amount(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(amount_eur="-10"), 2, ValidationConfig(), result)
        assert record is None
        assert any("amount_eur" in e.message for e in result.errors)

    def test_zero_liters(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(liters="0"), 2, ValidationConfig(), result)
        assert record is None

    def test_non_numeric_price(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(price_per_liter_eur="abc"), 2, ValidationConfig(), result)
        assert record is None


class TestValidateFuelRowFuelType:
    def test_invalid_fuel_type(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(fuel_type="E15"), 2, ValidationConfig(), result)
        assert record is None

    @pytest.mark.parametrize("ft", ["E5", "E10"])
    def test_valid_fuel_types(self, ft):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(fuel_type=ft), 2, ValidationConfig(), result)
        assert record is not None
        assert record.fuel_type.value == ft


class TestValidateFuelRowCountry:
    def test_invalid_format(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(country="Germany"), 2, ValidationConfig(), result)
        assert record is None

    def test_lowercase(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(country="de"), 2, ValidationConfig(), result)
        assert record is None

    def test_primary_country(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(country="AT"), 2, ValidationConfig(), result)
        assert record is not None
        assert len(result.warnings) == 0

    def test_non_primary_country_warning(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(country="ES"), 2, ValidationConfig(), result)
        assert record is not None
        assert any("primary set" in w.message for w in result.warnings)


class TestValidateFuelRowPriceConsistency:
    def test_consistent(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(), 2, ValidationConfig(), result)
        assert record is not None
        assert not any("inconsistency" in w.message.lower() for w in result.warnings)

    def test_large_discrepancy(self):
        result = ValidationResult()
        record = validate_fuel_row(_fuel_row(amount_eur="100.00"), 2, ValidationConfig(), result)
        assert record is not None
        assert any("inconsistency" in w.message.lower() for w in result.warnings)


class TestValidateFuelDataset:
    def test_empty(self):
        records, result = validate_fuel_dataset([])
        assert records == []
        assert result.is_valid

    def test_valid_rows(self):
        rows = [
            _fuel_row(datetime="2024-03-15 08:30:00"),
            _fuel_row(datetime="2024-04-15 08:30:00"),
        ]
        records, result = validate_fuel_dataset(rows)
        assert len(records) == 2

    def test_duplicate_detection_within_tolerance(self):
        rows = [
            _fuel_row(datetime="2024-03-15 08:30:00", liters="42.50"),
            _fuel_row(datetime="2024-03-15 08:40:00", liters="42.50"),
        ]
        records, result = validate_fuel_dataset(rows)
        assert len(records) == 2
        assert any("duplicate" in w.message.lower() for w in result.warnings)

    def test_no_duplicate_when_different_liters(self):
        rows = [
            _fuel_row(datetime="2024-03-15 08:30:00", liters="42.50"),
            _fuel_row(datetime="2024-03-15 08:35:00", liters="30.00", amount_eur="53.40", price_per_liter_eur="1.780"),
        ]
        records, result = validate_fuel_dataset(rows)
        assert not any("duplicate" in w.message.lower() for w in result.warnings)

    def test_no_duplicate_when_far_apart(self):
        rows = [
            _fuel_row(datetime="2024-03-15 08:30:00", liters="42.50"),
            _fuel_row(datetime="2024-03-15 10:30:00", liters="42.50"),
        ]
        records, result = validate_fuel_dataset(rows)
        assert not any("duplicate" in w.message.lower() for w in result.warnings)

    def test_mixed_valid_invalid(self):
        rows = [
            _fuel_row(),
            _fuel_row(liters="-5"),
        ]
        records, result = validate_fuel_dataset(rows)
        assert len(records) == 1
        assert not result.is_valid


class TestValidateOdometerRow:
    def test_valid(self):
        result = ValidationResult()
        record = validate_odometer_row(_odo_row(), 2, result)
        assert record is not None
        assert record.odometer_km == 45000

    def test_negative(self):
        result = ValidationResult()
        record = validate_odometer_row(_odo_row(odometer_km="-100"), 2, result)
        assert record is None

    def test_zero_is_valid(self):
        result = ValidationResult()
        record = validate_odometer_row(_odo_row(odometer_km="0"), 2, result)
        assert record is not None

    def test_non_numeric(self):
        result = ValidationResult()
        record = validate_odometer_row(_odo_row(odometer_km="abc"), 2, result)
        assert record is None


class TestValidateOdometerDataset:
    def test_empty(self):
        records, result = validate_odometer_dataset([])
        assert records == []
        assert result.is_valid

    def test_monotonicity_violation(self):
        rows = [
            _odo_row(datetime="2024-03-15 08:00:00", odometer_km="50000"),
            _odo_row(datetime="2024-03-16 08:00:00", odometer_km="49000"),
        ]
        records, result = validate_odometer_dataset(rows)
        assert len(records) == 2
        assert any("monotonicity" in w.message.lower() for w in result.warnings)

    def test_monotonically_increasing_no_warning(self):
        rows = [
            _odo_row(datetime="2024-03-15 08:00:00", odometer_km="45000"),
            _odo_row(datetime="2024-03-16 08:00:00", odometer_km="45500"),
        ]
        records, result = validate_odometer_dataset(rows)
        assert not any("monotonicity" in w.message.lower() for w in result.warnings)

    def test_duplicate_detection(self):
        rows = [
            _odo_row(datetime="2024-03-15 08:00:00", odometer_km="45000"),
            _odo_row(datetime="2024-03-15 08:10:00", odometer_km="45000"),
        ]
        records, result = validate_odometer_dataset(rows)
        assert any("duplicate" in w.message.lower() for w in result.warnings)


class TestValidationResult:
    def test_is_valid_with_warnings_only(self):
        r = ValidationResult()
        r.add_warning("some warning")
        assert r.is_valid

    def test_is_invalid_with_error(self):
        r = ValidationResult()
        r.add_error("some error")
        assert not r.is_valid

    def test_summary_format(self):
        r = ValidationResult()
        r.add_error("bad thing", row=2)
        r.add_warning("suspicious thing", row=3)
        s = r.summary()
        assert "1 error(s)" in s
        assert "1 warning(s)" in s
        assert "ERROR" in s
        assert "WARN" in s
