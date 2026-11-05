# Gate 2: Model card signed off (Week 3)

**Status:** met 5 November 2026 (planned 4 November). Real Chicago master table only.

## Delivered

- `lll.train`: training set from known customer-side rows (Lead/GRR vs Non-Lead);
  4,770 private-side "Home Built Date" rows held out; out-of-fold smoothed block target
  encoding; LightGBM with `is_unbalance`; nested isotonic calibration; GroupKFold by
  census block group plus a random-fold check; pre-1986 and block-majority baselines;
  error rates by income quartile and majority group.
- `lll.predict`: calibrated probability, confidence tiers, three SHAP sentences, and the
  hard rule that every prediction still says "Treat this line as lead until it is verified."
- `scripts/train_model.py`: one command fits v1, writes `models/lll_lightgbm_v1.pkl` and
  `models/calibrator_v1.pkl`, figures, Unknown-line scores, and refreshes equity CSVs.
- `notebooks/03_model_experiments.ipynb` (executed).
- `docs/model_card.md` (Appendix C). Figures: `docs/figures/reliability_v1.png`,
  `confusion_v1.png`, `shap_summary_v1.png`.
- Tests: ECE, out-of-fold encoding, Home Built Date hold-out, pre-1986 rule, tiers,
  explanations, and "never lowers urgency" on a synthetic fit.

## Benchmarks measured

All numbers are out-of-fold GroupKFold by block group on 215,692 training rows unless
noted. Full write-up: [model_card.md](../model_card.md).

| Benchmark | Target | Result |
|---|---|---|
| Pre-1986 and block majority recorded (#20) | both baselines | pre-1986 PR-AUC 0.697 / BA 0.683; block PR-AUC 0.602 / BA 0.533 |
| LightGBM vs baselines (#21) | +0.05 PR-AUC vs block; +5 pts BA vs pre-1986 | **PR-AUC 0.960** (+0.357 vs block); **BA 0.916** (+0.233 vs pre-1986) |
| Calibration (#22) | ECE ≤ 0.05; Brier reported | **ECE 0.001** (0.024 before calibration); Brier 0.060 |
| Error rates by income and race (#23) | both reported | `models/error_rates_v1.csv` and the model card; false non-lead is **not** higher in Q1 or majority-Black/Latino tracts than in Q4 / White, so the raised non-lead bar is not applied |
| Training script and artifact (#24) | versioned pickle | `scripts/train_model.py` → `models/lll_lightgbm_v1.pkl` + `calibrator_v1.pkl` |
| Model card (#25) | reliability diagram + SHAP | `docs/model_card.md` with both figures |

Random-fold PR-AUC is 0.962 (grouped 0.960). On the utility-side-Unknown slice (the
lookup case; 91.1% lead/GRR) PR-AUC is 0.965 vs block 0.910, but ROC-AUC is 0.764 and
balanced accuracy 0.547 — the model is conservative, not a sharp non-lead detector.

## Cut or deferred

- 3-class model (Lead vs GRR vs Non-Lead): still binary, per the brief's cut order.
- Diameter: unused in Chicago (100% missing); column kept for other utilities.
- Transfer to Burnham / East Dundee: Gate 6.
