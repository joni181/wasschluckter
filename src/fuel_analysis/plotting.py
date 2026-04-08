"""Plotting utilities for fuel and mileage analysis.

All charts use matplotlib. Charts are designed to be clear and readable
without unnecessary styling complexity.
"""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from .config import PlottingConfig


def _apply_defaults(
    ax: plt.Axes,
    title: str,
    xlabel: str,
    ylabel: str,
    config: PlottingConfig,
) -> None:
    """Apply common axis formatting."""
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(config.date_format))
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")


def _make_figure(config: Optional[PlottingConfig] = None) -> tuple[plt.Figure, plt.Axes]:
    if config is None:
        config = PlottingConfig()
    fig, ax = plt.subplots(figsize=(config.figure_width, config.figure_height), dpi=config.dpi)
    return fig, ax


def plot_fuel_price_over_time(
    fuel_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Line chart of fuel price per liter over time."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.plot(fuel_df["datetime"], fuel_df["price_per_liter_eur"], marker="o", linewidth=1.5)
    _apply_defaults(ax, "Fuel Price Over Time", "Date", "Price per Liter (EUR)", config)
    fig.tight_layout()
    return fig


def plot_monthly_liters(
    monthly_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Bar chart of liters purchased per month."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.bar(monthly_df["month"], monthly_df["liters"], width=20, color="steelblue")
    _apply_defaults(ax, "Liters Purchased per Month", "Month", "Liters", config)
    fig.tight_layout()
    return fig


def plot_monthly_spending(
    monthly_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Bar chart of fuel spending per month."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.bar(monthly_df["month"], monthly_df["amount_eur"], width=20, color="coral")
    _apply_defaults(ax, "Fuel Spending per Month", "Month", "EUR", config)
    fig.tight_layout()
    return fig


def plot_monthly_km(
    monthly_km_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Bar chart of kilometers driven per month."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.bar(monthly_km_df["month"], monthly_km_df["km_driven"], width=20, color="seagreen")
    _apply_defaults(ax, "Kilometers Driven per Month", "Month", "km", config)
    fig.tight_layout()
    return fig


def plot_consumption_over_time(
    consumption_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Line chart of estimated liters per 100 km over time.

    Points are color-coded by estimation quality:
    - Green: exact
    - Orange: estimated (interpolated)
    """
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)

    colors = consumption_df["liters_per_100km_quality"].map(
        {"exact": "green", "estimated": "orange", "insufficient": "red"}
    )
    ax.scatter(
        consumption_df["datetime"],
        consumption_df["liters_per_100km"],
        c=colors,
        s=60,
        zorder=3,
    )
    ax.plot(
        consumption_df["datetime"],
        consumption_df["liters_per_100km"],
        linewidth=1,
        alpha=0.5,
        color="gray",
    )
    _apply_defaults(
        ax,
        "Estimated Fuel Consumption Over Time (L/100km)\n"
        "[green=exact, orange=estimated via linear interpolation]",
        "Date",
        "L / 100 km",
        config,
    )
    fig.tight_layout()
    return fig


def plot_avg_price_by_country(
    country_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Horizontal bar chart of average price per liter by country."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.barh(country_df["country"], country_df["avg_price_per_liter"], color="mediumpurple")
    ax.set_title("Average Fuel Price per Liter by Country")
    ax.set_xlabel("Price per Liter (EUR)")
    ax.set_ylabel("Country")
    fig.tight_layout()
    return fig


def plot_avg_price_by_city(
    city_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Horizontal bar chart of average price per liter by city."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.barh(city_df["city"], city_df["avg_price_per_liter"], color="teal")
    ax.set_title("Average Fuel Price per Liter by City")
    ax.set_xlabel("Price per Liter (EUR)")
    ax.set_ylabel("City")
    fig.tight_layout()
    return fig
