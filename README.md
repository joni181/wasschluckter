# Was schluckt er? -- Vehicle Fuel Analysis

A Python toolkit for recording, validating, and analyzing vehicle fuel purchases and odometer readings across European countries. The project ingests manually maintained CSV logs, validates the data, computes fuel economy metrics, and produces charts for exploratory analysis in Jupyter notebooks.

## Setup

```bash
# Clone the repository and enter it
cd wasschluckter

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install the package in editable mode (from the project root)
pip install -e .

# Install additional tools (Jupyter for notebooks)
pip install -r requirements.txt
```

The `pip install -e .` command must be run from the project root where `pyproject.toml` lives.

## Dependencies

| Package    | Version       | Purpose                        |
|------------|---------------|--------------------------------|
| pandas     | >= 2.0, < 3.0 | Data loading and analysis      |
| matplotlib | >= 3.7, < 4.0 | Charts and plotting            |
| notebook   | >= 7.0, < 8.0 | Jupyter notebook support       |

## Folder Structure

```
wasschluckter/
├── README.md
├── pyproject.toml
├── requirements.txt
├── data/
│   ├── fuel_log.csv
│   └── odometer_log.csv
├── notebooks/
│   └── initial_analysis.ipynb
├── src/
│   └── fuel_analysis/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       ├── models.py
│       ├── loaders.py
│       ├── validators.py
│       ├── interpolation.py
│       ├── metrics.py
│       ├── plotting.py
│       └── cli.py
├── tests/
│   ├── test_models.py
│   ├── test_validation.py
│   ├── test_interpolation.py
│   └── test_metrics.py
└── .gitignore
```

## CSV Files

### CSV Dialect

Both CSV files use the same dialect:

- **Delimiter**: comma (`,`)
- **Encoding**: UTF-8
- **Decimal separator**: period (`.`)
- **Quote character**: double quote (`"`)
- **Datetime convention**: timezone-naive local time (ISO format, e.g. `2024-03-15 08:30:00`). All times represent the local time at the location of the event.

This dialect was chosen for maximum portability across Python, Excel, LibreOffice, and Google Sheets.

### `data/fuel_log.csv`

Each row records a single fuel purchase event.

| Column               | Type        | Required | Description                                                |
|----------------------|-------------|----------|------------------------------------------------------------|
| datetime             | datetime    | yes      | When the purchase happened (local time, ISO format)        |
| amount_eur           | float > 0   | yes      | Total amount paid in EUR                                   |
| liters               | float > 0   | yes      | Liters of fuel purchased                                   |
| price_per_liter_eur  | float > 0   | yes      | Price per liter in EUR                                     |
| fuel_type            | enum        | yes      | `E5` or `E10`                                              |
| is_full_tank         | bool/empty  | optional | `true`, `false`, or empty (= unknown)                      |
| station_name         | text        | yes      | Name of the fuel station                                   |
| city                 | text        | yes      | City where the station is located                          |
| country              | 2-letter    | yes      | ISO 3166-1 alpha-2 code (primary: DE, IT, AT, FR, HR, CH) |
| notes                | text        | optional | Free text notes                                            |

### `data/odometer_log.csv`

Each row records an odometer reading at a point in time.

| Column      | Type      | Required | Description                                         |
|-------------|-----------|----------|-----------------------------------------------------|
| datetime    | datetime  | yes      | When the reading was taken (local time, ISO format)  |
| odometer_km | float >= 0 | yes     | Odometer reading in kilometers                       |
| notes       | text      | optional | Free text notes                                     |

### Duplicate Detection

Instead of requiring manually maintained unique IDs, duplicates are detected automatically by comparing:

- **Fuel events**: datetime within +/- 20 minutes AND identical liters value
- **Odometer events**: datetime within +/- 20 minutes AND identical odometer_km value

Potential duplicates are reported as warnings, not errors.

## Usage

### Validate CSV files

```bash
python -m fuel_analysis validate
```

Checks both CSV files for structural errors and data quality issues. Reports hard errors and soft warnings.

