"""Interpolation module for estimating odometer values at arbitrary timestamps.

v1 uses linear interpolation exclusively.

Why linear interpolation:
- Odometer progression between sparse timestamped observations is best
  approximated conservatively.
- Linear interpolation is simple, interpretable, stable, and easy to audit.
- Higher-order polynomial methods (Newton, Aitken-Neville, etc.) are
  intentionally not used because:
  - They are unnecessary for sparse real-world event data.
  - They can introduce oscillatory or nonphysical behavior (Runge phenomenon).
  - They reduce interpretability.
  - They imply more model structure than the data justifies.

The architecture supports future extension to other estimation strategies
via the InterpolationStrategy protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .models import EstimatedValue, EstimationQuality, OdometerRecord


class InterpolationStrategy(ABC):
    """Abstract base for interpolation strategies.

    Extend this to add new estimation methods in future versions.
    """

    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the strategy."""
        ...

    @abstractmethod
    def estimate(
        self,
        target_dt: datetime,
        records: list[OdometerRecord],
    ) -> EstimatedValue:
        """Estimate the odometer value at the given datetime."""
        ...


class LinearInterpolation(InterpolationStrategy):
    """Linear interpolation between the two nearest odometer readings."""

    def name(self) -> str:
        return "linear"

    def estimate(
        self,
        target_dt: datetime,
        records: list[OdometerRecord],
    ) -> EstimatedValue:
        """Estimate odometer reading at target_dt using linear interpolation.

        If target_dt exactly matches a record, returns an exact value.
        If target_dt falls between two records, linearly interpolates.
        If target_dt is outside the range of records, returns insufficient.
        """
        if not records:
            return EstimatedValue(
                value=0.0,
                quality=EstimationQuality.INSUFFICIENT,
                method=self.name(),
            )

        sorted_records = sorted(records, key=lambda r: r.datetime)

        # Check for exact match.
        for r in sorted_records:
            if r.datetime == target_dt:
                return EstimatedValue(
                    value=r.odometer_km,
                    quality=EstimationQuality.EXACT,
                    method=self.name(),
                    source_interval=f"exact match at {r.event_id}",
                )

        # Find bracketing records.
        before: Optional[OdometerRecord] = None
        after: Optional[OdometerRecord] = None

        for r in sorted_records:
            if r.datetime < target_dt:
                before = r
            elif r.datetime > target_dt:
                after = r
                break

        if before is None or after is None:
            return EstimatedValue(
                value=0.0,
                quality=EstimationQuality.INSUFFICIENT,
                method=self.name(),
                source_interval=self._describe_bounds(before, after),
            )

        # Linear interpolation.
        total_seconds = (after.datetime - before.datetime).total_seconds()
        if total_seconds == 0:
            return EstimatedValue(
                value=before.odometer_km,
                quality=EstimationQuality.ESTIMATED,
                method=self.name(),
                source_interval=f"{before.event_id} -> {after.event_id}",
            )

        fraction = (target_dt - before.datetime).total_seconds() / total_seconds
        interpolated = before.odometer_km + fraction * (after.odometer_km - before.odometer_km)

        return EstimatedValue(
            value=interpolated,
            quality=EstimationQuality.ESTIMATED,
            method=self.name(),
            source_interval=f"{before.event_id} -> {after.event_id}",
        )

    @staticmethod
    def _describe_bounds(
        before: Optional[OdometerRecord],
        after: Optional[OdometerRecord],
    ) -> str:
        if before is None and after is None:
            return "no bracketing records"
        if before is None:
            return f"before first record ({after.event_id})"  # type: ignore[union-attr]
        return f"after last record ({before.event_id})"


def get_interpolation_strategy(method: str = "linear") -> InterpolationStrategy:
    """Factory function for interpolation strategies.

    v1 only supports 'linear'. Raises ValueError for unknown methods.
    """
    strategies: dict[str, type[InterpolationStrategy]] = {
        "linear": LinearInterpolation,
    }
    if method not in strategies:
        raise ValueError(
            f"Unknown interpolation method: '{method}'. "
            f"Available: {sorted(strategies.keys())}"
        )
    return strategies[method]()
