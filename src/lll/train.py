"""Train, validate, and calibrate the LightGBM service line material model.

Target: customer-side Lead or GRR (1) vs Non-Lead (0), trained on known rows only.
Validation: GroupKFold by census block group, plus a random-fold sanity check.
Baselines: pre-1986 rule and block majority vote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

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


@dataclass
class TrainResult:
    metrics: dict[str, float] = field(default_factory=dict)
    baselines: dict[str, dict[str, float]] = field(default_factory=dict)
    by_group: pd.DataFrame | None = None
    model_path: Path | None = None
    calibrator_path: Path | None = None


def make_training_set(master: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return (X, y, groups) from known customer-side rows.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError


def block_target_encoding(
    blocks: pd.Series, y: pd.Series, folds: np.ndarray, smoothing: float = 20.0
) -> pd.Series:
    """Out-of-fold smoothed target encoding of census block.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError


def baseline_pre1986(df: pd.DataFrame) -> np.ndarray:
    """Predict lead when year built < 1986.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError


def baseline_block_majority(df: pd.DataFrame, folds: np.ndarray) -> np.ndarray:
    """Out-of-fold block majority vote.

    TODO: implement (Gate 2).
    """
    raise NotImplementedError


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    """Equal-width-bin ECE.

    TODO: implement (Gate 2). Target <= 0.05 after calibration.
    """
    raise NotImplementedError


def train_model(master: pd.DataFrame, n_splits: int = 5, seed: int = 0) -> TrainResult:
    """Fit LightGBM with class weights, calibrate on a held-out fold, and save artifacts.

    TODO: implement (Gate 2). Saves models/lll_lightgbm_v1.pkl and models/calibrator_v1.pkl.
    """
    raise NotImplementedError
