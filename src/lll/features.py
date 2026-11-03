"""Spatial joins, neighbor features, and area aggregates for the master table."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

AREA_LEVELS: tuple[str, ...] = ("block", "block_group", "tract", "ward", "community_area")

# Projected CRS in meters for distance work (UTM 16N covers Chicago and most of Illinois).
METRIC_CRS = "EPSG:26916"
WGS84 = "EPSG:4326"

LEAD_LIKE = ("Lead", "GRR")

# Points this close to a ward or community area edge are assigned to the nearest one.
EDGE_SNAP_M = 100.0


def line_status(utility_side: pd.Series, customer_side: pd.Series) -> pd.Series:
    """Whole-line status from both sides: Lead > GRR > Unknown > Non-Lead.

    A line with any lead portion is Lead; any GRR portion (no lead) is GRR; any unknown
    portion (no lead or GRR) is Unknown; otherwise Non-Lead.
    """
    u, c = utility_side.astype(str), customer_side.astype(str)
    out = pd.Series("Non-Lead", index=u.index, dtype=object)
    for status in ("Unknown", "GRR", "Lead"):
        out[(u == status) | (c == status)] = status
    return out


def to_points(df: pd.DataFrame, lat: str = "latitude", lon: str = "longitude") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs=WGS84)


def assign_geographies(
    lines: gpd.GeoDataFrame,
    wards: gpd.GeoDataFrame | None = None,
    community_areas: gpd.GeoDataFrame | None = None,
    blocks: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Attach block, block group, tract, ward, and community area to every line.

    Columns already present (e.g. from the Assessor parcel join, which carries block
    GEOIDs and ward) are kept; polygons fill only what is missing.
    wards needs a 'ward' column, community_areas 'community_area', blocks 'block' (GEOID20).
    """
    out = lines.to_crs(WGS84).copy()
    for layer, col in ((blocks, "block"), (wards, "ward"), (community_areas, "community_area")):
        if layer is None:
            continue
        joined = gpd.sjoin(out[["geometry"]], layer[[col, "geometry"]].to_crs(WGS84),
                           how="left", predicate="within")
        joined = joined[~joined.index.duplicated(keep="first")][col]
        out[col] = out[col].fillna(joined) if col in out.columns else joined
    if "block" in out.columns:
        block = out["block"].astype("string")
        out["block_group"] = block.str[:12]
        out["tract"] = block.str[:11]
    return out


def neighbor_features(
    lines: pd.DataFrame,
    target: str = "customer_side_material",
    k: int = 10,
    radius_m: float = 100.0,
    block_col: str = "block",
) -> pd.DataFrame:
    """Leave-one-out neighbor features computed from lines with known material.

    Known means Lead, GRR, or Non-Lead on the target side; lead-like is Lead or GRR.
    A row never sees its own label. Returns, indexed like `lines`:
      nbr_lead_share_k10    share lead-like among the k nearest known lines within radius_m
      nbr_known_count_k10   how many known neighbors that share is based on (0..k)
      block_lead_share_loo  share lead-like among other known lines on the same block
      dist_nearest_nonlead_m  distance to the nearest other known Non-Lead line
    """
    pts = to_points(lines).to_crs(METRIC_CRS)
    xy = np.column_stack([pts.geometry.x.to_numpy(), pts.geometry.y.to_numpy()])
    mat = lines[target].astype(str).to_numpy()
    known = np.isin(mat, ("Lead", "GRR", "Non-Lead"))
    lead = np.isin(mat, LEAD_LIKE)
    n = len(lines)

    share = np.full(n, np.nan)
    count = np.zeros(n, dtype=int)
    k_idx = np.flatnonzero(known)
    if k_idx.size:
        tree = cKDTree(xy[k_idx])
        kq = min(k + 1, k_idx.size)
        dist, nb = tree.query(xy, k=kq, distance_upper_bound=radius_m)
        dist, nb = dist.reshape(n, kq), nb.reshape(n, kq)
        valid = np.isfinite(dist)
        nb_global = np.where(valid, k_idx[np.minimum(nb, k_idx.size - 1)], -1)
        valid &= nb_global != np.arange(n)[:, None]
        # keep at most k after dropping self
        valid &= np.cumsum(valid, axis=1) <= k
        nb_lead = np.where(valid, lead[np.maximum(nb_global, 0)], False)
        count = valid.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            share = np.where(count > 0, nb_lead.sum(axis=1) / count, np.nan)

    dist_nl = np.full(n, np.nan)
    nl_idx = np.flatnonzero(mat == "Non-Lead")
    if nl_idx.size:
        tree = cKDTree(xy[nl_idx])
        kq = min(2, nl_idx.size)
        d, nb = tree.query(xy, k=kq)
        d, nb = d.reshape(n, kq), nb.reshape(n, kq)
        is_self = nl_idx[nb[:, 0]] == np.arange(n)
        dist_nl = np.where(is_self, d[:, 1] if kq > 1 else np.nan, d[:, 0])
        dist_nl[~np.isfinite(dist_nl)] = np.nan

    block_share = np.full(n, np.nan)
    if block_col in lines.columns:
        b = lines[block_col].astype("string").fillna("__none__").to_numpy()
        frame = pd.DataFrame({"b": b, "k": known.astype(int), "l": lead.astype(int)})
        tot = frame.groupby("b")[["k", "l"]].transform("sum").to_numpy()
        k_loo = tot[:, 0] - frame["k"].to_numpy()
        l_loo = tot[:, 1] - frame["l"].to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            block_share = np.where(k_loo > 0, l_loo / k_loo, np.nan)
        block_share[b == "__none__"] = np.nan

    return pd.DataFrame(
        {
            "nbr_lead_share_k10": share,
            "nbr_known_count_k10": count,
            "block_lead_share_loo": block_share,
            "dist_nearest_nonlead_m": dist_nl,
        },
        index=lines.index,
    )


