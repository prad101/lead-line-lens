"""Lead Line Lens front end (Streamlit)."""

import streamlit as st
from ui import footer

st.set_page_config(page_title="Lead Line Lens", page_icon=None, layout="centered")

st.title("Lead Line Lens")
st.write(
    "Find out what Chicago's records say about the water service line at your address, "
    "what it likely is if the record says unknown, and what you can do today."
)
st.page_link("pages/lookup.py", label="Look up an address")
st.page_link("pages/report.py", label="Disparity report by ward and tract")
st.page_link("pages/scorecards.py", label="Ward scorecards")
st.page_link("pages/utility.py", label="Utility edition (prototype)")

footer()
