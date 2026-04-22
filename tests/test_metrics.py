"""Tests for metric computations."""

import pytest
from datetime import datetime

from fuel_analysis.models import (
    EstimationQuality,
    FuelRecord,
    FuelType,
    FullTankStatus,
    OdometerRecord,
)
from fuel_analysis.metrics import (
    average_fuel_price,
    avg_price_by_country,
    compute_consumption_estimates,
    consumption_estimates_to_dataframe,
    estimate_distance_between_datetimes,
    fuel_records_to_dataframe,
    fuel_type_summary,
    total_fuel_spending,
    total_fuel_volume,
)


def _fuel(
    dt: datetime,
    liters: float = 40.0,
    amount: float = 72.0,
    fuel_type: FuelType = FuelType.E10,
    country: str = "DE",
) -> FuelRecord:
    return FuelRecord(
        datetime=dt,
        amount_eur=amount,
        liters=liters,
        fuel_type=fuel_type,
        is_full_tank=FullTankStatus.YES,
        station_name="Test",
        city="Munich",
        country=country,
        notes="",
    )


def _odo(dt: datetime, km: float) -> OdometerRecord:
    return OdometerRecord(datetime=dt, odometer_km=km, notes="")


class TestFuelRecordsToDataframe:
    def test_empty(self):
        df = fuel_records_to_dataframe([])
        assert df.empty

    def test_single_record(self):
        df = fuel_records_to_dataframe([_fuel(datetime(2024, 3, 1))])
        assert len(df) == 1
        assert df["liters"].iloc[0] == 40.0

    def test_sorted_by_datetime(self):
        records = [
            _fuel(datetime(2024, 4, 1)),
            _fuel(datetime(2024, 3, 1)),
        ]
        df = fuel_records_to_dataframe(records)
        assert df["datetime"].iloc[0] < df["datetime"].iloc[1]

    def test_no_event_id_column(self):
        df = fuel_records_to_dataframe([_fuel(datetime(2024, 3, 1))])
        assert "event_id" not in df.columns


class TestTotalFuelVolume:
    def test_single(self):
        df = fuel_records_to_dataframe([_fuel(datetime(2024, 3, 1), liters=42.5)])
        assert total_fuel_volume(df) == pytest.approx(42.5)

    def test_multiple(self):
        records = [
            _fuel(datetime(2024, 3, 1), liters=40.0),
            _fuel(datetime(2024, 4, 1), liters=35.0),
        ]
        df = fuel_records_to_dataframe(records)
        assert total_fuel_volume(df) == pytest.approx(75.0)

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        assert total_fuel_volume(df) == pytest.approx(0.0)


class TestTotalFuelSpending:
    def test_single(self):
        df = fuel_records_to_dataframe([_fuel(datetime(2024, 3, 1), amount=75.50)])
        assert total_fuel_spending(df) == pytest.approx(75.50)

    def test_multiple(self):
        records = [
            _fuel(datetime(2024, 3, 1), amount=70.0),
            _fuel(datetime(2024, 4, 1), amount=80.0),
        ]
        df = fuel_records_to_dataframe(records)
        assert total_fuel_spending(df) == pytest.approx(150.0)


class TestAverageFuelPrice:
    def test_single(self):
        df = fuel_records_to_dataframe([_fuel(datetime(2024, 3, 1), liters=40, amount=72)])
        assert average_fuel_price(df) == pytest.approx(72.0 / 40.0)

    def test_weighted(self):
        records = [
            _fuel(datetime(2024, 3, 1), liters=10, amount=18),
            _fuel(datetime(2024, 4, 1), liters=20, amount=40),
        ]
        df = fuel_records_to_dataframe(records)
        assert average_fuel_price(df) == pytest.approx(58.0 / 30.0)

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        assert average_fuel_price(df) == 0.0


class TestFuelTypeSummary:
    def test_single_type(self):
        records = [_fuel(datetime(2024, 3, 1), fuel_type=FuelType.E10, liters=40, amount=72)]
        df = fuel_records_to_dataframe(records)
        summary = fuel_type_summary(df)
        assert len(summary) == 1
        assert summary["fuel_type"].iloc[0] == "E10"
        assert summary["total_liters"].iloc[0] == pytest.approx(40.0)

    def test_multiple_types(self):
        records = [
            _fuel(datetime(2024, 3, 1), fuel_type=FuelType.E5),
            _fuel(datetime(2024, 4, 1), fuel_type=FuelType.E10),
        ]
        df = fuel_records_to_dataframe(records)
        summary = fuel_type_summary(df)
        assert len(summary) == 2

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        summary = fuel_type_summary(df)
        assert summary.empty


