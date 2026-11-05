"""Train, validate, and calibrate the LightGBM service line material model.

Target: customer-side Lead or GRR (1) vs Non-Lead (0), trained on known rows only.
Rows whose customer-side class was assigned from "Home Built Date" are held out of
training so year built does not copy the label. Validation is GroupKFold by census
block group, plus a random-fold sanity check. Baselines: pre-1986 rule and block
majority vote.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold, StratifiedKFold

from lll import MODEL_DIR, PROCESSED_DIR

FEATURES: tuple[str, ...] = (
    "year_built",
    "building_class",
    "unit_count",
    "diameter_in",
    "utility_side_material",
    "install_year",
    "block_te",
    "nbr_lead_share_k10",
    "nbr_known_count_k10",
    "block_lead_share_loo",
    "dist_nearest_nonlead_m",
    "tract_unknown_rate",
)
CATEGORICAL: tuple[str, ...] = ("building_class", "utility_side_material")
LEAD_LIKE: tuple[str, ...] = ("Lead", "GRR")
KNOWN: tuple[str, ...] = ("Lead", "GRR", "Non-Lead")
HOME_BUILT_CUSTOMER = "PR: Home Built Date"
BAN_YEAR = 1986
SMOOTHING = 20.0
MODEL_VERSION = "v1"
N_BINS = 10

DEFAULT_PARAMS: dict = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 50,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "is_unbalance": True,
    "n_jobs": -1,
    "random_state": 0,
    "verbose": -1,
}


@dataclass
class TrainResult:
    metrics: dict[str, float] = field(default_factory=dict)
    baselines: dict[str, dict[str, float]] = field(default_factory=dict)
    by_group: pd.DataFrame | None = None
    model_path: Path | None = None
    calibrator_path: Path | None = None
    oof: pd.DataFrame | None = None
    meta: dict = field(default_factory=dict)


def _customer_home_built(method: pd.Series) -> pd.Series:
    return method.fillna("").astype(str).str.contains(HOME_BUILT_CUSTOMER, regex=False)


def make_training_set(
    master: pd.DataFrame,
    exclude_home_built_date: bool = True,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return (X, y, groups) from known customer-side rows.

    y is 1 for Lead or GRR, 0 for Non-Lead. groups is census block group; rows with
    no block group get a unique dummy group so they do not clump into one fold.
    X keeps `block` and `tract` for encoding and disaggregated metrics; they are not
    passed to LightGBM.
    """
    df = master.loc[master["customer_side_material"].astype(str).isin(KNOWN)].copy()
    if exclude_home_built_date and "verification_method" in df.columns:
        df = df.loc[~_customer_home_built(df["verification_method"])]
    df = df.reset_index(drop=True)
    y = df["customer_side_material"].isin(LEAD_LIKE).astype(int)
    groups = df["block_group"].astype("string") if "block_group" in df else pd.Series(
        pd.NA, index=df.index, dtype="string")
    miss = groups.isna()
    if miss.any():
        groups = groups.copy()
        groups.loc[miss] = [f"__na_{i}" for i in range(int(miss.sum()))]
    keep = [c for c in FEATURES if c != "block_te" and c in df.columns]
    extra = [c for c in ("block", "tract", "verification_method") if c in df.columns]
    X = df[keep + extra].copy()
    X["block_te"] = np.nan
    for c in FEATURES:
        if c not in X.columns:
            X[c] = np.nan
    return X, y, groups.astype(str)


