"""Country list used by the New Entry form.

The primary European set is listed first so it stays above the fold
in the dropdown. The rest of the ISO 3166-1 alpha-2 set follows for
completeness. Later we may reorder by user-frequency.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CountryOption:
    code: str       # ISO alpha-2
    name: str       # Display name in English


PRIMARY_CODES = ("DE", "AT", "IT", "FR", "HR", "CH")

# Full alpha-2 set (subset pragmatically chosen for drivers in Europe
# plus common long-haul destinations).
_ALL: tuple[CountryOption, ...] = (
    CountryOption("DE", "Germany"),
    CountryOption("AT", "Austria"),
    CountryOption("IT", "Italy"),
    CountryOption("FR", "France"),
    CountryOption("HR", "Croatia"),
    CountryOption("CH", "Switzerland"),
    CountryOption("BE", "Belgium"),
    CountryOption("NL", "Netherlands"),
    CountryOption("LU", "Luxembourg"),
    CountryOption("DK", "Denmark"),
    CountryOption("PL", "Poland"),
    CountryOption("CZ", "Czechia"),
    CountryOption("SK", "Slovakia"),
    CountryOption("SI", "Slovenia"),
    CountryOption("HU", "Hungary"),
    CountryOption("ES", "Spain"),
    CountryOption("PT", "Portugal"),
    CountryOption("SE", "Sweden"),
    CountryOption("NO", "Norway"),
    CountryOption("FI", "Finland"),
    CountryOption("GB", "United Kingdom"),
    CountryOption("IE", "Ireland"),
    CountryOption("GR", "Greece"),
    CountryOption("RO", "Romania"),
    CountryOption("BG", "Bulgaria"),
    CountryOption("LI", "Liechtenstein"),
    CountryOption("MC", "Monaco"),
    CountryOption("SM", "San Marino"),
    CountryOption("ME", "Montenegro"),
    CountryOption("RS", "Serbia"),
    CountryOption("BA", "Bosnia and Herzegovina"),
    CountryOption("MK", "North Macedonia"),
    CountryOption("AL", "Albania"),
    CountryOption("TR", "Turkey"),
)


def ordered_country_options() -> list[CountryOption]:
    primary = [c for c in _ALL if c.code in PRIMARY_CODES]
    # Preserve PRIMARY_CODES order.
    primary.sort(key=lambda c: PRIMARY_CODES.index(c.code))
    rest = sorted([c for c in _ALL if c.code not in PRIMARY_CODES], key=lambda c: c.name)
    return primary + rest


def is_known(code: str) -> bool:
    return any(c.code == code for c in _ALL)
