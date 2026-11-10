"""Read inventories from CSV/XLSX and map them to the canonical schema."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from lll.schema import CANONICAL_COLUMNS, normalize_material, validate_inventory

# Header aliases per canonical column, compared after lowercasing and stripping non-alphanumerics.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "line_id": ("lineid", "serviceid", "servicelineid", "id", "objectid", "accountnumber",
                "account", "locationid", "premiseid"),
    "address": ("address", "serviceaddress", "fulladdress", "streetaddress", "location",
                "propertyaddress", "siteaddress", "premiseaddress"),
    "pin": ("pin", "pin14", "parcel", "parcelid", "parcelnumber", "pinnumber"),
    "utility_side_material": ("utilitysidematerial", "utilityside", "publicsidematerial",
                              "publicside", "systemowned", "systemownedmaterial",
                              "utilityownedmaterial", "publicmaterial", "mainsidematerial"),
    "customer_side_material": ("customersidematerial", "customerside", "privatesidematerial",
                               "privateside", "customerowned", "customerownedmaterial",
                               "privatematerial", "propertysidematerial"),
    "year_built": ("yearbuilt", "yrbuilt", "buildingyear", "builtyear", "constructionyear"),
    "install_year": ("installyear", "installationyear", "yearinstalled", "installdate",
                     "installationdate"),
    "diameter_in": ("diameter", "diameterin", "diameterinches", "size", "pipesize",
                    "servicesize", "linesize"),
    "verification_method": ("verificationmethod", "verification", "basisofclassification",
                            "methodofverification", "classificationbasis", "source"),
    "replacement_date": ("replacementdate", "datereplaced", "replaceddate"),
    "notification_date": ("notificationdate", "datenotified", "noticedate"),
    "snapshot_date": ("snapshotdate", "asofdate", "inventorydate", "reportdate"),
}

IL_EPA_COUNT_COLUMNS: tuple[str, ...] = (
    "TotalServiceConnections",
    "WholesaleConnections",
    "RetailConnections",
    "ServicesLead",
    "ServicesUnknownMaterial",
    "ServicesCopperLeadSolder",
    "ServicesGalvanized",
    "ServicesUnknownNotLead",
    "ServicesCopperNonLeadSolder",
    "ServicesCastDuctileIronTransite",
    "ServicesPlastic",
)


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def read_bytes(data: bytes, filename: str) -> pd.DataFrame:
    """Read an uploaded CSV or XLSX from memory. Does not write to disk."""
    from io import BytesIO

    name = filename.lower()
    buf = BytesIO(data)
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        return pd.read_excel(buf, dtype=str)
    if name.endswith(".csv"):
        return pd.read_csv(buf, dtype=str, encoding="utf-8-sig", low_memory=False)
    raise ValueError("Upload a CSV or Excel file.")


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a CSV or XLSX file into a DataFrame of strings."""
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path, dtype=str)
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig", low_memory=False)


def suggest_mapping(columns: list[str]) -> dict[str, str]:
    """Guess a raw-column -> canonical-column mapping from header names.

    Exact alias matches win; otherwise a raw header containing an alias is used. Each
    canonical column is assigned at most once.
    """
    keys = {c: _key(c) for c in columns}
    mapping: dict[str, str] = {}
    taken: set[str] = set()
    for exact in (True, False):
        for canon, aliases in SYNONYMS.items():
            if canon in taken:
                continue
            for raw, k in keys.items():
                if raw in mapping:
                    continue
                hit = k in aliases if exact else any(len(a) > 3 and a in k for a in aliases)
                if hit:
                    mapping[raw] = canon
                    taken.add(canon)
                    break
    return mapping


_FRACTION = re.compile(r"^(?:(\d+)[\s-]+)?(\d+)/(\d+)$")


def parse_diameter(value: object) -> float:
    """Inches from strings like '1', '0.75', '3/4', '1-1/2', '1"', '1 inch'."""
    if value is None or (isinstance(value, float) and np.isnan(value)) or value is pd.NA:
        return np.nan
    s = re.sub(r'(inches|inch|in\.?|")', "", str(value).lower()).strip()
    if not s:
        return np.nan
    m = _FRACTION.match(s)
    if m:
        whole = float(m.group(1) or 0)
        return whole + float(m.group(2)) / float(m.group(3))
    try:
        return float(s)
    except ValueError:
        return np.nan