def block_target_encoding(
    blocks: pd.Series, y: pd.Series, folds: np.ndarray, smoothing: float = SMOOTHING
) -> pd.Series:
    """Out-of-fold smoothed target encoding of census block.

    Value for a row uses only other folds: (n * block_mean + m * fold_mean) / (n + m).
    Unseen blocks get the training-fold global mean.
    """
    blocks = pd.Series(blocks).astype("string").reset_index(drop=True)
    y = pd.Series(y, dtype=float).reset_index(drop=True)
    folds = np.asarray(folds)
    out = np.full(len(y), np.nan)
    for f in np.unique(folds):
        tr = folds != f
        gmean = float(y[tr].mean()) if tr.any() else float(y.mean())
        stats = y[tr].groupby(blocks[tr], dropna=False).agg(["sum", "count"])
        enc = (stats["sum"] + smoothing * gmean) / (stats["count"] + smoothing)
        mapped = blocks[folds == f].map(enc)
        out[folds == f] = pd.to_numeric(mapped, errors="coerce").fillna(gmean).to_numpy()
    return pd.Series(out)


def _full_block_encoding(
    blocks: pd.Series, y: pd.Series, smoothing: float = SMOOTHING
) -> tuple[pd.Series, float]:
    gmean = float(pd.Series(y, dtype=float).mean())
    stats = pd.Series(y, dtype=float).groupby(
        pd.Series(blocks).astype("string"), dropna=False).agg(["sum", "count"])
    enc = (stats["sum"] + smoothing * gmean) / (stats["count"] + smoothing)
    return enc.astype(float), gmean


def baseline_pre1986(df: pd.DataFrame) -> np.ndarray:
    """Predict lead when year built < 1986; missing year is treated as lead."""
    year = pd.to_numeric(df["year_built"], errors="coerce")
    return np.where(year.isna(), 1.0, (year < BAN_YEAR).astype(float))


def baseline_block_majority(df: pd.DataFrame, folds: np.ndarray) -> np.ndarray:
    """Out-of-fold block majority vote (1 if the training-fold block lead rate >= 0.5)."""
    if "y" not in df.columns:
        raise ValueError("baseline_block_majority needs a 'y' column")
    blocks = df["block"].astype("string") if "block" in df.columns else pd.Series(
        "__none__", index=df.index)
    y = pd.Series(df["y"], dtype=float).reset_index(drop=True)
    blocks = blocks.reset_index(drop=True)
    folds = np.asarray(folds)
    out = np.zeros(len(y), dtype=float)
    for f in np.unique(folds):
        tr = folds != f
        rate = y[tr].groupby(blocks[tr], dropna=False).mean()
        vote = (rate >= 0.5).astype(float)
        gmaj = float(y[tr].mean() >= 0.5)
        mapped = blocks[folds == f].map(vote)
        out[folds == f] = pd.to_numeric(mapped, errors="coerce").fillna(gmaj).to_numpy()
    return out


def baseline_block_rate(df: pd.DataFrame, folds: np.ndarray) -> np.ndarray:
    """Out-of-fold block lead rate; the probabilistic form of majority vote."""
    if "y" not in df.columns:
        raise ValueError("baseline_block_rate needs a 'y' column")
    blocks = df["block"].astype("string") if "block" in df.columns else pd.Series(
        "__none__", index=df.index)
    y = pd.Series(df["y"], dtype=float).reset_index(drop=True)
    blocks = blocks.reset_index(drop=True)
    folds = np.asarray(folds)
    out = np.zeros(len(y), dtype=float)
    for f in np.unique(folds):
        tr = folds != f
        rate = y[tr].groupby(blocks[tr], dropna=False).mean()
        gmean = float(y[tr].mean())
        mapped = blocks[folds == f].map(rate)
        out[folds == f] = pd.to_numeric(mapped, errors="coerce").fillna(gmean).to_numpy()
    return out


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = N_BINS) -> float:
    """Equal-width-bin ECE. Target <= 0.05 after calibration."""
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins = np.digitize(p, edges[1:-1], right=True)
    ece = 0.0
    n = len(y)
    if n == 0:
        return float("nan")
    for b in range(n_bins):
        m = bins == b
        if not m.any():
            continue
        ece += (m.sum() / n) * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(ece)


