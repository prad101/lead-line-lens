"""Spatial joins, neighbor features, and area aggregates for the master table."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

AREA_LEVELS: tuple[str, ...] = ("block", "block_group", "tract", "ward", "community_area")


def assign_geographies(
    lines: gpd.GeoDataFrame,
    wards: gpd.GeoDataFrame,
    community_areas: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Attach block, block group, tract, ward, and community area to every line.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def neighbor_features(
    lines: gpd.GeoDataFrame, k: int = 10, radius_m: float = 100.0
) -> pd.DataFrame:
    """Leave-one-out neighbor features computed from lines with known material.

    Returns nbr_lead_share_k10, nbr_known_count_k10, block_lead_share_loo,
    dist_nearest_nonlead_m. A row never sees its own label.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def build_master_table(out_path: str | Path | None = None) -> Path:
    """Run ingest -> geocode -> geographies -> features and write the parquet master table.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def area_aggregates(master: pd.DataFrame, level: str) -> pd.DataFrame:
    """Counts and shares by material for one area level, small cells suppressed.

    TODO: implement (Gate 1; suppression shared with equity.py).
    """
    raise NotImplementedError
