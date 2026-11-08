"""JSON-safe values from pandas cells. Never logs the input."""

from __future__ import annotations

import math

import pandas as pd

from lll.predict import TREAT_AS_LEAD_MESSAGE

LINE_FIELDS = (
    "line_id", "address", "utility_side_material", "customer_side_material", "line_status",
    "verification_method", "replaced", "replacement_date", "ward", "tract", "block",
    "community_area",
)


def cell(v):
    if v is None or v is pd.NA:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, pd.Timestamp):
        return str(v.date())
    if isinstance(v, (bool, str)):
        return v
    if isinstance(v, (int,)):
        return int(v)
    if isinstance(v, float):
        return None if math.isnan(v) else float(v)
    if hasattr(v, "item") and getattr(v, "size", 1) == 1:
        return cell(v.item())
    return str(v)


def line_record(row: pd.Series) -> dict:
    out = {k: cell(row[k]) if k in row.index else None for k in LINE_FIELDS}
    if out.get("replaced") is not None:
        out["replaced"] = bool(out["replaced"])
    status = out.get("line_status") or out.get("customer_side_material")
    if status == "Unknown":
        out["message"] = TREAT_AS_LEAD_MESSAGE
    return out
