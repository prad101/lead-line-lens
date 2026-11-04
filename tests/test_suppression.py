"""Small-cell suppression must never be bypassed (brief section 10.1)."""

import numpy as np
import pandas as pd
import pytest

from lll.equity import (
    SUPPRESSION_MIN,
    aggregate,
    disparity_report,
    group_rates,
    majority_group,
    suppress_small_cells,
)
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


def test_group_rates_suppresses_small_groups():
    lines = pd.DataFrame({"grp": ["big"] * 6 + ["small"] * 2,
                          "line_status": ["Lead"] * 3 + ["Non-Lead"] * 3 + ["Lead"] * 2})
    out = group_rates(lines, "grp").set_index("grp")
    assert out.loc["big", "share_lead"] == pytest.approx(0.5)
    assert out.loc["small", "suppressed"]
    assert pd.isna(out.loc["small", "share_lead"]) and pd.isna(out.loc["small", "total_lines"])


def _report_inputs():
    """Eight tracts of 6 lines plus one 3-line tract that must stay out of every number."""
    rows = []
    for i in range(8):
        status = ["Lead"] * (i % 4 + 1) + ["Non-Lead"] * (5 - i % 4)
        rows += [{"tract": f"t{i}", "ward": str(i % 2 + 1), "line_status": s} for s in status]
    rows += [{"tract": "tiny", "ward": "3", "line_status": "Lead"} for _ in range(3)]
    master = pd.DataFrame(rows)
    acs = pd.DataFrame({
        "tract": [f"t{i}" for i in range(8)] + ["tiny"],
        "median_income": [20e3, 30e3, 40e3, 50e3, 60e3, 70e3, 80e3, 90e3, 10e3],
        "majority_group": ["Black"] * 4 + ["White"] * 4 + ["Latino"],
    })
    return master, acs


def test_disparity_report_never_publishes_a_small_cell():
    report = disparity_report(*_report_inputs())
    for name, table in report.items():
        if "total_lines" not in table:
            continue
        published = table[~table["suppressed"].astype(bool)]
        assert (published["total_lines"] >= SUPPRESSION_MIN).all(), name
        hidden = table[table["suppressed"].astype(bool)]
        cols = [c for c in table if c.startswith(("n_", "share_", "pred_")) or c == "total_lines"]
        assert hidden[cols].isna().all().all(), f"{name} leaks a suppressed count"


def test_small_tract_is_left_out_of_group_comparisons():
    report = disparity_report(*_report_inputs())
    tract = report["tract"].set_index("tract")
    assert tract.loc["tiny", "suppressed"] and pd.isna(tract.loc["tiny", "income_quartile"])
    assert report["income_quartiles"]["total_lines"].sum() == 48
    assert "Latino" not in set(report["majority_group"]["majority_group"])
    assert report["majority_group"]["total_lines"].sum() == 48


def test_ratios_use_published_rates_only():
    report = disparity_report(*_report_inputs())
    r = report["disparity_ratios"].set_index(["group", "metric"])
    black = r.loc[("Black", "share_lead")]
    assert black["group_rate"] == pytest.approx(10 / 24)
    assert black["reference_rate"] == pytest.approx(10 / 24)
    assert black["ratio"] == pytest.approx(1.0)
    q1 = r.loc[("Q1 lowest income", "share_lead")]
    assert q1["ratio"] == pytest.approx((1 + 2) / 12 / ((3 + 4) / 12))


def test_ward_rank_one_is_highest_need():
    master, acs = _report_inputs()
    master.loc[master["ward"] == "1", "line_status"] = "Unknown"
    ward = disparity_report(master, acs)["ward"].set_index("ward")
    assert ward.loc["1", "rank_needs_action"] == 1
    assert pd.isna(ward.loc["3", "rank_needs_action"])


def test_majority_group_needs_more_than_half():
    df = pd.DataFrame({"pct_black": [0.6, 0.5, np.nan], "pct_latino": [0.2, 0.4, np.nan],
                       "pct_white": [0.1, 0.05, np.nan], "pct_asian": [0.1, 0.05, np.nan]})
    out = majority_group(df)
    assert list(out[:2]) == ["Black", "No majority"] and pd.isna(out[2])
