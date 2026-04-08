"""Simple CLI for fuel analysis operations.

Usage:
    python -m fuel_analysis validate
    python -m fuel_analysis summary
"""

from __future__ import annotations

import argparse
import sys

from .loaders import load_fuel_data, load_odometer_data
from .metrics import (
    average_fuel_price,
    compute_consumption_estimates,
    fuel_records_to_dataframe,
    odometer_records_to_dataframe,
    total_distance,
    total_fuel_spending,
    total_fuel_volume,
)


def cmd_validate() -> int:
    """Validate both CSV files and print a summary."""
    print("=== Fuel Log Validation ===")
    fuel_records, fuel_result = load_fuel_data()
    print(fuel_result.summary())
    print(f"Valid records: {len(fuel_records)}")
    print()

    print("=== Odometer Log Validation ===")
    odo_records, odo_result = load_odometer_data()
    print(odo_result.summary())
    print(f"Valid records: {len(odo_records)}")
    print()

    if fuel_result.is_valid and odo_result.is_valid:
        print("All data is valid.")
        return 0
    else:
        print("Validation errors found. See above for details.")
        return 1


def cmd_summary() -> int:
    """Print a basic metrics summary."""
    fuel_records, fuel_result = load_fuel_data()
    odo_records, odo_result = load_odometer_data()

    if not fuel_result.is_valid or not odo_result.is_valid:
        print("WARNING: Validation errors exist. Summary may be incomplete.")
        print()

    fuel_df = fuel_records_to_dataframe(fuel_records)
    odo_df = odometer_records_to_dataframe(odo_records)

    print("=== Fuel Summary ===")
    print(f"  Total records:       {len(fuel_records)}")
    print(f"  Total liters:        {total_fuel_volume(fuel_df):.1f} L")
    print(f"  Total spending:      {total_fuel_spending(fuel_df):.2f} EUR")
    print(f"  Average price/liter: {average_fuel_price(fuel_df):.3f} EUR")
    print()

    print("=== Odometer Summary ===")
    print(f"  Total records:       {len(odo_records)}")
    print(f"  Total distance:      {total_distance(odo_df):.0f} km")
    print()

    estimates = compute_consumption_estimates(fuel_records, odo_records)
    if estimates:
        avg_consumption = sum(e.liters_per_100km.value for e in estimates) / len(estimates)
        avg_cost_per_100 = sum(e.cost_per_100km.value for e in estimates) / len(estimates)
        print("=== Consumption Estimates (linear interpolation) ===")
        print(f"  Segments computed:      {len(estimates)}")
        print(f"  Avg L/100km:            {avg_consumption:.2f} (estimated)")
        print(f"  Avg cost/100km:         {avg_cost_per_100:.2f} EUR (estimated)")
        print()
        print("  Note: These are estimates based on linear interpolation of")
        print("  odometer readings. See README for details on methodology.")
    else:
        print("  Insufficient data for consumption estimates.")

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fuel_analysis",
        description="Fuel consumption and mileage analysis tool",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.add_parser("validate", help="Validate raw CSV files")
    subparsers.add_parser("summary", help="Print data quality and metrics summary")

    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate()
    elif args.command == "summary":
        return cmd_summary()
    else:
        parser.print_help()
        return 0
