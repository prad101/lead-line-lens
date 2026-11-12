"""Ward and tract disparity report with maps, comparisons, and CSV downloads."""

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from ui import footer

from lll import PROCESSED_DIR, sources
from lll.equity import SUPPRESSION_MIN, choropleth

METRICS = {
    "share_needs_action": "Lines requiring action",
    "share_lead": "Confirmed lead",
    "share_unknown": "Unknown (possibly lead until verified)",
    "share_replaced": "Replaced",
}
TABLES = {
    "ward": "Wards",
    "tract": "Census tracts",
    "income_quartiles": "Income quartiles",
    "majority_group": "Majority race and ethnicity",
    "disparity_ratios": "Disparity ratios",
}
SOURCE = "Chicago DWM inventory to IL EPA (FOIA copy); ACS 2020-2024."


def _latest_equity_dir() -> Path | None:
    dirs = sorted(PROCESSED_DIR.glob("equity_chicago_*"))
    return dirs[-1] if dirs else None


@st.cache_data
def load_tables(path: str) -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(Path(path) / f"{name}.csv", dtype={"ward": str, "tract": str})
            for name in TABLES}


@st.cache_resource
def load_geometry():
    return {"ward": sources.wards(), "tract": sources.tracts()}


def pct(v) -> str:
    return "suppressed" if pd.isna(v) else f"{v:.0%}"


st.set_page_config(page_title="Service line disparities - Lead Line Lens", layout="wide")
st.title("Service line disparities across Chicago")
st.write(
    "Compare lead, galvanized, and unknown service lines across Chicago wards and "
    "census tracts. The report also shows patterns by household income and race or "
    "ethnicity. Treat unknown lines as lead until they are verified."
)

eq_dir = _latest_equity_dir()
if eq_dir is None:
    st.warning(
        "Report data is not available yet. "
        "To create it locally, run `python scripts/build_equity.py`."
    )
    footer()
    st.stop()

tables = load_tables(str(eq_dir))
geo = load_geometry()
snapshot = eq_dir.name.rsplit("_", 1)[-1]
st.caption(f"Based on the city inventory dated {snapshot[:4]}-{snapshot[4:6]}-{snapshot[6:]}.")

c1, c2 = st.columns(2)
level = c1.radio(
    "Geographic area", ["ward", "tract"], format_func=lambda x: TABLES[x], horizontal=True
)
metric = c2.selectbox("Measure to display", list(METRICS), format_func=METRICS.get)

table = tables[level]
tooltip = {"total_lines": "Lines", metric: METRICS[metric]}
if "median_income" in table:
    tooltip["median_income"] = "Median household income"
if "majority_group" in table:
    tooltip["majority_group"] = "Majority group"
m = choropleth(table, geo[level], metric, f"{METRICS[metric]}, by {TABLES[level].lower()}",
               key=level, source=SOURCE, tooltip_cols=tooltip)
st_folium(m, height=560, use_container_width=True, returned_objects=[])

st.subheader("Where is action needed most?")
ratios = tables["disparity_ratios"]
q = ratios[(ratios.comparison == "income quartile") & (ratios.group == "Q1 lowest income")
           & (ratios.metric == "share_needs_action")]
b = ratios[(ratios.group == "Black") & (ratios.metric == "share_needs_action")]
la = ratios[(ratios.group == "Latino") & (ratios.metric == "share_needs_action")]
if not q.empty:
    r = q.iloc[0]
    st.write(
        f"Among tracts in the lowest-income quarter, **{pct(r.group_rate)}** of service "
        f"lines require action. The share is **{pct(r.reference_rate)}** among tracts in "
        f"the highest-income quarter, a ratio of {r.ratio:.2f} to 1."
    )
if not b.empty and not la.empty:
    st.write(
        f"The share requiring action is **{pct(b.iloc[0].group_rate)}** in majority-Black "
        f"tracts and **{pct(la.iloc[0].group_rate)}** in majority-Latino tracts, compared "
        f"with **{pct(b.iloc[0].reference_rate)}** in majority-White tracts."
    )

show = ["total_lines", "share_lead", "share_grr", "share_unknown", "share_needs_action",
        "share_replaced"]
labels = {"total_lines": "Service lines", "share_lead": "Lead", "share_grr": "Galvanized",
          "share_unknown": "Unknown", "share_needs_action": "Lines requiring action",
          "share_replaced": "Replaced", "areas": "Tracts", "income_min": "Income from",
          "income_max": "Income to"}
fmt = {c: "{:.1%}" for c in show if c.startswith("share_")}
fmt.update({"total_lines": "{:,.0f}", "income_min": "${:,.0f}", "income_max": "${:,.0f}"})

inc = tables["income_quartiles"].set_index("income_quartile").rename_axis("Income group")
st.markdown("**By tract median household income**")
st.dataframe(inc[show + ["areas", "income_min", "income_max"]].rename(columns=labels)
             .style.format({labels[k]: v for k, v in fmt.items()}, na_rep="suppressed"),
             width="stretch")
race = tables["majority_group"].set_index("majority_group").rename_axis("Majority group")
st.markdown("**By the tract's majority race or ethnicity** (more than half of residents)")
st.dataframe(race[show + ["areas"]].rename(columns=labels)
             .style.format({labels[k]: v for k, v in fmt.items() if k in show},
                           na_rep="suppressed"),
             width="stretch")
st.caption(
    "Each share combines all service lines in that group of tracts. A disparity ratio "
    "compares the group's share with the reference group: the highest-income quarter or "
    "majority-White tracts. The Census records incomes of $250,000 or more as $250,001."
)

st.subheader("Download report data")
cols = st.columns(len(TABLES))
for col, (name, label) in zip(cols, TABLES.items(), strict=True):
    col.download_button(label, tables[name].to_csv(index=False).encode(),
                        file_name=f"lead_line_lens_{name}_{snapshot}.csv", mime="text/csv")
st.caption(
    f"To protect privacy, counts and shares are blank for areas with fewer than "
    f"{SUPPRESSION_MIN} service lines. The same rule applies to downloaded files."
)

footer()
