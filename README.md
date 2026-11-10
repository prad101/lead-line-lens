# Lead Line Lens

Decode your water utility's lead service line inventory.

Lead Line Lens is a free web application that turns a water utility's published lead service line inventory into answers a resident can act on. A user enters an address and sees the recorded status of the utility-side and customer-side service line: lead, galvanized requiring replacement, non-lead, or unknown. Where the record says unknown, the app shows a predicted material with a confidence level, produced by a LightGBM model trained on the inventory's own known records using year built, block, the statuses of neighboring lines, and pipe diameter. The app then explains in plain language what to do now, drafts a verification and prioritization request to the utility, and produces ward and tract level disparity reports by income and race along with a one-page scorecard for the alderman.

Chicago is the launch city and the demo dataset (roughly 400,000 lead service lines). The engine is utility-agnostic: any system's inventory CSV or XLSX can be uploaded, mapped to a standard schema, and run through the same pipeline.

Built by Pradyumna Kumar as a ChiEAC Fellow (Chicago Education Advocacy Cooperative).

- [Methodology](docs/methodology.md) · [Model card](docs/model_card.md) · [Data dictionary](docs/data_dictionary.md) · [Data audit](docs/data_audit.md) · [Gate summaries](docs/gates/)

## Timeline: eight weeks, six gates

The project runs Monday, September 21 through Friday, November 13, 2026. A gate closes when its benchmarks are met and a summary is committed under [docs/gates](docs/gates/).

| Week | Focus | Benchmarks | Gate |
|---|---|---|---|
| 1 (Sep 21–25) | Foundations and data acquisition | Repo, Docker dev env, CI lint+test running; Chicago inventory (or records request filed), two small Illinois inventories, Cook County parcels, ACS tables, boundaries downloaded and documented; data dictionary covers 100% of inventory columns; half-page note on federal and state compliance dates | Gate 0: data in hand and documented |
| 2 (Sep 28–Oct 2) | Address matching and spatial joins | ≥95% of inventory rows matched to a parcel or geocoded; 100% of matched rows assigned block, tract, ward, community area; EDA notebook answers five questions | Gate 1: master table approved |
| 3 (Oct 5–9) | Model version 1 | Both baselines recorded; LightGBM beats block majority by ≥0.05 PR-AUC and the pre-1986 rule by ≥5 points balanced accuracy under GroupKFold; ECE ≤0.05 after calibration, Brier reported; error rates by income quartile and majority race/ethnicity | Gate 2: model card signed off |
| 4 (Oct 12–16) | FastAPI backend | Lookup, predict, area, letter, scorecard return in <2 s at p95 locally; OpenAPI docs complete; pytest coverage ≥70% on service modules; Docker image builds and runs; staging URL live | Gate 3: API live on staging |
| 5 (Oct 19–23) | Resident-facing front end | Address → status card → prediction → survey → guidance → letter in ≤5 clicks; 375 px layout, WCAG AA contrast; guidance text ≤8th-grade reading level (textstat); every health statement has a source link | Gate 4: MVP demonstrated |
| 6 (Oct 26–30) | Equity report and ward scorecards | Disparity report for all 50 wards and every tract with ≥5 lines, suppression enforced and tested; scorecard PDF for every ward; three sample scorecards reviewed externally | Gate 5: equity outputs approved |
| 7 (Nov 2–6) | Utility edition, user testing, v1.0 | Upload → mapping → classification → sampling plan → export on two non-Chicago Illinois inventories; five resident test sessions logged, top five issues fixed; error monitoring and uptime check on; v1.0 tagged and deployed | Gate 6: v1.0 public launch |
| 8 (Nov 9–13) | Buffer and handoff (no new features) | Zero open critical/high bugs; README, deployment runbook, data dictionary complete; handoff call; demo video; hard stop Friday Nov 13 | Project closed |

## Repository layout

```
src/lll/        pipeline and service modules (schema, ingest, geocode, features, train,
                predict, equity, letters, scorecard, utility)
api/            FastAPI app and routers (Appendix B endpoints)
app/            Streamlit front end
templates/      Jinja2 letter, scorecard, and methods-memo templates
notebooks/      audit, matching/EDA, model experiments
docs/           data dictionary, data audit, model card, methodology, gate summaries
data/raw/       downloads (gitignored)
data/processed/ parquet master table (gitignored)
models/         versioned model artifacts (gitignored)
```

