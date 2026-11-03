# Gate 0: Data in hand and documented (Week 1)

**Status:** met Nov 3, 2026 (planned Oct 31). Real line-level data only; no synthetic data used.

## Delivered

- Repository scaffold per Appendix A: package `lll`, FastAPI stubs, Streamlit stubs,
  Dockerfile, docker-compose, CI (ruff + pytest). CI green on `main`.
- GitHub project board ([project 6](https://github.com/users/prad101/projects/6)) with Gate 0–6
  and Backlog, 46 issues from the brief's benchmarks (`scripts/setup_project_board.sh`).
- Data on disk under `data/raw/` (gitignored), every source with URL, row count, snapshot, and
  download date in `docs/data_dictionary.md`:
  - Chicago line-level inventory: 491,705 lines, snapshot 2025-04-14 (Chicago's IEPA
    submission, FOIA copy published by Inside Climate News, Grist, and WBEZ).
  - Illinois EPA system-level reports: 9,100 rows, 1,794 systems, 2017–2025.
  - Two small Illinois systems: Burnham (1,208 lines) and East Dundee (1,497 lines).
  - Cook County Assessor parcel universe, addresses, residential and condo characteristics.
  - Ward (2023), community area, and 2020 tract boundaries; ACS 5-year 2024 via API key.
- Readers: `lll.ingest.read_iepa_template` (any IEPA-template workbook),
  `lll.sources.burnham`, `lll.sources.east_dundee`; all validate against the pandera schema.
- `notebooks/01_audit.ipynb` (executed) and `docs/data_audit.md`.
- `docs/data_dictionary.md`: every column of all three line-level inventories, the material
  vocabulary mapping, and the master table fields.
- `docs/compliance_dates.md`: federal LCRI and Illinois LSLRNA dates with sources.

## Benchmarks measured

| Benchmark | Target | Result |
|---|---|---|
| Repository, Docker, CI (#6) | builds and passes | CI green on both pushed commits |
| Chicago inventory (#7) | line-level file in hand | 491,705 lines; header totals match row counts exactly |
| Two small IL inventories (#8) | 2 systems | Burnham and East Dundee, both validate |
| Parcels, ACS, boundaries (#9) | on disk / reachable | 880,789 Chicago parcels with address; 50 wards, 77 community areas, 789 tracts; ACS returns 1,332 Cook tracts |
| Data dictionary (#10) | 100% of inventory columns | Chicago 18/18, Burnham 29/29, East Dundee 57/57 (checked in code against the raw headers) |
| Compliance-dates note (#11) | half page | `docs/compliance_dates.md`, 12 cited sources |
| README v0 and board (#12) | published | README v0 and project board live |
| Data audit memo (#13) | row counts, unknown share, duplicates, missingness | `docs/data_audit.md` |

## Findings that shape later gates

- Chicago reported 0 unknown lines in 2022 and 251,569 in 2024; about 259,000 lines moved from
  presumed lead to Unknown. The app must say Unknown means "possibly lead until verified".
- 5,050 Chicago classifications cite "Home Built Date". Gate 2 must test the model with and
  without these lines so year built does not leak the label.
- The Chicago file has no PIN or diameter, so matching is by address. Diameter can only be
  studied in East Dundee (85 lines).

## Cut or deferred

- An official DWM export (FOIA to the Department of Water Management) is drafted but not yet
  filed; the FOIA copy is used meanwhile. The filing date and tracking number go on #7 when
  available.
- The CDC childhood blood lead data URL returned 403; it was not needed for Gates 0–1.
