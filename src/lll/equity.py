"""Tract and ward disparity report.

Aggregates the master table, joins ACS income and race/ethnicity, compares income
quartiles and majority race/ethnicity groups, and computes disparity ratios.
Every cell with fewer than SUPPRESSION_MIN lines is suppressed.
"""

from __future__ import annotations

import pandas as pd

SUPPRESSION_MIN = 5


def suppress_small_cells(df: pd.DataFrame, count_col: str = "total_lines") -> pd.DataFrame:
    """Blank every count and share in rows with fewer than SUPPRESSION_MIN lines.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError


def aggregate(master: pd.DataFrame, level: str) -> pd.DataFrame:
    """Counts and shares by material for tracts or wards.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError


def fetch_acs(year: int = 2023) -> pd.DataFrame:
    """Pull ACS 5-year B19013 and B03002 for Cook County tracts.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError


def disparity_report(master: pd.DataFrame, acs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Tract and ward tables, income-quartile and majority-race comparisons, disparity ratios.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError


def choropleth(table: pd.DataFrame, geometry, value_col: str, caption: str):
    """Folium choropleth with caption and source line.

    TODO: implement (Gate 5).
    """
    raise NotImplementedError
