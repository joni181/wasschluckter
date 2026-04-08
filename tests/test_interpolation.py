"""Tests for fuel_analysis.interpolation: LinearInterpolation and factory."""

import pytest
from datetime import datetime

from fuel_analysis.interpolation import (
    LinearInterpolation,
    get_interpolation_strategy,
)
from fuel_analysis.models import EstimationQuality, OdometerRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _odo(
    event_id: str,
    dt: datetime,
    km: float,
) -> OdometerRecord:
    return OdometerRecord(event_id=event_id, datetime=dt, odometer_km=km, notes="")


# Reusable fixture records
_RECORDS = [
    _odo("O001", datetime(2024, 6, 1, 10, 0), 50000.0),
    _odo("O002", datetime(2024, 6, 11, 10, 0), 51000.0),
    _odo("O003", datetime(2024, 6, 21, 10, 0), 52000.0),
]


# ---------------------------------------------------------------------------
# LinearInterpolation
# ---------------------------------------------------------------------------


class TestLinearInterpolationExactMatch:
    def test_exact_match_first(self):
        interp = LinearInterpolation()
        result = interp.estimate(datetime(2024, 6, 1, 10, 0), _RECORDS)
        assert result.quality is EstimationQuality.EXACT
        assert result.value == 50000.0
        assert result.method == "linear"
        assert "exact match" in result.source_interval

    def test_exact_match_last(self):
        interp = LinearInterpolation()
        result = interp.estimate(datetime(2024, 6, 21, 10, 0), _RECORDS)
        assert result.quality is EstimationQuality.EXACT
        assert result.value == 52000.0

    def test_exact_match_middle(self):
        interp = LinearInterpolation()
        result = interp.estimate(datetime(2024, 6, 11, 10, 0), _RECORDS)
        assert result.quality is EstimationQuality.EXACT
        assert result.value == 51000.0


class TestLinearInterpolationBetweenPoints:
    def test_midpoint(self):
        interp = LinearInterpolation()
        # Midpoint between O001 (Jun 1) and O002 (Jun 11)
        mid = datetime(2024, 6, 6, 10, 0)
        result = interp.estimate(mid, _RECORDS)
        assert result.quality is EstimationQuality.ESTIMATED
        assert result.value == pytest.approx(50500.0)
        assert result.method == "linear"
        assert "O001" in result.source_interval
        assert "O002" in result.source_interval

    def test_quarter_point(self):
        interp = LinearInterpolation()
        # 25% between O001 and O002 (2.5 days out of 10)
        quarter = datetime(2024, 6, 3, 22, 0)
        total_sec = (datetime(2024, 6, 11, 10, 0) - datetime(2024, 6, 1, 10, 0)).total_seconds()
        frac = (quarter - datetime(2024, 6, 1, 10, 0)).total_seconds() / total_sec
        expected = 50000.0 + frac * 1000.0
        result = interp.estimate(quarter, _RECORDS)
        assert result.quality is EstimationQuality.ESTIMATED
        assert result.value == pytest.approx(expected, abs=0.1)

    def test_between_second_and_third(self):
        interp = LinearInterpolation()
        mid = datetime(2024, 6, 16, 10, 0)  # midpoint between O002 and O003
        result = interp.estimate(mid, _RECORDS)
        assert result.quality is EstimationQuality.ESTIMATED
        assert result.value == pytest.approx(51500.0)


class TestLinearInterpolationOutsideRange:
    def test_before_first_record(self):
        interp = LinearInterpolation()
        result = interp.estimate(datetime(2024, 5, 1, 10, 0), _RECORDS)
        assert result.quality is EstimationQuality.INSUFFICIENT
        assert result.value == 0.0

    def test_after_last_record(self):
        interp = LinearInterpolation()
        result = interp.estimate(datetime(2024, 7, 1, 10, 0), _RECORDS)
        assert result.quality is EstimationQuality.INSUFFICIENT
        assert result.value == 0.0


class TestLinearInterpolationEmptyRecords:
    def test_empty_list(self):
        interp = LinearInterpolation()
        result = interp.estimate(datetime(2024, 6, 1), [])
        assert result.quality is EstimationQuality.INSUFFICIENT
        assert result.value == 0.0
        assert result.method == "linear"


class TestLinearInterpolationSingleRecord:
    def test_exact_match_single(self):
        interp = LinearInterpolation()
        records = [_odo("O001", datetime(2024, 6, 1, 10, 0), 50000.0)]
        result = interp.estimate(datetime(2024, 6, 1, 10, 0), records)
        assert result.quality is EstimationQuality.EXACT

    def test_no_match_single(self):
        interp = LinearInterpolation()
        records = [_odo("O001", datetime(2024, 6, 1, 10, 0), 50000.0)]
        result = interp.estimate(datetime(2024, 6, 5, 10, 0), records)
        assert result.quality is EstimationQuality.INSUFFICIENT


class TestLinearInterpolationName:
    def test_name(self):
        assert LinearInterpolation().name() == "linear"


class TestLinearInterpolationUnsortedInput:
    def test_unsorted_records_still_work(self):
        """Records given in reverse order should produce the same result."""
        interp = LinearInterpolation()
        reversed_records = list(reversed(_RECORDS))
        mid = datetime(2024, 6, 6, 10, 0)
        result = interp.estimate(mid, reversed_records)
        assert result.quality is EstimationQuality.ESTIMATED
        assert result.value == pytest.approx(50500.0)


# ---------------------------------------------------------------------------
# get_interpolation_strategy factory
# ---------------------------------------------------------------------------


class TestGetInterpolationStrategy:
    def test_linear(self):
        s = get_interpolation_strategy("linear")
        assert isinstance(s, LinearInterpolation)
        assert s.name() == "linear"

    def test_default(self):
        s = get_interpolation_strategy()
        assert isinstance(s, LinearInterpolation)

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown interpolation method"):
            get_interpolation_strategy("cubic")
