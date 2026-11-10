"""Utility edition prototype: upload, map, classify, sample, export."""

from __future__ import annotations

import datetime as dt

import streamlit as st
from ui import UTILITY_EDITION, footer

from lll.ingest import map_columns, suggest_mapping
from lll.predict import TREAT_AS_LEAD_MESSAGE
from lll.schema import CANONICAL_COLUMNS, validate_inventory
from lll.utility import (
    classify,
    export_il_epa_template,
    methods_memo,
    stratified_sample_plan,
    summarize,
)

st.set_page_config(page_title="Utility edition - Lead Line Lens", layout="centered")
st.title("Utility edition (prototype)")

if not UTILITY_EDITION:
    st.info("The utility edition is turned off on this site.")
    footer()
    st.stop()

st.warning(
    "This tool supports prioritization and statistical estimation. Reclassifying an "
    "unknown line as non-lead must follow methods the Illinois EPA accepts. "
    "Your file stays in this browser session. It is not saved on the server."
)
st.caption(TREAT_AS_LEAD_MESSAGE)


def _reset() -> None:
    for key in ("raw", "mapped", "classified", "sample", "warning", "system_name"):
        st.session_state.pop(key, None)


col_a, col_b, col_c = st.columns(3)
if col_a.button("Try Burnham, IL"):
    from lll.sources import burnham

    _reset()
    st.session_state.mapped = burnham()
    st.session_state.system_name = "Burnham, IL (IL0310360)"
if col_b.button("Try East Dundee, IL"):
    from lll.sources import east_dundee

    _reset()
    st.session_state.mapped = east_dundee()
    st.session_state.system_name = "East Dundee, IL (IL0890250)"
if col_c.button("Start over"):
    _reset()
    st.rerun()

uploaded = st.file_uploader("Or upload a CSV or Excel inventory", type=["csv", "xlsx", "xls"])
if uploaded is not None:
    from lll.ingest import read_bytes

    _reset()
    st.session_state.raw = read_bytes(uploaded.getvalue(), uploaded.name)
    st.session_state.system_name = uploaded.name

raw = st.session_state.get("raw")
if raw is not None and st.session_state.get("mapped") is None:
    st.subheader("Match your columns")
    suggested = suggest_mapping([str(c) for c in raw.columns])
    inverse = {canon: raw_name for raw_name, canon in suggested.items()}
    options = ["(skip)"] + [str(c) for c in raw.columns]
    mapping: dict[str, str] = {}
    for canon in CANONICAL_COLUMNS:
        default = inverse.get(canon, "(skip)")
        idx = options.index(default) if default in options else 0
        choice = st.selectbox(canon, options, index=idx, key=f"map_{canon}")
        if choice != "(skip)":
            mapping[choice] = canon
    if st.button("Use this mapping", type="primary"):
        try:
            st.session_state.mapped = validate_inventory(
                map_columns(raw, mapping, snapshot_date=dt.date.today().isoformat())
            )
        except Exception as err:
            st.error(str(err))

mapped = st.session_state.get("mapped")
if mapped is None:
    footer()
    st.stop()

st.subheader(st.session_state.get("system_name") or "Mapped inventory")
base = summarize(mapped)
st.write(
    f"{base['n_rows']:,} lines. Known customer side: {base['n_known']:,}. "
    f"Unknown: {base['n_unknown']:,}."
)

if st.button("Score unknown lines", type="primary"):
    scored, warning = classify(mapped)
    st.session_state.classified = scored
    st.session_state.warning = warning
    st.session_state.sample = stratified_sample_plan(scored)

scored = st.session_state.get("classified")
if scored is None:
    footer()
    st.stop()

counts = summarize(scored)
if st.session_state.get("warning"):
    st.warning(st.session_state.warning)
else:
    st.success("A new model was fit on this inventory's known rows (200 or more).")
st.write(
    f"Mean predicted chance of lead or galvanized among unknown lines: "
    f"{counts['mean_p_unknown']:.0%}." if counts["mean_p_unknown"] is not None
    else "No unknown lines to score."
)
st.caption("A prediction never lowers urgency. Unknown stays possibly lead until checked.")

sample = st.session_state.get("sample")
if sample is not None and len(sample):
    st.subheader("Lines to check first")
    st.caption(
        f"Fixed sample of {len(sample)} unknown lines, "
        "by year built and city-side material."
    )
    st.dataframe(sample, hide_index=True, width="stretch")
    st.download_button(
        "Download the sample (CSV)",
        sample.to_csv(index=False).encode(),
        file_name="verification_sample.csv",
        mime="text/csv",
    )

memo = methods_memo({
    "system_name": st.session_state.get("system_name"),
    "system_id": None,
    "run_date": dt.date.today().isoformat(),
    "n_rows": counts["n_rows"],
    "n_known": counts["n_known"],
    "n_unknown": counts["n_unknown"],
    "transfer_warning": st.session_state.get("warning"),
    "sample_n": 0 if sample is None else int(len(sample)),
    "treat_as_lead": TREAT_AS_LEAD_MESSAGE,
})
export = export_il_epa_template(scored)
st.subheader("Export")
st.download_button(
    "Download Illinois EPA template (CSV)",
    export,
    file_name="il_epa_inventory_export.csv",
    mime="text/csv",
    type="primary",
)
st.download_button("Download the methods memo (text)", memo,
                   file_name="methods_memo.txt", mime="text/plain")
st.text_area("Methods memo", memo, height=220)

footer()
