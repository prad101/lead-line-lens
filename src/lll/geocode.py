"""Address normalization and matching to Cook County parcels.

Order of attempts: PIN match, then normalized address match to the Assessor parcel
address file, then the Census Geocoder batch endpoint. Every row that still fails
gets a reason code so the matching report accounts for 100% of rows.

Inventory addresses are public records. Resident-entered addresses go through
normalize_address() only and are never written anywhere by this module.
"""

from __future__ import annotations

import io
import re

import numpy as np
import pandas as pd
import requests
import usaddress

REASON_CODES: dict[str, str] = {
    "matched_pin": "Match on parcel PIN (building-level PIN10)",
    "matched_address": "Exact match on normalized address",
    "matched_nearby": "Nearest parcel on the same street and side within 10 address numbers "
                      "(location only; no building attributes)",
    "geocoded_census": "Matched by Census Geocoder batch",
    "no_address": "Address field empty",
    "intersection": "Address is a street intersection, not a building",
    "parse_error": "usaddress could not parse the address",
    "no_parcel_match": "No parcel with this normalized address",
    "ambiguous_parcel": "Normalized address matches parcels more than 100 m apart",
    "census_no_match": "Census Geocoder returned no match",
    "census_tie": "Census Geocoder returned a tie",
    "census_error": "Census Geocoder request failed",
}

MATCHED = ("matched_pin", "matched_address", "matched_nearby", "geocoded_census")

NEARBY_MAX_NUMBERS = 10

CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"

_DIRECTIONS = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}
_SUFFIXES = {
    "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD", "ROAD": "RD",
    "DRIVE": "DR", "PLACE": "PL", "COURT": "CT", "PARKWAY": "PKWY", "TERRACE": "TER",
    "LANE": "LN", "HIGHWAY": "HWY", "SQUARE": "SQ", "CIRCLE": "CIR", "PLAZA": "PLZ",
    "EXPRESSWAY": "EXPY", "WAY": "WAY", "ROW": "ROW", "TRAIL": "TRL",
}
_KEEP = ("AddressNumber", "StreetNamePreDirectional", "StreetNamePreType", "StreetName",
         "StreetNamePostType", "StreetNamePostDirectional")

_SUFFIX_TOKENS = "|".join(sorted(set(_SUFFIXES) | set(_SUFFIXES.values()), key=len, reverse=True))
# "10300 10 S WESTERN AVE" is shorthand for the range 10300-10310.
_RANGE_SHORTHAND = re.compile(r"^(\d+)\s+\d{1,3}\s+(?=(?:N|S|E|W)\b)")
# Trailing unit after the street suffix, e.g. "4800 S CHICAGO BEACH DR 1715N".
_TRAILING_UNIT = re.compile(rf"^(.*\b(?:{_SUFFIX_TOKENS})\b)\s+(?:UNIT\s+|APT\s+|#\s*)?[\w-]+$")
# "10539 S AVENUE H" is a street, not "S AVENUE" plus unit H.
_PRE_TYPE_STREET = re.compile(r"^\d+\s+(?:N|S|E|W)\s+\w+$")
_INTERSECTION = re.compile(r"&|\bAND\b|\s@\s")
# Spelling variants between the inventory and the Assessor ("LA SALLE" vs "LASALLE").
_NAME_PREFIX_JOIN = re.compile(r"^(LA|DE|DU|DES|MC|VAN|O) (?=\w)")
_STREET_ALIASES = {"DR MARTIN LUTHER KING JR": "MARTIN LUTHER KING",
                   "DR MARTIN LUTHER KING": "MARTIN LUTHER KING",
                   "MARTIN LUTHER KING JR": "MARTIN LUTHER KING"}


