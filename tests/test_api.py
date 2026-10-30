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
