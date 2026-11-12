"""Ward scorecard browser and PDF downloads."""

import io
import zipfile

import pandas as pd
import streamlit as st
from ui import footer

from lll import PROCESSED_DIR


@st.cache_data
def ward_table() -> pd.DataFrame | None:
    dirs = sorted(PROCESSED_DIR.glob("equity_chicago_*"))
    if not dirs:
        return None
    return pd.read_csv(dirs[-1] / "ward.csv", dtype={"ward": str})


@st.cache_data(show_spinner="Preparing the PDF...")
def ward_pdf(ward: int) -> bytes:
    from lll.scorecard import ward_pdf as render

    return render(ward)


@st.cache_data(show_spinner="Preparing all 50 PDFs...")
def all_pdfs_zip() -> bytes:
    from lll.scorecard import generate_all

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in generate_all():
            z.write(p, arcname=p.name)
    return buf.getvalue()


st.set_page_config(page_title="Ward scorecards - Lead Line Lens")
st.title("Ward scorecards")
st.write(
    "View a one-page summary for each of Chicago's 50 wards. Each scorecard shows "
    "service line materials, blocks with the greatest need, and steps residents can take. "
    "A priority rank of 1 indicates the highest share of lines requiring action."
)

wt = ward_table()
if wt is None:
    st.warning(
        "Scorecard data is not available yet. "
        "To create it locally, run `python scripts/build_equity.py`."
    )
    footer()
    st.stop()

wt["ward_num"] = wt["ward"].astype(int)
ward = st.selectbox("Ward", sorted(wt["ward_num"]), index=0)
row = wt.set_index("ward_num").loc[ward]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Service lines", f"{row.total_lines:,.0f}")
c2.metric("Lines requiring action", f"{row.share_needs_action:.0%}")
c3.metric("Priority rank (1 = highest)", f"{row.rank_needs_action:.0f} of {len(wt)}")
c4.metric("Replaced so far", f"{row.n_replaced:,.0f}")

st.download_button(f"Download Ward {ward} scorecard (PDF)", ward_pdf(int(ward)),
                   file_name=f"ward_{ward:02d}_scorecard.pdf", mime="application/pdf",
                   type="primary")
if st.button("Prepare all ward scorecards"):
    st.download_button("Download all 50 scorecards (ZIP)", all_pdfs_zip(),
                       file_name="lead_line_lens_ward_scorecards.zip", mime="application/zip")

st.subheader("Compare all wards")
cols = {"ward_num": "Ward", "rank_needs_action": "Rank", "total_lines": "Lines",
        "share_needs_action": "Lines requiring action", "share_lead": "Lead",
        "share_unknown": "Unknown", "n_replaced": "Replaced",
        "median_income": "Median household income"}
view = wt[list(cols)].rename(columns=cols).sort_values("Rank")
st.dataframe(
    view.style.format({"Lines": "{:,.0f}", "Lines requiring action": "{:.0%}", "Lead": "{:.0%}",
                       "Unknown": "{:.0%}", "Replaced": "{:,.0f}",
                       "Median household income": "${:,.0f}"}, na_rep="suppressed"),
    hide_index=True, width="stretch",
)
st.caption(
    "Household income is estimated from the American Community Survey. "
    "Census tract estimates are assigned to wards in proportion to shared land area."
)

footer()