def _normalize(raw: object) -> tuple[str | None, str | None]:
    """Return (normalized address, None) or (None, reason code)."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)) or raw is pd.NA:
        return None, "no_address"
    street = str(raw).upper().split(",")[0]
    if _INTERSECTION.search(street):
        return None, "intersection"
    s = re.sub(r"[^\w\s\-/#]", " ", street).strip()
    s = re.sub(r"\s+", " ", s)
    if not s:
        return None, "no_address"
    s = _RANGE_SHORTHAND.sub(r"\1 ", s)
    m = _TRAILING_UNIT.match(s)
    if m and not _PRE_TYPE_STREET.match(m.group(1)):
        s = m.group(1)
    try:
        tagged, _ = usaddress.tag(s)
    except usaddress.RepeatedLabelError:
        return None, "parse_error"
    number = tagged.get("AddressNumber", "")
    number = re.match(r"\d+", number)
    if not number or not tagged.get("StreetName"):
        return None, "parse_error"
    parts = [number.group(0)]
    for label in _KEEP[1:]:
        val = tagged.get(label)
        if not val:
            continue
        val = val.replace(".", "").strip()
        if label.endswith("Directional"):
            val = _DIRECTIONS.get(val, val)
        elif label == "StreetNamePostType":
            val = _SUFFIXES.get(val, val)
        elif label == "StreetName":
            val = _STREET_ALIASES.get(val, val)
            val = _NAME_PREFIX_JOIN.sub(r"\1", val)
        parts.append(val)
    return " ".join(parts), None


def normalize_address(raw: str | None) -> str | None:
    """Return a canonical 'NUMBER DIR STREET SUFFIX' string, or None if unparseable."""
    return _normalize(raw)[0]


def normalize_series(addresses: pd.Series) -> pd.DataFrame:
    """_normalize applied to each distinct value once; columns address_norm and reason."""
    uniq = pd.Series(addresses.dropna().unique(), dtype=object)
    parsed = pd.DataFrame([_normalize(v) for v in uniq], columns=["address_norm", "reason"],
                          index=uniq.to_numpy(), dtype=object)
    keys = addresses.astype(object)
    out = parsed.reindex(keys.to_numpy())
    out.index = addresses.index
    out.loc[keys.isna().to_numpy(), "reason"] = "no_address"
    return out


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def build_parcel_index(parcels: pd.DataFrame, max_spread_m: float = 100.0) -> pd.DataFrame:
    """Collapse parcels to one row per normalized address.

    Expects columns pin, address, latitude, longitude, and optionally building_class.
    Condo units sharing an address collapse to their building. When an address is shared
    with exempt (EX) or vacant-land (1xx) parcels, those are dropped in favor of building
    parcels. An address whose remaining parcels are spread more than max_spread_m apart
    is flagged ambiguous.
    """
    p = parcels.dropna(subset=["latitude", "longitude"]).copy()
    p["address_norm"] = normalize_series(p["address"])["address_norm"]
    p = p.dropna(subset=["address_norm"])
    if "building_class" in p.columns:
        cls = p["building_class"].astype(str)
        p["_weak"] = cls.eq("EX") | cls.str.startswith("1")
        has_strong = (~p["_weak"]).groupby(p["address_norm"]).transform("any")
        p = p[~(p["_weak"] & has_strong)]
    p["pin10"] = p["pin"].astype(str).str[:10]
    g = p.groupby("address_norm")
    idx = g.agg(
        pin=("pin", "first"),
        pin10=("pin10", "first"),
        n_pin10=("pin10", "nunique"),
        latitude=("latitude", "mean"),
        longitude=("longitude", "mean"),
        lat_min=("latitude", "min"),
        lat_max=("latitude", "max"),
        lon_min=("longitude", "min"),
        lon_max=("longitude", "max"),
    )
    spread = _haversine_m(idx.lat_min, idx.lon_min, idx.lat_max, idx.lon_max)
    idx["ambiguous"] = spread > max_spread_m
    return idx.drop(columns=["lat_min", "lat_max", "lon_min", "lon_max"])


def match_to_parcels(inventory: pd.DataFrame, parcels: pd.DataFrame) -> pd.DataFrame:
    """Attach pin, latitude, longitude, address_norm, and match_method/fail_reason.

    match_method is one of MATCHED for successes; fail_reason is a REASON_CODES key
    otherwise (and NA on success).
    """
    out = inventory.copy()
    out["match_method"] = pd.NA
    out["fail_reason"] = pd.NA
    for col in ("latitude", "longitude"):
        out[col] = np.nan
    out["matched_pin"] = pd.NA

    if "pin" in out.columns and out["pin"].notna().any():
        by_pin10 = (
            parcels.dropna(subset=["latitude", "longitude"])
            .assign(pin10=lambda d: d["pin"].astype(str).str[:10])
            .groupby("pin10")
            .agg(pin=("pin", "first"), latitude=("latitude", "mean"),
                 longitude=("longitude", "mean"))
        )
        pin10 = out["pin"].astype("string").str[:10]
        hit = pin10.isin(by_pin10.index).fillna(False).to_numpy(dtype=bool)
        rep = by_pin10.loc[pin10[hit]]
        out.loc[hit, "latitude"] = rep["latitude"].to_numpy()
        out.loc[hit, "longitude"] = rep["longitude"].to_numpy()
        out.loc[hit, "matched_pin"] = rep["pin"].to_numpy()
        out.loc[hit, "match_method"] = "matched_pin"

    norm = normalize_series(out.get("address", pd.Series(pd.NA, index=out.index)))
    out["address_norm"] = norm["address_norm"]
    todo = out["match_method"].isna()
    out.loc[todo, "fail_reason"] = norm.loc[todo, "reason"]

    index = build_parcel_index(parcels)
    cand = todo & out["address_norm"].notna()
    joined = out.loc[cand, ["address_norm"]].join(index, on="address_norm")
    found = joined["pin"].notna()
    ambiguous = found & joined["ambiguous"].fillna(False).astype(bool)
    ok = found & ~ambiguous
    rows = joined.index[ok]
    out.loc[rows, ["latitude", "longitude"]] = joined.loc[ok, ["latitude", "longitude"]].to_numpy()
    out.loc[rows, "matched_pin"] = joined.loc[ok, "pin"]
    out.loc[rows, "match_method"] = "matched_address"
    out.loc[rows, "fail_reason"] = pd.NA
    out.loc[joined.index[ambiguous], "fail_reason"] = "ambiguous_parcel"
    out.loc[joined.index[~found], "fail_reason"] = "no_parcel_match"

    out["nearby_pin"] = pd.NA
    unmatched = out.loc[joined.index[~found], "address_norm"]
    near = _nearest_number(unmatched, index[~index["ambiguous"]])
    if len(near):
        rows = near.index
        out.loc[rows, ["latitude", "longitude"]] = near[["latitude", "longitude"]].to_numpy()
        out.loc[rows, "nearby_pin"] = near["pin"].to_numpy()
        out.loc[rows, "match_method"] = "matched_nearby"
        out.loc[rows, "fail_reason"] = pd.NA
    return out


def _split_number(address_norm: pd.Series) -> pd.DataFrame:
    parts = address_norm.astype("string").str.extract(r"^(\d+) (.+)$")
    return pd.DataFrame(
        {"num": pd.to_numeric(parts[0], errors="coerce"), "street": parts[1].astype(str)},
        index=address_norm.index,
    )


def _nearest_number(address_norm: pd.Series, index: pd.DataFrame) -> pd.DataFrame:
    """For each address, the parcel on the same street and side with the nearest number."""
    if address_norm.empty:
        return pd.DataFrame(columns=["pin", "latitude", "longitude"])
    q = _split_number(address_norm).dropna()
    q["parity"] = (q["num"] % 2).astype(int)
    q["_row"] = q.index
    ref = _split_number(pd.Series(index.index, index=index.index)).dropna()
    ref = ref.join(index[["pin", "latitude", "longitude"]])
    ref["parity"] = (ref["num"] % 2).astype(int)
    q = q.sort_values("num")
    ref = ref.sort_values("num")
    m = pd.merge_asof(
        q, ref, on="num", by=["street", "parity"], direction="nearest",
        tolerance=NEARBY_MAX_NUMBERS,
    )
    m = m.dropna(subset=["pin"]).set_index("_row")
    return m[["pin", "latitude", "longitude"]]


def census_batch_geocode(
    addresses: pd.DataFrame,
    city: str = "Chicago",
    state: str = "IL",
    chunk_size: int = 5_000,
    retry_size: int = 1_000,
    timeout: int = 600,
) -> pd.DataFrame:
    """Geocode rows with the Census Geocoder batch endpoint.

    addresses needs columns id and street (zip optional). Returns id, census_status
    (Match / No_Match / Tie / error), latitude, longitude, and the 2020 census block GEOID.
    """
    cols = ["id", "census_status", "latitude", "longitude", "census_block_geoid"]
    results = []
    for start in range(0, len(addresses), chunk_size):
        chunk = addresses.iloc[start : start + chunk_size]
        try:
            results.append(_census_post(chunk, city, state, timeout))
        except requests.RequestException:
            # Large batches occasionally time out; retry once in smaller pieces.
            for sub_start in range(0, len(chunk), retry_size):
                sub = chunk.iloc[sub_start : sub_start + retry_size]
                try:
                    results.append(_census_post(sub, city, state, timeout))
                except requests.RequestException:
                    results.append(
                        pd.DataFrame({"id": sub["id"].astype(str), "census_status": "error"})
                    )
    if not results:
        return pd.DataFrame(columns=cols)
    return pd.concat(results, ignore_index=True).reindex(columns=cols)


def _census_post(chunk: pd.DataFrame, city: str, state: str, timeout: int) -> pd.DataFrame:
    payload = pd.DataFrame(
        {
            "id": chunk["id"].astype(str),
            "street": chunk["street"],
            "city": city,
            "state": state,
            "zip": chunk["zip"].fillna("") if "zip" in chunk else "",
        }
    ).to_csv(index=False, header=False)
    resp = requests.post(
        CENSUS_BATCH_URL,
        files={"addressFile": ("batch.csv", payload, "text/csv")},
        data={"benchmark": "Public_AR_Current", "vintage": "Current_Current"},
        timeout=timeout,
    )
    resp.raise_for_status()
    res = pd.read_csv(io.StringIO(resp.text), header=None, dtype=str, names=range(12))
    coords = res[5].fillna(",").str.split(",", expand=True).reindex(columns=[0, 1])
    block = res[8].fillna("") + res[9].fillna("") + res[10].fillna("") + res[11].fillna("")
    return pd.DataFrame(
        {
            "id": res[0],
            "census_status": res[2],
            "longitude": pd.to_numeric(coords[0], errors="coerce"),
            "latitude": pd.to_numeric(coords[1], errors="coerce"),
            "census_block_geoid": block.where(block.str.len() == 15),
        }
    )


_ZIP = re.compile(r"\b(\d{5})(?:-\d{4})?\s*$")


def geocode_inventory(
    inventory: pd.DataFrame,
    parcels: pd.DataFrame,
    use_census_fallback: bool = True,
    city: str = "Chicago",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full matching cascade; return (rows with coordinates, matching report).

    Census-geocoded rows also get census_block_geoid from the geocoder response.
    """
    out = match_to_parcels(inventory, parcels)
    out["census_block_geoid"] = pd.NA
    if use_census_fallback:
        out = apply_census_fallback(out, city=city)
    return out, matching_report(out)


