"""Typed data models for fuel purchase and odometer events.

Datetime convention (v1): all datetimes are timezone-naive and represent
the local time at the location of the event. This is documented here and
in the README. The entire codebase uses this convention consistently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class FuelType(str, Enum):
    """Allowed fuel types for v1."""

    E5 = "E5"
    E10 = "E10"


class Country(str, Enum):
    """Supported country codes (ISO 3166-1 alpha-2).

    The core set for v1. Additional codes are validated via regex
    in the validation layer rather than requiring enum membership,
    but these are the primary supported values.
    """

    DE = "DE"
    IT = "IT"
    AT = "AT"
    FR = "FR"
    HR = "HR"
    CH = "CH"


# Regex for valid ISO 3166-1 alpha-2 country codes.
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")


class FullTankStatus(Enum):
    """Three-valued full tank indicator: true, false, or unknown."""

    YES = "true"
    NO = "false"
    UNKNOWN = "unknown"

    @classmethod
    def from_csv_value(cls, value: str) -> FullTankStatus:
        """Parse a CSV cell value into a FullTankStatus.

        Empty string or whitespace-only is treated as UNKNOWN.
        """
        cleaned = value.strip().lower()
        if cleaned in ("", "na", "none"):
            return cls.UNKNOWN
        if cleaned in ("true", "1", "yes"):
            return cls.YES
        if cleaned in ("false", "0", "no"):
            return cls.NO
        raise ValueError(
            f"Invalid full tank value: '{value}'. "
            f"Expected true/false/empty or yes/no/1/0."
        )


@dataclass(frozen=True)
class FuelRecord:
    """A single validated fuel purchase event."""

    event_id: str
    datetime: datetime
    amount_eur: float
    liters: float
    price_per_liter_eur: float
    fuel_type: FuelType
    is_full_tank: FullTankStatus
    station_name: str
    city: str
    country: str
    notes: str

    def computed_amount(self) -> float:
        """Return liters * price_per_liter_eur for consistency checks."""
        return self.liters * self.price_per_liter_eur


@dataclass(frozen=True)
class OdometerRecord:
    """A single validated odometer reading event."""

    event_id: str
    datetime: datetime
    odometer_km: float
    notes: str


class EstimationQuality(str, Enum):
    """Quality classification for derived metric values."""

    EXACT = "exact"
    ESTIMATED = "estimated"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class EstimatedValue:
    """A numeric value with provenance metadata.

    Used for any derived metric that may involve interpolation.
    """

    value: float
    quality: EstimationQuality
    method: Optional[str] = None
    source_interval: Optional[str] = None

    def __repr__(self) -> str:
        label = f"{self.value:.4f} [{self.quality.value}]"
        if self.method:
            label += f" (method={self.method})"
        return label
