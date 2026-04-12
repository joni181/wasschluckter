"""Metric computation for fuel and odometer data.

All metrics that combine fuel and odometer data use interpolation
and are clearly labeled as estimated. See interpolation.py for
rationale on why linear interpolation is used in v1.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from .interpolation import InterpolationStrategy, get_interpolation_strategy
from .models import (
    EstimatedValue,
    EstimationQuality,
    FuelRecord,
    OdometerRecord,
)


# --- Fuel-only metrics ---


def fuel_records_to_dataframe(records: list[FuelRecord]) -> pd.DataFrame:
    """Convert fuel records to a pandas DataFrame."""
    data = [
        {
            "datetime": r.datetime,
            "amount_eur": r.amount_eur,
            "liters": r.liters,
            "price_per_liter_eur": r.price_per_liter_eur,
            "fuel_type": r.fuel_type.value,
            "is_full_tank": r.is_full_tank.value,
            "station_name": r.station_name,
            "city": r.city,
            "country": r.country,
            "notes": r.notes,
        }
        for r in records
    ]
    df = pd.DataFrame(data)
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
    return df


def odometer_records_to_dataframe(records: list[OdometerRecord]) -> pd.DataFrame:
    """Convert odometer records to a pandas DataFrame."""
    data = [
        {
            "datetime": r.datetime,
            "odometer_km": r.odometer_km,
            "notes": r.notes,
        }
        for r in records
    ]
    df = pd.DataFrame(data)
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime").reset_index(drop=True)
    return df


def total_fuel_volume(df: pd.DataFrame) -> float:
    """Total liters purchased."""
    if df.empty:
        return 0.0
    return float(df["liters"].sum())


def total_fuel_spending(df: pd.DataFrame) -> float:
    """Total EUR spent on fuel."""
    if df.empty:
        return 0.0
    return float(df["amount_eur"].sum())


def average_fuel_price(df: pd.DataFrame) -> float:
    """Average price per liter (weighted by volume)."""
    if df.empty or df["liters"].sum() == 0:
        return 0.0
    return float(df["amount_eur"].sum() / df["liters"].sum())


def fuel_price_over_time(df: pd.DataFrame) -> pd.DataFrame:
    """Price per liter at each purchase event, sorted by time."""
    return df[["datetime", "price_per_liter_eur"]].copy()


def fuel_price_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly average fuel price."""
    if df.empty:
        return pd.DataFrame(columns=["month", "avg_price_per_liter"])
    monthly = df.set_index("datetime").resample("ME")["price_per_liter_eur"].mean()
    return monthly.reset_index().rename(
        columns={"datetime": "month", "price_per_liter_eur": "avg_price_per_liter"}
    )


