# Model card: Lead Line Lens LightGBM v1

Signed off with Gate 2, 5 November 2026. Retrain and revise this card when the inventory
snapshot changes.

## Model details

| | |
|---|---|
| Name | Lead Line Lens customer-side material model |
| Version | v1 |
| Date | 5 November 2026 |
| Author | Pradyumna Kumar |
| Framework | LightGBM 4.7 classifier + sklearn isotonic calibration |
| Training data | Chicago DWM inventory snapshot 14 April 2025, joined to Cook County Assessor building characteristics and ACS 2020-2024 tract attributes |
| Artifacts | `models/lll_lightgbm_v1.pkl`, `models/calibrator_v1.pkl` (gitignored; rebuild with `python scripts/train_model.py`) |

## Intended use

Help residents and organizers interpret an **Unknown** customer-side record: the model
returns a calibrated probability that the customer's side is lead or galvanized requiring
replacement, a confidence tier, and three plain-language reasons.

**Prohibited uses**

- Regulatory reclassification without a verification method the Illinois EPA accepts.
- Deprioritizing any block, ward, or address because the predicted probability is low.
- Medical advice.

A prediction **never lowers urgency**. Unknown always displays as "possibly lead until
verified", including when the model is confident the line is not lead.

## Data

Training rows are customer-side **known** materials only (Lead or GRR = 1, Non-Lead = 0).

| Set | Rows | Lead or GRR |
|---|---|---|
| Known customer-side | 220,462 | 58.1% |
| Held out: customer class from "Home Built Date" | 4,770 | 0% (all Non-Lead; 89% built 1986 or later) |
| **Used to fit v1** | **215,692** | **59.4%** (128,026 positive) |
| Customer-side still Unknown (scored, not trained) | 271,243 | — |

Geographic coverage is Chicago. 3% of training rows have no census block group and are
given unique dummy groups so they do not clump into one validation fold.

**Known biases in what gets verified.** About half of Chicago lines list no verification
method. Field-verified private-side rows dominate the training set (119,463). Lines whose
private-side class came only from the building year were held out so year built cannot
copy the label. Unknowns are not a random sample of known lines: among training rows whose
**utility** side is also Unknown, 91.1% of known customer sides are lead or GRR.

## Features

| Feature | Source | Notes |
|---|---|---|
| year_built | Assessor residential/condo characteristics, exact parcel matches only | Missing for 14% of training rows |
| building_class | Assessor parcel class | 95 values, treated as categorical |
| unit_count | Assessor characteristics | |
| diameter_in | Inventory | Chicago has none; kept for other utilities |
| utility_side_material | Inventory | Strongest input (SHAP). Lead/Non-Lead on the city's side is information the resident already has on the status card |
| install_year | Inventory | 93% missing in Chicago; LightGBM uses missingness itself |
| block_te | Census block lead rate | Out-of-fold smoothed target encoding (smoothing 20) |
| nbr_lead_share_k10, nbr_known_count_k10 | 10 nearest known lines within 100 m | Leave-one-out: a row never sees its own label |
| block_lead_share_loo | Other known lines on the same block | Leave-one-out |
| dist_nearest_nonlead_m | Nearest other known Non-Lead line | |
| tract_unknown_rate | Share Unknown in the tract | For a known training row this is other lines, not itself |

Neighbor features are computed from currently known labels. That matches production
scoring of Unknown lines (neighbors are the known ones). It is slightly optimistic as a
CV estimate of a world in which more neighbors were also unknown.

## Training and validation

- **Target.** Customer-side Lead or GRR vs Non-Lead. Binary; a 3-class model is deferred.
- **Exclusion.** Private-side "Home Built Date" rows (4,770) held out of fitting.
- **Imbalance.** LightGBM `is_unbalance=True`.
- **Validation.** 5-fold `GroupKFold` by census block group, so a block group is never in
  both train and test. A shuffled `StratifiedKFold` sanity check is reported alongside.
- **Calibration.** Isotonic regression. Each fold's probabilities are calibrated with an
  isotonic fit that did not see that fold (honest ECE). The saved calibrator is then fit
  on all out-of-fold scores.
- **Hyperparameters.** 300 trees, learning rate 0.05, 31 leaves, min_child_samples 50,
  subsample and colsample 0.8, L2 1.0, seed 0.

## Metrics

Out-of-fold, GroupKFold by block group, after nested calibration. Positive class = lead
or GRR.

| | LightGBM v1 | Pre-1986 rule | Block majority (OOF rate / vote) |
|---|---|---|---|
| PR-AUC | **0.960** | 0.697 | 0.602 |
| ROC-AUC | 0.959 | 0.683 | 0.533 |
| Balanced accuracy | **0.916** | 0.683 | 0.533 |
| Brier | 0.060 | 0.258 | 0.381 |
| ECE (10 equal-width bins) | **0.001** (0.024 before calibration) | 0.258 | 0.381 |
| False non-lead rate | 0.029 | 0.003 | 0.006 |
| False lead rate | 0.139 | 0.631 | 0.928 |

