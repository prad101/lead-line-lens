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

st.set_page_config(page_title="Check an address - Lead Line Lens", layout="centered")
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

st.title("Check a Chicago address")
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
        st.error("Enter a Chicago street address.")
    else:
        try:
            st.session_state.lookup = fetch_lookup(address.strip())
            st.session_state.predict = fetch_predict(address.strip())
        except ApiError as err:
            if err.status_code == 404:
                st.error(
                    "We could not find a service line for that address. "
                    "Check the house number and street name, then try again."
                )
            elif err.status_code == 400:
                st.error(
                    "We could not recognize that address. "
                    "Include the house number, street name, and city."
                )
            elif err.status_code == 503:
                st.error(
                    "Service line records are not available right now. "
                    "Please try again later."
                )
            else:
                st.error(err.detail)

data = st.session_state.get("lookup")
pred = st.session_state.get("predict")
if not data:
    footer()
    st.stop()

line = data["lines"][0]
n_lines = data["n_lines"]
st.caption(f"City records last updated {data['snapshot']}. Your address is not stored.")

st.subheader("Chicago service line records")
if n_lines > 1:
    st.write(f"City records include {n_lines} service lines at this address.")
for i, row in enumerate(data["lines"], start=1):
    heading = f"Line {i}" if n_lines > 1 else "This service line"
    st.markdown(f"**{heading}**")
    st.write(
        f"City side of the service line: "
        f"**{status_plain(row.get('utility_side_material'))}**"
    )
    st.write(
        f"Property side of the service line: "
        f"**{status_plain(row.get('customer_side_material'))}**"
    )
    if row.get("verification_method"):
        st.write(f"Verification method: {row['verification_method']}")
    if row.get("replaced"):
        when = row.get("replacement_date") or "date not available"
        st.write(f"Recorded as replaced: {when}")
    bits = [f"Ward {row['ward']}" if row.get("ward") else None,
            f"Census tract {row['tract']}" if row.get("tract") else None]
    st.caption(" · ".join(b for b in bits if b) or "Location on file.")
    if row.get("message"):
        st.warning(row["message"])

if pred:
    st.subheader("Model estimate")
    st.write(pred.get("message") or TREAT_AS_LEAD_MESSAGE)
    p = pred.get("probability_lead")
    if p is not None:
        pct = round(float(p) * 100)
        tier = (pred.get("tier") or "Low").lower()
        st.write(
            f"The model estimates about a **{pct} out of 100** chance that the property side "
            f"is lead or galvanized. Confidence level: {tier}. This is not an inspection."
        )
        for reason in pred.get("reasons") or []:
            st.write(f"- {reason}")
    else:
        st.caption(
            "No model estimate is needed because city records already identify the material."
        )

st.subheader("Tell us about your household")
st.caption("Your responses are used only to tailor the next steps shown in this session.")
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

st.subheader("Recommended next steps")
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
    st.subheader("Review your service line request")
    st.caption(
        "Lead Line Lens does not send this letter or choose a recipient. "
        "Review and edit it before sending."
    )
    st.text_area("Letter", doc["text"], height=280, label_visibility="collapsed")
    raw = base64.b64decode(doc["docx_base64"])
    st.download_button(
        "Download Word document", raw,
        file_name="service_line_request.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    st.download_button("Download text file", doc["text"],
                       file_name="service_line_request.txt", mime="text/plain")
    st.link_button("Open a draft in your email app", doc["mailto"])
    st.caption(LEGAL_NOTE)

if st.button("Start over"):
    _clear_result()
    st.rerun()

footer()
