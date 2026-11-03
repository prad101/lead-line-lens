"""Canonical service line inventory schema.

Every inventory (Chicago's export or a utility upload) is mapped to these columns,
which follow the Illinois EPA service line inventory template. Material values are
normalized to four categories: Lead, GRR (galvanized requiring replacement),
Non-Lead, and Unknown. The full vocabulary mapping is recorded in
docs/data_dictionary.md.
"""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import pandera.pandas as pa

MATERIALS: tuple[str, ...] = ("Lead", "GRR", "Non-Lead", "Unknown")

CANONICAL_COLUMNS: tuple[str, ...] = (
    "line_id",
    "address",
    "pin",
    "utility_side_material",
    "customer_side_material",
    "year_built",
    "install_year",
    "diameter_in",
    "verification_method",
    "replacement_date",
    "notification_date",
    "snapshot_date",
)

REQUIRED_COLUMNS: tuple[str, ...] = (
    "line_id",
    "utility_side_material",
    "customer_side_material",
)

MIN_YEAR = 1830

_UNKNOWN_TOKENS = {"", "unk", "unknown", "na", "n/a", "none", "null", "not reported", "?"}

# Illinois EPA inventory template codes. G is galvanized never downstream of lead; it is
# mapped to GRR anyway so that a mapping never lowers urgency.
IEPA_CODES: dict[str, str] = {
    "l": "Lead",
    "grr": "GRR",
    "g": "GRR",
    "c": "Non-Lead",
    "cls": "Non-Lead",
    "o": "Non-Lead",
    "p": "Non-Lead",
    "nl": "Non-Lead",
    "unl": "Non-Lead",
    "u": "Unknown",
}

# Order matters: "non-lead" must be tested before "lead", and GRR before plain galvanized.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bunknown\b.*\bnot\s*-?\s*lead\b|\bnot\s*-?\s*lead\b.*\bunknown\b"), "Non-Lead"),
    (re.compile(r"\b(lead\s+status\s+)?unknown\b|\bunk\b|\bundetermined\b"), "Unknown"),
    (re.compile(r"\bnon\s*-?\s*lead\b|\bnot\s*-?\s*lead\b|\blead\s*-?\s*free\b"), "Non-Lead"),
    (re.compile(r"\bgrr\b|galvani[sz]ed.*requir|requir.*galvani[sz]ed"), "GRR"),
    # Plain "galvanized" is treated as GRR: a prediction or mapping never lowers urgency.
    (re.compile(r"galvani[sz]ed|\bgalv\b"), "GRR"),
    (re.compile(r"copper.*lead\s+solder|lead\s+solder"), "Non-Lead"),
    (re.compile(r"\blead\b|\bpb\b"), "Lead"),
    (
        re.compile(
            r"copper|\bcu\b|plastic|pvc|cpvc|\bpe\b|hdpe|pex|polyethylene|polybutylene"
            r"|cast\s*iron|ductile|\bci\b|\bdi\b|transite|asbestos|brass|\bsteel\b|\bac\b"
        ),
        "Non-Lead",
    ),
)


def normalize_material(value: object, strict: bool = False) -> str:
    """Map a raw material string (any vocabulary) to one of MATERIALS.

    Empty or missing values are Unknown. Unrecognized strings are Unknown, or raise
    ValueError when strict=True so audits can surface new vocabulary.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NA:
        return "Unknown"
    s = re.sub(r"\s+", " ", str(value).strip().lower())
    if s in _UNKNOWN_TOKENS:
        return "Unknown"
    if s in IEPA_CODES:
        return IEPA_CODES[s]
    for title in MATERIALS:
        if s == title.lower():
            return title
    for pattern, material in _RULES:
        if pattern.search(s):
            return material
    if strict:
        raise ValueError(f"Unrecognized material value: {value!r}")
    return "Unknown"


def unrecognized_materials(values: pd.Series) -> list[str]:
    """Distinct raw values that normalize_material cannot classify."""
    bad = []
    for v in values.dropna().astype(str).unique():
        try:
            normalize_material(v, strict=True)
        except ValueError:
            bad.append(v)
    return sorted(bad)


def inventory_schema() -> pa.DataFrameSchema:
    """No nulls in key columns, materials in MATERIALS, plausible years and diameters."""
    max_year = dt.date.today().year
    year = pa.Column(
        "Int64", pa.Check.in_range(MIN_YEAR, max_year), nullable=True, required=False
    )
    material = pa.Column(str, pa.Check.isin(MATERIALS), nullable=False)
    return pa.DataFrameSchema(
        {
            "line_id": pa.Column(str, nullable=False, unique=True),
            "address": pa.Column(str, nullable=True, required=False),
            "pin": pa.Column(str, pa.Check.str_matches(r"^\d{10}(\d{4})?$"), nullable=True,
                             required=False),
            "utility_side_material": material,
            "customer_side_material": material,
            "year_built": year,
            "install_year": year,
            "diameter_in": pa.Column(
                float, pa.Check.in_range(0, 48, include_min=False), nullable=True, required=False
            ),
            "verification_method": pa.Column(str, nullable=True, required=False),
            "replacement_date": pa.Column("datetime64[ns]", nullable=True, required=False),
            "notification_date": pa.Column("datetime64[ns]", nullable=True, required=False),
            "snapshot_date": pa.Column("datetime64[ns]", nullable=False, required=False),
        },
        strict=False,
        coerce=True,
    )


def validate_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a canonical inventory frame; raises pandera SchemaErrors listing every failure."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Inventory is missing required columns: {missing}")
    return inventory_schema().validate(df, lazy=True)
