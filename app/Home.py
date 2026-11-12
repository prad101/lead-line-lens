"""Lead Line Lens front end (Streamlit)."""

import streamlit as st
from ui import UTILITY_EDITION, footer

st.set_page_config(page_title="Lead Line Lens", page_icon=None, layout="centered")

st.title("Lead Line Lens")
st.write(
    "Review Chicago's records for the water service line at your address. "
    "If the material is unknown, see a model estimate and clear next steps."
)
st.page_link("pages/lookup.py", label="Check a Chicago address")
st.page_link("pages/report.py", label="Explore service line disparities")
st.page_link("pages/scorecards.py", label="View ward scorecards")
if UTILITY_EDITION:
    st.page_link("pages/utility.py", label="Open utility tools (prototype)")

footer()
