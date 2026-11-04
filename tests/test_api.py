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
