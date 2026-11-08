# Gate 3: API live on staging (Week 4)

**Status:** API complete locally 7 November 2026 (planned 16 October). Staging URL
is the remaining deploy step (#29).

## Delivered

- Process cache (`api/store.py`): master table, equity CSVs, and model loaded once
  per (path, mtime) fingerprint. A new snapshot or a retrain is picked up on the next
  request. Resident addresses are never written here. `GET /health` does not load the
  inventory.
- `GET /lookup`: normalized address, snapshot, recorded utility- and customer-side
  material, verification method, replacement, geographies. Unknown rows include
  "Treat this line as lead until it is verified." 400 / 404 / 503 documented.
- `POST /predict`: address or a feature dict. Known Lead/GRR/Non-Lead skip the model
  and return the record. Unknown always returns the treat-as-lead message; a prediction
  never lowers urgency.
- `GET /area/{level}/{id}`: ward/tract (and other area files when present). Cells
  under 5 lines pass through as nulls with `suppressed: true`.
- `POST /letter`: Jinja2 verification request (grade ≤ 8), in-memory `.docx`, mailto
  with empty recipient so the resident picks the inbox. Still renders if the inventory
  is missing.
- `GET /scorecard/ward/{ward}.pdf`: already from Gate 5.
- Utility edition routes stay 501 until Gate 6, with 501 documented in OpenAPI.
- Tests: lookup/predict/area/letter, store fingerprint reset, letter reading level,
  OpenAPI lists every Appendix B path.

## Benchmarks measured

Local `TestClient` against the April 14, 2025 Chicago master (491,705 lines) after a
warm store load (0.22 s). Sample address `64 E 98TH PL` (Unknown).

| Benchmark | Target | Result |
|---|---|---|
| Latency p95 locally (#26) | < 2 s | **lookup 10 ms; predict 612 ms; area 2 ms; letter 58 ms; scorecard PDF 751 ms** |
| OpenAPI complete (#27) | every Appendix B path | `/openapi.json` lists lookup, predict, area, letter, scorecard, and the five utility stubs; error responses documented |
| pytest coverage on service modules (#28) | ≥ 70% | **77%** on `src/lll` + `api` (`pytest --cov`) |
| Docker image builds and staging URL (#29) | image + live URL | Dockerfile and compose are ready; `./data` and `./models` mount read-only. Docker Desktop is not installed on this machine, and the Render URL needs a first deploy. **Refs #29.** |

Predict p95 includes the first SHAP `TreeExplainer` build (~1.1 s); later calls are
around 120 ms mean. Access log is off (`--no-access-log`) so lookup query strings are
not written.

## Cache

The model and lookup table live in the **API process**, keyed on file mtimes, not in
Streamlit cache. Streamlit `@st.cache_data` stays on the report and scorecard pages
until Gate 4 rewires those pages to `GET /area` and `GET /scorecard`.

Render needs a persistent disk: `LLL_DATA_DIR` for the parquet and equity CSVs,
`LLL_MODEL_DIR` for the two `.pkl` files. Those paths are gitignored and are not
copied into the image.

## Cut or deferred

- Render staging URL: first deploy by the operator (#29).
- Streamlit lookup MVP: Gate 4.
- Utility upload/map/classify/sample/export: Gate 6 (501).
- Server-side storage of addresses, surveys, or letters: never.