class TestAvgPriceByCountry:
    def test_single_country(self):
        records = [_fuel(datetime(2024, 3, 1), liters=40, amount=72, country="DE")]
        df = fuel_records_to_dataframe(records)
        result = avg_price_by_country(df)
        assert len(result) == 1
        assert result["avg_price_per_liter"].iloc[0] == pytest.approx(72.0 / 40.0)

    def test_multiple_countries(self):
        records = [
            _fuel(datetime(2024, 3, 1), liters=40, amount=72, country="DE"),
            _fuel(datetime(2024, 4, 1), liters=40, amount=80, country="AT"),
        ]
        df = fuel_records_to_dataframe(records)
        result = avg_price_by_country(df)
        assert len(result) == 2

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        result = avg_price_by_country(df)
        assert result.empty


class TestComputeConsumptionEstimates:
    def test_basic_pipeline(self):
        fuel = [
            _fuel(datetime(2024, 3, 15, 10, 0), liters=40, amount=72),
            _fuel(datetime(2024, 4, 15, 10, 0), liters=45, amount=81),
        ]
        odo = [
            _odo(datetime(2024, 3, 1, 10, 0), 45000),
            _odo(datetime(2024, 5, 1, 10, 0), 46000),
        ]
        estimates = compute_consumption_estimates(fuel, odo)
        assert len(estimates) == 1
        assert estimates[0].liters == 45
        assert estimates[0].estimated_km > 0

    def test_estimated_quality(self):
        fuel = [
            _fuel(datetime(2024, 3, 15, 10, 0)),
            _fuel(datetime(2024, 4, 15, 10, 0)),
        ]
        odo = [
            _odo(datetime(2024, 3, 1, 10, 0), 45000),
            _odo(datetime(2024, 5, 1, 10, 0), 46000),
        ]
        estimates = compute_consumption_estimates(fuel, odo)
        assert estimates[0].liters_per_100km.quality is EstimationQuality.ESTIMATED

    def test_too_few_fuel_records(self):
        fuel = [_fuel(datetime(2024, 3, 15))]
        odo = [_odo(datetime(2024, 3, 1), 45000), _odo(datetime(2024, 4, 1), 46000)]
        assert compute_consumption_estimates(fuel, odo) == []

    def test_too_few_odometer_records(self):
        fuel = [_fuel(datetime(2024, 3, 15)), _fuel(datetime(2024, 4, 15))]
        odo = [_odo(datetime(2024, 3, 1), 45000)]
        assert compute_consumption_estimates(fuel, odo) == []

    def test_fuel_outside_odometer_range(self):
        fuel = [
            _fuel(datetime(2024, 1, 1)),
            _fuel(datetime(2024, 2, 1)),
        ]
        odo = [
            _odo(datetime(2024, 3, 1), 45000),
            _odo(datetime(2024, 4, 1), 46000),
        ]
        assert compute_consumption_estimates(fuel, odo) == []

    def test_three_fuel_events(self):
        fuel = [
            _fuel(datetime(2024, 3, 10, 10, 0)),
            _fuel(datetime(2024, 3, 20, 10, 0)),
            _fuel(datetime(2024, 3, 30, 10, 0)),
        ]
        odo = [
            _odo(datetime(2024, 3, 1, 10, 0), 45000),
            _odo(datetime(2024, 4, 1, 10, 0), 46000),
        ]
        estimates = compute_consumption_estimates(fuel, odo)
        assert len(estimates) == 2

    def test_dataframe_contains_boundary_provenance(self):
        fuel = [
            _fuel(datetime(2024, 3, 15, 10, 0), liters=40, amount=72),
            _fuel(datetime(2024, 4, 15, 10, 0), liters=45, amount=81),
        ]
        odo = [
            _odo(datetime(2024, 3, 1, 10, 0), 45000),
            _odo(datetime(2024, 5, 1, 10, 0), 46000),
        ]
        estimates = compute_consumption_estimates(fuel, odo)
        df = consumption_estimates_to_dataframe(estimates)

        assert "previous_fuel_datetime" in df.columns
        assert "odometer_at_previous_quality" in df.columns
        assert "odometer_at_current_source_interval" in df.columns
        assert df["odometer_at_previous_quality"].iloc[0] == "estimated"


class TestEstimateDistanceBetweenDatetimes:
    def test_exact_when_both_boundaries_exist(self):
        odo = [
            _odo(datetime(2024, 3, 1, 10, 0), 45000),
            _odo(datetime(2024, 4, 1, 10, 0), 46000),
        ]
        distance = estimate_distance_between_datetimes(
            datetime(2024, 3, 1, 10, 0),
            datetime(2024, 4, 1, 10, 0),
            odo,
        )

        assert distance.quality is EstimationQuality.EXACT
        assert distance.value == pytest.approx(1000.0)

    def test_estimated_when_boundary_requires_interpolation(self):
        odo = [
            _odo(datetime(2024, 3, 1, 10, 0), 45000),
            _odo(datetime(2024, 4, 1, 10, 0), 46000),
            _odo(datetime(2024, 5, 1, 10, 0), 47000),
        ]
        distance = estimate_distance_between_datetimes(
            datetime(2024, 3, 15, 10, 0),
            datetime(2024, 4, 15, 10, 0),
            odo,
        )

        assert distance.quality is EstimationQuality.ESTIMATED
        assert distance.value > 0
        assert "start:" in distance.source_interval