def build_master_table(
    geocoded: pd.DataFrame,
    parcels: pd.DataFrame,
    characteristics: pd.DataFrame,
    wards: gpd.GeoDataFrame,
    community_areas: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """One row per service line with status, geography, building, and neighbor features.

    geocoded is the output of geocode.geocode_inventory. Blocks come from the matched
    parcel, the neighboring parcel for nearest-number matches, or the Census response;
    ward and community area come from a spatial join so every match type uses the same
    boundaries. Building attributes (class, year built, units) attach only to exact
    parcel matches. Unlocated lines stay in the table with empty geography.
    """
    df = geocoded.copy()
    parcel_attrs = (
        parcels.drop_duplicates("pin")
        .set_index("pin")[["building_class", "census_block_geoid"]]
    )
    geo_pin = df["matched_pin"].fillna(df["nearby_pin"])
    df["block"] = parcel_attrs["census_block_geoid"].reindex(geo_pin).to_numpy()
    df["block"] = df["block"].fillna(df["census_block_geoid"]).astype("string")
    df["building_class"] = (
        parcel_attrs["building_class"].reindex(df["matched_pin"]).to_numpy()
    )
    pin10 = df["matched_pin"].astype("string").str[:10]
    chars = characteristics.reindex(pin10)
    df["year_built"] = df["year_built"].fillna(pd.Series(chars["year_built"].to_numpy(),
                                                         index=df.index, dtype="Int64"))
    df["unit_count"] = pd.Series(chars["unit_count"].to_numpy(), index=df.index, dtype="Int64")

    df["line_status_derived"] = line_status(df["utility_side_material"],
                                            df["customer_side_material"])
    if "reported_line_class" in df.columns:
        df["line_status"] = df["reported_line_class"].fillna(df["line_status_derived"])
    else:
        df["line_status"] = df["line_status_derived"]
    replaced = df["replacement_date"].notna()
    if "prev_lead_replaced" in df.columns:
        replaced |= df["prev_lead_replaced"].fillna(False).astype(bool)
    df["replaced"] = replaced

    located = df["latitude"].notna() & df["longitude"].notna()
    pts = to_points(df.loc[located])
    geo = assign_geographies(pts, wards=wards, community_areas=community_areas)
    for col, layer in (("ward", wards), ("community_area", community_areas)):
        vals = pd.Series(geo[col].to_numpy(), index=geo.index)
        miss = vals.isna()
        if miss.any():
            near = gpd.sjoin_nearest(
                geo.loc[miss, ["geometry"]].to_crs(METRIC_CRS),
                layer[[col, "geometry"]].to_crs(METRIC_CRS),
                how="left", max_distance=EDGE_SNAP_M,
            )
            near = near[~near.index.duplicated(keep="first")][col]
            vals = vals.fillna(near)
        df[col] = vals.reindex(df.index).astype("string")
    # Chicago water reaches some addresses outside city limits; they keep block and
    # tract but have no ward or community area.
    df["in_city"] = df["ward"].notna().astype("boolean").mask(~located)
    block = df["block"]
    df["block_group"] = block.str[:12]
    df["tract"] = block.str[:11]

    nbr = neighbor_features(df.loc[located], target="line_status")
    df = df.join(nbr)
    unknown = df["line_status"].eq("Unknown")
    df["tract_unknown_rate"] = unknown.groupby(df["tract"]).transform("mean")
    df.loc[df["tract"].isna(), "tract_unknown_rate"] = np.nan
    return df


def area_aggregates(master: pd.DataFrame, level: str) -> pd.DataFrame:
    """Counts and shares by line status for one area level, small cells suppressed."""
    from lll.equity import aggregate

    if level not in AREA_LEVELS:
        raise ValueError(f"level must be one of {AREA_LEVELS}")
    return aggregate(master, level)
