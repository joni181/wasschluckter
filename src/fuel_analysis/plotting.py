"""Plotting utilities for fuel and mileage analysis.

All charts use matplotlib. Charts are designed to be clear and readable
without unnecessary styling complexity.
"""

from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

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


def plot_report_overview(
    fuel_df: pd.DataFrame,
    distance_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Combined overview chart for fuel purchases and odometer deltas."""
    if config is None:
        config = PlottingConfig()
    fig, ax_fuel = _make_figure(config)
    ax_distance = ax_fuel.twinx()

    if not fuel_df.empty:
        ax_fuel.bar(
            fuel_df["datetime"],
            fuel_df["liters"],
            width=pd.Timedelta(days=2),
            color="#2f6c8f",
            alpha=0.85,
        )

    if not distance_df.empty:
        ax_distance.plot(
            distance_df["datetime"],
            distance_df["km_since_last_entry"],
            color="#8f4e2d",
            linewidth=2,
            marker="o",
            zorder=3,
        )

    ax_fuel.set_title("Fuel Stops and Kilometers Since the Previous Odometer Entry")
    ax_fuel.set_xlabel("Date")
    ax_fuel.set_ylabel("Fuel purchased (L)")
    ax_distance.set_ylabel("Km driven since previous odometer entry")
    ax_fuel.xaxis.set_major_formatter(mdates.DateFormatter(config.date_format))
    plt.setp(ax_fuel.get_xticklabels(), rotation=45, ha="right")

    legend_items = [
        Patch(facecolor="#2f6c8f", alpha=0.85, label="Fuel purchase (liters)"),
        Line2D([0], [0], color="#8f4e2d", linewidth=2, marker="o", label="Km driven since previous odometer entry"),
    ]
    ax_fuel.legend(handles=legend_items, loc="upper left")

    fig.tight_layout()
    return fig


def plot_fuel_type_donuts(
    summary_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Render donut charts for fuel type breakdown by stops, liters, and EUR."""
    if config is None:
        config = PlottingConfig()

    fig, axes = plt.subplots(1, 3, figsize=(config.figure_width, config.figure_height * 0.72), dpi=config.dpi)
    colors = ["#2f6c8f", "#d88920", "#6d8b74", "#c05a4d"]
    metrics = [
        ("count", "Stops", "{:.0f}"),
        ("total_liters", "Liters", "{:.1f}"),
        ("total_eur", "EUR", "{:.2f}"),
    ]

    if summary_df.empty:
        for ax, (_, title, _) in zip(axes, metrics):
            ax.text(0.5, 0.5, "No data", ha="center", va="center")
            ax.set_title(title)
            ax.axis("off")
        fig.tight_layout()
        return fig

    labels = summary_df["fuel_type"].tolist()
    for ax, (column, title, value_format) in zip(axes, metrics):
        values = summary_df[column].tolist()
        total = float(summary_df[column].sum())
        ax.pie(
            values,
            labels=labels,
            startangle=90,
            colors=colors[: len(values)],
            wedgeprops={"width": 0.42, "edgecolor": "white"},
            autopct=lambda pct: f"{pct:.0f}%" if pct > 0 else "",
            pctdistance=0.8,
        )
        ax.text(0, 0, value_format.format(total), ha="center", va="center", fontsize=13, fontweight="bold")
        ax.set_title(title)

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
    title: str = "Average Fuel Price per Liter by Country",
) -> plt.Figure:
    """Horizontal bar chart of average price per liter by country."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.barh(country_df["country"], country_df["avg_price_per_liter"], color="mediumpurple")
    ax.set_title(title)
    ax.set_xlabel("Price per Liter (EUR)")
    ax.set_ylabel("Country")
    fig.tight_layout()
    return fig


def plot_avg_price_by_city(
    city_df: pd.DataFrame,
    config: Optional[PlottingConfig] = None,
    title: str = "Average Fuel Price per Liter by City",
) -> plt.Figure:
    """Horizontal bar chart of average price per liter by city."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)
    ax.barh(city_df["city"], city_df["avg_price_per_liter"], color="teal")
    ax.set_title(title)
    ax.set_xlabel("Price per Liter (EUR)")
    ax.set_ylabel("City")
    fig.tight_layout()
    return fig


def plot_fuel_type_donut(
    summary_df: pd.DataFrame,
    value_column: str,
    title: str,
    config: Optional[PlottingConfig] = None,
) -> plt.Figure:
    """Donut chart for fuel type breakdowns."""
    if config is None:
        config = PlottingConfig()
    fig, ax = _make_figure(config)

    if summary_df.empty or summary_df[value_column].sum() == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    colors = ["#2f6c8f", "#d88920", "#739f79", "#8b6bb3"]
    wedges, _, _ = ax.pie(
        summary_df[value_column],
        labels=None,
        autopct=lambda pct: f"{pct:.0f}%",
        startangle=90,
        colors=colors[: len(summary_df)],
        wedgeprops={"width": 0.4, "edgecolor": "white"},
        textprops={"color": "#1f1e1a", "fontsize": 10},
    )
    ax.legend(
        wedges,
        summary_df["fuel_type"],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=max(1, len(summary_df)),
        frameon=False,
    )
    ax.set_title(title)
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig
