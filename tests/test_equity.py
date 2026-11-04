import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import box

from lll import equity
from lll.equity import ACS_VARIABLES, NAN_FILL, choropleth, fetch_acs, ward_acs


def _acs_row(tract, income, pop, black, latino, white, asian):
    return {"tract": tract, "median_income": income, "pop_total": pop, "pop_black": black,
            "pop_latino": latino, "pop_white": white, "pop_asian": asian, "kids_under6": pop / 10,
            "housing_units": pop / 2, "units_pre1950": pop / 4}


def test_ward_acs_apportions_tract_counts_by_area():
    # tract A sits wholly in ward 1; tract B is split evenly between wards 1 and 2
    tracts = gpd.GeoDataFrame({"tract": ["A", "B"]},
                              geometry=[box(-87.70, 41.80, -87.69, 41.81),
                                        box(-87.69, 41.80, -87.67, 41.81)], crs="EPSG:4326")
    wards = gpd.GeoDataFrame({"ward": ["1", "2"]},
                             geometry=[box(-87.70, 41.80, -87.68, 41.81),
                                       box(-87.68, 41.80, -87.67, 41.81)], crs="EPSG:4326")
    acs = pd.DataFrame([_acs_row("A", 40_000, 1000, 800, 100, 100, 0),
                        _acs_row("B", 80_000, 2000, 0, 200, 1600, 200)])
    out = ward_acs(acs, tracts, wards).set_index("ward")
    assert out.loc["1", "pop_total"] == pytest.approx(2000, rel=0.01)
    assert out.loc["2", "pop_total"] == pytest.approx(1000, rel=0.01)
    assert out.loc["1", "median_income"] == pytest.approx(60_000, rel=0.01)
    assert out.loc["2", "median_income"] == pytest.approx(80_000, rel=0.01)
    assert out.loc["2", "majority_group"] == "White"
    assert out.loc["1", "majority_group"] == "No majority"


class _Resp:
    def __init__(self, rows):
        self.rows = rows

    def raise_for_status(self):
        pass

    def json(self):
        return self.rows


def test_fetch_acs_parses_and_blanks_sentinels(monkeypatch, tmp_path):
    header = list(ACS_VARIABLES) + ["state", "county", "tract"]
    vals = {v: "100" for v in ACS_VARIABLES}
    vals["B19013_001E"] = "-666666666"
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: _Resp([header, [*vals.values(), "17", "031", "010100"]]))
    cache = tmp_path / "acs.parquet"
    out = fetch_acs(cache=cache)
    assert out.loc[0, "tract"] == "17031010100"
    assert pd.isna(out.loc[0, "median_income"])
    assert out.loc[0, "kids_under6"] == 300
    assert cache.exists()


def test_fetch_acs_error_hides_url(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("https://api.census.gov/...&key=SECRET")

    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setenv("CENSUS_API_KEY", "SECRET")
    with pytest.raises(RuntimeError) as err:
        fetch_acs()
    assert "SECRET" not in str(err.value) and err.value.__cause__ is None


def test_choropleth_greys_suppressed_areas():
    geo = gpd.GeoDataFrame({"ward": [str(i) for i in range(1, 7)]},
                           geometry=[box(-87.7 + i * 0.01, 41.8, -87.69 + i * 0.01, 41.81)
                                     for i in range(6)], crs="EPSG:4326")
    table = pd.DataFrame({"ward": [str(i) for i in range(1, 7)], "total_lines": [10] * 5 + [None],
                          "share_lead": [0.1, 0.2, 0.3, 0.4, 0.5, None]})
    m = choropleth(table, geo, "share_lead", "Lead", key="ward", source="test")
    html = m.get_root().render()
    assert NAN_FILL in html
    assert "Fewer than 5 lines" in html
    assert "10% to" in html


def test_needs_action_counts_unknown_as_needing_action():
    assert "Unknown" in equity.NEEDS_ACTION and "Non-Lead" not in equity.NEEDS_ACTION
