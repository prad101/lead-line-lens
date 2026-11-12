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

st.set_page_config(page_title="Utility inventory tools - Lead Line Lens", layout="centered")
st.title("Utility inventory tools (prototype)")

if not UTILITY_EDITION:
    st.info("Utility inventory tools are not available on this site.")
    footer()
    st.stop()

st.warning(
    "Use this tool to prioritize verification work and estimate likely materials. "
    "It does not verify or reclassify a service line. An unknown line may be classified "
    "as non-lead only through a method accepted by the Illinois EPA. Uploaded files are "
    "kept only for the current session and are not saved."
)
st.caption(TREAT_AS_LEAD_MESSAGE)


def _reset() -> None:
    for key in ("raw", "mapped", "classified", "sample", "warning", "system_name"):
        st.session_state.pop(key, None)


col_a, col_b, col_c = st.columns(3)
if col_a.button("Load Burnham example"):
    from lll.sources import burnham

    _reset()
    st.session_state.mapped = burnham()
    st.session_state.system_name = "Burnham, IL (IL0310360)"
if col_b.button("Load East Dundee example"):
    from lll.sources import east_dundee

    _reset()
    st.session_state.mapped = east_dundee()
    st.session_state.system_name = "East Dundee, IL (IL0890250)"
if col_c.button("Start over"):
    _reset()
    st.rerun()

uploaded = st.file_uploader(
    "Upload your own CSV or Excel inventory", type=["csv", "xlsx", "xls"]
)
if uploaded is not None:
    from lll.ingest import read_bytes

    _reset()
    st.session_state.raw = read_bytes(uploaded.getvalue(), uploaded.name)
    st.session_state.system_name = uploaded.name

raw = st.session_state.get("raw")
if raw is not None and st.session_state.get("mapped") is None:
    st.subheader("Match inventory columns")
    st.caption("For each standard field, select the matching column from your file.")
    suggested = suggest_mapping([str(c) for c in raw.columns])
    inverse = {canon: raw_name for raw_name, canon in suggested.items()}
    options = ["(do not map)"] + [str(c) for c in raw.columns]
    mapping: dict[str, str] = {}
    for canon in CANONICAL_COLUMNS:
        default = inverse.get(canon, "(do not map)")
        idx = options.index(default) if default in options else 0
        choice = st.selectbox(canon, options, index=idx, key=f"map_{canon}")
        if choice != "(do not map)":
            mapping[choice] = canon
    if st.button("Confirm column mapping", type="primary"):
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
    f"Inventory total: **{base['n_rows']:,} service lines**. "
    f"Known property-side material: **{base['n_known']:,}**. "
    f"Unknown property-side material: **{base['n_unknown']:,}**."
)

if st.button("Estimate unknown service lines", type="primary"):
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
    st.success(
        "A local model was fitted using the known rows in this inventory "
        "(at least 200 rows)."
    )
st.write(
    f"Average estimated chance of lead or galvanized material among unknown lines: "
    f"{counts['mean_p_unknown']:.0%}." if counts["mean_p_unknown"] is not None
    else "This inventory has no unknown lines to estimate."
)
st.caption(
    "A prediction never reduces urgency. Treat every unknown line as lead until it is verified."
)

sample = st.session_state.get("sample")
if sample is not None and len(sample):
    st.subheader("Recommended verification sample")
    st.caption(
        f"This sample includes {len(sample)} unknown lines, grouped by construction year "
        "and city-side material."
    )
    st.dataframe(sample, hide_index=True, width="stretch")
    st.download_button(
        "Download verification sample (CSV)",
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
st.subheader("Download results")
st.download_button(
    "Download Illinois EPA inventory template (CSV)",
    export,
    file_name="il_epa_inventory_export.csv",
    mime="text/csv",
    type="primary",
)
st.download_button("Download methods memo (text)", memo,
                   file_name="methods_memo.txt", mime="text/plain")
st.text_area("Review the methods memo", memo, height=220)

footer()