Lift vs block majority PR-AUC: **+0.357** (gate: ≥ 0.05). Lift vs pre-1986 balanced
accuracy: **+0.233** (gate: ≥ 0.05, i.e. 5 points). Random-fold PR-AUC is 0.962, 0.002
above the grouped fold, so grouping is not hiding a large spatial leak.

Confusion matrix at 50% (OOF): 124,302 true lead/GRR, 3,724 missed lead/GRR, 75,480 true
non-lead, 12,186 false lead/GRR.

Reliability diagram: [`docs/figures/reliability_v1.png`](figures/reliability_v1.png).
SHAP summary: [`docs/figures/shap_summary_v1.png`](figures/shap_summary_v1.png).
Confusion matrix: [`docs/figures/confusion_v1.png`](figures/confusion_v1.png).

**Slice the gate cares about less, and residents more.** When the **utility side is also
Unknown** (117,946 training rows, 91.1% lead/GRR — the situation of most lookups):

| | LightGBM | Block rate | Pre-1986 |
|---|---|---|---|
| PR-AUC | 0.965 | 0.910 | |
| ROC-AUC | 0.764 | | |
| Balanced accuracy | 0.547 | | 0.503 |

PR-AUC stays high because the positive rate is 91%. Discrimination is modest (ROC 0.76,
balanced accuracy 0.55). The model mostly predicts lead, which matches the product rule
that Unknown never becomes "safe". Among 271,243 currently unknown customer-side lines
the mean predicted probability is 0.83 (median 0.89).

Home Built Date hold-out (4,770 Non-Lead rows, never trained on): mean predicted
probability 0.07. Year built still flags post-1986 buildings as non-lead without having
copied those labels.

## Disaggregated performance

False non-lead rate = share of actual lead/GRR predicted as non-lead at 50%. Lower is
safer. Groups with fewer than 5 positives or 5 negatives are not shown.

| Group | n | Lead/GRR share | PR-AUC | False non-lead | False lead |
|---|---|---|---|---|---|
| Q1 lowest income | 38,412 | 63.6% | 0.942 | 3.1% | 20.4% |
| Q2 | 50,314 | 69.9% | 0.965 | 2.7% | 18.8% |
| Q3 | 55,645 | 65.4% | 0.966 | 2.4% | 16.0% |
| Q4 highest income | 62,070 | 48.5% | 0.958 | 3.4% | 9.9% |
| Majority Black | 66,472 | 70.8% | 0.962 | 2.0% | 21.6% |
| Majority Latino | 40,400 | 70.9% | 0.965 | 3.4% | 20.0% |
| Majority White | 66,189 | 49.9% | 0.959 | 3.4% | 10.0% |
| Majority Asian | 1,764 | 29.1% | 0.876 | 4.3% | 7.1% |
| No majority | 33,786 | 53.4% | 0.947 | 3.1% | 13.5% |

False **non-lead** is not higher in lower-income or majority-Black/Latino tracts than in
the reference groups (Q4, majority White). The brief's rule to raise the non-lead
confidence bar for those tracts is **not triggered**. False **lead** is higher in Q1 and
majority-Black/Latino tracts, which is the safer direction (the model over-calls lead
where need is already high).

Confidence tiers (unchanged): High if p ≥ 0.85 or p ≤ 0.15; Moderate if 0.65–0.85 or
0.15–0.35; otherwise Low.

## Limitations and caveats

- **Unknowns are not random.** Known customer-side rows with an unknown utility side are
  91% lead/GRR. Performance on that slice should be read as "the model agrees they are
  probably lead", not as proof it can find the non-lead needles.
- **Utility-side material dominates SHAP.** When both sides are unknown, that feature is
  the value "Unknown" and the model falls back to year built, install-year missingness,
  and neighbors.
- **Verified records skew.** Field verification is uneven across the city. Neighbor
  features spread that pattern to nearby unknowns.
- **No diameter in Chicago.** The column is always missing here.
- **Install year is 93% missing.** Its SHAP value is largely "missing vs present".
- **Transfer to other systems is unproven.** The utility edition applies this Chicago
  model when an upload has fewer than 200 known customer-side rows, and always warns
  that the scores are not a verification. With 200 or more known rows it fits a new
  in-memory model on that inventory and does not write a pickle.
- **One snapshot.** Lines verified or replaced after 14 April 2025 are not in the labels.
- **Not a replacement for digging.** A high probability is not an inspection.

## Maintenance

Retrain when a new inventory snapshot lands:

```bash
python scripts/build_master.py
python scripts/train_model.py
```

That writes new `models/lll_lightgbm_v1.pkl` and `calibrator_v1.pkl`, refreshes the
figures, scores Unknown rows, and updates the disparity CSVs so ward scorecards show
predicted lead among unknowns. Bump the version string in `lll.train.MODEL_VERSION` and
edit this card. Contact: the repository owner listed in `pyproject.toml`.
