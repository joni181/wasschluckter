# Was schluckt er? -- Vehicle Fuel Analysis

A Python toolkit for recording, validating, and analyzing vehicle fuel purchases and odometer readings across European countries. The project ingests manually maintained CSV logs, validates the data, computes fuel economy metrics, and produces charts for exploratory analysis in Jupyter notebooks.

## Setup

1. Clone the repository and change into the project directory.

2. (Recommended) Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install the package in editable mode:
   ```
   pip install -e .
   ```

4. Install all dependencies:
   ```
   pip install -r requirements.txt
   ```

## Dependencies

| Package    | Version constraint | Purpose                                 |
|------------|--------------------|-----------------------------------------|
| pandas     | >=2.0, <3.0        | DataFrames, time-series resampling      |
| matplotlib | >=3.7, <4.0        | Charts and visualizations               |
| notebook   | >=7.0, <8.0        | Jupyter notebook runtime                |
| pydantic   | >=2.0, <3.0        | Data validation support                 |

Python 3.10 or later is required.

## Folder Structure

```
wasschluckter/
├── data/
│   ├── fuel_log.csv
│   └── odometer_log.csv
├── notebooks/
│   └── initial_analysis.ipynb
├── src/
│   └── fuel_analysis/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── interpolation.py
│       ├── loaders.py
│       ├── metrics.py
│       ├── models.py
│       ├── plotting.py
│       └── validators.py
├── tests/
│   └── __init__.py
├── .gitignore
├── requirements.txt
├── setup.py
└── README.md
```

## Data Files

Both CSV files use the following dialect:

- **Delimiter:** comma (`,`)
- **Encoding:** UTF-8
- **Decimal separator:** period (`.`)
- **Datetime convention:** all datetimes are timezone-naive and represent the local time at the location of the event.

### `data/fuel_log.csv`

Each row represents a single fuel purchase event.

| Column               | Type    | Description                                                                 |
|----------------------|---------|-----------------------------------------------------------------------------|
| `event_id`           | string  | Unique identifier for the fuel event (e.g. `F001`).                        |
| `datetime`           | string  | Timestamp of the purchase in `YYYY-MM-DD HH:MM:SS` format, timezone-naive. |
| `amount_eur`         | float   | Total cost of the purchase in EUR.                                         |
| `liters`             | float   | Volume of fuel purchased in liters.                                        |
| `price_per_liter_eur`| float   | Unit price in EUR per liter.                                               |
| `fuel_type`          | string  | Fuel grade. Allowed values in v1: `E5`, `E10`.                             |
| `is_full_tank`       | string  | Whether the tank was filled completely: `true`, `false`, or empty (unknown).|
| `station_name`       | string  | Name of the fuel station.                                                  |
| `city`               | string  | City where the station is located.                                         |
| `country`            | string  | ISO 3166-1 alpha-2 country code (e.g. `DE`, `AT`, `FR`).                  |
| `notes`              | string  | Optional free-text notes.                                                  |

### `data/odometer_log.csv`

Each row represents a single odometer reading.

| Column        | Type    | Description                                                                 |
|---------------|---------|-----------------------------------------------------------------------------|
| `event_id`    | string  | Unique identifier for the reading (e.g. `O001`).                           |
| `datetime`    | string  | Timestamp of the reading in `YYYY-MM-DD HH:MM:SS` format, timezone-naive.  |
| `odometer_km` | float   | Cumulative distance shown on the odometer in kilometers.                   |
| `notes`       | string  | Optional free-text notes.                                                  |

## Usage

### Validate Data

Run validation on both CSV files. Hard errors and soft warnings are printed to the console.

```
python -m fuel_analysis validate
```

### Print Summary

Compute and display fuel, odometer, and consumption metrics.

```
python -m fuel_analysis summary
```

### Run the Notebook

Launch Jupyter and open the exploratory analysis notebook.

```
jupyter notebook notebooks/initial_analysis.ipynb
```

## Interpolation Approach

Version 1 uses **linear interpolation** exclusively to estimate odometer readings at fuel purchase timestamps.

