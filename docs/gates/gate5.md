# Gate 5: Equity outputs approved (Week 6)

**Status:** built and tested Nov 4, 2026 (planned Oct 30). The gate closes when the three
earmarked scorecards below have been reviewed externally (#37).

## Delivered

- `lll.equity`: tract and ward tables (counts and shares by status, needs-action share,
  replaced), ACS 2020-2024 join (income, race and ethnicity, children under 6, pre-1950
  housing), ward demographics by area apportionment, pooled rates by income quartile and
  majority group, disparity ratios, CSV export, and folium choropleths. Every table passes
  through `suppress_small_cells` (fewer than 5 lines: all counts and shares blank).
- `scripts/build_equity.py`: one command builds the ACS cache and
  `data/processed/equity_chicago_20250414/{tract,ward,income_quartiles,majority_group,disparity_ratios}.csv`
  (about 2 seconds after the first ACS download).
- `lll.scorecard` + `templates/scorecard.html`: `python -m lll.scorecard` renders all 50
  one-page ward PDFs with WeasyPrint (about 13 seconds, 4.0 MB) into
  `data/processed/scorecards_chicago_20250414/`. Each has the needs-action share, rank, status
  counts, a hexbin map, the eight hundred-blocks with the most lines to act on, ward facts,
  what residents can do (with source links), and sources. "Predicted lead among unknown
  lines" reads "Pending model v1" until Gate 2.
- `GET /scorecard/ward/{ward}.pdf` returns the PDF (503 if the report has not been built).
- Streamlit `report` page: ward or tract choropleth for four measures, income-quartile and
  majority-group tables, and CSV downloads for all five tables. Streamlit `scorecards` page:
  ward picker, key numbers, PDF download, all-50 zip, and a ranked table of all wards.
- `docs/methodology.md`: complete (sources, matching, categories, suppression, disparity
  measures, prediction status, limitations). It is linked from every page footer.
- Tests: 90 passing. New: suppression across the whole disparity report, small tracts kept
  out of group comparisons, ratio arithmetic, ward rank direction, majority rule, area
  apportionment, ACS parsing and key hiding, choropleth grey fill, scorecard HTML, suppressed
  ward, one-page PDF, API route, and footer on every page.

## Benchmarks measured

| Benchmark | Target | Result |
|---|---|---|
| Disparity report (#35) | all 50 wards and every tract with ≥5 lines; suppression enforced and tested | 50 of 50 wards; 799 of 811 tracts published, 12 suppressed; `tests/test_suppression.py` fails on any published cell under 5 or any suppressed cell with a number |
| Scorecard PDF for every ward (#36) | automatic | 50 of 50, one page each, from one command |
| Three scorecards reviewed externally (#37) | 3 reviews | **pending**: Wards 9, 22, 42 earmarked (below) |
| Disparity report page with CSV downloads (#38) | page live | `app/pages/report.py`, 5 CSVs |
| Methodology linked from every footer (#39) | every page | 5 of 5 pages; `tests/test_footer.py` |

## Findings (April 14, 2025 snapshot)

- Citywide, 85% of lines located in a ward are lead, galvanized, or unknown.
- **Income:** in the lowest-income quarter of tracts it is 88.6%; in the highest-income
  quarter, 74.3% (ratio 1.19). The gap is mostly Unknown lines (54.8% vs 45.0%), and lines in
  lower-income tracts are also replaced more often so far (2.6% vs 1.8%).
- **Race and ethnicity:** majority-Latino tracts 92.2% and majority-Black tracts 89.9%,
  against 75.2% in majority-White tracts (ratios 1.23 and 1.20). Majority-Latino tracts have
  the highest Unknown share (60.8%).
- **Wards:** Ward 18 ranks 1 (96%), followed by Wards 9, 31, 8, and 14. Ward 42 ranks 50
  (29%). Nine of the ten highest-need wards are on the South and Southwest Sides (Ward 31 is
  on the Northwest Side); all ten are majority Black or Latino, or have no majority.

## Scorecards earmarked for external review (#37)

| Ward | Why this one | Suggested reviewer |
|---|---|---|
| 9 (Far South Side) | Rank 2 of 50 (95%); majority Black; lowest income of the top five; most confirmed lead of any top-five ward (6,909 lines) | Ward 9 office |
| 22 (Little Village) | Rank 6 (94%); majority Latino; 66% Unknown, the hardest test of the "possibly lead until checked" wording | A community organization in Little Village |
| 42 (Loop, Streeterville) | Rank 50 (29%); mostly high-rises, only 1,241 lines; tests how the card reads when the news is mostly good | A reporter who covered the inventory (Inside Climate News, Grist, or WBEZ) |

Each reviewer gets the PDF and three questions: Is anything confusing or misleading? Is
anything missing that a resident would need? Would you share it? Responses and changes are
logged on #37.

## Cut or deferred

- Predicted lead among unknown lines: filled by Gate 2 (`scripts/train_model.py` refreshes
  the equity CSVs). PDFs need `python -m lll.scorecard` after a retrain.
- ACS margins of error are not shown; listed under limitations.
- The Streamlit pages read processed files directly; they switch to `GET /area` with Gate 3.
