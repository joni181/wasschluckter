"""Tests for interpolation logic."""

import pytest
from datetime import datetime

from fuel_analysis.models import EstimationQuality, OdometerRecord
from fuel_analysis.interpolation import LinearInterpolation, get_interpolation_strategy


def _odo(dt: datetime, km: float) -> OdometerRecord:
    return OdometerRecord(datetime=dt, odometer_km=km, notes="")


RECORDS = [
    _odo(datetime(2024, 3, 1, 10, 0), 45000.0),
    _odo(datetime(2024, 4, 1, 10, 0), 46000.0),
    _odo(datetime(2024, 5, 1, 10, 0), 47500.0),
]


class TestLinearInterpolationExactMatch:
    def test_first(self):
        strategy = LinearInterpolation()
        result = strategy.estimate(datetime(2024, 3, 1, 10, 0), RECORDS)
        assert result.quality is EstimationQuality.EXACT
        assert result.value == 45000.0

    def test_middle(self):
        strategy = LinearInterpolation()
        result = strategy.estimate(datetime(2024, 4, 1, 10, 0), RECORDS)
        assert result.quality is EstimationQuality.EXACT
        assert result.value == 46000.0

    def test_last(self):
        strategy = LinearInterpolation()
        result = strategy.estimate(datetime(2024, 5, 1, 10, 0), RECORDS)
        assert result.quality is EstimationQuality.EXACT
        assert result.value == 47500.0


class TestLinearInterpolationBetween:
    def test_midpoint(self):
        strategy = LinearInterpolation()
        dt = datetime(2024, 3, 16, 22, 0)
        result = strategy.estimate(dt, RECORDS)
        assert result.quality is EstimationQuality.ESTIMATED
        assert result.method == "linear"
        assert 45000 < result.value < 46000

    def test_between_second_and_third(self):
        strategy = LinearInterpolation()
        dt = datetime(2024, 4, 16, 10, 0)
        result = strategy.estimate(dt, RECORDS)
        assert result.quality is EstimationQuality.ESTIMATED
        assert 46000 < result.value < 47500


class TestLinearInterpolationOutsideRange:
    def test_before_first(self):
        strategy = LinearInterpolation()
        result = strategy.estimate(datetime(2024, 2, 1, 10, 0), RECORDS)
        assert result.quality is EstimationQuality.INSUFFICIENT

    def test_after_last(self):
        strategy = LinearInterpolation()
        result = strategy.estimate(datetime(2024, 6, 1, 10, 0), RECORDS)
        assert result.quality is EstimationQuality.INSUFFICIENT


class TestLinearInterpolationEdgeCases:
    def test_empty_records(self):
        strategy = LinearInterpolation()
        result = strategy.estimate(datetime(2024, 3, 1), [])
        assert result.quality is EstimationQuality.INSUFFICIENT

    def test_single_record_exact(self):
        strategy = LinearInterpolation()
        records = [_odo(datetime(2024, 3, 1, 10, 0), 45000.0)]
        result = strategy.estimate(datetime(2024, 3, 1, 10, 0), records)
        assert result.quality is EstimationQuality.EXACT

    def test_single_record_no_match(self):
        strategy = LinearInterpolation()
        records = [_odo(datetime(2024, 3, 1, 10, 0), 45000.0)]
        result = strategy.estimate(datetime(2024, 3, 2, 10, 0), records)
        assert result.quality is EstimationQuality.INSUFFICIENT

    def test_unsorted_input(self):
        strategy = LinearInterpolation()
        unsorted = [RECORDS[2], RECORDS[0], RECORDS[1]]
        result = strategy.estimate(datetime(2024, 3, 16, 22, 0), unsorted)
        assert result.quality is EstimationQuality.ESTIMATED
        assert 45000 < result.value < 46000

    def test_name(self):
        assert LinearInterpolation().name() == "linear"


class TestGetInterpolationStrategy:
    def test_linear(self):
        s = get_interpolation_strategy("linear")
        assert isinstance(s, LinearInterpolation)

    def test_default(self):
        s = get_interpolation_strategy()
        assert isinstance(s, LinearInterpolation)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown interpolation"):
            get_interpolation_strategy("cubic")
