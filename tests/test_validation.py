"""Tests for fuel_analysis.validators: row-level and dataset-level validation."""

import pytest
from datetime import datetime

from fuel_analysis.config import ValidationConfig
from fuel_analysis.models import FuelType, FullTankStatus
from fuel_analysis.validators import (
    ValidationResult,
    validate_fuel_row,
    validate_fuel_dataset,
    validate_odometer_row,
    validate_odometer_dataset,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = ValidationConfig()


def _fuel_row(
    event_id: str = "F001",
    dt: str = "2024-06-01T10:00:00",
    amount_eur: str = "72.00",
    liters: str = "40.00",
    price_per_liter_eur: str = "1.800",
    fuel_type: str = "E5",
    is_full_tank: str = "true",
    station_name: str = "Shell Autobahn",
    city: str = "Berlin",
    country: str = "DE",
    notes: str = "",
) -> dict[str, str]:
    return {
        "event_id": event_id,
        "datetime": dt,
        "amount_eur": amount_eur,
        "liters": liters,
        "price_per_liter_eur": price_per_liter_eur,
        "fuel_type": fuel_type,
        "is_full_tank": is_full_tank,
        "station_name": station_name,
        "city": city,
        "country": country,
        "notes": notes,
    }


def _odometer_row(
    event_id: str = "O001",
    dt: str = "2024-06-01T10:00:00",
    odometer_km: str = "50000.0",
    notes: str = "",
) -> dict[str, str]:
    return {
        "event_id": event_id,
        "datetime": dt,
        "odometer_km": odometer_km,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# validate_fuel_row: happy path
# ---------------------------------------------------------------------------


class TestValidateFuelRowHappy:
    def test_valid_row_returns_record(self):
        result = ValidationResult()
        rec = validate_fuel_row(_fuel_row(), row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is not None
        assert rec.event_id == "F001"
        assert rec.fuel_type is FuelType.E5
        assert rec.is_full_tank is FullTankStatus.YES
        assert rec.country == "DE"
        assert result.is_valid

    def test_valid_row_no_warnings_when_consistent(self):
        result = ValidationResult()
        validate_fuel_row(_fuel_row(), row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# validate_fuel_row: positivity checks
# ---------------------------------------------------------------------------


class TestValidateFuelRowPositivity:
    @pytest.mark.parametrize("field", ["amount_eur", "liters", "price_per_liter_eur"])
    def test_negative_value_is_error(self, field):
        result = ValidationResult()
        row = _fuel_row(**{field: "-1.0"})
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None
        assert len(result.errors) >= 1
        assert any(field in e.field for e in result.errors if e.field)

    @pytest.mark.parametrize("field", ["amount_eur", "liters", "price_per_liter_eur"])
    def test_zero_value_is_error(self, field):
        result = ValidationResult()
        row = _fuel_row(**{field: "0"})
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None
        assert len(result.errors) >= 1

    @pytest.mark.parametrize("field", ["amount_eur", "liters", "price_per_liter_eur"])
    def test_non_numeric_value_is_error(self, field):
        result = ValidationResult()
        row = _fuel_row(**{field: "abc"})
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None
        assert any("Invalid numeric" in e.message for e in result.errors)


# ---------------------------------------------------------------------------
# validate_fuel_row: fuel_type validation
# ---------------------------------------------------------------------------


class TestValidateFuelRowFuelType:
    def test_invalid_fuel_type(self):
        result = ValidationResult()
        row = _fuel_row(fuel_type="Diesel")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None
        assert any("fuel_type" in (e.field or "") for e in result.errors)

    def test_empty_fuel_type(self):
        result = ValidationResult()
        row = _fuel_row(fuel_type="")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None

    @pytest.mark.parametrize("ft", ["E5", "E10"])
    def test_valid_fuel_types(self, ft):
        result = ValidationResult()
        row = _fuel_row(fuel_type=ft)
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is not None
        assert rec.fuel_type.value == ft


# ---------------------------------------------------------------------------
# validate_fuel_row: country validation
# ---------------------------------------------------------------------------


class TestValidateFuelRowCountry:
    def test_invalid_country_format(self):
        result = ValidationResult()
        row = _fuel_row(country="Germany")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None
        assert any("country" in (e.field or "") for e in result.errors)

    def test_lowercase_country_is_error(self):
        result = ValidationResult()
        row = _fuel_row(country="de")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None

    def test_primary_country_no_warning(self):
        result = ValidationResult()
        row = _fuel_row(country="DE")
        validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert not any("country" in (w.field or "") for w in result.warnings)

    def test_non_primary_country_gives_warning(self):
        result = ValidationResult()
        row = _fuel_row(country="ES")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is not None  # Valid ISO code, just not primary
        assert any("country" in (w.field or "") for w in result.warnings)

    def test_empty_country_is_error(self):
        result = ValidationResult()
        row = _fuel_row(country="")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None


# ---------------------------------------------------------------------------
# validate_fuel_row: price consistency warning
# ---------------------------------------------------------------------------


class TestValidateFuelRowPriceConsistency:
    def test_consistent_price_no_warning(self):
        result = ValidationResult()
        # 40 * 1.8 = 72.0 exactly
        row = _fuel_row(amount_eur="72.00", liters="40.00", price_per_liter_eur="1.800")
        validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert not any("inconsistency" in w.message.lower() for w in result.warnings)

    def test_inconsistent_price_gives_warning(self):
        result = ValidationResult()
        # 40 * 1.8 = 72, but claiming amount_eur = 80 => large discrepancy
        row = _fuel_row(amount_eur="80.00", liters="40.00", price_per_liter_eur="1.800")
        validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert any("inconsistency" in w.message.lower() for w in result.warnings)

    def test_minor_rounding_within_tolerance(self):
        result = ValidationResult()
        # 40 * 1.8 = 72.0, amount_eur=72.50 => ~0.69% off, within 2%
        row = _fuel_row(amount_eur="72.50", liters="40.00", price_per_liter_eur="1.800")
        validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert not any("inconsistency" in w.message.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_fuel_row: datetime parsing
# ---------------------------------------------------------------------------


class TestValidateFuelRowDatetime:
    def test_valid_datetime(self):
        result = ValidationResult()
        row = _fuel_row(dt="2024-06-15T14:30:00")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is not None
        assert rec.datetime == datetime(2024, 6, 15, 14, 30)

    def test_unparsable_datetime(self):
        result = ValidationResult()
        row = _fuel_row(dt="not-a-date")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None
        assert any("datetime" in (e.field or "") for e in result.errors)

    def test_empty_datetime(self):
        result = ValidationResult()
        row = _fuel_row(dt="")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None

    def test_missing_event_id(self):
        result = ValidationResult()
        row = _fuel_row(event_id="")
        rec = validate_fuel_row(row, row_number=2, config=_DEFAULT_CONFIG, result=result)
        assert rec is None
        assert any("event_id" in (e.field or "") for e in result.errors)


# ---------------------------------------------------------------------------
# validate_fuel_dataset: duplicate event_id
# ---------------------------------------------------------------------------


class TestValidateFuelDatasetDuplicates:
    def test_duplicate_event_id_error(self):
        rows = [_fuel_row(event_id="F001"), _fuel_row(event_id="F001")]
        records, result = validate_fuel_dataset(rows)
        assert any("Duplicate event_id" in e.message for e in result.errors)
        # Only the first should be in the list
        assert len(records) == 1

    def test_unique_ids_no_error(self):
        rows = [_fuel_row(event_id="F001"), _fuel_row(event_id="F002")]
        records, result = validate_fuel_dataset(rows)
        assert len(records) == 2
        assert result.is_valid

    def test_potential_duplicate_warning_same_datetime_station(self):
        rows = [
            _fuel_row(event_id="F001", dt="2024-06-01T10:00:00", station_name="Shell"),
            _fuel_row(event_id="F002", dt="2024-06-01T10:00:00", station_name="Shell"),
        ]
        records, result = validate_fuel_dataset(rows)
        assert any("Potential duplicate" in w.message for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_fuel_dataset: full run
# ---------------------------------------------------------------------------


class TestValidateFuelDatasetFull:
    def test_empty_dataset(self):
        records, result = validate_fuel_dataset([])
        assert len(records) == 0
        assert result.is_valid

    def test_mixed_valid_and_invalid(self):
        rows = [
            _fuel_row(event_id="F001"),
            _fuel_row(event_id="F002", amount_eur="-5"),  # invalid
            _fuel_row(event_id="F003"),
        ]
        records, result = validate_fuel_dataset(rows)
        assert len(records) == 2  # F001, F003
        assert not result.is_valid


# ---------------------------------------------------------------------------
# validate_odometer_row
# ---------------------------------------------------------------------------


class TestValidateOdometerRow:
    def test_valid_row(self):
        result = ValidationResult()
        rec = validate_odometer_row(_odometer_row(), row_number=2, result=result)
        assert rec is not None
        assert rec.event_id == "O001"
        assert rec.odometer_km == 50000.0
        assert result.is_valid

    def test_negative_odometer_is_error(self):
        result = ValidationResult()
        rec = validate_odometer_row(
            _odometer_row(odometer_km="-100"), row_number=2, result=result
        )
        assert rec is None
        assert len(result.errors) >= 1

    def test_zero_odometer_is_valid(self):
        result = ValidationResult()
        rec = validate_odometer_row(
            _odometer_row(odometer_km="0"), row_number=2, result=result
        )
        assert rec is not None
        assert rec.odometer_km == 0.0

    def test_missing_event_id(self):
        result = ValidationResult()
        rec = validate_odometer_row(
            _odometer_row(event_id=""), row_number=2, result=result
        )
        assert rec is None

    def test_unparsable_odometer(self):
        result = ValidationResult()
        rec = validate_odometer_row(
            _odometer_row(odometer_km="abc"), row_number=2, result=result
        )
        assert rec is None


# ---------------------------------------------------------------------------
# validate_odometer_dataset
# ---------------------------------------------------------------------------


class TestValidateOdometerDataset:
    def test_empty(self):
        records, result = validate_odometer_dataset([])
        assert len(records) == 0
        assert result.is_valid

    def test_duplicate_event_id(self):
        rows = [_odometer_row(event_id="O001"), _odometer_row(event_id="O001")]
        records, result = validate_odometer_dataset(rows)
        assert any("Duplicate event_id" in e.message for e in result.errors)
        assert len(records) == 1

    def test_monotonicity_violation_warning(self):
        rows = [
            _odometer_row(event_id="O001", dt="2024-06-01T10:00:00", odometer_km="50000"),
            _odometer_row(event_id="O002", dt="2024-06-02T10:00:00", odometer_km="49000"),
        ]
        records, result = validate_odometer_dataset(rows)
        assert any("monotonicity" in w.message.lower() for w in result.warnings)
        # Records are still included (warning, not error)
        assert len(records) == 2

    def test_monotonically_increasing_no_warning(self):
        rows = [
            _odometer_row(event_id="O001", dt="2024-06-01T10:00:00", odometer_km="50000"),
            _odometer_row(event_id="O002", dt="2024-06-02T10:00:00", odometer_km="50200"),
        ]
        records, result = validate_odometer_dataset(rows)
        assert not any("monotonicity" in w.message.lower() for w in result.warnings)
        assert len(records) == 2

    def test_duplicate_datetime_warning(self):
        rows = [
            _odometer_row(event_id="O001", dt="2024-06-01T10:00:00", odometer_km="50000"),
            _odometer_row(event_id="O002", dt="2024-06-01T10:00:00", odometer_km="50000"),
        ]
        records, result = validate_odometer_dataset(rows)
        assert any("Duplicate datetime" in w.message for w in result.warnings)


# ---------------------------------------------------------------------------
# ValidationResult helpers
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_is_valid_with_only_warnings(self):
        result = ValidationResult()
        result.add_warning("just a warning")
        assert result.is_valid

    def test_is_invalid_with_error(self):
        result = ValidationResult()
        result.add_error("bad data")
        assert not result.is_valid

    def test_summary_format(self):
        result = ValidationResult()
        result.add_error("err1", row=2)
        result.add_warning("warn1", row=3)
        summary = result.summary()
        assert "1 error(s)" in summary
        assert "1 warning(s)" in summary
        assert "ERROR" in summary
        assert "WARN" in summary