def _year(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.extract(r"(\d{4})", expand=False)
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def map_columns(
    df: pd.DataFrame,
    mapping: dict[str, str],
    snapshot_date: str | None = None,
    extra: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Rename raw columns to canonical names and normalize values.

    Unmapped canonical columns are added as nulls. A missing line_id is generated from
    the row number. snapshot_date fills the column when the source has none. `extra`
    maps raw columns to non-canonical names that are carried through unchanged.
    """
    bad = set(mapping.values()) - set(CANONICAL_COLUMNS)
    if bad:
        raise ValueError(f"Mapping targets non-canonical columns: {sorted(bad)}")
    out = df[list(mapping)].rename(columns=mapping).copy()
    for raw, name in (extra or {}).items():
        out[name] = df[raw].to_numpy()
    for col in CANONICAL_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    if out["line_id"].isna().all():
        out["line_id"] = [f"L{i:07d}" for i in range(len(out))]
    out["line_id"] = out["line_id"].astype(str)
    for side in ("utility_side_material", "customer_side_material"):
        out[f"{side}_raw"] = out[side]
        out[side] = out[side].map(normalize_material).astype(str)
    for col in ("year_built", "install_year"):
        out[col] = _year(out[col])
    out["diameter_in"] = out["diameter_in"].map(parse_diameter).astype(float)
    for col in ("replacement_date", "notification_date", "snapshot_date"):
        out[col] = pd.to_datetime(out[col], errors="coerce").astype("datetime64[ns]")
    if snapshot_date is not None:
        out["snapshot_date"] = out["snapshot_date"].fillna(pd.Timestamp(snapshot_date))
    out["pin"] = out["pin"].astype("string").str.replace(r"\D", "", regex=True)
    out.loc[out["pin"].str.len().isin([0]), "pin"] = pd.NA
    for col in ("address", "verification_method"):
        out[col] = out[col].astype("string").str.strip()
    return out


def load_inventory(
    path: str | Path,
    mapping: dict[str, str] | None = None,
    snapshot_date: str | None = None,
) -> pd.DataFrame:
    """Read, map, normalize, and validate an inventory in one call."""
    raw = read_table(path)
    mapping = mapping or suggest_mapping(list(raw.columns))
    return validate_inventory(map_columns(raw, mapping, snapshot_date=snapshot_date))


# Column order of the Illinois EPA lead service line inventory template (18 columns).
IEPA_TEMPLATE_COLUMNS: tuple[str, ...] = (
    "service_address",
    "lcr_site_id",
    "high_risk",
    "newly_identified",
    "pws_install_year",
    "customer_install_year",
    "source",
    "gooseneck",
    "pws_material",
    "customer_material",
    "overall_class",
    "galv_downstream_of_lead",
    "notified_date",
    "prev_lead_replaced",
    "replaced_date",
    "replacement_material",
    "refused_access",
    "waiver_date",
)

_IEPA_MAPPING = {
    "service_address": "address",
    "pws_material": "utility_side_material",
    "customer_material": "customer_side_material",
    "customer_install_year": "install_year",
    "source": "verification_method",
    "replaced_date": "replacement_date",
    "notified_date": "notification_date",
}
_IEPA_EXTRA = {
    "pws_install_year": "utility_install_year",
    "gooseneck": "gooseneck_material",
    "overall_class": "reported_line_class",
    "prev_lead_replaced": "prev_lead_replaced",
    "high_risk": "high_risk",
    "newly_identified": "newly_identified",
}


def _label_value(rows: list[tuple], label: str) -> object:
    """Value in the first non-empty cell after a header cell containing `label`."""
    for row in rows:
        for i, cell in enumerate(row):
            if isinstance(cell, str) and label.lower() in cell.lower():
                for v in row[i + 1 :]:
                    if v not in (None, ""):
                        return v
    return None


def read_iepa_template(path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Read an inventory submitted in the Illinois EPA template workbook.

    Skips the title block, totals, descriptive header, and example rows, then maps the
    18 template columns to the canonical schema. Returns (inventory, meta) where meta
    holds system_id, system_name, snapshot_date, and the header totals.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    head: list[tuple] = []
    for row in rows:
        head.append(row)
        first = row[0] if row else None
        if isinstance(first, str) and first.strip().lower().startswith("service address"):
            break
    else:
        raise ValueError(f"{path}: no 'Service Address' header row found")

    data = []
    for row in rows:
        first = row[0] if row else None
        if first is None or (isinstance(first, str) and not first.strip()):
            continue
        if isinstance(first, str) and first.strip().lower() == "fulladdress":
            continue
        data.append(tuple(row[: len(IEPA_TEMPLATE_COLUMNS)]))
    wb.close()

    raw = pd.DataFrame(data, columns=list(IEPA_TEMPLATE_COLUMNS)).astype("string")
    meta = {
        "system_id": _label_value(head, "System ID"),
        "system_name": _label_value(head, "Water System Name"),
        "snapshot_date": pd.to_datetime(_label_value(head, "Inventory Date"), errors="coerce"),
        "header_totals": {
            k: _label_value(head, label)
            for k, label in (
                ("total", "Total Service lines"),
                ("lead", "Total Lead"),
                ("nonlead", "Total  Non-Lead"),
                ("grr", "Galvanized Requiring"),
                ("unknown", "Total Unknown"),
            )
        },
    }
    prefix = str(meta["system_id"] or "LINE")
    raw["line_id"] = [f"{prefix}-{i:06d}" for i in range(1, len(raw) + 1)]
    mapping = {**_IEPA_MAPPING, "line_id": "line_id"}
    snap = meta["snapshot_date"]
    out = map_columns(
        raw, mapping, snapshot_date=None if pd.isna(snap) else str(snap.date()), extra=_IEPA_EXTRA
    )
    out["utility_install_year"] = _year(out["utility_install_year"])
    for col in ("gooseneck_material", "reported_line_class"):
        out[col] = out[col].map(normalize_material).astype(str)
    for col in ("prev_lead_replaced", "high_risk", "newly_identified"):
        out[col] = out[col].str.strip().str.upper().eq("Y").fillna(False).astype(bool)
    return out, meta


def read_il_epa_summary(path: str | Path) -> pd.DataFrame:
    """Read the Illinois EPA system-level inventory summary (one row per system-year).

    Adds lead_share and unknown_share (of TotalServiceConnections; NaN when total is 0).
    """
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"FacilityId": str})
    for col in IL_EPA_COUNT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["ReportingYear"] = pd.to_numeric(df["ReportingYear"], errors="coerce").astype("Int64")
    df["ReportedDate"] = pd.to_datetime(df["ReportedDate"], format="%m/%d/%Y %I:%M:%S %p",
                                        errors="coerce")
    total = df["TotalServiceConnections"].astype(float).replace(0, np.nan)
    df["lead_share"] = df["ServicesLead"].astype(float) / total
    df["unknown_share"] = df["ServicesUnknownMaterial"].astype(float) / total
    return df
