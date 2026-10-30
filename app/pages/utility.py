"""Utility edition prototype: upload, map, classify, sample, export."""

import streamlit as st
from ui import footer

st.title("Utility edition (prototype)")
st.warning(
    "This tool supports prioritization and statistical estimation. Reclassifying an "
    "unknown line as non-lead must follow methods the Illinois EPA accepts."
)
st.write("Coming in Gate 6.")
footer()
