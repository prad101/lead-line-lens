"""Small-cell suppression must never be bypassed (brief section 10.1)."""

import pandas as pd
import pytest

from lll.equity import SUPPRESSION_MIN, aggregate, suppress_small_cells
from lll.features import area_aggregates


def _master():
    wards = ["1"] * 4 + ["2"] * 5 + ["3"] * 10
    status = ["Lead"] * 3 + ["Unknown"] + ["Lead"] * 2 + ["Non-Lead"] * 3 + ["GRR"] * 10
    return pd.DataFrame({"ward": wards, "line_status": status})


def test_suppression_threshold_is_five():
    assert SUPPRESSION_MIN == 5


def test_area_under_five_lines_is_fully_blanked():
    out = aggregate(_master(), "ward").set_index("ward")
    w1 = out.loc["1"]
    assert bool(w1["suppressed"])
    data_cols = [c for c in out.columns if c.startswith(("n_", "share_")) or c == "total_lines"]
    assert data_cols, "expected count/share columns"
    assert w1[data_cols].isna().all(), "suppressed ward leaks a count or share"


def test_area_at_threshold_is_published():
    out = aggregate(_master(), "ward").set_index("ward")
    assert not bool(out.loc["2", "suppressed"])
    assert out.loc["2", "total_lines"] == 5
    assert out.loc["2", "share_lead"] == pytest.approx(0.4)
    assert out.loc["3", "share_grr"] == 1.0


def test_no_published_row_below_threshold():
    out = aggregate(_master(), "ward")
    published = out[~out["suppressed"]]
    assert (published["total_lines"] >= SUPPRESSION_MIN).all()


def test_area_aggregates_routes_through_suppression():
    out = area_aggregates(_master(), "ward")
    assert out.set_index("ward").loc["1", "suppressed"]


def test_prediction_columns_are_suppressed_too():
    m = _master()
    m["pred_lead_prob"] = 0.9
    out = aggregate(m, "ward").set_index("ward")
    assert pd.isna(out.loc["1", "pred_lead_share_unknown"])


def test_suppress_small_cells_on_arbitrary_table():
    t = pd.DataFrame({"tract": ["a", "b"], "total_lines": [4, 6], "n_lead": [4, 1],
                      "share_lead": [1.0, 1 / 6], "median_income": [30000, 90000]})
    out = suppress_small_cells(t).set_index("tract")
    assert pd.isna(out.loc["a", "n_lead"]) and pd.isna(out.loc["a", "share_lead"])
    assert out.loc["a", "median_income"] == 30000
    assert out.loc["b", "n_lead"] == 1
