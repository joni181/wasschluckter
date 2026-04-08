"""Tests for fuel_analysis.models: enums, data classes, and helper methods."""

import pytest
from datetime import datetime

from fuel_analysis.models import (
    Country,
    EstimatedValue,
    EstimationQuality,
    FuelRecord,
    FuelType,
    FullTankStatus,
)


# ---------------------------------------------------------------------------
# FuelType enum
# ---------------------------------------------------------------------------


class TestFuelType:
    def test_members(self):
        assert FuelType.E5.value == "E5"
        assert FuelType.E10.value == "E10"

    def test_str_enum_behaviour(self):
        assert FuelType.E5 == "E5"
        assert FuelType.E10 == "E10"

    def test_from_value(self):
        assert FuelType("E5") is FuelType.E5
        assert FuelType("E10") is FuelType.E10

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            FuelType("Diesel")


# ---------------------------------------------------------------------------
# Country enum
# ---------------------------------------------------------------------------


class TestCountry:
    def test_primary_countries(self):
        expected = {"DE", "IT", "AT", "FR", "HR", "CH"}
        actual = {c.value for c in Country}
        assert actual == expected

    def test_str_enum_behaviour(self):
        assert Country.DE == "DE"

    def test_invalid_country(self):
        with pytest.raises(ValueError):
            Country("XX")


# ---------------------------------------------------------------------------
# FullTankStatus enum & from_csv_value
# ---------------------------------------------------------------------------


class TestFullTankStatus:
    def test_members(self):
        assert FullTankStatus.YES.value == "true"
        assert FullTankStatus.NO.value == "false"
        assert FullTankStatus.UNKNOWN.value == "unknown"

    # --- from_csv_value truthy ---
    @pytest.mark.parametrize("raw", ["true", "True", "TRUE", "1", "yes", "Yes"])
    def test_from_csv_value_yes(self, raw):
        assert FullTankStatus.from_csv_value(raw) is FullTankStatus.YES

    # --- from_csv_value falsy ---
    @pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", "No"])
    def test_from_csv_value_no(self, raw):
        assert FullTankStatus.from_csv_value(raw) is FullTankStatus.NO

    # --- from_csv_value unknown ---
    @pytest.mark.parametrize("raw", ["", "  ", "NA", "na", "none", "None"])
    def test_from_csv_value_unknown(self, raw):
        assert FullTankStatus.from_csv_value(raw) is FullTankStatus.UNKNOWN

    # --- from_csv_value with surrounding whitespace ---
    def test_from_csv_value_strips_whitespace(self):
        assert FullTankStatus.from_csv_value("  true  ") is FullTankStatus.YES
        assert FullTankStatus.from_csv_value("  false  ") is FullTankStatus.NO

    # --- from_csv_value invalid ---
    def test_from_csv_value_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid full tank value"):
            FullTankStatus.from_csv_value("maybe")


# ---------------------------------------------------------------------------
# EstimationQuality enum
# ---------------------------------------------------------------------------


class TestEstimationQuality:
    def test_members(self):
        assert EstimationQuality.EXACT.value == "exact"
        assert EstimationQuality.ESTIMATED.value == "estimated"
        assert EstimationQuality.INSUFFICIENT.value == "insufficient"

    def test_str_enum(self):
        assert EstimationQuality.EXACT == "exact"


# ---------------------------------------------------------------------------
# FuelRecord.computed_amount
# ---------------------------------------------------------------------------


def _make_fuel_record(
    liters: float = 40.0,
    price_per_liter_eur: float = 1.80,
    amount_eur: float = 72.0,
    event_id: str = "F001",
) -> FuelRecord:
    return FuelRecord(
        event_id=event_id,
        datetime=datetime(2024, 6, 1, 10, 0),
        amount_eur=amount_eur,
        liters=liters,
        price_per_liter_eur=price_per_liter_eur,
        fuel_type=FuelType.E5,
        is_full_tank=FullTankStatus.YES,
        station_name="Test Station",
        city="Berlin",
        country="DE",
        notes="",
    )


class TestFuelRecordComputedAmount:
    def test_basic(self):
        rec = _make_fuel_record(liters=40.0, price_per_liter_eur=1.80)
        assert rec.computed_amount() == pytest.approx(72.0)

    def test_matches_amount_eur(self):
        rec = _make_fuel_record(liters=35.5, price_per_liter_eur=1.759, amount_eur=62.44)
        assert rec.computed_amount() == pytest.approx(35.5 * 1.759)

    def test_zero_liters(self):
        # Edge case: 0 liters would be invalid in real data but computed_amount still works
        rec = _make_fuel_record(liters=0.0, price_per_liter_eur=1.80, amount_eur=0.0)
        assert rec.computed_amount() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# EstimatedValue
# ---------------------------------------------------------------------------


class TestEstimatedValue:
    def test_basic_creation(self):
        ev = EstimatedValue(value=12345.0, quality=EstimationQuality.EXACT)
        assert ev.value == 12345.0
        assert ev.quality is EstimationQuality.EXACT
        assert ev.method is None
        assert ev.source_interval is None

    def test_full_creation(self):
        ev = EstimatedValue(
            value=100.5,
            quality=EstimationQuality.ESTIMATED,
            method="linear",
            source_interval="O001 -> O002",
        )
        assert ev.method == "linear"
        assert ev.source_interval == "O001 -> O002"

    def test_repr_without_method(self):
        ev = EstimatedValue(value=5.1234, quality=EstimationQuality.EXACT)
        r = repr(ev)
        assert "5.1234" in r
        assert "exact" in r
        assert "method=" not in r

    def test_repr_with_method(self):
        ev = EstimatedValue(
            value=7.0, quality=EstimationQuality.ESTIMATED, method="linear"
        )
        r = repr(ev)
        assert "estimated" in r
        assert "method=linear" in r

    def test_frozen(self):
        ev = EstimatedValue(value=1.0, quality=EstimationQuality.EXACT)
        with pytest.raises(AttributeError):
            ev.value = 2.0  # type: ignore[misc]
