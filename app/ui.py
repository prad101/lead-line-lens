"""Shared page chrome for the Streamlit app."""

import os

import streamlit as st

from lll import METHODOLOGY_URL, MODEL_CARD_URL

API_URL = os.environ.get("API_URL", "http://localhost:8000")
UTILITY_EDITION = os.environ.get("LLL_UTILITY_EDITION", "1").strip().lower() in {
    "1", "true", "yes", "on",
}

PRIVACY_NOTE = (
    "We do not save addresses, form responses, letters, or uploaded files. "
    "Information is kept only for your current session and is cleared when the session ends."
)


def footer() -> None:
    st.divider()
    st.caption(
        f"[Methodology]({METHODOLOGY_URL}) · [Model card]({MODEL_CARD_URL}) · {PRIVACY_NOTE}"
    )
