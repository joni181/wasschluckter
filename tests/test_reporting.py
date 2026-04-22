"""Tests for HTML report generation."""

from __future__ import annotations

from datetime import date, datetime

from fuel_analysis.metrics import estimate_distance_between_datetimes
from fuel_analysis.models import FuelRecord, FuelType, FullTankStatus, OdometerRecord
from fuel_analysis.reporting import generate_html_report, render_html_report, resolve_report_period
from fuel_analysis.validators import ValidationResult


def _fuel(
    dt: datetime,
    liters: float = 40.0,
    amount: float = 72.0,
    full_tank: FullTankStatus = FullTankStatus.YES,
) -> FuelRecord:
    return FuelRecord(
        datetime=dt,
        amount_eur=amount,
        liters=liters,
        fuel_type=FuelType.E10,
        is_full_tank=full_tank,
        station_name="Test Station",
        city="Munich",
        country="DE",
        notes="",
    )


def _odo(dt: datetime, km: float) -> OdometerRecord:
    return OdometerRecord(datetime=dt, odometer_km=km, notes="")


class TestResolveReportPeriod:
    def test_date_inputs_become_inclusive_day_bounds(self):
        period = resolve_report_period(
            fuel_records=[_fuel(datetime(2024, 3, 15, 8, 30))],
            odometer_records=[_odo(datetime(2024, 3, 16, 9, 0), 45230)],
            start=date(2024, 3, 15),
            end=date(2024, 3, 16),
        )

        assert period.start == datetime(2024, 3, 15, 0, 0)
        assert period.end.date().isoformat() == "2024-03-16"
        assert period.end.hour == 23


class TestRenderHtmlReport:
    def test_report_mentions_selected_period_and_estimates(self):
        fuel_records = [
            _fuel(datetime(2024, 3, 15, 8, 30), liters=42.5, amount=75.5),
            _fuel(datetime(2024, 3, 28, 17, 45), liters=45.2, amount=82.3, full_tank=FullTankStatus.NO),
            _fuel(datetime(2024, 4, 22, 14, 0), liters=41.8, amount=71.2),
        ]
        odometer_records = [
            _odo(datetime(2024, 3, 14, 20, 0), 45230),
            _odo(datetime(2024, 3, 22, 18, 0), 45810),
            _odo(datetime(2024, 4, 18, 12, 0), 47350),
            _odo(datetime(2024, 5, 1, 8, 0), 48100),
        ]

        html = render_html_report(
            fuel_records,
            odometer_records,
            ValidationResult(),
            ValidationResult(),
            start=date(2024, 3, 15),
            end=date(2024, 4, 30),
        )

        assert "Reporting period: from 2024-03-15 to 2024-04-30" in html
        assert "Consumption Interval Provenance" in html
        assert "linear interpolation" in html
        assert "partial or unknown fills" in html.lower()

    def test_generate_html_report_writes_file(self, tmp_path):
        fuel_records = [
            _fuel(datetime(2024, 3, 15, 8, 30), liters=42.5, amount=75.5),
            _fuel(datetime(2024, 4, 22, 14, 0), liters=41.8, amount=71.2),
        ]
        odometer_records = [
            _odo(datetime(2024, 3, 14, 20, 0), 45230),
            _odo(datetime(2024, 4, 18, 12, 0), 47350),
            _odo(datetime(2024, 5, 1, 8, 0), 48100),
        ]

        output_path = tmp_path / "report.html"
        written = generate_html_report(
            fuel_records,
            odometer_records,
            ValidationResult(),
            ValidationResult(),
            start=date(2024, 3, 15),
            end=date(2024, 4, 30),
            output_path=output_path,
        )

        assert written == output_path
        assert output_path.exists()
        assert "Fuel Analysis Report" in output_path.read_text(encoding="utf-8")

    def test_report_without_explicit_dates_uses_full_data_range(self):
        fuel_records = [
            _fuel(datetime(2024, 3, 15, 8, 30)),
            _fuel(datetime(2024, 4, 22, 14, 0)),
        ]
        odometer_records = [
            _odo(datetime(2024, 3, 14, 20, 0), 45230),
            _odo(datetime(2024, 5, 1, 8, 0), 48100),
        ]

        html = render_html_report(
            fuel_records,
            odometer_records,
            ValidationResult(),
            ValidationResult(),
        )

        assert "Reporting period: from 2024-03-14 to 2024-05-01" in html


class TestPeriodDistanceEstimate:
    def test_distance_estimate_can_span_selected_range(self):
        distance = estimate_distance_between_datetimes(
            datetime(2024, 3, 15, 0, 0),
            datetime(2024, 4, 30, 23, 59, 59, 999999),
            [
                _odo(datetime(2024, 3, 14, 20, 0), 45230),
                _odo(datetime(2024, 3, 22, 18, 0), 45810),
                _odo(datetime(2024, 4, 18, 12, 0), 47350),
                _odo(datetime(2024, 5, 1, 8, 0), 48100),
            ],
        )

        assert distance.value > 0
        assert distance.method == "linear"
