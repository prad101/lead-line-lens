import pandas as pd
import pytest

from lll.geocode import REASON_CODES, geocode_inventory, match_to_parcels, normalize_address


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("123 North Main Street", "123 N MAIN ST"),
        ("123 N. Main St.", "123 N MAIN ST"),
        ("4500 W Fullerton Avenue, Chicago, IL 60639", "4500 W FULLERTON AVE"),
        ("1200-1210 S Michigan Ave", "1200 S MICHIGAN AVE"),
        ("2244 58 W OHIO ST", "2244 W OHIO ST"),
        ("4800 S CHICAGO BEACH DR 1715N", "4800 S CHICAGO BEACH DR"),
        ("10539 S AVENUE H, Chicago, IL 60617", "10539 S AVENUE H"),
        ("10148 S LA SALLE ST", "10148 S LASALLE ST"),
        ("7324 S DR MARTIN LUTHER KING JR DR", "7324 S MARTIN LUTHER KING DR"),
        ("4500 W Fullerton Ave & N Kildare Ave", None),
        ("", None),
        (None, None),
        ("Chicago", None),
    ],
)
def test_normalize_address(raw, expected):
    assert normalize_address(raw) == expected


def _parcels():
    return pd.DataFrame(
        {
            "pin": ["14083170170000", "14083170171001", "14083170171002", "20000000000000",
                    "30000000000000"],
            "address": ["5000 N Broadway", "5010 N Broadway", "5010 N Broadway",
                        "100 W Elm St", "100 W Elm St"],
            "latitude": [41.97, 41.9701, 41.9701, 41.90, 41.95],
            "longitude": [-87.66, -87.66, -87.66, -87.63, -87.63],
        }
    )


def test_match_cascade_and_reason_codes():
    inv = pd.DataFrame(
        {
            "line_id": ["a", "b", "c", "d", "e", "f"],
            "pin": ["1408317017", None, None, None, None, None],
            "address": [None, "5010 North Broadway", "100 W Elm Street", "9 Nowhere Rd", "",
                        "5000 N Broadway"],
        }
    )
    out, report = geocode_inventory(inv, _parcels(), use_census_fallback=False)
    out = out.set_index("line_id")
    assert out.loc["a", "match_method"] == "matched_pin"
    assert out.loc["b", "match_method"] == "matched_address"  # condo units collapse
    assert out.loc["c", "fail_reason"] == "ambiguous_parcel"  # parcels ~5.5 km apart
    assert out.loc["d", "fail_reason"] == "no_parcel_match"
    assert out.loc["e", "fail_reason"] == "no_address"
    assert out.loc["f", "match_method"] == "matched_address"
    assert set(report["code"]) <= set(REASON_CODES)
    assert report["rows"].sum() == len(inv)


def test_nearby_number_same_side_only():
    parcels = pd.DataFrame(
        {
            "pin": ["10000000000000", "11000000000000"],
            "address": ["8221 S Wolcott Ave", "8224 S Wolcott Ave"],
            "latitude": [41.744, 41.744],
            "longitude": [-87.671, -87.672],
        }
    )
    inv = pd.DataFrame(
        {"line_id": ["odd", "even", "far"],
         "address": ["8223 S Wolcott Ave", "8226 S Wolcott Ave", "8301 S Wolcott Ave"]}
    )
    out = match_to_parcels(inv, parcels).set_index("line_id")
    assert out.loc["odd", "match_method"] == "matched_nearby"
    assert out.loc["odd", "nearby_pin"] == "10000000000000"
    assert pd.isna(out.loc["odd", "matched_pin"])  # no building attributes borrowed
    assert out.loc["even", "nearby_pin"] == "11000000000000"
    assert out.loc["far", "fail_reason"] == "no_parcel_match"


def test_exempt_duplicate_does_not_make_address_ambiguous():
    parcels = pd.DataFrame(
        {
            "pin": ["25092180010000", "25092220410000"],
            "address": ["9701 S Princeton Ave", "9701 S Princeton Ave"],
            "building_class": ["205", "EX"],
            "latitude": [41.7179, 41.6000],
            "longitude": [-87.6306, -87.6258],
        }
    )
    inv = pd.DataFrame({"line_id": ["a"], "address": ["9701 S PRINCETON AVE"]})
    out = match_to_parcels(inv, parcels)
    assert out.loc[0, "match_method"] == "matched_address"
    assert out.loc[0, "matched_pin"] == "25092180010000"


def test_every_row_is_accounted_for():
    inv = pd.DataFrame({"line_id": ["x"], "address": ["5000 N Broadway"]})
    out = match_to_parcels(inv, _parcels())
    assert out["match_method"].notna().sum() + out["fail_reason"].notna().sum() == len(out)