**Why linear interpolation:**

- **Conservative.** It assumes a constant rate of distance accumulation between two known odometer readings, which is the least presumptive model possible.
- **Simple.** The implementation is a single formula with no tuneable parameters.
- **Interpretable.** Any analyst can verify an interpolated value by hand.
- **Stable.** Results do not change unexpectedly when new data points are added elsewhere in the timeline.
- **Auditable.** Every estimated value carries provenance metadata (method name, source interval) so downstream consumers can trace how it was derived.

**Why higher-order methods (Newton, Aitken-Neville, splines) are not used:**

- **Unnecessary for sparse data.** Odometer readings are recorded days or weeks apart; polynomial curves fitted to a handful of points do not yield meaningful additional accuracy.
- **Oscillatory behavior.** Higher-degree polynomials are prone to the Runge phenomenon, producing nonphysical swings between data points.
- **Reduced interpretability.** A cubic or higher-order estimate is harder for a non-technical user to verify or explain.
- **Implies more structure than the data justifies.** Using a complex model on sparse observations creates a false sense of precision.

The interpolation layer is designed for extensibility: the `InterpolationStrategy` abstract base class allows new methods to be added in future versions without changing downstream code.

## Exact vs. Estimated Metrics

The project distinguishes between two quality levels for every computed metric.

- **Exact metrics** are derived from a single data source and require no interpolation. Examples: total liters purchased, total EUR spent, average price per liter (fuel log only), total distance driven (odometer log only).
- **Estimated metrics** combine data from both CSVs and require interpolating odometer values at fuel event timestamps. Examples: liters per 100 km, cost per 100 km, cost per km.

Every estimated value carries an `EstimationQuality` label (`exact`, `estimated`, or `insufficient`) and the name of the method used. Charts color-code data points by quality -- green for exact, orange for estimated -- so the viewer can immediately see which values are directly measured and which are derived.

## Validation Policy

Validation runs in two tiers.

### Hard errors

Hard errors indicate structurally invalid data. A record with a hard error is excluded from all analysis. Examples:

- Missing or empty `event_id`.
- Unparsable datetime string.
- Negative or zero numeric values for `amount_eur`, `liters`, or `price_per_liter_eur`.
- Unrecognized `fuel_type` (not in `{E5, E10}`).
- Invalid country code format (not a two-letter uppercase ISO code).
- Duplicate `event_id` within a dataset.
- Missing required columns in the CSV header.

### Soft warnings

Soft warnings flag suspicious data that is still loadable. The record is included in analysis but the issue is reported. Examples:

- Price consistency mismatch: `amount_eur` differs from `liters * price_per_liter_eur` by more than 2%.
- Suspiciously low (below 0.80 EUR) or high (above 3.00 EUR) price per liter.
- Odometer monotonicity violation (a later reading is lower than an earlier one).
- Potential duplicate entries (same datetime and station for two different event IDs).
- Missing optional fields such as `city`.

## Limitations of v1

The current version is intentionally minimal. The following capabilities are out of scope:

- No OCR or image-based receipt ingestion.
- No image import of any kind.
- No database backend; all data lives in flat CSV files.
- No web UI or REST API.
- No PDF or HTML report export.
- No advanced interpolation methods (splines, polynomial regression, Bayesian estimation).
- No machine learning or predictive modeling.

## Future Extensibility

The architecture is designed to accommodate the following extensions in later versions:

- **New fuel types.** Additional values can be added to the `FuelType` enum and the allowed-types configuration set.
- **New countries.** The country validation accepts any valid ISO 3166-1 alpha-2 code; the primary-set warning list can be expanded in configuration.
- **New metrics.** Metric functions follow a consistent pattern (accept a DataFrame, return a scalar or DataFrame) and can be added independently.
- **New charts.** The plotting module is stateless; new plot functions can be added without modifying existing ones.
- **Image ingestion.** A future OCR pipeline could feed parsed receipt data directly into the existing validation and loading layers.
- **Richer reporting.** PDF or HTML export could consume the same DataFrames and estimation objects that the notebook uses today.
