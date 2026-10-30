"""Read inventories from CSV/XLSX and map them to the canonical schema."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a CSV or XLSX file into a DataFrame of strings.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def suggest_mapping(columns: list[str]) -> dict[str, str]:
    """Guess a raw-column -> canonical-column mapping from header names.

    TODO: implement (Gate 1; reused by the utility edition column mapper).
    """
    raise NotImplementedError


def map_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Rename raw columns to canonical names and normalize material vocabularies.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def load_inventory(path: str | Path, mapping: dict[str, str] | None = None) -> pd.DataFrame:
    """Read, map, normalize, and validate an inventory in one call.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def read_il_epa_summary(path: str | Path) -> pd.DataFrame:
    """Read the Illinois EPA system-level inventory summary (one row per system-year).

    TODO: implement (Gate 0).
    """
    raise NotImplementedError
