"""Canonical service line inventory schema.

Every inventory (Chicago's export or a utility upload) is mapped to these columns,
which follow the Illinois EPA service line inventory template. Material values are
normalized to four categories: Lead, GRR (galvanized requiring replacement),
Non-Lead, and Unknown. The full vocabulary mapping is recorded in
docs/data_dictionary.md.
"""

from __future__ import annotations

import pandas as pd

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


def normalize_material(value: object) -> str:
    """Map a raw material string (any vocabulary) to one of MATERIALS.

    TODO: implement vocabulary mapping (Gate 1).
    """
    raise NotImplementedError


def inventory_schema():
    """Return the pandera DataFrameSchema for the canonical inventory.

    TODO: no nulls in key columns, materials in MATERIALS, plausible year built (Gate 1).
    """
    raise NotImplementedError


def validate_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a canonical inventory frame and return it unchanged on success.

    TODO: implement with inventory_schema() (Gate 1).
    """
    raise NotImplementedError
