import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from lll.equity import disparity_report
from lll.scorecard import MODEL_PENDING, hundred_blocks, render_html, render_pdf, ward_context


@pytest.fixture(scope="module")
def inputs():
    rows = []
    for i in range(40):
        status = ["Lead", "GRR", "Unknown", "Non-Lead"][i % 4]
        rows.append({"ward": "1", "tract": "t1", "line_status": status,
                     "address_norm": f"{1200 + (i % 10) * 2} W MAIN ST",
                     "latitude": 41.80 + (i % 7) * 0.001, "longitude": -87.70 + (i // 7) * 0.001})
    for i in range(3):
        rows.append({"ward": "2", "tract": "t2", "line_status": "Lead",
                     "address_norm": f"{500 + i * 2} N OAK AVE",
                     "latitude": 41.90, "longitude": -87.60})
    master = pd.DataFrame(rows)
    acs = pd.DataFrame({"tract": ["t1", "t2"], "median_income": [40e3, 90e3],
                        "majority_group": ["Black", "White"]})
    ward_table = disparity_report(master, acs)["ward"]
    wards = gpd.GeoDataFrame({"ward": ["1", "2"]},
                             geometry=[box(-87.71, 41.79, -87.69, 41.81),
                                       box(-87.61, 41.89, -87.59, 41.91)], crs="EPSG:4326")
    return ward_table, master, wards


def test_scorecard_html_has_numbers_and_pending_model(inputs):
    ctx = ward_context(1, *inputs, snapshot="2025-04-14")
    html = render_html(ctx)
    assert "Ward 1" in html
    assert MODEL_PENDING in html
    assert "75%" in html
    assert ctx["map_png"] and ctx["blocks"]
    assert "docs/methodology.md" in html
    for url in ctx["links"].values():
        assert url in html


def test_suppressed_ward_shows_no_numbers(inputs):
    ctx = ward_context(2, *inputs, snapshot="2025-04-14")
    html = render_html(ctx)
    assert ctx["suppressed"]
    assert "fewer than 5 service lines" in html
    assert ctx["blocks"] == [] and ctx["map_png"] is None
    assert ctx["total_lines"] == "n/a"
    assert "500 block" not in html


def test_hundred_blocks_skip_blocks_under_five_lines():
    lines = pd.DataFrame({"address_norm": ["1200 W MAIN ST"] * 6 + ["1300 W MAIN ST"] * 4,
                          "line_status": ["Lead"] * 10})
    blocks = hundred_blocks(lines)
    assert [b["label"] for b in blocks] == ["1200 block of W Main St"]


def test_scorecard_pdf_is_one_page(inputs):
    from weasyprint import HTML

    from lll import TEMPLATE_DIR

    ctx = ward_context(1, *inputs, snapshot="2025-04-14")
    assert render_pdf(ctx).startswith(b"%PDF")
    doc = HTML(string=render_html(ctx), base_url=str(TEMPLATE_DIR)).render()
    assert len(doc.pages) == 1
