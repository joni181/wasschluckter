"""Tests for fuel_analysis.metrics: DataFrame conversions and metric functions."""

import pytest
from datetime import datetime

import pandas as pd

from fuel_analysis.models import (
    EstimationQuality,
    FuelRecord,
    FuelType,
    FullTankStatus,
    OdometerRecord,
)
from fuel_analysis.metrics import (
    avg_price_by_country,
    average_fuel_price,
    compute_consumption_estimates,
    fuel_records_to_dataframe,
    fuel_type_summary,
    total_fuel_spending,
    total_fuel_volume,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fuel(
    event_id: str = "F001",
    dt: datetime = datetime(2024, 6, 1, 10, 0),
    amount_eur: float = 72.0,
    liters: float = 40.0,
    price_per_liter_eur: float = 1.80,
    fuel_type: FuelType = FuelType.E5,
    is_full_tank: FullTankStatus = FullTankStatus.YES,
    station_name: str = "Shell",
    city: str = "Berlin",
    country: str = "DE",
    notes: str = "",
) -> FuelRecord:
    return FuelRecord(
        event_id=event_id,
        datetime=dt,
        amount_eur=amount_eur,
        liters=liters,
        price_per_liter_eur=price_per_liter_eur,
        fuel_type=fuel_type,
        is_full_tank=is_full_tank,
        station_name=station_name,
        city=city,
        country=country,
        notes=notes,
    )


def _odo(event_id: str, dt: datetime, km: float) -> OdometerRecord:
    return OdometerRecord(event_id=event_id, datetime=dt, odometer_km=km, notes="")


# ---------------------------------------------------------------------------
# fuel_records_to_dataframe
# ---------------------------------------------------------------------------


class TestFuelRecordsToDataframe:
    def test_empty_list(self):
        df = fuel_records_to_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_single_record(self):
        df = fuel_records_to_dataframe([_fuel()])
        assert len(df) == 1
        assert df["event_id"].iloc[0] == "F001"
        assert df["liters"].iloc[0] == 40.0
        assert df["fuel_type"].iloc[0] == "E5"
        assert df["is_full_tank"].iloc[0] == "true"

    def test_sorted_by_datetime(self):
        records = [
            _fuel(event_id="F002", dt=datetime(2024, 6, 15, 10, 0)),
            _fuel(event_id="F001", dt=datetime(2024, 6, 1, 10, 0)),
        ]
        df = fuel_records_to_dataframe(records)
        assert df["event_id"].iloc[0] == "F001"
        assert df["event_id"].iloc[1] == "F002"

    def test_columns_present(self):
        df = fuel_records_to_dataframe([_fuel()])
        expected_cols = {
            "event_id", "datetime", "amount_eur", "liters",
            "price_per_liter_eur", "fuel_type", "is_full_tank",
            "station_name", "city", "country", "notes",
        }
        assert expected_cols.issubset(set(df.columns))


# ---------------------------------------------------------------------------
# total_fuel_volume
# ---------------------------------------------------------------------------


class TestTotalFuelVolume:
    def test_single_record(self):
        df = fuel_records_to_dataframe([_fuel(liters=40.0)])
        assert total_fuel_volume(df) == pytest.approx(40.0)

    def test_multiple_records(self):
        records = [
            _fuel(event_id="F001", liters=40.0),
            _fuel(event_id="F002", liters=35.0),
        ]
        df = fuel_records_to_dataframe(records)
        assert total_fuel_volume(df) == pytest.approx(75.0)

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        assert total_fuel_volume(df) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# total_fuel_spending
# ---------------------------------------------------------------------------


class TestTotalFuelSpending:
    def test_single_record(self):
        df = fuel_records_to_dataframe([_fuel(amount_eur=72.0)])
        assert total_fuel_spending(df) == pytest.approx(72.0)

    def test_multiple_records(self):
        records = [
            _fuel(event_id="F001", amount_eur=72.0),
            _fuel(event_id="F002", amount_eur=60.0),
        ]
        df = fuel_records_to_dataframe(records)
        assert total_fuel_spending(df) == pytest.approx(132.0)


# ---------------------------------------------------------------------------
# average_fuel_price (volume-weighted)
# ---------------------------------------------------------------------------


class TestAverageFuelPrice:
    def test_single_record(self):
        df = fuel_records_to_dataframe([_fuel(amount_eur=72.0, liters=40.0)])
        assert average_fuel_price(df) == pytest.approx(1.80)

    def test_weighted_average(self):
        records = [
            _fuel(event_id="F001", amount_eur=72.0, liters=40.0),   # 1.80/L
            _fuel(event_id="F002", amount_eur=40.0, liters=20.0),   # 2.00/L
        ]
        df = fuel_records_to_dataframe(records)
        # (72 + 40) / (40 + 20) = 112/60 = 1.8667
        assert average_fuel_price(df) == pytest.approx(112.0 / 60.0)

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        assert average_fuel_price(df) == 0.0


# ---------------------------------------------------------------------------
# fuel_type_summary
# ---------------------------------------------------------------------------


class TestFuelTypeSummary:
    def test_single_type(self):
        records = [
            _fuel(event_id="F001", fuel_type=FuelType.E5, liters=40.0, amount_eur=72.0),
            _fuel(event_id="F002", fuel_type=FuelType.E5, liters=35.0, amount_eur=63.0),
        ]
        df = fuel_records_to_dataframe(records)
        summary = fuel_type_summary(df)
        assert len(summary) == 1
        row = summary.iloc[0]
        assert row["fuel_type"] == "E5"
        assert row["count"] == 2
        assert row["total_liters"] == pytest.approx(75.0)
        assert row["total_eur"] == pytest.approx(135.0)

    def test_multiple_types(self):
        records = [
            _fuel(event_id="F001", fuel_type=FuelType.E5, liters=40.0, amount_eur=72.0),
            _fuel(event_id="F002", fuel_type=FuelType.E10, liters=30.0, amount_eur=51.0),
        ]
        df = fuel_records_to_dataframe(records)
        summary = fuel_type_summary(df)
        assert len(summary) == 2
        types = set(summary["fuel_type"])
        assert types == {"E5", "E10"}

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        summary = fuel_type_summary(df)
        assert summary.empty


# ---------------------------------------------------------------------------
# avg_price_by_country
# ---------------------------------------------------------------------------


class TestAvgPriceByCountry:
    def test_single_country(self):
        records = [
            _fuel(event_id="F001", country="DE", amount_eur=72.0, liters=40.0),
            _fuel(event_id="F002", country="DE", amount_eur=63.0, liters=35.0),
        ]
        df = fuel_records_to_dataframe(records)
        result = avg_price_by_country(df)
        assert len(result) == 1
        assert result.iloc[0]["country"] == "DE"
        # (72+63)/(40+35) = 135/75 = 1.80
        assert result.iloc[0]["avg_price_per_liter"] == pytest.approx(1.80)
        assert result.iloc[0]["total_liters"] == pytest.approx(75.0)

    def test_multiple_countries(self):
        records = [
            _fuel(event_id="F001", country="DE", amount_eur=72.0, liters=40.0),
            _fuel(event_id="F002", country="IT", amount_eur=80.0, liters=40.0),
        ]
        df = fuel_records_to_dataframe(records)
        result = avg_price_by_country(df)
        assert len(result) == 2
        de_row = result[result["country"] == "DE"].iloc[0]
        it_row = result[result["country"] == "IT"].iloc[0]
        assert de_row["avg_price_per_liter"] == pytest.approx(1.80)
        assert it_row["avg_price_per_liter"] == pytest.approx(2.00)

    def test_empty(self):
        df = fuel_records_to_dataframe([])
        result = avg_price_by_country(df)
        assert result.empty


# ---------------------------------------------------------------------------
# compute_consumption_estimates
# ---------------------------------------------------------------------------


class TestComputeConsumptionEstimates:
    def _make_scenario(self):
        """Two fuel events bracketed by two odometer readings."""
        fuel = [
            _fuel(
                event_id="F001",
                dt=datetime(2024, 6, 5, 10, 0),
                liters=40.0,
                amount_eur=72.0,
            ),
            _fuel(
                event_id="F002",
                dt=datetime(2024, 6, 15, 10, 0),
                liters=35.0,
                amount_eur=63.0,
            ),
        ]
        odo = [
            _odo("O001", datetime(2024, 6, 1, 10, 0), 50000.0),
            _odo("O002", datetime(2024, 6, 21, 10, 0), 52000.0),
        ]
        return fuel, odo

    def test_basic_pipeline(self):
        fuel, odo = self._make_scenario()
        estimates = compute_consumption_estimates(fuel, odo)
        assert len(estimates) == 1
        est = estimates[0]
        assert est.fuel_event_id == "F002"
        assert est.liters == 35.0
        assert est.amount_eur == 63.0
        assert est.estimated_km > 0
        assert est.liters_per_100km.quality is EstimationQuality.ESTIMATED
        assert est.liters_per_100km.method == "linear"
        assert est.cost_per_100km.value > 0
        assert est.cost_per_km.value > 0

    def test_estimated_km_value(self):
        fuel, odo = self._make_scenario()
        estimates = compute_consumption_estimates(fuel, odo)
        est = estimates[0]
        # O001: Jun 1 = 50000, O002: Jun 21 = 52000
        # F001: Jun 5 => fraction = 4/20 * 2000 = 400 => 50400
        # F002: Jun 15 => fraction = 14/20 * 2000 = 1400 => 51400
        # estimated_km = 51400 - 50400 = 1000
        assert est.estimated_km == pytest.approx(1000.0)
        # liters_per_100km = 35 / 1000 * 100 = 3.5
        assert est.liters_per_100km.value == pytest.approx(3.5)

    def test_too_few_fuel_records(self):
        fuel = [_fuel()]
        odo = [
            _odo("O001", datetime(2024, 6, 1), 50000.0),
            _odo("O002", datetime(2024, 6, 21), 52000.0),
        ]
        assert compute_consumption_estimates(fuel, odo) == []

    def test_too_few_odometer_records(self):
        fuel = [
            _fuel(event_id="F001", dt=datetime(2024, 6, 5)),
            _fuel(event_id="F002", dt=datetime(2024, 6, 15)),
        ]
        odo = [_odo("O001", datetime(2024, 6, 1), 50000.0)]
        assert compute_consumption_estimates(fuel, odo) == []

    def test_fuel_outside_odometer_range_skipped(self):
        """When fuel events fall outside odometer range, they produce INSUFFICIENT
        and are skipped."""
        fuel = [
            _fuel(event_id="F001", dt=datetime(2024, 5, 1, 10, 0)),
            _fuel(event_id="F002", dt=datetime(2024, 5, 10, 10, 0)),
        ]
        odo = [
            _odo("O001", datetime(2024, 6, 1, 10, 0), 50000.0),
            _odo("O002", datetime(2024, 6, 21, 10, 0), 52000.0),
        ]
        estimates = compute_consumption_estimates(fuel, odo)
        assert len(estimates) == 0

    def test_exact_odometer_match_quality(self):
        """When fuel event datetimes exactly match odometer readings, quality is EXACT."""
        fuel = [
            _fuel(event_id="F001", dt=datetime(2024, 6, 1, 10, 0), liters=40.0, amount_eur=72.0),
            _fuel(event_id="F002", dt=datetime(2024, 6, 21, 10, 0), liters=35.0, amount_eur=63.0),
        ]
        odo = [
            _odo("O001", datetime(2024, 6, 1, 10, 0), 50000.0),
            _odo("O002", datetime(2024, 6, 21, 10, 0), 52000.0),
        ]
        estimates = compute_consumption_estimates(fuel, odo)
        assert len(estimates) == 1
        assert estimates[0].liters_per_100km.quality is EstimationQuality.EXACT
        assert estimates[0].estimated_km == pytest.approx(2000.0)

    def test_three_fuel_events_produce_two_estimates(self):
        fuel = [
            _fuel(event_id="F001", dt=datetime(2024, 6, 5, 10, 0), liters=40.0, amount_eur=72.0),
            _fuel(event_id="F002", dt=datetime(2024, 6, 10, 10, 0), liters=35.0, amount_eur=63.0),
            _fuel(event_id="F003", dt=datetime(2024, 6, 15, 10, 0), liters=30.0, amount_eur=54.0),
        ]
        odo = [
            _odo("O001", datetime(2024, 6, 1, 10, 0), 50000.0),
            _odo("O002", datetime(2024, 6, 21, 10, 0), 52000.0),
        ]
        estimates = compute_consumption_estimates(fuel, odo)
        assert len(estimates) == 2
        assert estimates[0].fuel_event_id == "F002"
        assert estimates[1].fuel_event_id == "F003"
