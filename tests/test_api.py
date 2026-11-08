from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_lists_every_appendix_b_endpoint():
    paths = client.get("/openapi.json").json()["paths"]
    for p in (
        "/lookup",
        "/predict",
        "/area/{level}/{area_id}",
        "/letter",
        "/scorecard/ward/{ward}.pdf",
        "/utility/upload",
        "/utility/map",
        "/utility/classify",
        "/utility/sample-plan",
        "/utility/export",
    ):
        assert p in paths, p


def test_scorecard_returns_pdf(monkeypatch):
    import lll.scorecard

    monkeypatch.setattr(lll.scorecard, "ward_pdf", lambda ward: b"%PDF-1.7 fake")
    r = client.get("/scorecard/ward/7.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_scorecard_without_built_data_is_503(monkeypatch):
    import lll.scorecard

    def missing(ward):
        raise FileNotFoundError("ward.csv missing; run scripts/build_equity.py first.")

    monkeypatch.setattr(lll.scorecard, "ward_pdf", missing)
    assert client.get("/scorecard/ward/7.pdf").status_code == 503


def test_scorecard_rejects_ward_out_of_range():
    assert client.get("/scorecard/ward/51.pdf").status_code == 422


def _store(rows=None, areas=None, model=None):
    import pandas as pd

    from api.store import Store

    if rows is None:
        rows = [{
            "line_id": "L1", "address": "123 N Main St", "address_norm": "123 N MAIN ST",
            "utility_side_material": "Unknown", "customer_side_material": "Unknown",
            "line_status": "Unknown", "verification_method": None, "replaced": False,
            "replacement_date": None, "ward": "18", "tract": "17031430700",
            "block": "170314307001000", "community_area": "25",
            "year_built": 1912, "building_class": "2", "unit_count": 1,
            "diameter_in": None, "install_year": None, "block_te": 0.8,
            "nbr_lead_share_k10": 0.9, "nbr_known_count_k10": 8,
            "block_lead_share_loo": 0.85, "dist_nearest_nonlead_m": 40.0,
            "tract_unknown_rate": 0.6,
        }]
    return Store(snapshot="20250414", lines=pd.DataFrame(rows),
                 areas=areas or {}, model=model)


def test_lookup_returns_status_and_treat_as_lead(monkeypatch):
    import api.store as store_mod
    from lll.predict import TREAT_AS_LEAD_MESSAGE

    monkeypatch.setattr(store_mod, "get", _store)
    r = client.get("/lookup", params={"address": "123 North Main Street"})
    assert r.status_code == 200
    body = r.json()
    assert body["normalized"] == "123 N MAIN ST"
    assert body["n_lines"] == 1
    assert body["lines"][0]["line_status"] == "Unknown"
    assert body["lines"][0]["message"] == TREAT_AS_LEAD_MESSAGE
    assert body["lines"][0]["ward"] == "18"


def test_lookup_404_and_400(monkeypatch):
    import api.store as store_mod

    monkeypatch.setattr(store_mod, "get", _store)
    assert client.get("/lookup", params={"address": "999 N Nowhere Ave"}).status_code == 404
    assert client.get("/lookup", params={"address": "Chicago"}).status_code == 400


def test_lookup_503_without_inventory(monkeypatch):
    import api.store as store_mod

    def boom():
        raise FileNotFoundError("no master")

    monkeypatch.setattr(store_mod, "get", boom)
    assert client.get("/lookup", params={"address": "123 N Main St"}).status_code == 503


def test_predict_unknown_uses_model(monkeypatch):
    import api.store as store_mod
    from lll.predict import TREAT_AS_LEAD_MESSAGE, Prediction

    monkeypatch.setattr(store_mod, "get", lambda: _store(model={"ok": True}))
    monkeypatch.setattr("api.routers.predict.predict_line",
                        lambda features, model=None: Prediction(
                            0.91, "High", ["Nearby lines are often lead."], "v1"))
    r = client.post("/predict", json={"address": "123 North Main Street"})
    assert r.status_code == 200
    body = r.json()
    assert body["probability_lead"] == 0.91
    assert body["tier"] == "High"
    assert body["message"] == TREAT_AS_LEAD_MESSAGE
    assert body["reasons"]


def test_predict_known_lead_skips_model(monkeypatch):
    import api.store as store_mod

    rows = _store().lines.copy()
    rows["customer_side_material"] = "Lead"
    rows["line_status"] = "Lead"
    monkeypatch.setattr(store_mod, "get", lambda: _store(rows=rows.to_dict("records"),
                                                         model={"ok": True}))
    r = client.post("/predict", json={"address": "123 N Main St"})
    assert r.status_code == 200
    assert r.json()["probability_lead"] is None
    assert "lead" in r.json()["message"].lower()


def test_area_suppressed_and_published(monkeypatch):
    import pandas as pd

    import api.store as store_mod

    areas = {
        "ward": pd.DataFrame({"ward": ["18", "42"], "total_lines": [16631, None],
                              "share_needs_action": [0.96, None], "suppressed": [False, True]}),
    }
    monkeypatch.setattr(store_mod, "get", lambda: _store(areas=areas))
    ok = client.get("/area/ward/18").json()
    assert ok["suppressed"] is False
    assert ok["values"]["share_needs_action"] == 0.96
    hid = client.get("/area/ward/42").json()
    assert hid["suppressed"] is True
    assert hid["values"]["total_lines"] is None
    assert client.get("/area/ward/99").status_code == 404


def test_letter_returns_text_docx_and_mailto(monkeypatch):
    import api.store as store_mod

    monkeypatch.setattr(store_mod, "get", _store)
    r = client.post("/letter", json={"address": "123 N Main St", "child_or_pregnancy": True,
                                     "tenure": "rent"})
    assert r.status_code == 200
    body = r.json()
    assert "123 N Main St" in body["text"]
    assert body["docx_base64"]
    assert body["mailto"].startswith("mailto:")
    assert "Unknown" in body["text"]


def test_utility_stays_unimplemented():
    spec = client.get("/openapi.json").json()
    assert "501" in spec["paths"]["/utility/upload"]["post"]["responses"]
    assert client.post("/utility/upload").status_code in {501, 422}


def test_openapi_documents_error_responses():
    spec = client.get("/openapi.json").json()
    lookup = spec["paths"]["/lookup"]["get"]
    assert "404" in lookup["responses"]
    assert "503" in lookup["responses"]
    pred = spec["paths"]["/predict"]["post"]
    assert pred["requestBody"]
