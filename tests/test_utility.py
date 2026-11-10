from io import BytesIO

import pandas as pd
import pytest

from lll.ingest import IEPA_TEMPLATE_COLUMNS, read_bytes, suggest_mapping
from lll.predict import TREAT_AS_LEAD_MESSAGE
from lll.schema import validate_inventory
from lll.utility import (
    EXPORT_HEADER,
    MIN_KNOWN_FOR_FRESH_MODEL,
    SAMPLE_SIZE,
    classify,
    export_il_epa_template,
    methods_memo,
    stratified_sample_plan,
    summarize,
)


def _inventory(n_lead=80, n_nl=80, n_unk=40, n_grr=0):
    rows = []
    n = 0
    for label, count in (("Lead", n_lead), ("GRR", n_grr), ("Non-Lead", n_nl), ("Unknown", n_unk)):
        for _i in range(count):
            n += 1
            rows.append({
                "line_id": f"T-{n:05d}",
                "address": f"{100 + n} N Main St",
                "utility_side_material": "Lead" if label == "Lead" else "Unknown",
                "customer_side_material": label,
                "year_built": 1910 + (n % 90),
                "install_year": pd.NA,
                "diameter_in": 0.75 if n % 2 == 0 else 1.0,
                "verification_method": pd.NA,
                "replacement_date": pd.NaT,
                "notification_date": pd.NaT,
                "snapshot_date": pd.Timestamp("2025-04-14"),
                "pin": pd.NA,
            })
    return validate_inventory(pd.DataFrame(rows))


def test_read_bytes_csv_roundtrip_does_not_need_a_path():
    raw = pd.DataFrame({"Address": ["1 Main"], "Public": ["L"], "Private": ["U"]})
    data = raw.to_csv(index=False).encode()
    got = read_bytes(data, "inv.csv")
    assert list(got.columns) == ["Address", "Public", "Private"]
    assert suggest_mapping(list(got.columns))["Address"] == "address"


def test_fresh_model_when_enough_known_rows():
    df = _inventory(n_lead=120, n_nl=120, n_unk=40)
    assert int((df.customer_side_material != "Unknown").sum()) >= MIN_KNOWN_FOR_FRESH_MODEL
    out, warning = classify(df)
    assert warning is None
    assert out["model_source"].iloc[0] == "fresh"
    assert out["customer_side_material"].eq(df["customer_side_material"]).all()
    assert out["probability_lead"].between(0, 1).all()
    assert TREAT_AS_LEAD_MESSAGE in set(out["message"])


def test_transfer_warning_under_200_known():
    train = _inventory(n_lead=120, n_nl=120, n_unk=0)
    bundle = __import__("lll.utility", fromlist=["_fit_local"])._fit_local(train)
    small = _inventory(n_lead=20, n_nl=20, n_unk=30)
    out, warning = classify(small, model=bundle)
    assert warning
    assert "Chicago" in warning
    assert out["model_source"].iloc[0] == "chicago_transfer"
    assert "safe" not in warning.lower()


def test_sample_plan_is_unknown_only_and_fixed_size():
    df = _inventory(n_lead=50, n_nl=50, n_unk=80)
    scored, _ = classify(df, model=__import__("lll.utility", fromlist=["_fit_local"])._fit_local(
        _inventory(120, 120, 0)))
    plan = stratified_sample_plan(scored, n=SAMPLE_SIZE)
    assert len(plan) == SAMPLE_SIZE
    picked = scored.loc[scored.line_id.isin(plan.line_id), "customer_side_material"]
    assert set(picked) == {"Unknown"}
    assert "stratum" in plan.columns


def test_export_keeps_recorded_materials_and_header():
    df = _inventory(n_lead=5, n_nl=5, n_unk=5)
    scored, _ = classify(
        df, model=__import__("lll.utility", fromlist=["_fit_local"])._fit_local(
            _inventory(120, 120, 0)),
    )
    raw = export_il_epa_template(scored).decode()
    assert raw.startswith("# " + EXPORT_HEADER)
    lines = [ln for ln in raw.splitlines() if not ln.startswith("#")]
    header = lines[0].split(",")
    for col in IEPA_TEMPLATE_COLUMNS:
        assert col in header
    assert "predicted_lead_prob" in header
    body = pd.read_csv(BytesIO("\n".join(lines).encode()))
    assert set(body["customer_material"]) <= {"L", "GRR", "NL", "U"}
    # recorded unknown stays U even if the model is sure
    unk = scored["customer_side_material"].eq("Unknown")
    exported_unk = body.loc[unk.to_numpy(), "customer_material"]
    assert (exported_unk == "U").all()


def test_methods_memo_states_limits():
    text = methods_memo({
        "system_name": "Burnham", "system_id": "IL0310360",
        "run_date": "2026-11-09", "n_rows": 1208, "n_known": 400, "n_unknown": 800,
        "transfer_warning": None, "sample_n": 60,
        "treat_as_lead": TREAT_AS_LEAD_MESSAGE,
    })
    assert "Burnham" in text
    assert "Illinois EPA" in text
    assert TREAT_AS_LEAD_MESSAGE in text
    assert "not a verification" in text.lower() or "not an inspection" in text.lower()


def test_summarize_counts():
    df = _inventory(n_lead=3, n_nl=2, n_unk=4, n_grr=1)
    s = summarize(df)
    assert s["n_rows"] == 10
    assert s["n_known"] == 6
    assert s["n_unknown"] == 4
    assert s["n_lead"] == 3 and s["n_grr"] == 1 and s["n_nonlead"] == 2


@pytest.mark.parametrize("system", ["burnham", "east_dundee"])
def test_end_to_end_on_small_illinois_systems(system, tmp_path):
    from lll import sources

    path = sources.BURNHAM if system == "burnham" else sources.EAST_DUNDEE
    if not path.exists():
        pytest.skip(f"{path} not on disk")
    reader = sources.burnham if system == "burnham" else sources.east_dundee
    df = reader()
    before = set(tmp_path.iterdir()) if tmp_path.exists() else set()
    out, warning = classify(df)
    plan = stratified_sample_plan(out)
    export = export_il_epa_template(out)
    memo = methods_memo({
        "system_name": system, "system_id": None, "run_date": "2026-11-09",
        "n_rows": len(out), "n_known": int((out.customer_side_material != "Unknown").sum()),
        "n_unknown": int((out.customer_side_material == "Unknown").sum()),
        "transfer_warning": warning, "sample_n": len(plan),
        "treat_as_lead": TREAT_AS_LEAD_MESSAGE,
    })
    assert len(out) == len(df)
    assert (out["customer_side_material"] == df["customer_side_material"]).all()
    assert export.startswith(b"# " + EXPORT_HEADER.encode())
    assert system.replace("_", " ").split()[0].lower() in memo.lower() or system in memo
    if plan.empty:
        assert int((out.customer_side_material == "Unknown").sum()) == 0
    else:
        assert len(plan) <= SAMPLE_SIZE
    # classify must not write the upload or a new pickle into tmp
    assert set(tmp_path.iterdir()) == before
