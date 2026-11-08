import pandas as pd

from api.store import Store, reset


def test_store_lookup_uses_normalized_address():
    lines = pd.DataFrame({
        "address_norm": ["123 N MAIN ST", "4500 W FULLERTON AVE"],
        "line_status": ["Unknown", "Lead"],
        "customer_side_material": ["Unknown", "Lead"],
        "utility_side_material": ["Unknown", "Lead"],
    })
    s = Store(snapshot="20250414", lines=lines)
    hit = s.lookup("123 North Main Street")
    assert len(hit) == 1 and hit.iloc[0]["line_status"] == "Unknown"
    assert s.lookup("nope").empty


def test_store_area_matches_string_ids():
    areas = {"ward": pd.DataFrame({"ward": ["18"], "total_lines": [10], "suppressed": [False]})}
    s = Store(snapshot="20250414", lines=pd.DataFrame(), areas=areas)
    row = s.area("ward", "18")
    assert int(row["total_lines"]) == 10
    assert s.area("ward", "1") is None
    assert s.area("block", "1") is None


def test_reset_clears_lru(monkeypatch, tmp_path):
    import api.store as store_mod

    master = pd.DataFrame({
        "line_id": ["a"], "address_norm": ["123 N MAIN ST"],
        "utility_side_material": ["Unknown"], "customer_side_material": ["Unknown"],
        "line_status": ["Unknown"], "snapshot_date": ["2025-04-14"],
    })
    master.to_parquet(tmp_path / "master_chicago_20250414.parquet")
    monkeypatch.setattr(store_mod, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(store_mod, "MODEL_DIR", tmp_path)
    monkeypatch.setattr("lll.PROCESSED_DIR", tmp_path)
    reset()
    loaded = store_mod.get()
    assert loaded.snapshot == "20250414"
    assert len(loaded.lookup("123 N Main St")) == 1
    reset()
