"""Reusable HTML report generation for fuel and mileage analysis."""

from __future__ import annotations

import base64
import io
import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, time
from html import escape
from pathlib import Path
from typing import Callable, Optional

_RUNTIME_CACHE_ROOT = Path(tempfile.gettempdir()) / "fuel_analysis_runtime_cache"
_RUNTIME_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
(_RUNTIME_CACHE_ROOT / "matplotlib").mkdir(parents=True, exist_ok=True)
(_RUNTIME_CACHE_ROOT / "xdg").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_RUNTIME_CACHE_ROOT / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(_RUNTIME_CACHE_ROOT / "xdg"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .config import PathConfig, PlottingConfig
from .interpolation import InterpolationStrategy, get_interpolation_strategy
from .metrics import (
    average_fuel_price,
    compute_consumption_estimates,
    consumption_estimates_to_dataframe,
    estimate_distance_between_datetimes,
    fuel_records_to_dataframe,
    fuel_type_summary,
    monthly_liters,
    monthly_spending,
    odometer_records_to_dataframe,
    total_distance,
    total_fuel_spending,
    total_fuel_volume,
)
from .models import EstimationQuality, FuelRecord, OdometerRecord
from .plotting import (
    plot_consumption_over_time,
    plot_fuel_price_over_time,
    plot_fuel_type_donuts,
    plot_monthly_liters,
    plot_monthly_spending,
    plot_report_overview,
)
from .validators import ValidationResult


DateInput = date | datetime


@dataclass(frozen=True)
class ReportPeriod:
    """Resolved inclusive report period."""

    start: datetime
    end: datetime

    @property
    def display_start(self) -> str:
        return self.start.date().isoformat()

    @property
    def display_end(self) -> str:
        return self.end.date().isoformat()


@dataclass(frozen=True)
class DistanceTimeline:
    """Distance series for the report overview chart."""

    frame: pd.DataFrame


@dataclass(frozen=True)
class ReportMetric:
    """Display-ready metric card."""

    label: str
    value: str
    source: str
    note: str = ""
    tone: str = "neutral"


def resolve_report_period(
    fuel_records: list[FuelRecord],
    odometer_records: list[OdometerRecord],
    start: Optional[DateInput] = None,
    end: Optional[DateInput] = None,
) -> ReportPeriod:
    """Resolve an inclusive report period from explicit or inferred bounds."""
    all_datetimes = [record.datetime for record in fuel_records] + [record.datetime for record in odometer_records]
    if not all_datetimes:
        raise ValueError("Cannot generate a report without any fuel or odometer records.")

    default_start = min(all_datetimes)
    default_end = max(all_datetimes)

    start_dt = _normalize_period_boundary(start, default_start, is_end=False)
    end_dt = _normalize_period_boundary(end, default_end, is_end=True)

    if start_dt > end_dt:
        raise ValueError("Report start date must not be after the end date.")

    return ReportPeriod(start=start_dt, end=end_dt)


def render_html_report(
    fuel_records: list[FuelRecord],
    odometer_records: list[OdometerRecord],
    fuel_validation: ValidationResult,
    odometer_validation: ValidationResult,
    start: Optional[DateInput] = None,
    end: Optional[DateInput] = None,
    strategy: Optional[InterpolationStrategy] = None,
    plotting_config: Optional[PlottingConfig] = None,
) -> str:
    """Render a static HTML report for a selected period."""
    if plotting_config is None:
        plotting_config = PlottingConfig()
    if strategy is None:
        strategy = get_interpolation_strategy("linear")

    period = resolve_report_period(fuel_records, odometer_records, start=start, end=end)

    period_fuel_records = [
        record for record in fuel_records if period.start <= record.datetime <= period.end
    ]
    period_odometer_records = [
        record for record in odometer_records if period.start <= record.datetime <= period.end
    ]

    fuel_df = fuel_records_to_dataframe(period_fuel_records)
    odometer_df = odometer_records_to_dataframe(period_odometer_records)
    consumption_estimates = compute_consumption_estimates(period_fuel_records, odometer_records, strategy)
    consumption_df = consumption_estimates_to_dataframe(consumption_estimates)

    overview_chart = _render_figure(
        plot_report_overview(
            fuel_df,
            build_distance_timeline(odometer_records, period).frame,
            plotting_config,
        )
    )

    estimated_period_distance = estimate_distance_between_datetimes(
        period.start,
        period.end,
        odometer_records,
        strategy,
    )
    period_start_odo = strategy.estimate(period.start, odometer_records)
    period_end_odo = strategy.estimate(period.end, odometer_records)

    fuel_charts: list[str] = []
    if not fuel_df.empty:
        fuel_charts.append(
            _chart_block(
                "Fuel Price Over Time",
                "Observed price per liter for each fuel purchase in the selected period.",
                _render_figure(plot_fuel_price_over_time(fuel_df, plotting_config)),
            )
        )

        monthly_liters_df = monthly_liters(fuel_df)
        if not monthly_liters_df.empty:
            fuel_charts.append(
                _chart_block(
                    "Monthly Fuel Volume",
                    "Total liters purchased per month from the fuel log.",
                    _render_figure(plot_monthly_liters(monthly_liters_df, plotting_config)),
                )
            )

        monthly_spending_df = monthly_spending(fuel_df)
        if not monthly_spending_df.empty:
            fuel_charts.append(
                _chart_block(
                    "Monthly Fuel Spending",
                    "Total fuel spending per month from the fuel log.",
                    _render_figure(plot_monthly_spending(monthly_spending_df, plotting_config)),
                )
            )

    estimated_chart = ""
    if not consumption_df.empty:
        estimated_chart = _chart_block(
            "Estimated Fuel Consumption",
            "Fuel consumption intervals based on consecutive fuel events inside the selected period.",
            _render_figure(plot_consumption_over_time(consumption_df, plotting_config)),
        )

    fuel_metrics = _build_fuel_metrics(fuel_df)
    distance_metrics = _build_distance_metrics(odometer_df, estimated_period_distance)
    estimated_metrics = _build_estimated_metrics(consumption_df)

    fuel_mix_chart = _render_figure(plot_fuel_type_donuts(fuel_type_summary(fuel_df), plotting_config))
    country_table = _render_table(
        _build_location_overview(fuel_df, "country"),
        {
            "Stops": _format_count,
            "Liters": _format_liters,
            "EUR": _format_eur,
            "Avg price per liter (EUR)": _format_eur_per_liter,
        },
    )
    city_table = _render_table(
        _build_location_overview(fuel_df, "city"),
        {
            "Stops": _format_count,
            "Liters": _format_liters,
            "EUR": _format_eur,
            "Avg price per liter (EUR)": _format_eur_per_liter,
        },
    )
    odometer_table = _render_table(
        _build_odometer_readings_table(odometer_records, period),
        {
            "Timestamp": _format_table_datetime,
            "Odometer (km)": _format_km,
            "Km since previous exact reading": _format_optional_km,
        },
    )
    boundary_details = _render_boundary_details(period, period_start_odo, period_end_odo)
    consumption_table = _render_consumption_table(consumption_df)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fuel Analysis Report</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --ink: #1f1e1a;
      --muted: #645f56;
      --accent: #8f4e2d;
      --exact: #2f7d4a;
      --estimated: #d88920;
      --border: #d7c9b5;
      --shadow: 0 18px 42px rgba(68, 49, 28, 0.08);
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(220, 174, 130, 0.35), transparent 32%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", Helvetica, sans-serif;
      line-height: 1.55;
    }}

    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 48px 24px 72px;
    }}

    .page-header {{
      margin-bottom: 38px;
    }}

    h1, h2, h3 {{
      font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      margin: 0;
    }}

    h1 {{
      font-size: 2.7rem;
      letter-spacing: -0.03em;
    }}

    h2 {{
      font-size: 1.85rem;
      margin-bottom: 18px;
    }}

    h3 {{
      font-size: 1.2rem;
      margin-bottom: 10px;
    }}

    p {{
      margin: 0 0 14px;
    }}

    .period-pill {{
      display: inline-block;
      margin-top: 12px;
      padding: 7px 13px;
      border-radius: 999px;
      background: rgba(143, 78, 45, 0.10);
      border: 1px solid rgba(143, 78, 45, 0.18);
      font-weight: 600;
      letter-spacing: 0.02em;
      color: var(--accent);
    }}

    .section {{
      margin-top: 44px;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}

    .metric {{
      padding: 18px;
      border-radius: 18px;
      background: #fff;
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
    }}

    .metric.exact {{
      border-left: 5px solid var(--exact);
    }}

    .metric.estimated {{
      border-left: 5px solid var(--estimated);
    }}

    .metric.neutral {{
      border-left: 5px solid var(--accent);
    }}

    .metric-label {{
      color: var(--muted);
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .metric-value {{
      margin-top: 6px;
      font-size: 1.8rem;
      font-weight: 700;
      line-height: 1.15;
    }}

    .metric-source {{
      margin-top: 8px;
      font-size: 0.93rem;
      color: var(--muted);
    }}

    .metric-note {{
      margin-top: 6px;
      font-size: 0.9rem;
    }}

    .figure-panel,
    .panel {{
      padding: 18px 20px;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.84);
      box-shadow: var(--shadow);
    }}

    .figure-panel img,
    .panel img {{
      display: block;
      width: 100%;
      height: auto;
      margin-top: 12px;
      border-radius: 14px;
      border: 1px solid #e1d7c7;
      background: #fff;
    }}

    .chart-stack {{
      display: flex;
      flex-direction: column;
      gap: 22px;
      margin-top: 20px;
    }}

    .panel-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 18px;
      margin-top: 20px;
    }}

    .table-wrap,
    .boundary-table {{
      overflow-x: auto;
    }}

    .table-wrap table,
    .consumption-table {{
      min-width: 720px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
      margin-top: 10px;
    }}

    th, td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid #e5dac8;
      vertical-align: top;
    }}

    th {{
      font-size: 0.84rem;
      color: var(--muted);
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    .empty-state {{
      color: var(--muted);
      font-style: italic;
    }}

    ul.validation-list {{
      margin: 12px 0 0;
      padding-left: 18px;
    }}

    .quality-tag {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}

    .quality-tag.exact {{
      background: rgba(47, 125, 74, 0.14);
      color: var(--exact);
    }}

    .quality-tag.estimated {{
      background: rgba(216, 137, 32, 0.15);
      color: var(--estimated);
    }}

    .quality-tag.insufficient {{
      background: rgba(100, 95, 86, 0.14);
      color: var(--muted);
    }}

    .provenance-line + .provenance-line {{
      margin-top: 6px;
    }}

    .consumption-table td:last-child {{
      min-width: 320px;
      white-space: normal;
    }}

    @media (max-width: 760px) {{
      main {{
        padding: 20px 14px 44px;
      }}

      h1 {{
        font-size: 2.05rem;
      }}

      .figure-panel,
      .panel,
      .metric {{
        padding: 16px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="page-header">
      <h1>Fuel Analysis Report</h1>
      <div class="period-pill">Reporting period: from {escape(period.display_start)} to {escape(period.display_end)}</div>
    </header>

    <section class="section">
      <h2>Overview</h2>
      <figure class="figure-panel">
        <img alt="Overview chart" src="data:image/png;base64,{overview_chart}">
      </figure>
    </section>

    <section class="section">
      <h2>Fuel Activity</h2>
      {_render_metrics(fuel_metrics)}
      <div class="chart-stack">
        {"".join(fuel_charts) or '<p class="empty-state">No fuel events were found in the selected period.</p>'}
      </div>
      <div class="panel" style="margin-top: 20px;">
        <h3>Fuel Type Summary</h3>
        <img alt="Fuel type summary" src="data:image/png;base64,{fuel_mix_chart}">
      </div>
      <div class="panel-row">
        <div class="panel">
          <h3>Country Overview</h3>
          {country_table}
        </div>
        <div class="panel">
          <h3>City Overview</h3>
          {city_table}
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Distance Coverage</h2>
      {_render_metrics(distance_metrics)}
      <div class="panel" style="margin-top: 20px;">
        <h3>Period Boundaries</h3>
        {boundary_details}
      </div>
      <div class="panel" style="margin-top: 18px;">
        <h3>Odometer Readings in Period</h3>
        {odometer_table}
      </div>
    </section>

    <section class="section">
      <h2>Estimated Consumption</h2>
      <p>These metrics combine fuel logs and odometer logs. They are exact only when odometer readings exist at both fuel event timestamps. Otherwise, they are estimated using linear interpolation between the bracketing odometer readings. Partial and unknown fills are currently still included in this interval pipeline.</p>
      {_render_metrics(estimated_metrics)}
      {estimated_chart or '<p class="empty-state" style="margin-top: 18px;">Not enough data is available to compute consumption estimates for this period.</p>'}
      <div class="panel" style="margin-top: 18px;">
        <h3>Consumption Interval Provenance</h3>
        <p>Every estimated value below states whether the odometer value at each boundary was exact or interpolated, and which odometer interval supported the calculation.</p>
        {consumption_table}
      </div>
    </section>

    <section class="section">
      <h2>Data Quality and Method</h2>
      <p>The report keeps exact and estimated values separate so it is always clear where the underlying data ends and interpolation begins.</p>
      <div class="panel-row">
        <div class="panel">
          <h3>Fuel Validation</h3>
          {_render_validation_summary(fuel_validation)}
        </div>
        <div class="panel">
          <h3>Odometer Validation</h3>
          {_render_validation_summary(odometer_validation)}
        </div>
      </div>
      <div class="panel" style="margin-top: 18px;">
        <h3>Interpretation Rules</h3>
        <ul class="validation-list">
          <li><strong>Exact:</strong> derived directly from the source log without interpolation.</li>
          <li><strong>Estimated:</strong> requires linear interpolation between two odometer readings.</li>
          <li><strong>Insufficient:</strong> the report could not compute the value because the required supporting data was missing.</li>
          <li><strong>Boundary interpolation:</strong> period-level distance may use odometer readings just outside the selected reporting window to estimate the start or end of the chosen range.</li>
        </ul>
      </div>
    </section>
  </main>
</body>
</html>
"""


def generate_html_report(
    fuel_records: list[FuelRecord],
    odometer_records: list[OdometerRecord],
    fuel_validation: ValidationResult,
    odometer_validation: ValidationResult,
    start: Optional[DateInput] = None,
    end: Optional[DateInput] = None,
    output_path: Optional[Path] = None,
    strategy: Optional[InterpolationStrategy] = None,
    plotting_config: Optional[PlottingConfig] = None,
) -> Path:
    """Render and write an HTML report to disk."""
    period = resolve_report_period(fuel_records, odometer_records, start=start, end=end)
    html = render_html_report(
        fuel_records,
        odometer_records,
        fuel_validation,
        odometer_validation,
        start=period.start,
        end=period.end,
        strategy=strategy,
        plotting_config=plotting_config,
    )

    if output_path is None:
        output_path = PathConfig().reports_dir / (
            f"fuel-report-{period.display_start}-to-{period.display_end}.html"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def build_distance_timeline(
    odometer_records: list[OdometerRecord],
    period: ReportPeriod,
) -> DistanceTimeline:
    """Build exact km deltas between consecutive odometer entries for the overview chart."""
    if not odometer_records:
        return DistanceTimeline(frame=pd.DataFrame(columns=["datetime", "km_since_last_entry"]))

    all_points = odometer_records_to_dataframe(odometer_records)
    all_points["km_since_last_entry"] = all_points["odometer_km"].diff()
    visible = all_points[
        (all_points["datetime"] >= period.start)
        & (all_points["datetime"] <= period.end)
        & (all_points["km_since_last_entry"].notna())
    ]
    return DistanceTimeline(frame=visible[["datetime", "km_since_last_entry"]].reset_index(drop=True))


def _build_fuel_metrics(fuel_df: pd.DataFrame) -> list[ReportMetric]:
    if fuel_df.empty:
        return [
            ReportMetric(
                label="Fuel stops",
                value="0",
                source="Fuel log",
                tone="neutral",
            )
        ]

    return [
        ReportMetric(
            label="Fuel stops",
            value=str(len(fuel_df)),
            source="Fuel log",
            tone="exact",
        ),
        ReportMetric(
            label="Fuel purchased",
            value=f"{total_fuel_volume(fuel_df):.1f} L",
            source="Fuel log",
            tone="exact",
        ),
        ReportMetric(
            label="Fuel spending",
            value=f"{total_fuel_spending(fuel_df):.2f} EUR",
            source="Fuel log",
            tone="exact",
        ),
        ReportMetric(
            label="Average fuel price",
            value=f"{average_fuel_price(fuel_df):.3f} EUR/L",
            source="Fuel log",
            tone="exact",
        ),
    ]


def _build_distance_metrics(
    odometer_df: pd.DataFrame,
    estimated_period_distance,
) -> list[ReportMetric]:
    exact_distance = total_distance(odometer_df)
    observed_readings = len(odometer_df)

    metrics = [
        ReportMetric(
            label="Observed odometer readings",
            value=str(observed_readings),
            source="Odometer log",
            tone="exact",
        ),
        ReportMetric(
            label="Observed distance driven",
            value=f"{exact_distance:.1f} km",
            source="Odometer log",
            tone="exact",
        ),
    ]

    if estimated_period_distance.quality == EstimationQuality.INSUFFICIENT:
        metrics.append(
            ReportMetric(
                label="Estimated overall distance driven",
                value="Not available",
                source="Odometer log + linear interpolation",
                note=estimated_period_distance.source_interval or "Not enough odometer data is available for the selected period.",
                tone="estimated",
            )
        )
    else:
        metrics.append(
            ReportMetric(
                label="Estimated overall distance driven",
                value=f"{estimated_period_distance.value:.1f} km",
                source="Odometer log + linear interpolation",
                note="" if estimated_period_distance.quality == EstimationQuality.EXACT else "At least one report boundary required interpolation.",
                tone="exact" if estimated_period_distance.quality == EstimationQuality.EXACT else "estimated",
            )
        )

    return metrics


def _build_estimated_metrics(consumption_df: pd.DataFrame) -> list[ReportMetric]:
    if consumption_df.empty:
        return [
            ReportMetric(
                label="Consumption intervals",
                value="0",
                source="Fuel log + odometer log",
                tone="neutral",
            )
        ]

    contains_estimate = (consumption_df["liters_per_100km_quality"] == "estimated").any()
    tone = "estimated" if contains_estimate else "exact"
    source = "Fuel log + odometer log via linear interpolation"

    return [
        ReportMetric(
            label="Consumption intervals",
            value=str(len(consumption_df)),
            source=source,
            tone=tone,
        ),
        ReportMetric(
            label="Average consumption",
            value=f"{consumption_df['liters_per_100km'].mean():.2f} L/100km",
            source=source,
            tone=tone,
        ),
        ReportMetric(
            label="Average cost per 100 km",
            value=f"{consumption_df['cost_per_100km'].mean():.2f} EUR",
            source=source,
            tone=tone,
        ),
        ReportMetric(
            label="Average cost per km",
            value=f"{consumption_df['cost_per_km'].mean():.3f} EUR",
            source=source,
            tone=tone,
        ),
    ]


def _build_location_overview(
    fuel_df: pd.DataFrame,
    column: str,
) -> pd.DataFrame:
    label = column.title()
    empty = pd.DataFrame(columns=[label, "Stops", "Liters", "EUR", "Avg price per liter (EUR)"])
    if fuel_df.empty or column not in fuel_df.columns:
        return empty

    working = fuel_df.copy()
    if column == "city":
        working = working[working["city"].astype(str).str.strip() != ""]
    if working.empty:
        return empty

    grouped = (
        working.groupby(column)
        .agg(
            Stops=(column, "count"),
            Liters=("liters", "sum"),
            EUR=("amount_eur", "sum"),
        )
        .reset_index()
        .rename(columns={column: label})
    )
    grouped["Avg price per liter (EUR)"] = grouped["EUR"] / grouped["Liters"]
    return grouped.sort_values(["Liters", "Stops"], ascending=[False, False]).reset_index(drop=True)


def _build_odometer_readings_table(
    odometer_records: list[OdometerRecord],
    period: ReportPeriod,
) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["Timestamp", "Odometer (km)", "Km since previous exact reading"])
    if not odometer_records:
        return empty

    df = odometer_records_to_dataframe(odometer_records)
    df["Km since previous exact reading"] = df["odometer_km"].diff()
    visible = df[(df["datetime"] >= period.start) & (df["datetime"] <= period.end)].copy()
    if visible.empty:
        return empty

    return visible.rename(
        columns={
            "datetime": "Timestamp",
            "odometer_km": "Odometer (km)",
        }
    )[["Timestamp", "Odometer (km)", "Km since previous exact reading"]]


def _render_metrics(metrics: list[ReportMetric]) -> str:
    cards = []
    for metric in metrics:
        note_html = f"<div class=\"metric-note\">{escape(metric.note)}</div>" if metric.note else ""
        cards.append(
            f"""
            <article class="metric {escape(metric.tone)}">
              <div class="metric-label">{escape(metric.label)}</div>
              <div class="metric-value">{escape(metric.value)}</div>
              <div class="metric-source">{escape(metric.source)}</div>
              {note_html}
            </article>
            """
        )
    return f"<div class=\"metrics\">{''.join(cards)}</div>"


def _render_figure(figure: plt.Figure) -> str:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(figure)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _render_table(
    df: pd.DataFrame,
    formatters: Optional[dict[str, Callable[[object], str]]] = None,
) -> str:
    if df.empty:
        return "<p class=\"empty-state\">No data is available for this view.</p>"

    display_df = df.copy()
    if formatters:
        for column, formatter in formatters.items():
            if column in display_df.columns:
                display_df[column] = display_df[column].map(formatter)

    table_html = display_df.to_html(index=False, classes="data-table", border=0, escape=True)
    return f"<div class=\"table-wrap\">{table_html}</div>"


def _render_consumption_table(consumption_df: pd.DataFrame) -> str:
    if consumption_df.empty:
        return "<p class=\"empty-state\">No consumption intervals are available for the selected period.</p>"

    rows = []
    sorted_df = consumption_df.sort_values("datetime")
    for _, row in sorted_df.iterrows():
        provenance = "".join(
            [
                "<div class=\"provenance-line\">"
                f"<strong>Previous:</strong> {_render_quality_tag(row['odometer_at_previous_quality'])} "
                f"{escape(str(row['odometer_at_previous_source_interval'] or 'No supporting odometer interval'))}"
                "</div>",
                "<div class=\"provenance-line\">"
                f"<strong>Current:</strong> {_render_quality_tag(row['odometer_at_current_quality'])} "
                f"{escape(str(row['odometer_at_current_source_interval'] or 'No supporting odometer interval'))}"
                "</div>",
            ]
        )

        rows.append(
            "<tr>"
            f"<td>{escape(_format_table_datetime(row['previous_fuel_datetime']))}</td>"
            f"<td>{escape(_format_table_datetime(row['datetime']))}</td>"
            f"<td>{escape(_format_liters(row['liters']))}</td>"
            f"<td>{escape(_format_km(row['estimated_km']))}</td>"
            f"<td>{escape(_format_consumption(row['liters_per_100km']))} {_render_quality_tag(row['liters_per_100km_quality'])}</td>"
            f"<td>{provenance}</td>"
            "</tr>"
        )

    return (
        "<div class=\"table-wrap\">"
        "<table class=\"consumption-table\">"
        "<thead><tr>"
        "<th>Previous fuel event</th>"
        "<th>Current fuel event</th>"
        "<th>Fuel bought (L)</th>"
        "<th>Estimated km</th>"
        "<th>L/100km</th>"
        "<th>Odometer basis</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
    )


def _render_boundary_details(
    period: ReportPeriod,
    period_start_odo,
    period_end_odo,
) -> str:
    rows = [
        (
            "Start of report",
            period.start,
            period_start_odo,
        ),
        (
            "End of report",
            period.end,
            period_end_odo,
        ),
    ]

    body = []
    for label, boundary_dt, value in rows:
        body.append(
            "<tr>"
            f"<td>{escape(label)}</td>"
            f"<td>{escape(boundary_dt.strftime('%Y-%m-%d %H:%M'))}</td>"
            f"<td>{escape(_format_km(value.value)) if value.quality != EstimationQuality.INSUFFICIENT else 'Not available'}</td>"
            f"<td>{_render_estimate_tag(value)}</td>"
            f"<td>{escape(_describe_estimate(value))}</td>"
            "</tr>"
        )

    return (
        "<div class=\"boundary-table\">"
        "<table>"
        "<thead><tr>"
        "<th>Boundary</th>"
        "<th>Timestamp</th>"
        "<th>Odometer (km)</th>"
        "<th>Basis</th>"
        "<th>Supporting data</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table>"
        "</div>"
    )


def _render_validation_summary(result: ValidationResult) -> str:
    summary = (
        f"<p><strong>{len(result.errors)} error(s)</strong> and "
        f"<strong>{len(result.warnings)} warning(s)</strong>.</p>"
    )
    if not result.issues:
        return summary + "<p class=\"empty-state\">No validation issues were reported.</p>"

    items = "".join(
        f"<li><strong>{escape(issue.severity.upper())}</strong> "
        f"{escape('dataset' if issue.row is None else f'row {issue.row}')}: "
        f"{escape(issue.message)}</li>"
        for issue in result.issues
    )
    return summary + f"<ul class=\"validation-list\">{items}</ul>"


def _describe_estimate(value) -> str:
    if value.quality == EstimationQuality.INSUFFICIENT:
        return value.source_interval or "Not enough odometer data."
    if value.quality == EstimationQuality.EXACT:
        return value.source_interval or "Exact reading."
    return value.source_interval or "Estimated by interpolation."


def _render_estimate_tag(value) -> str:
    return _render_quality_tag(value.quality.value)


def _render_quality_tag(value: str) -> str:
    return f"<span class=\"quality-tag {escape(value)}\">{escape(value)}</span>"


def _chart_block(title: str, description: str, image_base64: str) -> str:
    return f"""
    <article class="figure-panel">
      <h3>{escape(title)}</h3>
      <p>{escape(description)}</p>
      <img alt="{escape(title)}" src="data:image/png;base64,{image_base64}">
    </article>
    """


def _normalize_period_boundary(
    value: Optional[DateInput],
    default: datetime,
    *,
    is_end: bool,
) -> datetime:
    if value is None:
        return default
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.max if is_end else time.min)


def _format_table_datetime(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _format_count(value) -> str:
    return f"{int(value)}"


def _format_eur(value) -> str:
    return f"{float(value):.2f}"


def _format_liters(value) -> str:
    return f"{float(value):.1f}"


def _format_km(value) -> str:
    return f"{float(value):.1f}"


def _format_optional_km(value) -> str:
    if pd.isna(value):
        return ""
    return _format_km(value)


def _format_consumption(value) -> str:
    return f"{float(value):.2f}"


def _format_eur_per_liter(value) -> str:
    return f"{float(value):.3f}"