def fuel_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Count and total liters by fuel type."""
    if df.empty:
        return pd.DataFrame(columns=["fuel_type", "count", "total_liters", "total_eur"])
    return (
        df.groupby("fuel_type")
        .agg(count=("liters", "count"), total_liters=("liters", "sum"), total_eur=("amount_eur", "sum"))
        .reset_index()
    )


def avg_price_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """Volume-weighted average price per liter by country."""
    if df.empty:
        return pd.DataFrame(columns=["country", "avg_price_per_liter", "total_liters"])
    grouped = df.groupby("country").agg(
        total_eur=("amount_eur", "sum"),
        total_liters=("liters", "sum"),
    )
    grouped["avg_price_per_liter"] = grouped["total_eur"] / grouped["total_liters"]
    return grouped[["avg_price_per_liter", "total_liters"]].reset_index()


def avg_price_by_city(df: pd.DataFrame) -> pd.DataFrame:
    """Volume-weighted average price per liter by city."""
    if df.empty:
        return pd.DataFrame(columns=["city", "avg_price_per_liter", "total_liters"])
    valid = df[df["city"].str.strip() != ""]
    if valid.empty:
        return pd.DataFrame(columns=["city", "avg_price_per_liter", "total_liters"])
    grouped = valid.groupby("city").agg(
        total_eur=("amount_eur", "sum"),
        total_liters=("liters", "sum"),
    )
    grouped["avg_price_per_liter"] = grouped["total_eur"] / grouped["total_liters"]
    return grouped[["avg_price_per_liter", "total_liters"]].reset_index()


def monthly_liters(df: pd.DataFrame) -> pd.DataFrame:
    """Total liters purchased per month."""
    if df.empty:
        return pd.DataFrame(columns=["month", "liters"])
    monthly = df.set_index("datetime").resample("ME")["liters"].sum()
    return monthly.reset_index().rename(columns={"datetime": "month"})


def monthly_spending(df: pd.DataFrame) -> pd.DataFrame:
    """Total EUR spent per month."""
    if df.empty:
        return pd.DataFrame(columns=["month", "amount_eur"])
    monthly = df.set_index("datetime").resample("ME")["amount_eur"].sum()
    return monthly.reset_index().rename(columns={"datetime": "month"})


# --- Odometer-only metrics ---


def total_distance(df: pd.DataFrame) -> float:
    """Total distance based on first and last odometer readings."""
    if len(df) < 2:
        return 0.0
    return float(df["odometer_km"].iloc[-1] - df["odometer_km"].iloc[0])


def monthly_km_driven(df: pd.DataFrame) -> pd.DataFrame:
    """Estimated kilometers driven per month based on odometer readings.

    Uses the difference between the last and first reading in each month.
    Months with only one reading show 0 km.
    """
    if df.empty:
        return pd.DataFrame(columns=["month", "km_driven"])

    df_sorted = df.sort_values("datetime").copy()
    df_sorted["month"] = df_sorted["datetime"].dt.to_period("M")

    monthly_data = []
    for month, group in df_sorted.groupby("month"):
        if len(group) >= 2:
            km = group["odometer_km"].iloc[-1] - group["odometer_km"].iloc[0]
        else:
            km = 0.0
        monthly_data.append({"month": month.to_timestamp(), "km_driven": km})

    return pd.DataFrame(monthly_data)


def cumulative_distance(df: pd.DataFrame) -> pd.DataFrame:
    """Cumulative distance from the first odometer reading."""
    if df.empty:
        return pd.DataFrame(columns=["datetime", "cumulative_km"])
    result = df[["datetime", "odometer_km"]].copy()
    result["cumulative_km"] = result["odometer_km"] - result["odometer_km"].iloc[0]
    return result[["datetime", "cumulative_km"]]


# --- Combined metrics (estimated via interpolation) ---


@dataclass
class ConsumptionEstimate:
    """A single fuel consumption estimate between two fuel events."""

    fuel_datetime: datetime
    liters: float
    estimated_km: float
    liters_per_100km: EstimatedValue
    cost_per_100km: EstimatedValue
    cost_per_km: EstimatedValue
    amount_eur: float


def compute_consumption_estimates(
    fuel_records: list[FuelRecord],
    odometer_records: list[OdometerRecord],
    strategy: Optional[InterpolationStrategy] = None,
) -> list[ConsumptionEstimate]:
    """Estimate fuel consumption by interpolating odometer readings at fuel event times.

    For each consecutive pair of fuel events, this function:
    1. Interpolates the odometer reading at each fuel event's datetime.
    2. Computes the estimated distance driven between the two events.
    3. Computes liters/100km, cost/100km, and cost/km.

    All results are labeled with estimation quality metadata.
    """
    if strategy is None:
        strategy = get_interpolation_strategy("linear")

    if len(fuel_records) < 2 or len(odometer_records) < 2:
        return []

    sorted_fuel = sorted(fuel_records, key=lambda r: r.datetime)
    estimates: list[ConsumptionEstimate] = []

    for i in range(1, len(sorted_fuel)):
        prev_fuel = sorted_fuel[i - 1]
        curr_fuel = sorted_fuel[i]

        odo_at_prev = strategy.estimate(prev_fuel.datetime, odometer_records)
        odo_at_curr = strategy.estimate(curr_fuel.datetime, odometer_records)

        # Both must be usable (exact or estimated).
        if (
            odo_at_prev.quality == EstimationQuality.INSUFFICIENT
            or odo_at_curr.quality == EstimationQuality.INSUFFICIENT
        ):
            continue

        estimated_km = odo_at_curr.value - odo_at_prev.value
        if estimated_km <= 0:
            continue

        # Determine overall quality: if either is estimated, result is estimated.
        quality = EstimationQuality.EXACT
        if (
            odo_at_prev.quality == EstimationQuality.ESTIMATED
            or odo_at_curr.quality == EstimationQuality.ESTIMATED
        ):
            quality = EstimationQuality.ESTIMATED

        method = strategy.name()
        interval = f"{prev_fuel.datetime} -> {curr_fuel.datetime}"

        liters_per_100 = curr_fuel.liters / estimated_km * 100
        cost_per_100 = curr_fuel.amount_eur / estimated_km * 100
        cost_per_1 = curr_fuel.amount_eur / estimated_km

        estimates.append(
            ConsumptionEstimate(
                fuel_datetime=curr_fuel.datetime,
                liters=curr_fuel.liters,
                estimated_km=estimated_km,
                liters_per_100km=EstimatedValue(
                    value=liters_per_100, quality=quality,
                    method=method, source_interval=interval,
                ),
                cost_per_100km=EstimatedValue(
                    value=cost_per_100, quality=quality,
                    method=method, source_interval=interval,
                ),
                cost_per_km=EstimatedValue(
                    value=cost_per_1, quality=quality,
                    method=method, source_interval=interval,
                ),
                amount_eur=curr_fuel.amount_eur,
            )
        )

    return estimates


def consumption_estimates_to_dataframe(
    estimates: list[ConsumptionEstimate],
) -> pd.DataFrame:
    """Convert consumption estimates to a DataFrame with quality labels."""
    data = [
        {
            "datetime": e.fuel_datetime,
            "liters": e.liters,
            "estimated_km": e.estimated_km,
            "liters_per_100km": e.liters_per_100km.value,
            "liters_per_100km_quality": e.liters_per_100km.quality.value,
            "liters_per_100km_method": e.liters_per_100km.method,
            "cost_per_100km": e.cost_per_100km.value,
            "cost_per_100km_quality": e.cost_per_100km.quality.value,
            "cost_per_km": e.cost_per_km.value,
            "cost_per_km_quality": e.cost_per_km.quality.value,
            "estimation_method": e.liters_per_100km.method,
            "source_interval": e.liters_per_100km.source_interval,
            "amount_eur": e.amount_eur,
        }
        for e in estimates
    ]
    df = pd.DataFrame(data)
    if not df.empty:
        df["datetime"] = pd.to_datetime(df["datetime"])
    return df
