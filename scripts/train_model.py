"""Train LightGBM v1, write artifacts, figures, and optional unknown-line scores.

    python scripts/train_model.py
    python scripts/train_model.py --no-save-scores
"""

from __future__ import annotations

import argparse

import pandas as pd

from lll import PROCESSED_DIR
from lll.features import latest_master
from lll.predict import predict_frame
from lll.train import (
    KNOWN,
    _customer_home_built,
    _scores,
    score_unknowns,
    train_model,
    write_figures,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-save-scores", action="store_true",
                    help="do not write pred_lead_prob onto a predictions parquet")
    args = ap.parse_args()

    cols = None
    master, snap = latest_master(columns=cols)
    print(f"master {snap}: {len(master):,} lines")

    tract_path = PROCESSED_DIR / f"equity_chicago_{snap}" / "tract.csv"
    tract = pd.read_csv(tract_path, dtype={"tract": str}) if tract_path.exists() else None
    if tract is not None:
        print(f"tract table: {len(tract):,} rows for disaggregated error rates")

    result = train_model(master, tract_table=tract, save=True)
    m, b = result.metrics, result.baselines
    print(f"train n={result.meta['n']:,}  positive={result.meta['n_positive']:,}")
    print(f"  LightGBM  PR-AUC {m['pr_auc']:.3f}  ROC-AUC {m['roc_auc']:.3f}  "
          f"Brier {m['brier']:.3f}  ECE {m['ece']:.3f} (before {m['ece_before']:.3f})")
    print(f"  balanced accuracy {m['balanced_accuracy']:.3f}  "
          f"false non-lead {m['false_nonlead_rate']:.3f}")
    print(f"  pre-1986    PR-AUC {b['pre1986']['pr_auc']:.3f}  "
          f"BA {b['pre1986']['balanced_accuracy']:.3f}")
    print(f"  block maj.  PR-AUC {b['block_majority']['pr_auc']:.3f}  "
          f"BA {b['block_majority']['balanced_accuracy']:.3f}")
    print(f"  lift vs block PR-AUC {m['pr_auc_lift_vs_block']:+.3f}  "
          f"lift vs pre-1986 BA {m['ba_lift_vs_pre1986']:+.3f}")
    print(f"  random-fold PR-AUC {m['pr_auc_random_fold']:.3f}  "
          f"(group fold {m['pr_auc']:.3f})")
    if "pr_auc_utility_unknown" in m:
        print(f"  utility-side Unknown slice n={m['n_utility_unknown']:,}  "
              f"prevalence {m['prevalence_utility_unknown']:.1%}  "
              f"PR-AUC {m['pr_auc_utility_unknown']:.3f} "
              f"(block {m['pr_auc_block_utility_unknown']:.3f})  "
              f"ROC-AUC {m['roc_auc_utility_unknown']:.3f}  "
              f"BA {m['balanced_accuracy_utility_unknown']:.3f} "
              f"(pre-1986 {m['ba_pre1986_utility_unknown']:.3f})")
    if result.by_group is not None:
        show = result.by_group[["grouping", "group", "n", "false_nonlead_rate", "pr_auc"]]
        print(show.to_string(index=False))
        print("conservative groups:", result.meta["conservative_groups"] or "(none)")
    print(f"saved {result.model_path} and {result.calibrator_path}")

    for p in write_figures(result):
        print(f"  figure {p.name}")

    known = master["customer_side_material"].astype(str).isin(KNOWN)
    hbd = known & _customer_home_built(master["verification_method"])
    if hbd.any():
        y_hbd = master.loc[hbd, "customer_side_material"].isin(("Lead", "GRR")).astype(int)
        p_hbd = predict_frame(master.loc[hbd], result.meta)
        n_pos = int(y_hbd.sum())
        print(f"Home Built Date holdout n={int(hbd.sum()):,}  lead/GRR labels {n_pos}  "
              f"mean predicted {float(p_hbd.mean()):.2f}  "
              "(held out of training so year built does not copy the label)")
        if n_pos >= 5 and int((1 - y_hbd).sum()) >= 5:
            hs = _scores(y_hbd.to_numpy(), p_hbd.to_numpy())
            print(f"  PR-AUC {hs['pr_auc']:.3f}  false non-lead {hs['false_nonlead_rate']:.3f}")

    if not args.no_save_scores:
        pred = score_unknowns(master, result)
        out = PROCESSED_DIR / f"pred_lead_prob_chicago_{snap}.parquet"
        pd.DataFrame({"line_id": master["line_id"] if "line_id" in master else master.index,
                      "pred_lead_prob": pred}).to_parquet(out, index=False)
        print(f"scored {int(pred.notna().sum()):,} unknown customer-side lines -> {out.name}")
        _refresh_equity(master, pred, snap, tract)


def _refresh_equity(master: pd.DataFrame, pred: pd.Series, snap: str, tract) -> None:
    """Rewrite the ward/tract CSVs so scorecards can show predicted lead among unknowns."""
    if tract is None:
        return
    from lll import sources
    from lll.equity import ACS_YEAR, disparity_report, export_csvs, fetch_acs, ward_acs

    scored = master.copy()
    scored["pred_lead_prob"] = pred.to_numpy()
    acs = fetch_acs(cache=PROCESSED_DIR / f"acs_{ACS_YEAR}_cook_tracts.parquet")
    ward_cache = PROCESSED_DIR / f"acs_{ACS_YEAR}_wards.parquet"
    wacs = pd.read_parquet(ward_cache) if ward_cache.exists() else ward_acs(
        acs, sources.tracts(), sources.wards())
    report = disparity_report(scored, acs, wacs)
    export_csvs(report, PROCESSED_DIR / f"equity_chicago_{snap}")
    n = int(report["ward"]["pred_lead_share_unknown"].notna().sum())
    print(f"updated equity CSVs with predicted lead among unknowns ({n} wards)")


if __name__ == "__main__":
    main()
