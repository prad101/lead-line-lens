"""Address lookup -> status card -> prediction -> survey -> guidance -> letter."""

import streamlit as st
from ui import PRIVACY_NOTE, footer

st.title("Look up an address")
st.info(PRIVACY_NOTE)
st.write("Coming in Gate 4.")
footer()
