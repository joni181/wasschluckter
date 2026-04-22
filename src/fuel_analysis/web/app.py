"""FastAPI app — single entry point for the wasschluckter web UI + API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterator, Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..config import PROJECT_ROOT, ValidationConfig
from ..metrics import (
    average_fuel_price,
    avg_price_by_country,
    compute_consumption_estimates,
    fuel_price_trend,
    fuel_records_to_dataframe,
    fuel_type_summary,
    monthly_liters,
    monthly_spending,
    odometer_records_to_dataframe,
    total_fuel_spending,
    total_fuel_volume,
)
from ..models import COUNTRY_CODE_PATTERN, FuelType, FullTankStatus
from . import countries as country_module
from .db import (
    Car,
    FuelEntry,
    User,
    init_db,
    make_engine,
    make_session_factory,
)
from .seed import bootstrap
from .service import (
    fetch_all_fuel_records,
    fetch_all_odometer_records,
    fetch_fuel_entries,
    month_bounds,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app(db_path: Optional[Path] = None) -> FastAPI:
    engine = make_engine(db_path)
    init_db(engine)
    SessionFactory = make_session_factory(engine)

    with SessionFactory() as session:
        user, car = bootstrap(session)
        default_user_id = user.id
        default_car_id = car.id

    app = FastAPI(title="wasschluckter", docs_url=None, redoc_url=None)
    app.state.engine = engine
    app.state.session_factory = SessionFactory
    app.state.default_user_id = default_user_id
    app.state.default_car_id = default_car_id

    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    templates.env.globals["active_page"] = None  # overridden per-render

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def get_session() -> Iterator[Session]:
        session: Session = SessionFactory()
        try:
            yield session
        finally:
            session.close()

    def get_current_context(session: Session = Depends(get_session)) -> tuple[User, Car, Session]:
        user = session.get(User, app.state.default_user_id)
        car = session.get(Car, app.state.default_car_id)
        if user is None or car is None:
            raise HTTPException(500, "Default user/car missing — re-seed the DB.")
        return user, car, session

    # ------------------------------------------------------------------
    # HTML routes
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def main_page(
        request: Request,
        ctx: tuple[User, Car, Session] = Depends(get_current_context),
    ) -> HTMLResponse:
        user, car, session = ctx
        start, end = month_bounds()
        month_entries = fetch_fuel_entries(session, car, start=start, end=end)
        month_liters = sum(e.liters for e in month_entries)
        month_spend = sum(e.amount_eur for e in month_entries)

        history = fetch_fuel_entries(session, car, limit=30)

        return templates.TemplateResponse(
            request,
            "main.html",
            {
                "active_page": "main",
                "month_liters": month_liters,
                "month_spend": month_spend,
                "history": [_entry_view(e) for e in history],
                "month_label": start.strftime("%B %Y"),
                "countries": country_module.ordered_country_options(),
                "today": date.today().isoformat(),
                "fuel_types": [ft.value for ft in FuelType],
                "user": user,
                "car": car,
            },
        )

    @app.get("/analysis", response_class=HTMLResponse)
    def analysis_page(
        request: Request,
        ctx: tuple[User, Car, Session] = Depends(get_current_context),
    ) -> HTMLResponse:
        user, car, session = ctx
        return templates.TemplateResponse(
            request,
            "analysis.html",
            {
                "active_page": "analysis",
                "user": user,
                "car": car,
            },
        )

    # ------------------------------------------------------------------
    # API — create fuel entry
    # ------------------------------------------------------------------

    @app.post("/api/entries")
    def create_entry(
        station_name: str = Form(...),
        city: str = Form(...),
        country: str = Form(...),
        liters: float = Form(...),
        amount_eur: float = Form(...),
        entry_date: str = Form(...),
        fuel_type: str = Form(...),
        is_full_tank: str = Form("unknown"),
        notes: str = Form(""),
        ctx: tuple[User, Car, Session] = Depends(get_current_context),
    ) -> JSONResponse:
        user, car, session = ctx
        errors: dict[str, str] = {}

        station_name = station_name.strip()
        city = city.strip()
        country = country.strip().upper()
        fuel_type = fuel_type.strip()
        is_full_tank = is_full_tank.strip().lower()

        if not station_name:
            errors["station_name"] = "Required."
        if not city:
            errors["city"] = "Required."
        if not COUNTRY_CODE_PATTERN.match(country):
            errors["country"] = "Must be a 2-letter ISO country code."
        if liters <= 0:
            errors["liters"] = "Must be greater than 0."
        if amount_eur <= 0:
            errors["amount_eur"] = "Must be greater than 0."
        if fuel_type not in {ft.value for ft in FuelType}:
            errors["fuel_type"] = f"Must be one of {sorted(ft.value for ft in FuelType)}."
        if is_full_tank not in {s.value for s in FullTankStatus}:
            errors["is_full_tank"] = "Must be true, false, or unknown."

        try:
            parsed_date = date.fromisoformat(entry_date)
        except ValueError:
            errors["entry_date"] = "Must be a valid date (YYYY-MM-DD)."
            parsed_date = None

        if errors:
            return JSONResponse({"ok": False, "errors": errors}, status_code=400)

        # Suspicious-price soft warnings.
        warnings: list[str] = []
        cfg = ValidationConfig()
        derived_price = amount_eur / liters
        if derived_price < cfg.price_per_liter_min_warn:
            warnings.append(
                f"Derived price per liter ({derived_price:.3f} EUR/L) is suspiciously low."
            )
        if derived_price > cfg.price_per_liter_max_warn:
            warnings.append(
                f"Derived price per liter ({derived_price:.3f} EUR/L) is suspiciously high."
            )

        entry = FuelEntry(
            car_id=car.id,
            created_by_user_id=user.id,
            datetime=datetime.combine(parsed_date, time(12, 0)),
            amount_eur=amount_eur,
            liters=liters,
            fuel_type=fuel_type,
            is_full_tank=is_full_tank,
            station_name=station_name,
            city=city,
            country=country,
            notes=notes.strip(),
        )
        session.add(entry)
        session.commit()

        return JSONResponse(
            {"ok": True, "id": entry.id, "warnings": warnings},
            status_code=201,
        )

    # ------------------------------------------------------------------
    # API — analysis data
    # ------------------------------------------------------------------

    @app.get("/api/analysis")
    def api_analysis(
        range: str = "month",
        start: Optional[str] = None,
        end: Optional[str] = None,
        ctx: tuple[User, Car, Session] = Depends(get_current_context),
    ) -> JSONResponse:
        user, car, session = ctx
        try:
            period_start, period_end, range_label = _resolve_range(range, start, end)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        fuel_records = fetch_all_fuel_records(session, car)
        odo_records = fetch_all_odometer_records(session, car)

        in_range_fuel = [
            r for r in fuel_records if period_start <= r.datetime <= period_end
        ]
        in_range_odo = [
            r for r in odo_records if period_start <= r.datetime <= period_end
        ]

        fuel_df = fuel_records_to_dataframe(in_range_fuel)
        odo_df = odometer_records_to_dataframe(in_range_odo)

        metrics = {
            "total_liters": float(total_fuel_volume(fuel_df)),
            "total_eur": float(total_fuel_spending(fuel_df)),
            "avg_price_per_liter": float(average_fuel_price(fuel_df)),
            "entries": int(len(in_range_fuel)),
        }

        # Consumption estimates (use the full odometer dataset as support
        # but restrict fuel events to the range).
        estimates = compute_consumption_estimates(in_range_fuel, odo_records)
        if estimates:
            metrics["avg_l_per_100km"] = float(
                sum(e.liters_per_100km.value for e in estimates) / len(estimates)
            )
            metrics["avg_cost_per_100km"] = float(
                sum(e.cost_per_100km.value for e in estimates) / len(estimates)
            )
        else:
            metrics["avg_l_per_100km"] = None
            metrics["avg_cost_per_100km"] = None

        charts = {
            "price_trend": _price_trend_series(fuel_df),
            "monthly_liters": _monthly_series(monthly_liters(fuel_df), "liters"),
            "monthly_spending": _monthly_series(monthly_spending(fuel_df), "amount_eur"),
            "fuel_type_summary": _fuel_type_series(fuel_df),
            "country_breakdown": _country_series(fuel_df),
            "consumption_series": _consumption_series(estimates),
        }

        return JSONResponse(
            {
                "range": range,
                "range_label": range_label,
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
                "metrics": metrics,
                "charts": charts,
            }
        )

    return app


# ----------------------------------------------------------------------
# Helpers (pure functions, no state)
# ----------------------------------------------------------------------


def _entry_view(entry: FuelEntry) -> dict:
    return {
        "id": entry.id,
        "datetime": entry.datetime.isoformat(),
        "date": entry.datetime.date().isoformat(),
        "station_name": entry.station_name,
        "city": entry.city,
        "country": entry.country,
        "country_name": _country_name(entry.country),
        "liters": entry.liters,
        "amount_eur": entry.amount_eur,
        "fuel_type": entry.fuel_type,
        "is_full_tank": entry.is_full_tank,
    }


def _country_name(code: str) -> str:
    for c in country_module.ordered_country_options():
        if c.code == code:
            return c.name
    return code


def _resolve_range(
    key: str,
    custom_start: Optional[str],
    custom_end: Optional[str],
) -> tuple[datetime, datetime, str]:
    now = datetime.now()

    if key == "month":
        start, end = month_bounds(now)
        return start, end, f"This month ({start.strftime('%B %Y')})"

    if key == "last_month":
        first_of_this = datetime(now.year, now.month, 1)
        last_month_end = first_of_this - timedelta(microseconds=1)
        start = datetime(last_month_end.year, last_month_end.month, 1)
        return start, last_month_end, f"Last month ({start.strftime('%B %Y')})"

    if key == "ytd":
        start = datetime(now.year, 1, 1)
        return start, now, f"Year to date ({now.year})"

    if key == "last_12_months":
        start = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now, "Last 12 months"

    if key == "all_time":
        return datetime(1970, 1, 1), now, "All time"

    if key == "custom":
        if not custom_start or not custom_end:
            raise ValueError("custom range requires start and end")
        try:
            s = date.fromisoformat(custom_start)
            e = date.fromisoformat(custom_end)
        except ValueError as exc:
            raise ValueError(f"invalid ISO date: {exc}")
        start = datetime.combine(s, time.min)
        end = datetime.combine(e, time.max).replace(microsecond=0)
        return start, end, f"{s.isoformat()} → {e.isoformat()}"

    raise ValueError(f"unknown range: {key}")


def _price_trend_series(df) -> list[dict]:
    trend = fuel_price_trend(df)
    if trend.empty:
        return []
    return [
        {
            "month": row["month"].strftime("%Y-%m"),
            "avg_price_per_liter": float(row["avg_price_per_liter"]),
        }
        for _, row in trend.iterrows()
    ]


def _monthly_series(df, value_key: str) -> list[dict]:
    if df.empty:
        return []
    return [
        {
            "month": row["month"].strftime("%Y-%m"),
            "value": float(row[value_key]),
        }
        for _, row in df.iterrows()
    ]


def _fuel_type_series(df) -> list[dict]:
    summary = fuel_type_summary(df)
    if summary.empty:
        return []
    return [
        {
            "fuel_type": row["fuel_type"],
            "count": int(row["count"]),
            "total_liters": float(row["total_liters"]),
            "total_eur": float(row["total_eur"]),
        }
        for _, row in summary.iterrows()
    ]


def _country_series(df) -> list[dict]:
    summary = avg_price_by_country(df)
    if summary.empty:
        return []
    return [
        {
            "country": row["country"],
            "avg_price_per_liter": float(row["avg_price_per_liter"]),
            "total_liters": float(row["total_liters"]),
        }
        for _, row in summary.iterrows()
    ]


def _consumption_series(estimates) -> list[dict]:
    return [
        {
            "datetime": e.fuel_datetime.isoformat(),
            "liters_per_100km": float(e.liters_per_100km.value),
            "quality": e.liters_per_100km.quality.value,
        }
        for e in estimates
    ]


app = create_app()
