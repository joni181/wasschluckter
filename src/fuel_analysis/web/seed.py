"""First-run seeding: ensures a default user + default car exist, and
imports the legacy CSV logs into SQLite if they aren't in the DB yet.

Idempotent: safe to run repeatedly. Re-imports are skipped by checking
whether any fuel entries already exist for the default car.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import PathConfig
from ..loaders import load_fuel_data, load_odometer_data
from .db import Car, FuelEntry, OdometerEntry, User, UserCar

DEFAULT_USER_EMAIL = "me@localhost"
DEFAULT_USER_NAME = "Me"
DEFAULT_CAR_NAME = "My Car"


def ensure_default_user(session: Session) -> User:
    user = session.execute(
        select(User).where(User.email == DEFAULT_USER_EMAIL)
    ).scalar_one_or_none()
    if user is None:
        user = User(email=DEFAULT_USER_EMAIL, display_name=DEFAULT_USER_NAME)
        session.add(user)
        session.flush()
    return user


def ensure_default_car(session: Session, user: User) -> Car:
    # The "default car" is the first car linked to the default user.
    link = session.execute(
        select(UserCar).where(UserCar.user_id == user.id)
    ).scalar_one_or_none()
    if link is not None:
        return session.get(Car, link.car_id)

    car = Car(name=DEFAULT_CAR_NAME)
    session.add(car)
    session.flush()
    session.add(UserCar(user_id=user.id, car_id=car.id, role="owner"))
    session.flush()
    return car


def import_csvs_if_empty(
    session: Session,
    user: User,
    car: Car,
    fuel_csv: Optional[Path] = None,
    odometer_csv: Optional[Path] = None,
) -> tuple[int, int]:
    """Import CSVs into the DB only if the car has no entries yet.

    Returns (fuel_imported, odometer_imported).
    """
    fuel_count = session.execute(
        select(FuelEntry).where(FuelEntry.car_id == car.id).limit(1)
    ).first()
    odo_count = session.execute(
        select(OdometerEntry).where(OdometerEntry.car_id == car.id).limit(1)
    ).first()

    fuel_imported = 0
    odo_imported = 0

    if fuel_count is None:
        fuel_path = fuel_csv or PathConfig().fuel_log
        if fuel_path.exists():
            fuel_records, _ = load_fuel_data(path=fuel_path)
            for r in fuel_records:
                session.add(
                    FuelEntry(
                        car_id=car.id,
                        created_by_user_id=user.id,
                        datetime=r.datetime,
                        amount_eur=r.amount_eur,
                        liters=r.liters,
                        fuel_type=r.fuel_type.value,
                        is_full_tank=r.is_full_tank.value,
                        station_name=r.station_name,
                        city=r.city,
                        country=r.country,
                        notes=r.notes,
                    )
                )
                fuel_imported += 1

    if odo_count is None:
        odo_path = odometer_csv or PathConfig().odometer_log
        if odo_path.exists():
            odo_records, _ = load_odometer_data(path=odo_path)
            for r in odo_records:
                session.add(
                    OdometerEntry(
                        car_id=car.id,
                        created_by_user_id=user.id,
                        datetime=r.datetime,
                        odometer_km=r.odometer_km,
                        notes=r.notes,
                    )
                )
                odo_imported += 1

    session.commit()
    return fuel_imported, odo_imported


def bootstrap(session: Session) -> tuple[User, Car]:
    """Ensure a default user+car exist and CSV data is imported."""
    user = ensure_default_user(session)
    car = ensure_default_car(session, user)
    import_csvs_if_empty(session, user, car)
    return user, car
