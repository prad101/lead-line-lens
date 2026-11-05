"""Calibrated predictions, confidence tiers, and plain-language SHAP reasons.

A prediction never lowers urgency: an Unknown line is always shown as
"possibly lead until verified", whatever the model says.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

TREAT_AS_LEAD_MESSAGE = "Treat this line as lead until it is verified."
MODEL_VERSION = "v1"
HIGH_LEAD = 0.85
HIGH_NONLEAD = 0.15
HIGH_NONLEAD_CONSERVATIVE = 0.10
MOD_LEAD = 0.65
MOD_NONLEAD = 0.35


@dataclass
class Prediction:
    probability_lead: float
    tier: str
    reasons: list[str]
    model_version: str
    message: str = TREAT_AS_LEAD_MESSAGE
    conservative: bool = False


def confidence_tier(p: float, group: str | None = None,
                    conservative_groups: list[str] | None = None) -> str:
    """High if p >= 0.85 or p <= high-nonlead; Moderate if 0.65-0.85 or 0.15-0.35; else Low.

    When `group` is in conservative_groups (higher false-non-lead rate than the
    reference), High for non-lead requires p <= 0.10 instead of 0.15.
    """
    p = float(p)
    groups = set(conservative_groups or [])
    hi_nl = HIGH_NONLEAD_CONSERVATIVE if group in groups else HIGH_NONLEAD
    if p >= HIGH_LEAD or p <= hi_nl:
        return "High"
    if p >= MOD_LEAD or p <= MOD_NONLEAD:
        return "Moderate"
    return "Low"


def load_model(model_dir: str | Path | None = None) -> dict:
    """Load the LightGBM bundle and calibrator saved by train.py."""
    import pickle

    from lll import MODEL_DIR

    d = Path(model_dir) if model_dir else MODEL_DIR
    bundle = pickle.loads((d / "lll_lightgbm_v1.pkl").read_bytes())
    bundle["calibrator"] = pickle.loads((d / "calibrator_v1.pkl").read_bytes())
    return bundle


def _fmt_year(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    return str(int(v))


def _fmt_pct(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    return f"{float(v):.0%}"


def _sentence(name: str, shap_val: float, value) -> str:
    up = float(shap_val) > 0
    effect = "raises" if up else "lowers"
    if name == "year_built":
        year = _fmt_year(value)
        if year is None:
            return (f"The building year is not on file, which {effect} the chance "
                    "this line is lead.")
        when = "before" if float(value) < 1986 else "in or after"
        return (f"This building dates to {year} ({when} the 1986 lead-pipe ban), "
                f"which {effect} the chance this line is lead.")
    if name == "utility_side_material":
        val = "unknown" if pd.isna(value) or value in (None, "") else str(value).lower()
        return (f"The city's side of the line is recorded as {val}, which {effect} "
                "the chance the customer's side is lead.")
    if name == "nbr_lead_share_k10":
        pct = _fmt_pct(value)
        if pct is None:
            return f"There are no nearby known lines, which {effect} the chance this one is lead."
        return (f"{pct} of nearby known lines are lead or galvanized, which {effect} "
                "the chance this one is too.")
    if name == "block_lead_share_loo":
        pct = _fmt_pct(value)
        if pct is None:
            return (f"This block has no other known lines, which {effect} the chance "
                    "this one is lead.")
        return (f"On this block, {pct} of other known lines are lead or galvanized, "
                f"which {effect} the chance this one is too.")
    if name == "block_te":
        pct = _fmt_pct(value)
        if pct is None:
            return f"This census block has little known history, which {effect} the chance of lead."
        return (f"Known lines on this census block are lead or galvanized about {pct} "
                f"of the time, which {effect} the chance this one is too.")
    if name == "tract_unknown_rate":
        pct = _fmt_pct(value)
        if pct is None:
            return f"The tract's unknown rate is missing, which {effect} the chance of lead."
        return (f"Records are still unknown for {pct} of lines in this census tract, "
                f"which {effect} the chance this one is lead.")
    if name == "dist_nearest_nonlead_m":
        if value is None or pd.isna(value):
            return (f"No known non-lead line is nearby, which {effect} the chance "
                    "this one is lead.")
        return (f"The nearest known non-lead line is {float(value):.0f} meters away, "
                f"which {effect} the chance this one is lead.")
    if name == "building_class":
        val = "not on file" if pd.isna(value) or value in (None, "") else str(value)
        return f"The Assessor building class is {val}, which {effect} the chance of lead."
    if name == "unit_count":
        if value is None or pd.isna(value):
            return f"The unit count is not on file, which {effect} the chance of lead."
        n = int(value)
        units = "unit" if n == 1 else "units"
        return f"The building has {n} {units}, which {effect} the chance of lead."
    if name == "install_year":
        year = _fmt_year(value)
        if year is None:
            return f"The install year is not on file, which {effect} the chance of lead."
        return f"The service line was installed in {year}, which {effect} the chance of lead."
    if name == "diameter_in":
        if value is None or pd.isna(value):
            return f"Pipe diameter is not on file, which {effect} the chance of lead."
        return (f"The pipe is {float(value):.2g} inches across, which {effect} "
                "the chance of lead.")
    if name == "nbr_known_count_k10":
        n = 0 if value is None or pd.isna(value) else int(value)
        return (f"The model used {n} nearby known lines, which {effect} the chance "
                "this one is lead.")
    return f"{name.replace('_', ' ')} {effect} the chance this line is lead."


def explain(
    shap_row: dict[str, float], feature_values: dict[str, object], top_n: int = 3
) -> list[str]:
    """Turn the largest SHAP contributions into short plain-language sentences."""
    ranked = sorted(shap_row.items(), key=lambda kv: abs(float(kv[1])), reverse=True)
    reasons = []
    for name, val in ranked:
        if abs(float(val)) < 1e-12:
            continue
        reasons.append(_sentence(name, float(val), feature_values.get(name)))
        if len(reasons) >= top_n:
            break
    if not reasons:
        reasons.append("The model does not have a strong signal on this line.")
    return reasons


def _with_block_te(frame: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    out = frame.copy()
    enc = bundle.get("block_te_map")
    gmean = bundle.get("block_te_global", np.nan)
    if enc is not None and "block" in out.columns:
        mapped = out["block"].astype("string").map(enc)
        out["block_te"] = pd.to_numeric(mapped, errors="coerce").fillna(gmean).astype("float64")
    elif "block_te" not in out.columns:
        out["block_te"] = gmean
    return out


def predict_frame(frame: pd.DataFrame, bundle: dict | None = None) -> pd.Series:
    """Calibrated P(customer-side lead or GRR) for each row."""
    from lll.train import model_matrix

    bundle = bundle or load_model()
    X = _with_block_te(frame, bundle)
    M = model_matrix(X, bundle.get("categories"))
    raw = bundle["model"].predict_proba(M)[:, 1]
    p = bundle["calibrator"].predict(raw)
    return pd.Series(np.clip(p, 0.0, 1.0), index=frame.index)


def _shap_one(bundle: dict, matrix_row: pd.DataFrame) -> dict[str, float]:
    import shap

    from lll.train import FEATURES

    explainer = shap.TreeExplainer(bundle["model"])
    sv = explainer.shap_values(matrix_row)
    if isinstance(sv, list):
        sv = sv[1]
    row = np.asarray(sv).reshape(-1)
    return {FEATURES[i]: float(row[i]) for i in range(len(FEATURES))}


def predict_line(features: dict[str, object], model=None) -> Prediction:
    """Predict one line from its feature dict."""
    from lll.train import model_matrix

    bundle = model if isinstance(model, dict) else (model or load_model())
    if not isinstance(bundle, dict):
        bundle = load_model()
    frame = pd.DataFrame([features])
    frame = _with_block_te(frame, bundle)
    M = model_matrix(frame, bundle.get("categories"))
    raw = float(bundle["model"].predict_proba(M)[0, 1])
    p = float(np.clip(bundle["calibrator"].predict([raw])[0], 0.0, 1.0))
    shap_row = _shap_one(bundle, M)
    group = features.get("majority_group") or features.get("income_quartile")
    group = None if group is None else str(group)
    cons = bundle.get("conservative_groups") or []
    return Prediction(
        probability_lead=p,
        tier=confidence_tier(p, group=group, conservative_groups=cons),
        reasons=explain(shap_row, {**features, "block_te": frame["block_te"].iloc[0]}),
        model_version=str(bundle.get("version", MODEL_VERSION)),
        conservative=group in set(cons),
    )