def apply_census_fallback(
    out: pd.DataFrame,
    city: str = "Chicago",
    reasons: tuple[str, ...] = ("no_parcel_match", "ambiguous_parcel"),
) -> pd.DataFrame:
    """Geocode unmatched rows whose fail_reason is in reasons; updates and returns out.

    Rerun with reasons=("census_error",) to retry rows whose batch failed.
    """
    out = out.copy()
    if "census_block_geoid" not in out:
        out["census_block_geoid"] = pd.NA
    retry = (
        out["match_method"].isna()
        & out["fail_reason"].isin(reasons)
        & out["address_norm"].notna()
    )
    if not retry.any():
        return out
    zips = out.loc[retry, "address"].astype("string").str.extract(_ZIP, expand=False)
    req = (
        pd.DataFrame({"street": out.loc[retry, "address_norm"], "zip": zips})
        .drop_duplicates("street")
        .reset_index(drop=True)
    )
    req["id"] = req.index.astype(str)
    geo = census_batch_geocode(req, city=city).merge(req[["id", "street"]], on="id", how="left")
    geo = geo.set_index("street")
    streets = out.loc[retry, "address_norm"]
    status = geo["census_status"].reindex(streets).fillna("error").to_numpy()
    matched = status == "Match"
    idx = streets.index[matched]
    hits = streets[matched]
    out.loc[idx, "latitude"] = geo["latitude"].reindex(hits).to_numpy()
    out.loc[idx, "longitude"] = geo["longitude"].reindex(hits).to_numpy()
    out.loc[idx, "census_block_geoid"] = geo["census_block_geoid"].reindex(hits).to_numpy()
    out.loc[idx, "match_method"] = "geocoded_census"
    out.loc[idx, "fail_reason"] = pd.NA
    code = np.where(status == "Tie", "census_tie",
                    np.where(status == "error", "census_error", "census_no_match"))
    out.loc[streets.index[~matched], "fail_reason"] = code[~matched]
    return out


def matching_report(matched: pd.DataFrame) -> pd.DataFrame:
    """Row counts and shares by outcome code, with a total match rate row."""
    outcome = matched["match_method"].fillna(matched["fail_reason"]).fillna("unclassified")
    rep = outcome.value_counts().rename_axis("code").reset_index(name="rows")
    rep["share"] = rep["rows"] / max(len(matched), 1)
    rep["description"] = rep["code"].map(REASON_CODES)
    rep["matched"] = rep["code"].isin(MATCHED)
    return rep
