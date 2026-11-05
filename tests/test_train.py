import numpy as np
import pandas as pd
import pytest

from lll.train import (
    BAN_YEAR,
    HOME_BUILT_CUSTOMER,
    baseline_block_majority,
    baseline_pre1986,
    block_target_encoding,
    expected_calibration_error,
    make_training_set,
    train_model,
)


def test_ece_perfect_is_zero():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.0, 0.0, 1.0, 1.0])
    assert expected_calibration_error(y, p) == pytest.approx(0.0)


def test_ece_equal_width_gap():
    y = np.array([0.0, 0.0, 1.0, 1.0])
    p = np.array([0.1, 0.1, 0.9, 0.9])
    assert expected_calibration_error(y, p, n_bins=10) == pytest.approx(0.1)


def test_pre1986_missing_year_is_lead():
    df = pd.DataFrame({"year_built": [1910, 1990, np.nan]})
    pred = baseline_pre1986(df)
    assert list(pred) == [1.0, 0.0, 1.0]
    assert BAN_YEAR == 1986


def test_block_encoding_is_out_of_fold():
    blocks = pd.Series(["a", "a", "a", "b", "b", "b"])
    y = pd.Series([1.0, 1.0, 0.0, 0.0, 0.0, 1.0])
    folds = np.array([0, 1, 2, 0, 1, 2])
    enc = block_target_encoding(blocks, y, folds, smoothing=0.0)
    # Fold 0 row 0 (block a, y=1) sees only fold 1-2 of a: y=[1, 0] mean 0.5
    assert enc.iloc[0] == pytest.approx(0.5)
    # Fold 0 row 3 (block b, y=0) sees fold 1-2 of b: y=[0, 1] mean 0.5
    assert enc.iloc[3] == pytest.approx(0.5)


def test_block_majority_is_out_of_fold():
    df = pd.DataFrame({
        "block": ["a", "a", "a", "b", "b", "b"],
        "y": [1, 1, 1, 0, 0, 0],
    })
    folds = np.array([0, 1, 2, 0, 1, 2])
    vote = baseline_block_majority(df, folds)
    assert list(vote[:3]) == [1.0, 1.0, 1.0]
    assert list(vote[3:]) == [0.0, 0.0, 0.0]


def test_home_built_date_rows_are_held_out():
    df = pd.DataFrame({
        "customer_side_material": ["Lead", "Non-Lead", "Lead"],
        "block_group": ["g1", "g1", "g1"],
        "block": ["b1", "b1", "b1"],
        "year_built": [1910, 1990, 1950],
        "verification_method": [
            "PR: Field Verification",
            f"PU: Home Built Date, {HOME_BUILT_CUSTOMER}",
            "PU: Home Built Date, PR: Field Verification",
        ],
    })
    X, y, _ = make_training_set(df)
    assert len(X) == 2
    assert list(y) == [1, 1]
    X2, y2, _ = make_training_set(df, exclude_home_built_date=False)
    assert len(X2) == 3 and int(y2.sum()) == 2


def _synthetic(n=180, seed=0):
    rng = np.random.default_rng(seed)
    year = rng.integers(1890, 2010, size=n)
    grp = np.repeat([f"g{i}" for i in range(12)], n // 12 + 1)[:n]
    block = np.repeat([f"b{i}" for i in range(30)], n // 30 + 1)[:n]
    util = rng.choice(["Lead", "Non-Lead", "Unknown"], size=n, p=[0.3, 0.4, 0.3])
    # Label mostly follows year and utility side, with noise.
    p = np.clip(0.15 + 0.7 * (year < 1986) + 0.15 * (util == "Lead")
                - 0.25 * (year >= 1986), 0.05, 0.95)
    y = rng.random(n) < p
    mat = np.where(y, "Lead", "Non-Lead")
    return pd.DataFrame({
        "customer_side_material": mat,
        "utility_side_material": util,
        "year_built": year,
        "building_class": rng.choice(["2", "5", "99"], size=n),
        "unit_count": rng.integers(1, 4, size=n),
        "diameter_in": np.nan,
        "install_year": np.nan,
        "block": block,
        "block_group": grp,
        "tract": np.repeat([f"t{i}" for i in range(6)], n // 6 + 1)[:n],
        "nbr_lead_share_k10": np.clip(p + rng.normal(0, 0.1, n), 0, 1),
        "nbr_known_count_k10": 8,
        "block_lead_share_loo": np.clip(p + rng.normal(0, 0.1, n), 0, 1),
        "dist_nearest_nonlead_m": rng.uniform(10, 200, n),
        "tract_unknown_rate": rng.uniform(0.2, 0.8, n),
        "verification_method": "PR: Field Verification",
    })


def test_train_model_on_synthetic(tmp_path, monkeypatch):
    from lll import train as train_mod

    monkeypatch.setattr(train_mod, "MODEL_DIR", tmp_path)
    master = _synthetic()
    result = train_model(master, n_splits=3, seed=0, save=True)
    assert result.model_path.exists() and result.calibrator_path.exists()
    assert 0.0 <= result.metrics["ece"] <= 1.0
    assert 0.5 <= result.metrics["pr_auc"] <= 1.0
    assert result.oof["p"].between(0, 1).all()
