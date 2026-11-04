"""Tract and ward disparity report.

Aggregates the master table, joins ACS income and race/ethnicity, compares income
quartiles and majority race/ethnicity groups, and computes disparity ratios.
Every area or group with fewer than SUPPRESSION_MIN lines is suppressed.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

SUPPRESSION_MIN = 5
NAN_FILL = "#cccccc"

STATUSES: tuple[str, ...] = ("Lead", "GRR", "Unknown", "Non-Lead")
_SLUG = {"Lead": "lead", "GRR": "grr", "Unknown": "unknown", "Non-Lead": "nonlead"}
# Lines a resident should act on: known lead, galvanized requiring replacement, or not yet known.
NEEDS_ACTION = ("Lead", "GRR", "Unknown")

ACS_YEAR = 2024
ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_VARIABLES = {
    "B19013_001E": "median_income",
    "B03002_001E": "pop_total",
    "B03002_003E": "pop_white",
    "B03002_004E": "pop_black",
    "B03002_006E": "pop_asian",
    "B03002_012E": "pop_latino",
    "B09001_003E": "kids_under3",
    "B09001_004E": "kids_3_4",
    "B09001_005E": "kids_5",
    "B25034_001E": "housing_units",
    "B25034_010E": "units_1940s",
    "B25034_011E": "units_pre1940",
}
ACS_COUNTS = ("pop_total", "pop_white", "pop_black", "pop_asian", "pop_latino",
              "kids_under6", "housing_units", "units_pre1950")
RACE_GROUPS = {"pop_black": "Black", "pop_latino": "Latino", "pop_white": "White",
               "pop_asian": "Asian"}
NO_MAJORITY = "No majority"
INCOME_QUARTILES = ("Q1 lowest income", "Q2", "Q3", "Q4 highest income")
RATE_METRICS = ("share_lead", "share_grr", "share_unknown", "share_needs_action",
                "share_replaced")


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


def _status_counts(df: pd.DataFrame, by: str) -> pd.DataFrame:
    status = df["line_status"].astype(str)
    key = df[by]
    out = pd.DataFrame({"total_lines": df.groupby(by, observed=True).size()})
    for s in STATUSES:
        out[f"n_{_SLUG[s]}"] = (status == s).groupby(key, observed=True).sum()
    out["n_needs_action"] = status.isin(NEEDS_ACTION).groupby(key, observed=True).sum()
    replaced = None
    if "replaced" in df.columns:
        replaced = df["replaced"].fillna(False).astype(bool)
    elif "replacement_date" in df.columns:
        replaced = df["replacement_date"].notna()
    if replaced is not None:
        out["n_replaced"] = replaced.groupby(key, observed=True).sum()
    for s in STATUSES:
        out[f"share_{_SLUG[s]}"] = out[f"n_{_SLUG[s]}"] / out["total_lines"]
    out["share_needs_action"] = out["n_needs_action"] / out["total_lines"]
    if "n_replaced" in out:
        out["share_replaced"] = out["n_replaced"] / out["total_lines"]
    if "pred_lead_prob" in df.columns:
        unk = df[status == "Unknown"]
        out["pred_lead_share_unknown"] = unk.groupby(by, observed=True)["pred_lead_prob"].mean()
    return out


def aggregate(master: pd.DataFrame, level: str) -> pd.DataFrame:
    """Counts and shares by line status for one area column, suppressed.

    master needs `level` and `line_status`; optional `replaced` (or `replacement_date`)
    and `pred_lead_prob` (model probability for Unknown lines).
    """
    df = master.dropna(subset=[level])
    out = _status_counts(df, level)
    out.index = out.index.astype(str)
    out.index.name = level
    return suppress_small_cells(out.reset_index())


def fetch_acs(year: int = ACS_YEAR, cache: str | Path | None = None) -> pd.DataFrame:
    """ACS 5-year tract estimates for Cook County, with derived shares and majority group.

    Reads CENSUS_API_KEY from the environment. The key is never logged: request errors
    are re-raised without the URL. A cached parquet is used when it exists.
    """
    if cache is not None and Path(cache).exists():
        return pd.read_parquet(cache)
    params = {"get": ",".join(ACS_VARIABLES), "for": "tract:*", "in": "state:17 county:031"}
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        params["key"] = key
    try:
        resp = requests.get(ACS_URL.format(year=year), params=params, timeout=120)
        resp.raise_for_status()
        rows = resp.json()
    except (requests.RequestException, ValueError) as err:
        hint = "" if key else "; CENSUS_API_KEY is not set (conda env vars load on activation)"
        raise RuntimeError(f"ACS {year} request failed ({type(err).__name__}){hint}") from None
    raw = pd.DataFrame(rows[1:], columns=rows[0])
    out = pd.DataFrame({"tract": raw["state"] + raw["county"] + raw["tract"]})
    for var, name in ACS_VARIABLES.items():
        v = pd.to_numeric(raw[var], errors="coerce")
        out[name] = v.where(v >= 0)  # the API codes "not available" as large negatives
    out = _derive_acs(out)
    out["acs_year"] = year
    if cache is not None:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(cache)
    return out


def _derive_acs(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "kids_under6" not in out:
        out["kids_under6"] = out[["kids_under3", "kids_3_4", "kids_5"]].sum(axis=1, min_count=1)
    if "units_pre1950" not in out:
        out["units_pre1950"] = out[["units_1940s", "units_pre1940"]].sum(axis=1, min_count=1)
    pop = out["pop_total"].where(out["pop_total"] > 0)
    for col, name in RACE_GROUPS.items():
        out[f"pct_{name.lower()}"] = out[col] / pop
    out["pct_housing_pre1950"] = out["units_pre1950"] / out["housing_units"].where(
        out["housing_units"] > 0)
    out["majority_group"] = majority_group(out)
    return out


def majority_group(df: pd.DataFrame) -> pd.Series:
    """Group with more than half the population, else 'No majority'; empty if no people."""
    pcts = pd.DataFrame({name: df[f"pct_{name.lower()}"] for name in RACE_GROUPS.values()},
                        dtype=float)
    share = pcts.max(axis=1)
    out = pd.Series(None, index=df.index, dtype=object)
    has = share.notna()
    if has.any():
        top = pcts[has].idxmax(axis=1)
        out[has] = np.where(share[has] > 0.5, top, NO_MAJORITY)
    return out


def ward_acs(acs: pd.DataFrame, tracts, wards) -> pd.DataFrame:
    """Apportion tract ACS counts to wards by area overlap.

    Counts are split in proportion to the share of each tract's area inside the ward.
    Ward income is the population-weighted mean of tract medians, an approximation
    (medians cannot be added); docs/methodology.md says so.
    """
    import geopandas as gpd

    from lll.features import METRIC_CRS

    t = tracts.to_crs(METRIC_CRS)[["tract", "geometry"]].copy()
    t["tract_area"] = t.area
    w = wards.to_crs(METRIC_CRS)[["ward", "geometry"]]
    ov = gpd.overlay(t, w, how="intersection", keep_geom_type=True)
    ov["weight"] = ov.area / ov["tract_area"]
    ov = ov.merge(acs, on="tract", how="inner")
    counts = list(ACS_COUNTS)
    weighted = ov[counts].multiply(ov["weight"], axis=0)
    weighted["ward"] = ov["ward"].astype(str)
    out = weighted.groupby("ward")[counts].sum()
    pop_w = ov["pop_total"] * ov["weight"]
    has_income = ov["median_income"].notna()
    inc = (ov["median_income"] * pop_w)[has_income].groupby(ov.loc[has_income, "ward"]).sum()
    den = pop_w[has_income].groupby(ov.loc[has_income, "ward"]).sum()
    out["median_income"] = (inc / den.where(den > 0)).reindex(out.index)
    out = _derive_acs(out.reset_index())
    out[counts] = out[counts].round().astype("Int64")
    return out


def _quartiles(values: pd.Series) -> pd.Series:
    """Quartile labels for tract incomes; tied incomes may fall on either side of a cut."""
    values = values.dropna()
    if len(values) < len(INCOME_QUARTILES):
        return pd.Series(pd.Categorical([None] * len(values), categories=INCOME_QUARTILES),
                         index=values.index)
    return pd.qcut(values.rank(method="first"), 4, labels=list(INCOME_QUARTILES))


def group_rates(lines: pd.DataFrame, by: str) -> pd.DataFrame:
    """Pooled counts and shares for a grouping of lines (not an average of area shares)."""
    df = lines.dropna(subset=[by])
    out = _status_counts(df, by)
    if "tract" in df.columns:
        out["areas"] = df.groupby(by, observed=True)["tract"].nunique()
    out.index = out.index.astype(str)
    out.index.name = by
    return suppress_small_cells(out.reset_index())


def _ratios(table: pd.DataFrame, by: str, groups: list[str], reference: str,
            comparison: str) -> pd.DataFrame:
    t = table.set_index(by)
    rows = []
    if reference not in t.index:
        return pd.DataFrame()
    for g in groups:
        if g not in t.index or g == reference:
            continue
        for metric in RATE_METRICS:
            if metric not in t.columns:
                continue
            a, b = t.loc[g, metric], t.loc[reference, metric]
            ratio = a / b if pd.notna(a) and pd.notna(b) and b > 0 else np.nan
            rows.append({"comparison": comparison, "group": g, "reference": reference,
                         "metric": metric, "group_rate": a, "reference_rate": b,
                         "ratio": ratio})
    return pd.DataFrame(rows)


def disparity_report(
    master: pd.DataFrame,
    acs: pd.DataFrame,
    ward_acs_table: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Tract and ward tables, income-quartile and majority-group comparisons, ratios.

    Income quartiles are cut over tracts with at least SUPPRESSION_MIN lines and a
    published median income; majority groups use every tract with at least
    SUPPRESSION_MIN lines. Each line takes its tract's quartile and majority group.
    Disparity ratio = group rate / reference rate (Q4 highest income; majority White).
    """
    acs = acs.copy()
    acs["tract"] = acs["tract"].astype(str)
    tract = aggregate(master, "tract").merge(acs, on="tract", how="left")
    ward = aggregate(master, "ward")
    if ward_acs_table is not None:
        ward = ward.merge(ward_acs_table, on="ward", how="left")
    ward["rank_needs_action"] = (
        ward["share_needs_action"].rank(ascending=False, method="min").astype("Int64")
    )
    ward = ward.sort_values("ward", key=lambda s: pd.to_numeric(s, errors="coerce"))

    published = tract[~tract["suppressed"] & tract["median_income"].notna()]
    quart = _quartiles(published.set_index("tract")["median_income"])
    tract["income_quartile"] = tract["tract"].map(quart).astype(object)

    lines = master.dropna(subset=["tract"]).copy()
    lines["tract"] = lines["tract"].astype(str)
    lines["income_quartile"] = lines["tract"].map(quart).astype(object)
    lines["majority_group"] = lines["tract"].map(acs.set_index("tract")["majority_group"])
    lines.loc[~lines["tract"].isin(tract.loc[~tract["suppressed"], "tract"]),
              "majority_group"] = None

    by_income = group_rates(lines, "income_quartile")
    by_income = by_income.set_index("income_quartile").reindex(INCOME_QUARTILES).reset_index()
    by_income = by_income.merge(
        published.assign(q=published["tract"].map(quart).astype(object))
        .groupby("q")["median_income"].agg(["min", "max"])
        .rename(columns={"min": "income_min", "max": "income_max"}),
        left_on="income_quartile", right_index=True, how="left",
    )
    by_race = group_rates(lines, "majority_group").sort_values("total_lines", ascending=False)

    ratios = pd.concat(
        [
            _ratios(by_income, "income_quartile", list(INCOME_QUARTILES), INCOME_QUARTILES[-1],
                    "income quartile"),
            _ratios(by_race, "majority_group", list(RACE_GROUPS.values()) + [NO_MAJORITY],
                    "White", "majority group"),
        ],
        ignore_index=True,
    )
    return {"tract": tract, "ward": ward, "income_quartiles": by_income,
            "majority_group": by_race, "disparity_ratios": ratios}


