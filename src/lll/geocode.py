"""Address normalization and matching to Cook County parcels.

Order of attempts: normalized address match to the Assessor parcel address file,
then PIN match, then the Census Geocoder batch endpoint. Every row that still fails
gets a reason code so the matching report can account for 100% of rows.
"""

from __future__ import annotations

import pandas as pd

REASON_CODES: dict[str, str] = {
    "matched_address": "Exact match on normalized address",
    "matched_pin": "Match on parcel PIN",
    "geocoded_census": "Matched by Census Geocoder batch",
    "no_address": "Address field empty",
    "parse_error": "usaddress could not parse the address",
    "no_parcel_match": "No parcel with this normalized address",
    "ambiguous_parcel": "Normalized address matches more than one parcel",
    "census_no_match": "Census Geocoder returned no match",
    "census_tie": "Census Geocoder returned a tie",
}


def normalize_address(raw: str | None) -> str | None:
    """Return a canonical 'NUMBER DIR STREET SUFFIX' string, or None if unparseable.

    TODO: implement with usaddress (Gate 1).
    """
    raise NotImplementedError


def match_to_parcels(inventory: pd.DataFrame, parcels: pd.DataFrame) -> pd.DataFrame:
    """Attach pin, latitude, longitude, match_method, and fail_reason to each row.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def census_batch_geocode(addresses: pd.DataFrame, chunk_size: int = 10_000) -> pd.DataFrame:
    """Geocode unmatched rows with the Census Geocoder batch endpoint.

    TODO: implement (Gate 1).
    """
    raise NotImplementedError


def geocode_inventory(
    inventory: pd.DataFrame, parcels: pd.DataFrame, use_census_fallback: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full matching cascade; return (matched rows, matching report).

    TODO: implement (Gate 1). Target: >= 95% matched or geocoded.
    """
    raise NotImplementedError
