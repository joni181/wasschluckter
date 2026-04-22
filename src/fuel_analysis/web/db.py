"""Database layer for the web app.

Schema is intentionally shaped for multi-user / multi-car extensibility:

- users(id, email, display_name, created_at) — one row per person.
- cars(id, name, created_at) — one row per physical vehicle.
- user_cars(user_id, car_id, role) — many-to-many, so one car can be
  shared between users and one user can own multiple cars.
- fuel_entries(id, car_id, created_by_user_id, datetime, ...) — scoped
  to a car. Who entered it is recorded but not required for queries.
- odometer_entries(id, car_id, created_by_user_id, datetime, ...) — same.

Auth is not yet wired. For the current single-user deployment the seed
creates one user ("default") and one car ("default"), and the web layer
reads/writes against those. When login lands, nothing in this schema
changes — only the session layer picks up real user_id + car_id.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    create_engine,
    event,
    func,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
    Session,
)

from ..config import PROJECT_ROOT


def default_db_path() -> Path:
    return PROJECT_ROOT / "data" / "wasschluckter.sqlite3"


def make_engine(db_path: Optional[Path] = None) -> Engine:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path}",
        future=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_pragmas(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    return engine


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cars: Mapped[list["UserCar"]] = relationship(back_populates="user")


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    users: Mapped[list["UserCar"]] = relationship(back_populates="car")
    fuel_entries: Mapped[list["FuelEntry"]] = relationship(back_populates="car")
    odometer_entries: Mapped[list["OdometerEntry"]] = relationship(back_populates="car")


class UserCar(Base):
    """Link between a user and a car, with a role (e.g. owner, shared)."""

    __tablename__ = "user_cars"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="cars")
    car: Mapped[Car] = relationship(back_populates="users")


class FuelEntry(Base):
    __tablename__ = "fuel_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount_eur: Mapped[float] = mapped_column(Float)
    liters: Mapped[float] = mapped_column(Float)
    fuel_type: Mapped[str] = mapped_column(String(8))       # "E5" | "E10" (extensible)
    is_full_tank: Mapped[str] = mapped_column(String(8))    # "true" | "false" | "unknown"
    station_name: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(2))         # ISO 3166-1 alpha-2
    notes: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    car: Mapped[Car] = relationship(back_populates="fuel_entries")

    @property
    def price_per_liter_eur(self) -> float:
        return self.amount_eur / self.liters


class OdometerEntry(Base):
    __tablename__ = "odometer_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    odometer_km: Mapped[float] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    car: Mapped[Car] = relationship(back_populates="odometer_entries")


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db(engine: Engine) -> None:
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(engine)
