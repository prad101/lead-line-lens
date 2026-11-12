"""Address lookup -> status card -> prediction -> survey -> guidance -> letter."""

from __future__ import annotations

import base64

import streamlit as st
from api_client import ApiError
from api_client import letter as fetch_letter
from api_client import lookup as fetch_lookup
from api_client import predict as fetch_predict
from ui import PRIVACY_NOTE, footer

from lll.guidance import (
    LETTER_BUTTON,
    LOOKUP_BUTTON,
    PLAN_BUTTON,
    PRIMARY_CLICKS,
    SURVEY_QUESTIONS,
    markdown,
    plan_for,
    status_plain,
)
from lll.letters import LEGAL_NOTE
from lll.predict import TREAT_AS_LEAD_MESSAGE

assert len(PRIMARY_CLICKS) <= 5

st.set_page_config(page_title="Look up an address - Lead Line Lens", layout="centered")
st.markdown(
    """
    <style>
      .block-container { max-width: 40rem; padding-left: 1rem; padding-right: 1rem; }
      div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {
        width: 100%;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Look up an address")
st.info(PRIVACY_NOTE)

YES_NO = {"Yes": True, "No": False}
FILTER = {"Yes": "yes", "No": "no", "I don't know": "unknown"}
NOTIFY = {"Yes": "yes", "No": "no", "I'm not sure": "unsure"}
TENURE = {"I own it": "own", "I rent it": "rent"}
TESTED = {"Yes": "yes", "No": "no", "I'm not sure": "unsure"}


def _clear_result() -> None:
    for key in ("lookup", "predict", "survey", "plan", "letter_doc"):
        st.session_state.pop(key, None)


with st.form("lookup_form"):
    address = st.text_input(
        "Street address in Chicago",
        placeholder="123 N Main St, Chicago, IL",
        key="address_input",
    )
    looked_up = st.form_submit_button(LOOKUP_BUTTON, type="primary")

if looked_up:
    _clear_result()
    if not address or len(address.strip()) < 3:
        st.error("Please enter a street address.")
    else:
        try:
            st.session_state.lookup = fetch_lookup(address.strip())
            st.session_state.predict = fetch_predict(address.strip())
        except ApiError as err:
            if err.status_code == 404:
                st.error(
                    "No service line was found for that address. "
                    "Check the house number and street."
                )
            elif err.status_code == 400:
                st.error("Could not read that address. Try a house number, street, and city.")
            elif err.status_code == 503:
                st.error("The inventory is not loaded yet.")
            else:
                st.error(err.detail)

data = st.session_state.get("lookup")
pred = st.session_state.get("predict")
if not data:
    footer()
    st.stop()

line = data["lines"][0]
n_lines = data["n_lines"]
st.caption(f"City records as of {data['snapshot']}. Address is not saved.")

st.subheader("What city records say")
if n_lines > 1:
    st.write(f"City records list {n_lines} service lines at this address. Showing each one.")
for i, row in enumerate(data["lines"], start=1):
    heading = f"Line {i}" if n_lines > 1 else "This service line"
    st.markdown(f"**{heading}**")
    st.write(f"City side of the pipe: **{status_plain(row.get('utility_side_material'))}**")
    st.write(f"Property side of the pipe: **{status_plain(row.get('customer_side_material'))}**")
    if row.get("verification_method"):
        st.write(f"How it was checked: {row['verification_method']}")
    if row.get("replaced"):
        when = row.get("replacement_date") or "date not on file"
        st.write(f"Marked replaced: {when}")
    bits = [f"Ward {row['ward']}" if row.get("ward") else None,
            f"tract {row['tract']}" if row.get("tract") else None]
    st.caption(" · ".join(b for b in bits if b) or "Location on file.")
    if row.get("message"):
        st.warning(row["message"])

if pred:
    st.subheader("What the model says")
    st.write(pred.get("message") or TREAT_AS_LEAD_MESSAGE)
    p = pred.get("probability_lead")
    if p is not None:
        pct = round(float(p) * 100)
        tier = (pred.get("tier") or "Low").lower()
        st.write(
            f"The model estimates about **{pct} in 100** chance the property side is "
            f"lead or galvanized ({tier} confidence). This is not an inspection."
        )
        for reason in pred.get("reasons") or []:
            st.write(f"- {reason}")
    else:
        st.caption("No model score is shown when city records already list a known material.")

st.subheader("A few questions")
st.caption("Answers stay in this page session. They are not saved.")
with st.form("survey_form"):
    q1, q2, q3, q4, q5 = SURVEY_QUESTIONS
    child = st.radio(q1, list(YES_NO), index=None)
    filt = st.radio(q2, list(FILTER), index=None)
    noted = st.radio(q3, list(NOTIFY), index=None)
    tenure = st.radio(q4, list(TENURE), index=None)
    tested = st.radio(q5, list(TESTED), index=None)
    plan_clicked = st.form_submit_button(PLAN_BUTTON, type="primary")

if plan_clicked:
    if None in (child, filt, noted, tenure, tested):
        st.error("Please answer each question.")
    else:
        survey = {
            "child_or_pregnancy": YES_NO[child],
            "has_filter": FILTER[filt],
            "notified": NOTIFY[noted],
            "tenure": TENURE[tenure],
            "tested": TESTED[tested],
        }
        st.session_state.survey = survey
        st.session_state.plan = plan_for(
            line_status=line.get("line_status") or "Unknown",
            utility_side=line.get("utility_side_material") or "Unknown",
            customer_side=line.get("customer_side_material") or "Unknown",
            **survey,
        )
        st.session_state.pop("letter_doc", None)

plan = st.session_state.get("plan")
if not plan:
    footer()
    st.stop()

st.subheader("What you can do today")
for item in plan:
    st.markdown(f"- {markdown(item)}")

if st.button(LETTER_BUTTON, type="primary"):
    survey = st.session_state["survey"]
    try:
        addr = st.session_state["address_input"].strip()
        st.session_state.letter_doc = fetch_letter(addr, survey)
    except ApiError as err:
        st.error(err.detail)

doc = st.session_state.get("letter_doc")
if doc:
    st.subheader("A letter you can edit and send")
    st.caption("We do not send this for you. We do not guess a city inbox.")
    st.text_area("Letter", doc["text"], height=280, label_visibility="collapsed")
    raw = base64.b64decode(doc["docx_base64"])
    st.download_button(
        "Download as a Word file", raw,
        file_name="service_line_request.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    st.download_button("Download as a text file", doc["text"],
                       file_name="service_line_request.txt", mime="text/plain")
    st.link_button("Open in your email app", doc["mailto"])
    st.caption(LEGAL_NOTE)

if st.button("Start over"):
    _clear_result()
    st.rerun()

footer()
