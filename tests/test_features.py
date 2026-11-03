import numpy as np
import pandas as pd
import pytest

from lll.features import AREA_LEVELS, build_master_table, line_status, neighbor_features

# ~1.1 m per 1e-5 degree of latitude; these points sit on one Chicago block.
BASE_LAT, BASE_LON = 41.88, -87.63


def _lines(materials, dlat_m, block="B1"):
    return pd.DataFrame(
        {
            "customer_side_material": materials,
            "latitude": [BASE_LAT + d / 111_000 for d in dlat_m],
            "longitude": [BASE_LON] * len(materials),
            "block": [block] * len(materials),
        }
    )


def test_area_levels():
    assert {"block", "tract", "ward", "community_area"} <= set(AREA_LEVELS)


def test_line_status_priority():
    u = pd.Series(["Non-Lead", "Lead", "Unknown", "Non-Lead", "GRR"])
    c = pd.Series(["Non-Lead", "Unknown", "Non-Lead", "GRR", "Unknown"])
    assert list(line_status(u, c)) == ["Non-Lead", "Lead", "Unknown", "GRR", "GRR"]


def test_neighbor_features_never_see_own_label():
    df = _lines(["Lead", "Non-Lead", "Non-Lead", "Unknown"], [0, 10, 20, 30])
    f = neighbor_features(df)
    # Row 0 (Lead) sees only the two Non-Lead lines: share 0, not 1/3.
    assert f.loc[0, "nbr_lead_share_k10"] == 0.0
    assert f.loc[0, "nbr_known_count_k10"] == 2
    # Row 1 (Non-Lead) sees Lead + Non-Lead.
    assert f.loc[1, "nbr_lead_share_k10"] == pytest.approx(0.5)
    # Unknown row sees all three known lines.
    assert f.loc[3, "nbr_known_count_k10"] == 3
    assert f.loc[3, "nbr_lead_share_k10"] == pytest.approx(1 / 3)
    # Block share is leave-one-out too.
    assert f.loc[0, "block_lead_share_loo"] == 0.0
    assert f.loc[1, "block_lead_share_loo"] == pytest.approx(0.5)
    assert f.loc[3, "block_lead_share_loo"] == pytest.approx(1 / 3)


def test_nearest_nonlead_excludes_self():
    df = _lines(["Non-Lead", "Non-Lead", "Lead"], [0, 50, 100])
    f = neighbor_features(df)
    assert f.loc[0, "dist_nearest_nonlead_m"] == pytest.approx(50, abs=1)
    assert f.loc[2, "dist_nearest_nonlead_m"] == pytest.approx(50, abs=1)


def test_radius_and_k_limits():
    far = _lines(["Lead", "Lead"], [0, 500])
    f = neighbor_features(far)
    assert np.isnan(f.loc[0, "nbr_lead_share_k10"])
    assert f.loc[0, "nbr_known_count_k10"] == 0

    many = _lines(["Lead"] * 15, [i for i in range(15)])
    f = neighbor_features(many)
    assert f["nbr_known_count_k10"].max() == 10


def test_build_master_table():
    import geopandas as gpd
    from shapely.geometry import box

    city = box(BASE_LON - 0.01, BASE_LAT - 0.01, BASE_LON + 0.01, BASE_LAT + 0.01)
    wards = gpd.GeoDataFrame({"ward": ["42"]}, geometry=[city], crs="EPSG:4326")
    cas = gpd.GeoDataFrame({"community_area": ["32"]}, geometry=[city], crs="EPSG:4326")
    na = pd.NA
    geocoded = pd.DataFrame(
        {
            "line_id": ["exact", "nearby", "census", "outside", "failed"],
            "utility_side_material": ["Lead", "Non-Lead", "Unknown", "Unknown", "Unknown"],
            "customer_side_material": ["Unknown", "Non-Lead", "Non-Lead", "Unknown", "Unknown"],
            "reported_line_class": ["Lead", "Non-Lead", "Unknown", "Unknown", "Unknown"],
            "replacement_date": pd.to_datetime([None, "2024-05-01", None, None, None]),
            "year_built": pd.array([na] * 5, dtype="Int64"),
            "match_method": ["matched_address", "matched_nearby", "geocoded_census",
                             "geocoded_census", na],
            "matched_pin": ["17000000010000", na, na, na, na],
            "nearby_pin": [na, "17000000020000", na, na, na],
            "census_block_geoid": [na, na, "170310818003000", "170318000001000", na],
            "latitude": [BASE_LAT, BASE_LAT + 0.0002, BASE_LAT + 0.0004, BASE_LAT + 0.5, np.nan],
            "longitude": [BASE_LON] * 4 + [np.nan],
        }
    )
    parcels = pd.DataFrame(
        {
            "pin": ["17000000010000", "17000000020000"],
            "building_class": ["211", "203"],
            "census_block_geoid": ["170310818002008", "170310818002009"],
        }
    )
    chars = pd.DataFrame(
        {"year_built": pd.array([1905, 1950], dtype="Int64"),
         "unit_count": pd.array([2, 1], dtype="Int64")},
        index=pd.Index(["1700000001", "1700000002"], name="pin10"),
    )
    m = build_master_table(geocoded, parcels, chars, wards, cas).set_index("line_id")

    assert m.loc["exact", "block"] == "170310818002008"
    assert m.loc["nearby", "block"] == "170310818002009"  # neighbor's block
    assert m.loc["census", "block"] == "170310818003000"
    assert m.loc["exact", "tract"] == "17031081800"
    assert m.loc["exact", "year_built"] == 1905
    assert pd.isna(m.loc["nearby", "year_built"])  # no borrowed building attributes
    assert pd.isna(m.loc["nearby", "building_class"])
    assert m.loc["census", "ward"] == "42"
    assert not m.loc["outside", "in_city"]
    assert pd.isna(m.loc["failed", "in_city"])
    assert bool(m.loc["nearby", "replaced"])
    assert list(m["line_status"]) == list(m["line_status_derived"])
    assert m.loc["exact", "nbr_known_count_k10"] == 1  # sees the Non-Lead line only
