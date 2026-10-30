"""Shared page chrome for the Streamlit app."""

import os

import streamlit as st

from lll import METHODOLOGY_URL, MODEL_CARD_URL

API_URL = os.environ.get("API_URL", "http://localhost:8000")

PRIVACY_NOTE = (
    "We do not save your address, your answers, or your letter. "
    "Everything stays in this browser session and is gone when you close the page."
)


def footer() -> None:
    st.divider()
    st.caption(
        f"[Methodology]({METHODOLOGY_URL}) · [Model card]({MODEL_CARD_URL}) · {PRIVACY_NOTE}"
    )
