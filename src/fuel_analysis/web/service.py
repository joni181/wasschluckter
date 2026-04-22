"""Service layer: bridges the DB rows and the existing domain models.

Reuses the pure-Python metric / plotting code from fuel_analysis.* by
converting ORM rows back into FuelRecord / OdometerRecord dataclasses
before handing them off. This keeps the analysis code free of any DB
concerns, which is useful for tests and future extensibility.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FuelRecord, FuelType, FullTankStatus, OdometerRecord
from .db import Car, FuelEntry, OdometerEntry


def fuel_entry_to_record(entry: FuelEntry) -> FuelRecord:
    return FuelRecord(
        datetime=entry.datetime,
        amount_eur=entry.amount_eur,
        liters=entry.liters,
        fuel_type=FuelType(entry.fuel_type),
        is_full_tank=_parse_full_tank(entry.is_full_tank),
        station_name=entry.station_name,
        city=entry.city,
        country=entry.country,
        notes=entry.notes or "",
    )


def odometer_entry_to_record(entry: OdometerEntry) -> OdometerRecord:
    return OdometerRecord(
        datetime=entry.datetime,
        odometer_km=entry.odometer_km,
        notes=entry.notes or "",
    )


def _parse_full_tank(value: str) -> FullTankStatus:
    for status in FullTankStatus:
        if status.value == value:
            return status
    return FullTankStatus.UNKNOWN


def fetch_fuel_entries(
    session: Session,
    car: Car,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> list[FuelEntry]:
    stmt = select(FuelEntry).where(FuelEntry.car_id == car.id)
    if start is not None:
        stmt = stmt.where(FuelEntry.datetime >= start)
    if end is not None:
        stmt = stmt.where(FuelEntry.datetime <= end)
    stmt = stmt.order_by(FuelEntry.datetime.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.execute(stmt).scalars())


def fetch_all_fuel_records(session: Session, car: Car) -> list[FuelRecord]:
    return [
        fuel_entry_to_record(e)
        for e in session.execute(
            select(FuelEntry).where(FuelEntry.car_id == car.id).order_by(FuelEntry.datetime)
        ).scalars()
    ]


def fetch_all_odometer_records(session: Session, car: Car) -> list[OdometerRecord]:
    return [
        odometer_entry_to_record(e)
        for e in session.execute(
            select(OdometerEntry).where(OdometerEntry.car_id == car.id).order_by(OdometerEntry.datetime)
        ).scalars()
    ]


def month_bounds(reference: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Inclusive [start, end] of the month containing `reference` (default: now)."""
    ref = reference or datetime.now()
    start = datetime.combine(date(ref.year, ref.month, 1), time.min)
    if ref.month == 12:
        next_start = datetime(ref.year + 1, 1, 1)
    else:
        next_start = datetime(ref.year, ref.month + 1, 1)
    end = next_start - timedelta(microseconds=1)
    return start, end