def export_csvs(report: dict[str, pd.DataFrame], out_dir: str | Path) -> list[Path]:
    """Write every report table to CSV (all tables are already suppressed)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, table in report.items():
        p = out_dir / f"{name}.csv"
        table.to_csv(p, index=False)
        paths.append(p)
    return paths


def choropleth(
    table: pd.DataFrame,
    geometry,
    value_col: str,
    caption: str,
    key: str,
    source: str,
    tooltip_cols: dict[str, str] | None = None,
):
    """Folium choropleth of a share column; suppressed or missing areas are grey.

    geometry is a GeoDataFrame with `key`. tooltip_cols maps column -> label; share
    columns are shown as percentages.
    """
    import folium

    gdf = geometry[[key, "geometry"]].merge(table, on=key, how="left").to_crs("EPSG:4326")
    tooltip_cols = tooltip_cols or {value_col: caption}
    for col in tooltip_cols:
        vals = gdf[col]
        if col.startswith(("share_", "pct_")):
            text = vals.map(lambda v: f"{v:.0%}" if pd.notna(v) else "suppressed")
        elif col == "median_income":
            text = vals.map(lambda v: f"${v:,.0f}" if pd.notna(v) else "n/a")
        else:
            text = vals.map(lambda v: f"{v:,}" if isinstance(v, (int, np.integer)) else
                            ("n/a" if pd.isna(v) else str(v)))
        gdf[f"_{col}"] = text.astype(str)
    gdf[f"_{key}"] = gdf[key].astype(str)
    m = folium.Map(location=[41.84, -87.68], zoom_start=10, tiles="OpenStreetMap")
    from branca.utilities import color_brewer

    values = gdf[value_col].astype(float)
    edges = sorted(set(values.dropna().quantile([0, 0.2, 0.4, 0.6, 0.8, 1])))
    if len(edges) < 2:
        edges = [0.0, 1.0]
    colors = color_brewer("YlOrRd", max(len(edges) - 1, 3))[-(len(edges) - 1):]
    band = pd.cut(values, edges, include_lowest=True, labels=False)
    gdf["_fill"] = [NAN_FILL if pd.isna(b) else colors[int(b)] for b in band]

    fields = [f"_{key}"] + [f"_{c}" for c in tooltip_cols]
    aliases = [key.replace("_", " ").title()] + list(tooltip_cols.values())
    folium.GeoJson(
        gdf[fields + ["_fill", "geometry"]].to_json(),
        style_function=lambda f: {"fillColor": f["properties"]["_fill"], "fillOpacity": 0.75,
                                  "color": "#555555", "weight": 0.5},
        tooltip=folium.GeoJsonTooltip(fields=fields, aliases=aliases),
    ).add_to(m)

    p = ".1%" if edges[-1] < 0.1 else ".0%"
    rows = [(c, f"{lo:{p}} to {hi:{p}}")
            for c, lo, hi in zip(colors, edges, edges[1:], strict=False)]
    rows.append((NAN_FILL, f"Fewer than {SUPPRESSION_MIN} lines (not shown)"))
    legend = "".join(
        f'<div><span style="display:inline-block;width:12px;height:12px;background:{c};'
        f'margin-right:6px;vertical-align:middle"></span>{label}</div>' for c, label in rows)
    title = (f'<div style="font-size:14px;font-weight:600">{caption}</div>'
             f'<div style="font-size:12px;margin:4px 0">{legend}</div>'
             f'<div style="font-size:11px">{source}</div>')
    m.get_root().html.add_child(folium.Element(
        f'<div style="position:fixed;top:10px;right:10px;max-width:38%;z-index:9999;'
        f'background:white;padding:6px 10px;border-radius:4px">{title}</div>'))
    return m