### Print metrics summary

```bash
python -m fuel_analysis summary
```

Prints total fuel volume, spending, average price, distance driven, and estimated consumption metrics.

### Run the analysis notebook

```bash
jupyter notebook notebooks/initial_analysis.ipynb
```

The notebook loads data through the package (no inline re-parsing), validates inputs, computes metrics, and generates charts.

## Interpolation Approach

### Why linear interpolation (v1)

Combined metrics like L/100km require knowing the odometer reading at each fuel event time. Since odometer readings and fuel events are logged independently, exact alignment is rare. v1 uses **linear interpolation** to estimate odometer values between known readings.

Linear interpolation was chosen because:

- It is the most **conservative** approximation for sparse, irregularly-spaced observations
- It is **simple**, **interpretable**, **stable**, and **easy to audit**
- It assumes constant driving speed between two readings, which is a reasonable first-order approximation

### Why not higher-order methods?

Higher-order polynomial interpolation methods (Newton, Aitken-Neville, cubic splines) are **intentionally not used** in v1:

- **Unnecessary for sparse real-world data**: odometer readings are recorded at irregular, widely-spaced intervals. Higher-order polynomials impose structure the data does not support.
- **Oscillatory artifacts (Runge phenomenon)**: polynomial interpolation through sparse points can produce nonphysical oscillations, leading to negative distances or implausible speed estimates.
- **Reduced interpretability**: linear interpolation is trivial to audit. Higher-order methods make it harder to trace how an estimated value was derived.
- **No justified model complexity**: a more complex model would imply knowledge about driving patterns that we do not have.

The architecture supports future extension via the `InterpolationStrategy` abstract base class.

## Exact vs Estimated Metrics

The project clearly distinguishes between:

- **Exact metrics**: computed directly from a single data source without interpolation.
  - Fuel-only: total volume, total spending, average price, price by country/city
  - Odometer-only: total distance, monthly km driven, cumulative distance
- **Estimated metrics**: require combining fuel and odometer data via interpolation.
  - L/100km, cost/100km, cost/km

Every estimated value carries metadata indicating:
- That interpolation was used
- Which method was used (`linear`)
- The source interval used for interpolation
- The quality classification: `exact`, `estimated`, or `insufficient`

In the consumption chart, data points are color-coded:
- **Green**: exact (odometer readings existed at both fuel event timestamps)
- **Orange**: estimated (at least one odometer value was interpolated)

## Validation Policy

### Hard errors (block loading)

- Unparsable datetime
- Negative or zero values for amount_eur, liters, price_per_liter_eur
- Negative odometer_km
- Invalid fuel_type (not E5 or E10)
- Invalid country code format (not 2 uppercase letters)
- Missing required fields (station_name, country)
- Missing required columns in the CSV header

### Soft warnings (reported, do not block)

- Price consistency: `amount_eur` vs `liters * price_per_liter_eur` mismatch beyond 2% tolerance
- Suspiciously high (> 3.00 EUR) or low (< 0.80 EUR) price per liter
- Odometer monotonicity violations (reading decreases over time)
- Potential duplicate entries (based on datetime proximity + value matching)
- Country code not in the primary set (DE, IT, AT, FR, HR, CH)
- Missing city value

## Limitations of v1

- No OCR for receipts or odometer photos
- No image import pipeline
- No database storage (CSV only)
- No web UI
- No PDF/report export
- No advanced interpolation beyond linear
- No machine learning or forecasting
- No automated scheduling

## Future Extensibility

The project is designed for straightforward extension:

- **New fuel types**: add values to the `FuelType` enum and `ALLOWED_FUEL_TYPES`
- **New countries**: add values to `Country` enum and `REQUIRED_COUNTRY_CODES`
- **New metrics**: add functions to `metrics.py`
- **New charts**: add functions to `plotting.py`
- **New interpolation strategies**: implement the `InterpolationStrategy` ABC
- **Image ingestion**: add new loader modules
- **Richer reporting**: add export modules (PDF, HTML)
