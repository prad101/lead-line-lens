# Data audit (Gate 0 summary)

Numbers from `notebooks/01_audit.ipynb`, run Nov 3, 2026. Sources, URLs, and download dates
are in `docs/data_dictionary.md`.

## Row counts

| Source | Rows | Notes |
|---|---|---|
| Illinois EPA inventory reports | 9,100 system-year rows, 1,794 systems, reporting years 2017–2025 | System totals only, no lines |
| Chicago line-level inventory (IL0316000, 2025-04-14) | 491,705 lines, 487,669 unique addresses | Matches the workbook header totals exactly (Lead 150,864; GRR 10,526; Unknown 251,247; Non-Lead 79,068) |
| Assessor parcels with addresses (Chicago) | 880,789 PINs, 604,414 buildings (PIN10) | 0 missing coordinates, 1 missing block GEOID |
| Assessor building characteristics | 448,404 buildings | Residential and condo only; commercial buildings have no year built |
| Burnham (IL0310360) | 1,208 lines | |
| East Dundee (IL0890250) | 1,497 lines | |

## Share unknown by side

| Source | Utility side | Customer side | Whole line |
|---|---|---|---|
| Chicago | 72.6% | 55.2% | 51.1% |
| Burnham | 34.2% | 7.6% | 30.6% |
| East Dundee | 8.7% | 8.7% | 8.7% |
| Illinois statewide, 2024 reports (602 systems) | | | 25.1% of connections |

In Chicago, the customer side is known more often than the utility side. Of lines whose
utility side is Unknown, 27% have a Lead customer side and 67% are Unknown on both sides.

## Duplicates

- Illinois EPA reports: 12 system-year rows appear more than once (refiled reports). For
  current-status questions the audit uses each system's most recent report.
- Chicago: 2,285 rows identical to another row in every field but the generated line ID, and
  7,470 lines (1.5%) share an address with another line. Large buildings can have more
  than one service, so these are kept; the master table counts lines, not addresses.
- East Dundee: the village flags 343 rows as `Duplicate`; 6.9% of rows share an address.
  Kept and marked with `duplicate_flag`.

## Missingness (Chicago)

| Field | Missing |
|---|---|
| PIN, year built, diameter | 100% (not in the file; year built comes from the Assessor join) |
| Verification method (`CombinedSourceDescription`) | 49.6% |
| Utility / customer install year | 96.3% / 96.9% |
| Notification date | 95.1% |
| Replacement date | 97.8% |

## Implausible values

- No install years before 1850 or after the snapshot, and no replacement dates after the
  snapshot or before 1990.
- No line marked previously replaced still has a Lead utility side.
- Assessor year built: 4 buildings before 1830 (earliest 1801), below the schema minimum.
  `sources.building_characteristics()` sets them to missing.

## Surprises

1. **Chicago's 2022 report had zero unknowns.** It reported 409,734 lead lines and 0 unknown;
   the 2024 report has 150,767 lead and 251,569 unknown. About 259,000 lines moved from
   presumed lead to Unknown. Unknown does not mean lead-free.
2. **2024 statewide reports carry only lead and unknown counts.** All non-lead detail columns
   are empty for the 602 systems that filed for 2024, so the state file cannot give a
   non-lead breakdown for 2024.
3. **5,050 Chicago classifications cite "Home Built Date".** Using year built as a model
   feature would partly reproduce the label for these lines. Gate 2 must exclude them from
   training or test with and without them.
4. **The Chicago inventory has no PIN or diameter.** Matching relies on addresses, and the
   diameter question in Gate 1 can only be answered with East Dundee (85 lines with a size).
5. **Burnham publishes numeric material codes.** The layer's coded-value domains are saved
   next to the data (`burnham_layer.json`), and the side status fields map directly to the four
   canonical classes.
