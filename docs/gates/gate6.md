# Gate 6: Version 1.0 public launch (Week 7)

**Status:** utility edition complete locally 9 November 2026 (planned 6 November).
Public v1.0 URL, user-test log, and error monitoring remain operator steps.

## Delivered

- `lll.utility`: in-memory classify (fresh LightGBM if ≥200 known customer-side rows
  of both classes; otherwise Chicago model + transfer warning), fixed-size stratified
  sample (60 unknown lines by year-built band and city-side material), Illinois EPA
  template CSV (recorded materials unchanged; predictions in extra columns), methods
  memo. Uploads are never written to disk.
- API: `POST /utility/upload|map|classify|sample-plan|export` with an in-memory job
  id. Feature flag `LLL_UTILITY_EDITION` (default on). 403 when off.
- Streamlit utility page: Burnham and East Dundee demos, CSV/XLSX upload, column
  mapping, score, sample, export. Hidden from the home page when the flag is off.
- Model card notes the transfer rule. Tests cover fresh vs transfer, sample contents,
  export ethics, memo language, API round-trip, and both small Illinois systems.

## Benchmarks measured

Burnham IL0310360 (1,208 lines, 1,116 known) and East Dundee IL0890250
(1,497 lines, 1,367 known). Both fit a fresh in-memory model.

| Benchmark | Target | Result |
|---|---|---|
| Utility edition on two non-Chicago inventories (#40) | Burnham + East Dundee | Both run end-to-end: map (already canonical), classify, sample, EPA CSV + memo |
| Fresh vs transfer (#40) | ≥200 known → fresh | Encoded in `classify`; synthetic 240 known fits local; <200 uses Chicago with warning |
| Sample plan (#40) | stratified verification | **Fixed n=60** (margin-of-error sizing deferred per cut order) |
| Utility page + methods memo (#44) | page + template | `app/pages/utility.py`, `templates/methods_memo.j2` |
| Feature flag (#45) | resident vs utility | `LLL_UTILITY_EDITION`; home link and API 403 when off |
| Five resident test sessions (#41) | 5 sessions, top 5 fixes | **pending** — no sessions logged this week. **Refs #41 #46.** |
| Error monitoring and uptime (#42) | live check | `/health` is the liveness probe; no third-party APM. **Refs #42.** |
| v1.0 tagged and deployed (#43) | tag + production URL | Code is on `main`. Tag and Render URL need the operator. **Refs #43.** |

## Cut or deferred

- Margin-of-error sample sizing: fixed 60, per the brief's cut order.
- Five resident user tests and a public v1.0 URL.
- Third-party error monitoring (Sentry or similar).
- Writing a new pickle for a utility's fresh model: scores stay in memory so an
  upload cannot overwrite Chicago v1.