def _scores(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    pred = (np.asarray(p) >= 0.5).astype(int)
    y = np.asarray(y).astype(int)
    return {
        "pr_auc": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "ece": expected_calibration_error(y, p),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "false_nonlead_rate": float(((y == 1) & (pred == 0)).sum() / max((y == 1).sum(), 1)),
        "false_lead_rate": float(((y == 0) & (pred == 1)).sum() / max((y == 0).sum(), 1)),
    }


def model_matrix(frame: pd.DataFrame, categories: dict | None = None) -> pd.DataFrame:
    """Feature frame in FEATURES order, categoricals aligned to training levels."""
    M = pd.DataFrame(index=frame.index)
    for c in FEATURES:
        M[c] = frame[c] if c in frame.columns else np.nan
    for c in CATEGORICAL:
        s = M[c].astype("string")
        M[c] = pd.Categorical(s, categories=categories[c]) if categories and c in categories \
            else s.astype("category")
    for c in FEATURES:
        if c not in CATEGORICAL:
            M[c] = pd.to_numeric(M[c], errors="coerce").astype("float64")
    return M


def _lgbm(n: int, seed: int):
    import lightgbm as lgb

    params = {**DEFAULT_PARAMS, "random_state": seed}
    if n < 2000:
        params.update(n_estimators=80, min_child_samples=5, num_leaves=8, n_jobs=1)
    return lgb.LGBMClassifier(**params)


def _idx(mask: np.ndarray) -> np.ndarray:
    return np.flatnonzero(mask)


def _fit_fold(X: pd.DataFrame, y: pd.Series, tr: np.ndarray, categories: dict, seed: int):
    ii = _idx(tr)
    model = _lgbm(len(ii), seed)
    model.fit(model_matrix(X.iloc[ii], categories), y.iloc[ii])
    return model


def group_error_rates(y: np.ndarray, p: np.ndarray, labels: pd.Series, name: str) -> pd.DataFrame:
    """Per-group error rates; groups with fewer than 5 positives or negatives are blanked."""
    rows = []
    pred = (np.asarray(p) >= 0.5).astype(int)
    y = np.asarray(y).astype(int)
    lab = pd.Series(labels).astype(object).reset_index(drop=True)
    tmp = pd.DataFrame({"g": lab, "i": np.arange(len(lab))}).dropna(subset=["g"])
    for g, part in tmp.groupby("g", observed=True):
        ii = part["i"].to_numpy()
        yg, pg, predg = y[ii], np.asarray(p)[ii], pred[ii]
        n_pos, n_neg = int((yg == 1).sum()), int((yg == 0).sum())
        row = {"grouping": name, "group": str(g), "n": int(len(ii)),
               "n_lead": n_pos, "rate_lead": n_pos / max(len(ii), 1)}
        if n_pos >= 5 and n_neg >= 5:
            row.update(_scores(yg, pg))
            row["false_nonlead_rate"] = float(
                ((yg == 1) & (predg == 0)).sum() / max(n_pos, 1))
        rows.append(row)
    return pd.DataFrame(rows)


def _apply_block_te(X: pd.DataFrame, enc: pd.Series, gmean: float) -> pd.DataFrame:
    out = X.copy()
    mapped = out["block"].astype("string").map(enc) if "block" in out.columns else np.nan
    out["block_te"] = pd.to_numeric(mapped, errors="coerce").fillna(gmean)
    return out


def train_model(
    master: pd.DataFrame,
    n_splits: int = 5,
    seed: int = 0,
    exclude_home_built_date: bool = True,
    tract_table: pd.DataFrame | None = None,
    save: bool = True,
) -> TrainResult:
    """Fit LightGBM with class weights, calibrate on OOF scores, and save artifacts."""
    from sklearn.isotonic import IsotonicRegression

    X, y, groups = make_training_set(master, exclude_home_built_date=exclude_home_built_date)
    n_splits = max(2, min(n_splits, int(groups.nunique())))
    gkf = GroupKFold(n_splits=n_splits)
    folds = np.zeros(len(y), dtype=int)
    for i, (_, te) in enumerate(gkf.split(X, y, groups)):
        folds[te] = i

    X = X.copy()
    X["block_te"] = block_target_encoding(X["block"], y, folds)
    X["y"] = y.to_numpy()
    categories = {c: list(X[c].astype("string").dropna().unique()) for c in CATEGORICAL}

    oof = np.zeros(len(y), dtype=float)
    for i in range(n_splits):
        tr = folds != i
        te = _idx(~tr)
        model = _fit_fold(X, y, tr, categories, seed)
        oof[te] = model.predict_proba(model_matrix(X.iloc[te], categories))[:, 1]

    # Honest ECE: each fold is calibrated with an isotonic fit that never saw that fold.
    oof_cal = np.zeros(len(y), dtype=float)
    for i in range(n_splits):
        tr = folds != i
        fold_cal = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        fold_cal.fit(oof[tr], y.iloc[_idx(tr)])
        oof_cal[_idx(~tr)] = fold_cal.predict(oof[~tr])
    cal = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    cal.fit(oof, y)

    pre = baseline_pre1986(X)
    blk_hard = baseline_block_majority(X, folds)
    blk_rate = baseline_block_rate(X, folds)
    metrics = _scores(y, oof_cal)
    metrics["ece_before"] = expected_calibration_error(y.to_numpy(), oof)
    metrics["pr_auc_uncalibrated"] = float(average_precision_score(y, oof))

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    rand_folds = np.zeros(len(y), dtype=int)
    for i, (_, te) in enumerate(skf.split(X, y)):
        rand_folds[te] = i
    Xr = X.copy()
    Xr["block_te"] = block_target_encoding(X["block"], y, rand_folds)
    rand = np.zeros(len(y), dtype=float)
    for i in range(n_splits):
        tr = rand_folds != i
        te = _idx(~tr)
        model = _fit_fold(Xr, y, tr, categories, seed)
        rand[te] = model.predict_proba(model_matrix(Xr.iloc[te], categories))[:, 1]
    metrics["pr_auc_random_fold"] = float(average_precision_score(y, rand))

    baselines = {
        "pre1986": _scores(y, pre),
        "block_majority": {**_scores(y, blk_hard),
                           "pr_auc": float(average_precision_score(y, blk_rate))},
    }
    metrics["pr_auc_lift_vs_block"] = metrics["pr_auc"] - baselines["block_majority"]["pr_auc"]
    metrics["ba_lift_vs_pre1986"] = (
        metrics["balanced_accuracy"] - baselines["pre1986"]["balanced_accuracy"]
    )
    util_unk = X["utility_side_material"].astype(str).eq("Unknown").to_numpy()
    if util_unk.sum() >= 50 and int(y.to_numpy()[util_unk].sum()) >= 5:
        metrics["n_utility_unknown"] = int(util_unk.sum())
        metrics.update({f"{k}_utility_unknown": v
                        for k, v in _scores(y.to_numpy()[util_unk], oof_cal[util_unk]).items()})
        metrics["pr_auc_block_utility_unknown"] = float(
            average_precision_score(y.to_numpy()[util_unk], blk_rate[util_unk]))
        metrics["ba_pre1986_utility_unknown"] = float(
            balanced_accuracy_score(y.to_numpy()[util_unk], (pre[util_unk] >= 0.5).astype(int)))
        metrics["prevalence_utility_unknown"] = float(y.to_numpy()[util_unk].mean())

    by_group = None
    if tract_table is not None and "tract" in X.columns:
        t = tract_table.copy()
        t["tract"] = t["tract"].astype(str)
        joined = X[["tract"]].merge(t, on="tract", how="left")
        parts = []
        if "income_quartile" in joined:
            parts.append(group_error_rates(y, oof_cal, joined["income_quartile"],
                                           "income_quartile"))
        if "majority_group" in joined:
            parts.append(group_error_rates(y, oof_cal, joined["majority_group"],
                                           "majority_group"))
        if parts:
            by_group = pd.concat(parts, ignore_index=True)

    conservative = _conservative_groups(by_group)

    enc, gmean = _full_block_encoding(X["block"], y)
    X_full = _apply_block_te(X, enc, gmean)
    # Train the saved booster on OOF block_te so the feature is not in-sample encoded.
    X_full["block_te"] = X["block_te"]
    final = _lgbm(len(X), seed)
    final.fit(model_matrix(X_full, categories), y)

    result = TrainResult(
        metrics=metrics,
        baselines=baselines,
        by_group=by_group,
        oof=pd.DataFrame({"y": y, "p_raw": oof, "p": oof_cal, "fold": folds,
                          "tract": X["tract"].astype(str) if "tract" in X else None}),
        meta={
            "version": MODEL_VERSION,
            "n": int(len(y)),
            "n_positive": int(y.sum()),
            "exclude_home_built_date": exclude_home_built_date,
            "features": list(FEATURES),
            "categories": categories,
            "block_te_global": gmean,
            "block_te_map": enc,
            "conservative_groups": conservative,
            "n_splits": n_splits,
            "seed": seed,
        },
    )
    if save:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        result.model_path, result.calibrator_path = save_artifacts(final, cal, result.meta)
        (MODEL_DIR / "metrics_v1.json").write_text(
            json.dumps(_jsonable(metrics | {"baselines": baselines,
                                            "conservative_groups": conservative,
                                            "n": result.meta["n"]}), indent=2)
        )
        if by_group is not None:
            by_group.to_csv(MODEL_DIR / "error_rates_v1.csv", index=False)
        if result.oof is not None:
            result.oof.assign(utility_side=X["utility_side_material"].astype(str)).to_parquet(
                PROCESSED_DIR / "oof_pred_v1.parquet", index=False)
    result.meta["model"] = final
    result.meta["calibrator"] = cal
    attach_train_sample(result, X_full, n=min(2000, len(X_full)), seed=seed)
    return result


def _conservative_groups(by_group: pd.DataFrame | None) -> list[str]:
    """Groups whose false-non-lead rate is worse than the reference by 2+ points."""
    if by_group is None or "false_nonlead_rate" not in by_group.columns:
        return []
    out = []
    t = by_group.dropna(subset=["false_nonlead_rate"])
    refs = {("income_quartile", "Q4 highest income"), ("majority_group", "White")}
    for grouping, ref_name in refs:
        g = t[t["grouping"] == grouping].set_index("group")
        if ref_name not in g.index:
            continue
        ref = float(g.loc[ref_name, "false_nonlead_rate"])
        for name, row in g.iterrows():
            if name == ref_name:
                continue
            if float(row["false_nonlead_rate"]) >= ref + 0.02:
                out.append(str(name))
    return out


def save_artifacts(model, calibrator, meta: dict) -> tuple[Path, Path]:
    import pickle

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "lll_lightgbm_v1.pkl"
    cal_path = MODEL_DIR / "calibrator_v1.pkl"
    bundle = {k: v for k, v in meta.items()
              if k not in {"model", "calibrator", "block_te_map"}}
    bundle["model"] = model
    bundle["block_te_map"] = meta["block_te_map"]
    bundle["block_te_global"] = meta["block_te_global"]
    model_path.write_bytes(pickle.dumps(bundle, protocol=5))
    cal_path.write_bytes(pickle.dumps(calibrator, protocol=5))
    return model_path, cal_path


def write_figures(result: TrainResult, out_dir: str | Path | None = None) -> list[Path]:
    """Reliability diagram, confusion matrix, and SHAP bar plot."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from lll import REPO_ROOT

    fig_dir = Path(out_dir) if out_dir else REPO_ROOT / "docs" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    y = result.oof["y"].to_numpy()
    p = result.oof["p"].to_numpy()
    paths = []

    edges = np.linspace(0, 1, N_BINS + 1)
    bins = np.digitize(p, edges[1:-1], right=True)
    xs, ys = [], []
    for b in range(N_BINS):
        m = bins == b
        if m.any():
            xs.append(float(p[m].mean()))
            ys.append(float(y[m].mean()))
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.plot([0, 1], [0, 1], color="#888888", lw=1)
    ax.plot(xs, ys, marker="o", color="#b10026")
    ax.set_xlabel("Predicted probability of lead or galvanized")
    ax.set_ylabel("Actual share")
    ax.set_title("Reliability (after calibration)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    p1 = fig_dir / "reliability_v1.png"
    fig.savefig(p1, dpi=140)
    plt.close(fig)
    paths.append(p1)

    pred = (p >= 0.5).astype(int)
    tn = int(((y == 0) & (pred == 0)).sum())
    fp = int(((y == 0) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    tp = int(((y == 1) & (pred == 1)).sum())
    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    ax.imshow([[tn, fp], [fn, tp]], cmap="Reds")
    for (i, j, v) in ((0, 0, tn), (0, 1, fp), (1, 0, fn), (1, 1, tp)):
        ax.text(j, i, f"{v:,}", ha="center", va="center", color="black")
    ax.set_xticks([0, 1], ["Pred. non-lead", "Pred. lead/GRR"])
    ax.set_yticks([0, 1], ["Is non-lead", "Is lead/GRR"])
    ax.set_title("Confusion matrix at 50%")
    fig.tight_layout()
    p2 = fig_dir / "confusion_v1.png"
    fig.savefig(p2, dpi=140)
    plt.close(fig)
    paths.append(p2)

    shap_path = _shap_bar(result, fig_dir)
    if shap_path:
        paths.append(shap_path)
    return paths


def _shap_bar(result: TrainResult, fig_dir: Path) -> Path | None:
    import matplotlib.pyplot as plt
    import shap

    model = result.meta.get("model")
    if model is None or result.oof is None:
        return None
    # Rebuild a sample from OOF-aligned rows is hard; use the fitted model on a
    # random slice of the training matrix stored on the booster feature names.
    sample = getattr(model, "_train_sample", None)
    if sample is None:
        return None
    try:
        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(sample)
    except Exception:
        return None
    if isinstance(sv, list):
        sv = sv[1]
    imp = np.abs(sv).mean(axis=0)
    order = np.argsort(imp)[::-1]
    names = [FEATURES[i] for i in order]
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    ax.barh(range(len(names) - 1, -1, -1), imp[order])
    ax.set_yticks(range(len(names) - 1, -1, -1), names)
    ax.set_xlabel("mean |SHAP|")
    ax.set_title("Which inputs move the prediction")
    fig.tight_layout()
    path = fig_dir / "shap_summary_v1.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def attach_train_sample(result: TrainResult, X: pd.DataFrame, n: int = 2000, seed: int = 0):
    """Keep a small matrix on the model so write_figures can compute SHAP."""
    rng = np.random.default_rng(seed)
    take = rng.choice(len(X), size=min(n, len(X)), replace=False)
    cats = result.meta["categories"]
    result.meta["model"]._train_sample = model_matrix(X.iloc[take], cats)


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    return str(obj)


def score_unknowns(master: pd.DataFrame, result: TrainResult | None = None) -> pd.Series:
    """Calibrated P(lead/GRR) for every row; known rows keep NaN on request of caller.

    Scores customer-side Unknown rows. Known rows are left as NaN.
    """
    from lll.predict import load_model, predict_frame

    bundle = result.meta if result is not None else load_model()
    unk = master["customer_side_material"].astype(str).eq("Unknown")
    out = pd.Series(np.nan, index=master.index, dtype=float)
    if not unk.any():
        return out
    out.loc[unk] = predict_frame(master.loc[unk], bundle).to_numpy()
    return out
