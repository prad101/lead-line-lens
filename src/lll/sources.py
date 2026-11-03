"""Loaders for the raw files under data/raw (see docs/data_dictionary.md, Sources)."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pv

from lll import RAW_DIR
from lll.ingest import map_columns
from lll.schema import MIN_YEAR, normalize_material

CHICAGO_INVENTORY = RAW_DIR / "chicago" / "2025_inventory.xlsx"
PARCEL_UNIVERSE = RAW_DIR / "Assessor_-_Parcel_Universe_(Current)_20261029.csv"
PARCEL_ADDRESSES = RAW_DIR / "assessor" / "addresses_chicago_2026.csv"
RES_CHARS = RAW_DIR / "assessor" / "res_chars_chicago_2026.csv"
CONDO_CHARS = RAW_DIR / "assessor" / "condo_chars_chicago_2026.csv"
WARDS = RAW_DIR / "boundaries" / "wards_2023.geojson"
COMMUNITY_AREAS = RAW_DIR / "boundaries" / "community_areas.geojson"
TRACTS = RAW_DIR / "boundaries" / "tracts_2020.geojson"
IL_EPA_SUMMARY = RAW_DIR / "ServiceLineMaterialInventoryReports.csv"
BURNHAM = RAW_DIR / "small_systems" / "burnham.geojson"
EAST_DUNDEE = RAW_DIR / "small_systems" / "east_dundee.geojson"

_APTS = {"Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6}

# Coded-value domains from the Burnham FeatureServer layer (burnham_layer.json).
_BURNHAM_STATUS = {0: "Unknown", 1: "Lead", 2: "Non-Lead", 3: "GRR"}
_BURNHAM_SOURCE = {
    1: "Existing Records", 2: "Test Results", 3: "Visual Confirmation",
    4: "Notified by Customer", 5: "Age of Home", 6: "Statistical Model",
    7: "Excavation - Utility", 8: "Excavation - Contractor", 9: "Survey Result",
    10: "Indoor Inspection - Utility", 11: "Indoor Inspection - Contractor",
}
_BURNHAM_REPLACE = {1: "Doesn't Need Replacement", 2: "Needs Replacement",
                    3: "Scheduled Replacement", 4: "Replaced"}


def chicago_parcel_universe(path: Path = PARCEL_UNIVERSE) -> pd.DataFrame:
    """Chicago parcels with coordinates and census/ward geography (one row per PIN)."""
    cols = {
        "pin": pa.string(),
        "class": pa.string(),
        "longitude": pa.float64(),
        "latitude": pa.float64(),
        "census_block_geoid": pa.string(),
        "census_tract_geoid": pa.string(),
        "municipality_name": pa.string(),
        "ward_num": pa.string(),
    }
    t = pv.read_csv(
        path,
        convert_options=pv.ConvertOptions(
            include_columns=list(cols), column_types=cols, strings_can_be_null=True
        ),
    )
    df = t.to_pandas()
    df = df[df["municipality_name"].eq("CITY OF CHICAGO")].drop(columns="municipality_name")
    return df.rename(columns={"class": "building_class", "ward_num": "ward"})


def chicago_parcels() -> pd.DataFrame:
    """Parcel universe joined to property addresses: pin, address, coordinates, geography."""
    addr = pd.read_csv(PARCEL_ADDRESSES, dtype=str).rename(
        columns={"prop_address_full": "address", "prop_address_zipcode_1": "zip"}
    )
    uni = chicago_parcel_universe()
    return addr[["pin", "address", "zip"]].merge(uni, on="pin", how="inner")


def building_characteristics() -> pd.DataFrame:
    """Year built and unit count per building (pin10) from residential and condo records.

    Residential: earliest card year per PIN, units from char_apts (single-family = 1).
    Condo: median unit year per building, units = number of unit PINs in the building.
    """
    res = pd.read_csv(RES_CHARS, dtype=str)
    res["year_built"] = pd.to_numeric(res["char_yrblt"], errors="coerce")
    res["units"] = res["char_apts"].map(_APTS).fillna(1)
    res["pin10"] = res["pin"].str[:10]
    r = res.groupby("pin10").agg(year_built=("year_built", "min"), unit_count=("units", "sum"))

    condo = pd.read_csv(CONDO_CHARS, dtype=str)
    condo["year_built"] = pd.to_numeric(condo["char_yrblt"], errors="coerce")
    c = condo.groupby("pin10").agg(year_built=("year_built", "median"),
                                   unit_count=("pin", "nunique"))
    out = pd.concat([r, c[~c.index.isin(r.index)]])
    out["year_built"] = out["year_built"].round().astype("Int64")
    out.loc[out["year_built"] < MIN_YEAR, "year_built"] = pd.NA
    out["unit_count"] = out["unit_count"].astype("Int64")
    return out


def wards() -> gpd.GeoDataFrame:
    g = gpd.read_file(WARDS)[["ward", "geometry"]]
    g["ward"] = g["ward"].astype(str)
    return g


def community_areas() -> gpd.GeoDataFrame:
    g = gpd.read_file(COMMUNITY_AREAS)
    g = g.rename(columns={"area_numbe": "community_area", "community": "community_area_name"})
    g["community_area"] = g["community_area"].astype(str)
    g["community_area_name"] = g["community_area_name"].str.title()
    return g[["community_area", "community_area_name", "geometry"]]


def tracts() -> gpd.GeoDataFrame:
    g = gpd.read_file(TRACTS).rename(columns={"tract_full": "tract"})
    return g[["tract", "geometry"]]


def _download_date(path: Path) -> str:
    """Live ArcGIS layers have no snapshot date; the download date stands in for it."""
    return str(pd.Timestamp(path.stat().st_mtime, unit="s").date())


def _epoch_ms(s: pd.Series) -> pd.Series:
    """ArcGIS date fields arrive as milliseconds since 1970."""
    return pd.to_datetime(pd.to_numeric(s, errors="coerce"), unit="ms").dt.normalize()


def _with_coords(out: pd.DataFrame, g: gpd.GeoDataFrame) -> pd.DataFrame:
    pts = g.geometry.to_crs("EPSG:4326")
    out["latitude"] = pts.y.to_numpy()
    out["longitude"] = pts.x.to_numpy()
    return out


def burnham(path: Path = BURNHAM) -> pd.DataFrame:
    """Burnham (IL0310360) inventory in the canonical schema.

    Side materials come from utilstatus/custstatus (already Lead/GRR/Non-Lead/Unknown).
    Install dates are filled only for new installs, so for lines with replace status
    Replaced the later of the two install dates is the replacement date.
    """
    g = gpd.read_file(path)
    installed = pd.concat([_epoch_ms(g["utilinstalldate"]), _epoch_ms(g["custinstalldate"])],
                          axis=1).max(axis=1)
    raw = pd.DataFrame(
        {
            "line_id": "IL0310360-" + g["OBJECTID"].astype(int).astype(str).str.zfill(6),
            "address": g["address"],
            "pin": g["PIN"],
            "utility": g["utilstatus"].map(_BURNHAM_STATUS),
            "customer": g["custstatus"].map(_BURNHAM_STATUS),
            "basis": g["utilsource"].map(_BURNHAM_SOURCE).fillna("")
            + " / " + g["custsource"].map(_BURNHAM_SOURCE).fillna(""),
            "replace_status": g["replacestatus"].map(_BURNHAM_REPLACE),
        }
    )
    raw["replaced_on"] = installed.where(raw["replace_status"].eq("Replaced"))
    mapping = {"line_id": "line_id", "address": "address", "pin": "pin",
               "utility": "utility_side_material", "customer": "customer_side_material",
               "basis": "verification_method", "replaced_on": "replacement_date"}
    out = map_columns(raw, mapping, snapshot_date=_download_date(path),
                      extra={"replace_status": "replace_status"})
    out["replaced"] = out["replace_status"].eq("Replaced")
    return _with_coords(out, g)


def east_dundee(path: Path = EAST_DUNDEE) -> pd.DataFrame:
    """East Dundee (IL0890250) inventory in the canonical schema.

    The only test inventory with service line diameter (ServSize) and an estimated
    building year. Rows the village flags as Duplicate are kept and marked.
    """
    g = gpd.read_file(path)
    mapping = {
        "StreetAddr": "address",
        "LegacyPIN": "pin",
        "SystMatlClass": "utility_side_material",
        "CustMatlClass": "customer_side_material",
        "EstBldgYear": "year_built",
        "CustInstlYear": "install_year",
        "ServSize": "diameter_in",
        "CustClassBasis": "verification_method",
        "DateLeadServLineReplaced": "replacement_date",
    }
    raw = pd.DataFrame(g.drop(columns="geometry"))
    raw["line_id"] = "IL0890250-" + raw["OBJECTID"].astype(int).astype(str).str.zfill(6)
    raw["DateLeadServLineReplaced"] = _epoch_ms(raw["DateLeadServLineReplaced"])
    out = map_columns(
        raw, {**mapping, "line_id": "line_id"}, snapshot_date=_download_date(path),
        extra={"EntireMatlClass": "reported_line_class", "SystInstlYear": "utility_install_year",
               "GooseneckMatlClass": "gooseneck_material", "PropertyType": "property_type",
               "Duplicate": "duplicate_flag"},
    )
    out["utility_install_year"] = pd.to_numeric(out["utility_install_year"],
                                                errors="coerce").astype("Int64")
    out["gooseneck_material"] = out["gooseneck_material"].map(normalize_material).astype(str)
    out["reported_line_class"] = out["reported_line_class"].map(normalize_material).astype(str)
    out["duplicate_flag"] = out["duplicate_flag"].astype("string").str.lower().eq("yes")
    return _with_coords(out, g)


def year_band(year: pd.Series) -> pd.Series:
    bins = [0, 1900, 1930, 1950, 1970, 1986, 2000, 3000]
    labels = ["<1900", "1900-29", "1930-49", "1950-69", "1970-85", "1986-99", "2000+"]
    return pd.cut(year.astype(float), bins=bins, labels=labels, right=False)


def nan_to_none(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else v
