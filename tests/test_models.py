"""Tests for data models."""

import pytest
from datetime import datetime

from fuel_analysis.models import (
    Country,
    EstimatedValue,
    EstimationQuality,
    FuelRecord,
    FuelType,
    FullTankStatus,
    OdometerRecord,
)


class TestFuelType:
    def test_members(self):
        assert FuelType.E5.value == "E5"
        assert FuelType.E10.value == "E10"

    def test_str_enum(self):
        assert str(FuelType.E5) == "FuelType.E5"

    def test_from_value(self):
        assert FuelType("E5") is FuelType.E5

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            FuelType("E15")


class TestCountry:
    def test_primary_countries(self):
        for code in ("DE", "IT", "AT", "FR", "HR", "CH"):
            assert Country(code).value == code

    def test_invalid(self):
        with pytest.raises(ValueError):
            Country("XX")


class TestFullTankStatus:
    @pytest.mark.parametrize("val", ["true", "True", "1", "yes", "YES"])
    def test_yes(self, val):
        assert FullTankStatus.from_csv_value(val) is FullTankStatus.YES

    @pytest.mark.parametrize("val", ["false", "False", "0", "no", "NO"])
    def test_no(self, val):
        assert FullTankStatus.from_csv_value(val) is FullTankStatus.NO

    @pytest.mark.parametrize("val", ["", "  ", "NA", "none"])
    def test_unknown(self, val):
        assert FullTankStatus.from_csv_value(val) is FullTankStatus.UNKNOWN

    def test_invalid(self):
        with pytest.raises(ValueError):
            FullTankStatus.from_csv_value("maybe")


class TestFuelRecord:
    def test_computed_amount(self):
        r = FuelRecord(
            datetime=datetime(2024, 1, 1),
            amount_eur=75.0,
            liters=42.0,
            price_per_liter_eur=1.80,
            fuel_type=FuelType.E10,
            is_full_tank=FullTankStatus.YES,
            station_name="Test",
            city="Munich",
            country="DE",
            notes="",
        )
        assert r.computed_amount() == pytest.approx(42.0 * 1.80)


class TestEstimatedValue:
    def test_basic(self):
        v = EstimatedValue(value=5.5, quality=EstimationQuality.ESTIMATED, method="linear")
        assert v.value == 5.5
        assert v.quality is EstimationQuality.ESTIMATED
        assert v.method == "linear"

    def test_repr_with_method(self):
        v = EstimatedValue(value=1.0, quality=EstimationQuality.EXACT, method="linear")
        assert "exact" in repr(v)
        assert "linear" in repr(v)

    def test_repr_without_method(self):
        v = EstimatedValue(value=1.0, quality=EstimationQuality.INSUFFICIENT)
        assert "method=" not in repr(v)
