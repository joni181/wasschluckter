"""Configuration for the fuel analysis project.

All configuration is centralized here. Paths, CSV dialect settings,
validation tolerances, allowed enum values, and plotting defaults.
"""

from pathlib import Path
from dataclasses import dataclass, field


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class CsvConfig:
    """CSV dialect configuration.

    Choice: comma-separated, UTF-8, period as decimal separator.
    Rationale: this is the most portable dialect across Python's csv module,
    pandas, and common spreadsheet tools (Excel, LibreOffice, Google Sheets).
    """

    delimiter: str = ","
    encoding: str = "utf-8"
    decimal: str = "."
    quotechar: str = '"'


@dataclass(frozen=True)
class PathConfig:
    """File path configuration."""

    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "reports")
    fuel_log: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "fuel_log.csv")
    odometer_log: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "odometer_log.csv")


@dataclass(frozen=True)
class ValidationConfig:
    """Validation tolerances and constraints."""

    # Relative tolerance for amount_eur vs liters * price_per_liter_eur check.
    # 2% allows for minor rounding differences in real-world receipts.
    price_consistency_tolerance: float = 0.002

    # Suspiciously low/high price per liter thresholds (EUR) for warnings.
    price_per_liter_min_warn: float = 0.80
    price_per_liter_max_warn: float = 3.00


@dataclass(frozen=True)
class PlottingConfig:
    """Matplotlib plotting defaults."""

    figure_width: float = 12.0
    figure_height: float = 6.0
    dpi: int = 100
    style: str = "seaborn-v0_8-whitegrid"
    date_format: str = "%Y-%m"


# Allowed fuel types for v1.
ALLOWED_FUEL_TYPES: frozenset[str] = frozenset({"E5", "E10"})

# Allowed country codes for v1.
# At minimum DE, IT, AT, FR, HR, CH. Additional ISO 3166-1 alpha-2 codes
# are accepted if they are exactly 2 uppercase ASCII letters.
REQUIRED_COUNTRY_CODES: frozenset[str] = frozenset({"DE", "IT", "AT", "FR", "HR", "CH"})

# Interpolation method for v1.
DEFAULT_INTERPOLATION_METHOD: str = "linear"


def get_config() -> dict:
    """Return a dictionary of all configuration objects."""
    return {
        "csv": CsvConfig(),
        "paths": PathConfig(),
        "validation": ValidationConfig(),
        "plotting": PlottingConfig(),
    }
