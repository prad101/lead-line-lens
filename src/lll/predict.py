"""Calibrated predictions, confidence tiers, and plain-language SHAP reasons.

A prediction never lowers urgency: an Unknown line is always shown as
"possibly lead until verified", whatever the model says.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TREAT_AS_LEAD_MESSAGE = "Treat this line as lead until it is verified."


@dataclass
class Prediction:
    probability_lead: float
    tier: str
    reasons: list[str]
    model_version: str
    message: str = TREAT_AS_LEAD_MESSAGE


def confidence_tier(p: float) -> str:
    """High if p >= 0.85 or p <= 0.15; Moderate if 0.65-0.85 or 0.15-0.35; else Low.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError


def load_model(model_dir: str | Path | None = None):
    """Load the LightGBM model and calibrator saved by train.py.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError


def explain(
    shap_row: dict[str, float], feature_values: dict[str, object], top_n: int = 3
) -> list[str]:
    """Turn the largest SHAP contributions into short plain-language sentences.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError


def predict_line(features: dict[str, object], model=None) -> Prediction:
    """Predict one line from its feature dict.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError
