from lll.predict import (
    HIGH_NONLEAD_CONSERVATIVE,
    TREAT_AS_LEAD_MESSAGE,
    confidence_tier,
    explain,
    predict_line,
)


def test_confidence_tiers():
    assert confidence_tier(0.90) == "High"
    assert confidence_tier(0.10) == "High"
    assert confidence_tier(0.70) == "Moderate"
    assert confidence_tier(0.20) == "Moderate"
    assert confidence_tier(0.50) == "Low"


def test_conservative_group_raises_nonlead_bar():
    assert confidence_tier(0.12, group="Black", conservative_groups=["Black"]) == "Moderate"
    assert confidence_tier(0.12) == "High"
    assert HIGH_NONLEAD_CONSERVATIVE == 0.10
    assert confidence_tier(0.08, group="Black", conservative_groups=["Black"]) == "High"


def test_explain_top_three_plain_language():
    shap_row = {"year_built": 0.4, "nbr_lead_share_k10": 0.2, "utility_side_material": -0.15,
                "unit_count": 0.01}
    values = {"year_built": 1912, "nbr_lead_share_k10": 0.8, "utility_side_material": "Lead",
              "unit_count": 2}
    reasons = explain(shap_row, values, top_n=3)
    assert len(reasons) == 3
    assert "1912" in reasons[0] and "raises" in reasons[0]
    assert "80%" in reasons[1]
    assert "lead" in reasons[2].lower()


def test_predict_never_lowers_urgency(tmp_path, monkeypatch):
    from lll import train as train_mod
    from tests.test_train import _synthetic

    monkeypatch.setattr(train_mod, "MODEL_DIR", tmp_path)
    master = _synthetic(n=180, seed=1)
    train_mod.train_model(master, n_splits=3, seed=0, save=True)
    bundle = pickle_bundle(tmp_path)
    row = master.iloc[0].to_dict()
    out = predict_line(row, model=bundle)
    assert out.message == TREAT_AS_LEAD_MESSAGE
    assert 0.0 <= out.probability_lead <= 1.0
    assert out.tier in {"High", "Moderate", "Low"}
    assert 1 <= len(out.reasons) <= 3


def pickle_bundle(model_dir):
    import pickle

    bundle = pickle.loads((model_dir / "lll_lightgbm_v1.pkl").read_bytes())
    bundle["calibrator"] = pickle.loads((model_dir / "calibrator_v1.pkl").read_bytes())
    return bundle
