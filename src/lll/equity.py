"""Tract and ward disparity report.

Aggregates the master table, joins ACS income and race/ethnicity, compares income
quartiles and majority race/ethnicity groups, and computes disparity ratios.
Every area with fewer than SUPPRESSION_MIN lines is suppressed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SUPPRESSION_MIN = 5

STATUSES: tuple[str, ...] = ("Lead", "GRR", "Unknown", "Non-Lead")
_SLUG = {"Lead": "lead", "GRR": "grr", "Unknown": "unknown", "Non-Lead": "nonlead"}


def suppress_small_cells(df: pd.DataFrame, count_col: str = "total_lines") -> pd.DataFrame:
    """Blank every count and share in rows with fewer than SUPPRESSION_MIN lines.

    Count columns start with 'n_' or equal count_col; share columns start with 'share_'
    or 'pred_'. Adds a boolean 'suppressed' column. Total line counts are blanked too,
    so a suppressed area reveals only that it has fewer than five lines.
    """
    out = df.copy()
    small = out[count_col].fillna(0) < SUPPRESSION_MIN
    cols = [
        c for c in out.columns
        if c == count_col or c.startswith(("n_", "share_", "pred_"))
    ]
    for c in cols:
        if pd.api.types.is_integer_dtype(out[c]):
            out[c] = out[c].astype("Int64")
        out.loc[small, c] = pd.NA if str(out[c].dtype) == "Int64" else np.nan
    out["suppressed"] = small.to_numpy()
    return out


def aggregate(master: pd.DataFrame, level: str) -> pd.DataFrame:
    """Counts and shares by line status for one area column, suppressed.

    master needs `level` and `line_status`; optional `replacement_date` and
    `pred_lead_prob` (model probability for Unknown lines).
    """
    df = master.dropna(subset=[level])
    status = df["line_status"].astype(str)
    g = df.groupby(level, observed=True)
    out = pd.DataFrame({"total_lines": g.size()})
    for s in STATUSES:
        out[f"n_{_SLUG[s]}"] = (status == s).groupby(df[level], observed=True).sum()
    if "replacement_date" in df.columns:
        out["n_replaced"] = df["replacement_date"].notna().groupby(df[level], observed=True).sum()
    for s in STATUSES:
        out[f"share_{_SLUG[s]}"] = out[f"n_{_SLUG[s]}"] / out["total_lines"]
    if "n_replaced" in out:
        out["share_replaced"] = out["n_replaced"] / out["total_lines"]
    if "pred_lead_prob" in df.columns:
        unk = df[status == "Unknown"]
        out["pred_lead_share_unknown"] = unk.groupby(level, observed=True)["pred_lead_prob"].mean()
    out.index = out.index.astype(str)
    out.index.name = level
    return suppress_small_cells(out.reset_index())


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
