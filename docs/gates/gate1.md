# Gate 1: Master table approved (Week 2)

**Status:** met Nov 3, 2026 (planned Nov 3).

## Delivered

- `lll.geocode`: usaddress normalization; match cascade of PIN, exact address, nearest
  same-side house number (within 10 numbers), then the Census Geocoder batch endpoint. Every
  row gets a match method or a reason code.
- `lll.features.build_master_table`: block, block group, tract, ward, community area; Assessor
  building class, year built, and unit count; whole-line status; leave-one-out neighbor
  features; tract unknown rate.
- `scripts/build_master.py`: one command builds the master table, matching report, and area
  aggregates from `data/raw/` (cached geocoding, about 30 seconds; first run about 9 minutes
  for the Census step).
- Outputs in `data/processed/` (gitignored): `master_chicago_20250414.parquet`,
  `matching_report_chicago_20250414.csv`, `areas_{block,block_group,tract,ward,community_area}_chicago_20250414.parquet`.
- `notebooks/02_matching_eda.ipynb` (executed): matching report and the five EDA questions.
- Maps: `docs/figures/map1_unknown_share_community_area.png`,
  `docs/figures/map2_lead_share_tract.png`.
- Tests: 70 passing (normalization cases, nearest-number matching, exempt-parcel
  disambiguation, IEPA template reader, master table build, suppression).

## Benchmarks measured

| Benchmark | Target | Result |
|---|---|---|
| Matched or geocoded (#14) | ≥ 95% | **98.28%**: exact address 90.97%, nearest number 5.29%, Census 2.02% |
| Geographies (#15) | 100% of located lines | block, block group, tract 100%; ward and community area 99.97% (153 lines are outside city limits and are flagged `in_city = False`) |
| EDA five questions (#16) | answered | all five in `02_matching_eda.ipynb`; diameter answered with East Dundee only |
| Master table parquet + build script (#17) | reproducible | `scripts/build_master.py` |
| Matching report with reason codes (#18) | 100% of rows accounted for | 8 outcome codes, sums to 491,705 |
| First two maps (#19) | 2 maps | unknown share by community area; Lead/GRR share by tract |

## EDA answers

1. **Unknown by community area:** from 9.4% (Near South Side) to 67.8% (Lower West Side).
   The highest-unknown areas are on the Southwest and Northwest Sides (West Lawn, South
   Lawndale, Gage Park, Belmont Cragin); downtown and the lakefront are lowest.
2. **Unknown by year built:** 50–60% for buildings before 1986, then 4.1% for 1986–99 and 2.7%
   for 2000 and later. Among known lines, Lead or GRR is 79–94% before 1986 and under 2% after,
   consistent with the 1986 federal lead ban.
3. **Unknown by diameter:** Chicago has no diameter. In East Dundee, the 85 lines with a size
   are 3/4" (13 lead, 35 non-lead), 1" (34 non-lead), and 2–3" (non-lead).
4. **By utility-side material:** when the utility side is Unknown (357,000 lines), the customer
   side is Unknown 67% of the time and Lead 27%. When the utility side is Lead, the customer
   side is Unknown 60% and Lead 30%.
5. **Replacements by year:** 10,640 lines replaced: 1 in 2017, 34 in 2021, 349 in 2022,
   4,174 in 2023, 4,753 in 2024, and 1,329 by the April 2025 snapshot.

## Matching notes

- Unmatched lines are 75% Non-Lead and only 7% Unknown, so matching failures mostly drop new
  and large buildings, not the uncertain lines the model will score.
- 7,585 lines got `census_error` because one Census batch timed out. The code now retries
  failed batches in smaller pieces (`python scripts/build_master.py --retry-census-errors`); not
  rerun because the target is already met.
- Nearest-number matches carry location only; building attributes are never borrowed from a
  neighboring parcel.

## Cut or deferred

- Census block polygons were not downloaded; blocks come from the Assessor parcel record or
  the Census Geocoder response instead of a spatial join.
