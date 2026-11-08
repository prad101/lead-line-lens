# Gate 4: MVP demonstrated (Week 5)

**Status:** met 8 November 2026 (planned 23 October). Resident lookup talks to the Gate 3
API. Local demo at `http://127.0.0.1:8501/lookup`. Staging URL and a two-minute
recording are the remaining #34 step.

## Delivered

- `app/pages/lookup.py`: address → status card → prediction → five-question survey →
  guidance → letter. Three primary clicks (`Look up this address`, `See what I can do
  today`, `Get a letter you can send`). Session state only; no `st.cache_data` of
  addresses.
- `app/api_client.py`: `GET /lookup`, `POST /predict`, `POST /letter` via `API_URL`.
- `lll.guidance`: plain-language next steps. Unknown always includes "Treat this line
  as lead until it is verified." Every health claim has an HTTPS source (EPA, City of
  Chicago, CDPH).
- Centered 375 px layout; theme contrast ≥ 4.5:1; Streamlit toolbar set to `minimal`.
- Tests: click budget, health sources, grade ≤ 8, unknown never called safe, WCAG AA
  on theme colors, API client 404 handling.

## Benchmarks measured

Checked locally on `64 E 98TH PL, Chicago, IL 60628` (Unknown, Ward 9) at a 375×812
viewport. `document.documentElement.scrollWidth` stayed 375 (no horizontal scroll).

| Benchmark | Target | Result |
|---|---|---|
| Address → letter in ≤5 clicks (#30) | ≤ 5 | **3** primary clicks; status and prediction load with the lookup |
| 375 px + WCAG AA (#31) | 375 px, AA | viewport 375, no overflow; text `#1a1a1a` on `#ffffff` contrast **17.4:1**; primary `#0b5394` on white **7.8:1** |
| Guidance reading level (#32) | ≤ 8th grade | **grade 3.2** (textstat on the full plan + five questions) |
| Health statements sourced (#33) | every health line | EPA (harm, boiling, filters), City of Chicago (test kit, map), CDPH (not medical advice) |
| MVP demo URL and recording (#34) | URL + 2 min video | Local URL verified. Staging URL and recording still need a Render deploy. **Refs #34.** |

## Cut or deferred

- Render / public demo URL and two-minute screen recording (#34).
- Rewiring the report and scorecard pages to `GET /area` and `GET /scorecard`: they
  still read processed files; lookup is the resident MVP.
- Spanish interface and a tenant-specific letter template: cut order.
- Utility edition: Gate 6.