## Development

Requires Python 3.11. The project uses the conda env `lead`.

```bash
conda activate lead
pip install -e ".[dev]"
ruff check .
pytest --cov
uvicorn api.main:app --reload --no-access-log   # http://localhost:8000/docs
streamlit run app/streamlit_app.py              # http://localhost:8501
```

### Build the master table

Download the sources listed in [docs/data_dictionary.md](docs/data_dictionary.md) into `data/raw/`, then:

```bash
python scripts/build_master.py          # writes data/processed/master_chicago_<snapshot>.parquet
```

The first run calls the Census Geocoder for unmatched addresses (about 9 minutes); later runs reuse the cached result. See [Gate 1](docs/gates/gate1.md) for the matching rate and EDA.

### Build the disparity report and scorecards

```bash
python scripts/build_equity.py          # ACS join, tract/ward tables, CSVs in data/processed/equity_chicago_<snapshot>/
python -m lll.scorecard                 # 50 ward PDFs in data/processed/scorecards_chicago_<snapshot>/
```

`build_equity.py` reads the Census API key from `CENSUS_API_KEY` on the first run and caches the ACS tables; add `--refresh-acs` to download again. The Streamlit report and scorecard pages and `GET /scorecard/ward/{ward}.pdf` read these outputs. See [Gate 5](docs/gates/gate5.md) and the [methodology](docs/methodology.md).

### Train the model

```bash
python scripts/train_model.py           # writes models/lll_lightgbm_v1.pkl and calibrator_v1.pkl
```

About 30 seconds after the master table exists. See the [model card](docs/model_card.md) and [Gate 2](docs/gates/gate2.md).

On macOS, WeasyPrint needs Pango. Either `brew install pango`, or install it into the conda env (`conda install -c conda-forge pango`) and set `WEASYPRINT_DLL_DIRECTORIES=$CONDA_PREFIX/lib`. LightGBM needs OpenMP (`conda install -c conda-forge llvm-openmp`).

### Utility edition

The Streamlit **Utility edition** page uploads a CSV/XLSX (in memory only), maps columns, scores unknown lines, draws a 60-line stratified verification sample, and exports an Illinois EPA template plus a methods memo. With 200 or more known customer-side rows it fits a fresh model; otherwise it uses the Chicago model and shows a transfer warning. Turn it off with `LLL_UTILITY_EDITION=0`. Demo buttons load Burnham and East Dundee from `data/raw/small_systems/`.

### Docker

```bash
docker compose up --build   # API on :8000, Streamlit on :8501
```

Compose mounts `./data` and `./models` read-only. The image does not bake in the gitignored parquet or `.pkl` files. `GET /health` stays cheap and does not load the inventory.

### CI

GitHub Actions runs `ruff check` and `pytest` on every push ([.github/workflows/ci.yml](.github/workflows/ci.yml)). To make a failing check block merges, enable branch protection on `main` (Settings → Branches → require the `lint-test` status check).

## Hosting

Staging and production deploy to **Render** (one Docker web service for the API, one for Streamlit). Chosen once; not switching.

The gitignored inventory and model are **not** in the image. Attach one persistent disk and point the env vars at it:

| Env | Example on the disk | Contents |
|---|---|---|
| `LLL_DATA_DIR` | `/persist/data` | `processed/master_chicago_*.parquet`, `equity_chicago_*/*.csv`, scorecard PDFs |
| `LLL_MODEL_DIR` | `/persist/models` | `lll_lightgbm_v1.pkl`, `calibrator_v1.pkl` |

Copy those files onto the disk once after the first deploy. Until then, `/health` is 200 and lookup/predict/area/scorecard return 503. Start the API with `--no-access-log` (already the Docker `CMD`) so address query strings are not logged.

The staging URL is created on the first Render deploy ([#29](https://github.com/prad101/lead-line-lens/issues/29)).

## Privacy

No address, survey response, or letter is written to disk, a database, or logs. The API runs with the access log disabled because lookup query strings contain addresses. No third-party analytics; Streamlit usage stats are off.

## License

See [LICENSE](LICENSE). Terms are finalized under the ChiEAC fellowship agreement.
