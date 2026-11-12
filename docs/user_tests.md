# Resident user tests

Five sessions on the resident lookup flow. Testers used live Chicago inventory
in the local app. Addresses, names, and session dates are not recorded here.

The issue asked for the top five problems. The sessions produced **four** distinct
issues. All four are fixed in this pass. There was not a fifth product bug.

The new Department of Water Management FOIA inventory is **not** in this pass.
The master table still uses the 2025-04-14 snapshot.

## Issues found and fixed

### 1. EPA pitcher-filter link was unreachable

The “certified filter” step pointed at an old EPA page that no longer loads.
It now uses the EPA consumer tool for pitcher and point-of-use filters
certified to reduce lead
(`pitcher-filters-certified-reduce-lead` in `lll.guidance.LINKS["epa_filter"]`).

### 2. Multi-line addresses hid the lead line

Some addresses have more than one service line. Lookup returned rows in parquet
order. The letter and the prediction then used the first row. At
`9222 S HALSTED ST, Chicago, IL 60620` that first row was Unknown–Unknown while
a second row was Unknown–Lead. Showing only Unknown–Unknown lowers urgency,
which the ethics rule forbids.

Lines are now sorted **Lead > GRR > Unknown > Non-Lead** (the same rule as
whole-line `line_status`). The lookup page still lists every line. The letter
lists every line in that order. Predict and the “what you can do” plan use the
worst row. If that row is already known lead or galvanized, the model is not
used.

### 3. Legal disclaimer sat inside the draft letter

The sentence “This letter is a request I can edit and send. It is not legal
advice.” was in the Jinja body, so it went into the .txt, .docx, and mailto
draft. It is no longer in the letter. The same sentence is a caption on the
lookup page next to the download and email buttons.

### 4. Home tab was labeled “streamlit app”

Streamlit names the sidebar from the entrypoint file. `app/streamlit_app.py`
showed as “streamlit app.” The entrypoint is now `app/Home.py`, so the tab
reads **Home**. The browser title stays “Lead Line Lens.”

## What did not change

Calibration, small-cell suppression, health source links, and the model card
were not cut. Addresses, surveys, and letters are still not stored. A
prediction still never lowers urgency.
