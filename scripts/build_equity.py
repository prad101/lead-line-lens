"""Build the disparity report from the master table and ACS.

    python scripts/build_equity.py            # needs CENSUS_API_KEY on first run
    python scripts/build_equity.py --refresh-acs

Writes to data/processed/:
    acs_<year>_cook_tracts.parquet, acs_<year>_wards.parquet   ACS cache
    equity_chicago_<snapshot>/{tract,ward,income_quartiles,majority_group,disparity_ratios}.csv
"""

from __future__ import annotations

import argparse

from lll import PROCESSED_DIR, sources
from lll.equity import ACS_YEAR, disparity_report, export_csvs, fetch_acs, ward_acs
from lll.features import latest_master


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh-acs", action="store_true")
    args = ap.parse_args()

    master, snap = latest_master()
    tract_cache = PROCESSED_DIR / f"acs_{ACS_YEAR}_cook_tracts.parquet"
    ward_cache = PROCESSED_DIR / f"acs_{ACS_YEAR}_wards.parquet"
    if args.refresh_acs:
        tract_cache.unlink(missing_ok=True)
        ward_cache.unlink(missing_ok=True)
    acs = fetch_acs(cache=tract_cache)
    print(f"ACS {ACS_YEAR}: {len(acs):,} Cook County tracts")
    if ward_cache.exists():
        import pandas as pd

        wacs = pd.read_parquet(ward_cache)
    else:
        wacs = ward_acs(acs, sources.tracts(), sources.wards())
        wacs.to_parquet(ward_cache)

    report = disparity_report(master, acs, wacs)
    out_dir = PROCESSED_DIR / f"equity_chicago_{snap}"
    for p in export_csvs(report, out_dir):
        print(f"  {p.relative_to(PROCESSED_DIR)}")

    t, w = report["tract"], report["ward"]
    print(f"tracts: {len(t):,} ({int(t.suppressed.sum())} suppressed, "
          f"{int(t.median_income.isna().sum())} without ACS income)")
    print(f"wards: {len(w)} ({int(w.suppressed.sum())} suppressed)")
    cols = ["income_quartile", "total_lines", "share_lead", "share_unknown",
            "share_needs_action", "share_replaced", "income_min", "income_max"]
    print(report["income_quartiles"][cols].to_string(index=False))
    cols = ["majority_group", "total_lines", "areas", "share_lead", "share_unknown",
            "share_needs_action", "share_replaced"]
    print(report["majority_group"][cols].to_string(index=False))
    r = report["disparity_ratios"]
    print(r[r.metric.isin(["share_needs_action", "share_lead", "share_unknown",
                           "share_replaced"])].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
