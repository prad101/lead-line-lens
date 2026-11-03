"""Build the Chicago master table and area aggregates from data/raw.

    python scripts/build_master.py                 # reuse cached geocoding if present
    python scripts/build_master.py --refresh-geocode
    python scripts/build_master.py --no-census     # parcel matching only, no network

Writes to data/processed/:
    geocoded_chicago_<snapshot>.parquet   matching cascade output (cache)
    master_chicago_<snapshot>.parquet     one row per service line
    matching_report_chicago_<snapshot>.csv
    areas_<level>_chicago_<snapshot>.parquet for each area level (small cells suppressed)
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

from lll import PROCESSED_DIR, sources
from lll.features import AREA_LEVELS, area_aggregates, build_master_table
from lll.geocode import apply_census_fallback, geocode_inventory, matching_report
from lll.ingest import read_iepa_template
from lll.schema import validate_inventory


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh-geocode", action="store_true")
    ap.add_argument("--no-census", action="store_true")
    ap.add_argument("--retry-census-errors", action="store_true",
                    help="re-send rows whose Census batch failed, then rebuild")
    args = ap.parse_args()

    t0 = time.time()
    inv, meta = read_iepa_template(sources.CHICAGO_INVENTORY)
    validate_inventory(inv)
    snap = pd.Timestamp(meta["snapshot_date"]).strftime("%Y%m%d")
    print(f"inventory: {len(inv):,} lines, snapshot {snap}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cache = PROCESSED_DIR / f"geocoded_chicago_{snap}.parquet"
    parcels = sources.chicago_parcels()
    if cache.exists() and not args.refresh_geocode:
        geocoded = pd.read_parquet(cache)
        print(f"geocoding: cached {cache.name}")
    else:
        geocoded, _ = geocode_inventory(inv, parcels, use_census_fallback=not args.no_census)
    if args.retry_census_errors:
        geocoded = apply_census_fallback(geocoded, reasons=("census_error",))
    geocoded.to_parquet(cache)

    report = matching_report(geocoded)
    report.to_csv(PROCESSED_DIR / f"matching_report_chicago_{snap}.csv", index=False)
    rate = report.loc[report["matched"], "share"].sum()
    print(f"matched: {rate:.2%}")

    master = build_master_table(
        geocoded, parcels, sources.building_characteristics(),
        sources.wards(), sources.community_areas(),
    )
    out = PROCESSED_DIR / f"master_chicago_{snap}.parquet"
    master.to_parquet(out)
    print(f"master: {len(master):,} rows -> {out.name}")
    for level in AREA_LEVELS:
        agg = area_aggregates(master, level)
        agg.to_parquet(PROCESSED_DIR / f"areas_{level}_chicago_{snap}.parquet")
        print(f"  {level}: {len(agg):,} areas, {int(agg['suppressed'].sum()):,} suppressed")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
