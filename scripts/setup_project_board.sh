#!/usr/bin/env bash
# Create the "Lead Line Lens" GitHub Projects (v2) board, a single-select "Gate" field,
# gate labels, and one issue per Section 8 benchmark/deliverable. Safe to re-run: existing
# project, field, labels, and issues (matched by exact title) are reused.
#
# Requires: gh auth refresh -s project,read:project
set -euo pipefail

OWNER="prad101"
REPO="prad101/lead-line-lens"
TITLE="Lead Line Lens"
GATES=("Gate 0" "Gate 1" "Gate 2" "Gate 3" "Gate 4" "Gate 5" "Gate 6" "Backlog")

if ! gh auth status 2>&1 | grep -q "'project'"; then
  echo "error: gh token is missing the 'project' scope." >&2
  echo "Run: gh auth refresh -s project,read:project" >&2
  exit 1
fi

num=$(gh project list --owner "$OWNER" --format json \
  --jq ".projects[] | select(.title==\"$TITLE\") | .number")
if [[ -z "$num" ]]; then
  num=$(gh project create --owner "$OWNER" --title "$TITLE" --format json --jq .number)
  echo "created project #$num"
fi
gh project link "$num" --owner "$OWNER" --repo "$REPO" >/dev/null 2>&1 || true
project_id=$(gh project view "$num" --owner "$OWNER" --format json --jq .id)

field_json() { gh project field-list "$num" --owner "$OWNER" --format json; }
if [[ -z "$(field_json | jq -r '.fields[] | select(.name=="Gate") | .id')" ]]; then
  opts=$(IFS=,; echo "${GATES[*]}")
  gh project field-create "$num" --owner "$OWNER" --name "Gate" \
    --data-type SINGLE_SELECT --single-select-options "$opts" >/dev/null
fi
fields=$(field_json)
field_id=$(jq -r '.fields[] | select(.name=="Gate") | .id' <<<"$fields")
option_id() { jq -r --arg n "$1" '.fields[] | select(.name=="Gate") | .options[] | select(.name==$n) | .id' <<<"$fields"; }

for i in 0 1 2 3 4 5 6; do
  gh label create "gate-$i" --repo "$REPO" --color "0b5394" --description "Gate $i" --force >/dev/null
done
gh label create "week-8" --repo "$REPO" --color "777777" --description "Buffer and handoff" --force >/dev/null

existing=$(gh issue list --repo "$REPO" --state all --limit 500 --json title --jq '.[].title')

add_issue() {  # gate_option label week title
  local gate="$1" label="$2" week="$3" title="$4" url item
  if grep -Fxq "$title" <<<"$existing"; then
    echo "skip (exists): $title"
    return
  fi
  url=$(gh issue create --repo "$REPO" --title "$title" --label "$label" \
    --body "Benchmark from the project brief, Section 8 ($week). Closes toward **$gate**.")
  item=$(gh project item-add "$num" --owner "$OWNER" --url "$url" --format json --jq .id)
  gh project item-edit --id "$item" --project-id "$project_id" --field-id "$field_id" \
    --single-select-option-id "$(option_id "$gate")" >/dev/null
  echo "created: $title"
}

W1="Week 1, Sep 21-25"; W2="Week 2, Sep 28-Oct 2"; W3="Week 3, Oct 5-9"; W4="Week 4, Oct 12-16"
W5="Week 5, Oct 19-23"; W6="Week 6, Oct 26-30"; W7="Week 7, Nov 2-6"; W8="Week 8, Nov 9-13"

add_issue "Gate 0" gate-0 "$W1" "Repository, Docker dev environment, and CI lint+test job running"
add_issue "Gate 0" gate-0 "$W1" "Chicago line-level inventory downloaded (or records request filed)"
add_issue "Gate 0" gate-0 "$W1" "Two small Illinois system inventories downloaded and documented"
add_issue "Gate 0" gate-0 "$W1" "Cook County parcels, ACS tables, and boundaries downloaded and documented"
add_issue "Gate 0" gate-0 "$W1" "Data dictionary covers 100% of inventory columns"
add_issue "Gate 0" gate-0 "$W1" "Half-page note on current federal and Illinois compliance dates"
add_issue "Gate 0" gate-0 "$W1" "README v0 and project board"
add_issue "Gate 0" gate-0 "$W1" "Data audit memo: row counts, unknown share, duplicates, missingness"

add_issue "Gate 1" gate-1 "$W2" "At least 95% of inventory rows matched to a parcel or geocoded"
add_issue "Gate 1" gate-1 "$W2" "100% of matched rows assigned block, tract, ward, and community area"
add_issue "Gate 1" gate-1 "$W2" "EDA notebook answers the five Week 2 questions"
add_issue "Gate 1" gate-1 "$W2" "Master table (parquet) with build script"
add_issue "Gate 1" gate-1 "$W2" "Matching report with failure reason codes"
add_issue "Gate 1" gate-1 "$W2" "First two maps"

add_issue "Gate 2" gate-2 "$W3" "Pre-1986 rule and block majority baselines computed and recorded"
add_issue "Gate 2" gate-2 "$W3" "LightGBM beats block majority by >=0.05 PR-AUC and pre-1986 rule by >=5 pts balanced accuracy (GroupKFold)"
add_issue "Gate 2" gate-2 "$W3" "ECE <= 0.05 after calibration; Brier score reported"
add_issue "Gate 2" gate-2 "$W3" "Error rates by income quartile and majority race/ethnicity reported"
add_issue "Gate 2" gate-2 "$W3" "Training pipeline script and versioned model artifact"
add_issue "Gate 2" gate-2 "$W3" "Model card v1 with reliability diagram and SHAP summary"

add_issue "Gate 3" gate-3 "$W4" "Lookup, predict, area, letter, scorecard endpoints under 2 s at p95 locally"
add_issue "Gate 3" gate-3 "$W4" "OpenAPI documentation complete for every endpoint"
add_issue "Gate 3" gate-3 "$W4" "pytest coverage >= 70% on service modules"
add_issue "Gate 3" gate-3 "$W4" "Docker image builds and runs; Render staging URL live"

add_issue "Gate 4" gate-4 "$W5" "Address to status card to prediction to survey to guidance to letter in <= 5 clicks"
add_issue "Gate 4" gate-4 "$W5" "Layout verified at 375 px; color contrast meets WCAG AA"
add_issue "Gate 4" gate-4 "$W5" "All guidance text at or below 8th-grade reading level (textstat test)"
add_issue "Gate 4" gate-4 "$W5" "Every health statement carries a source link"
add_issue "Gate 4" gate-4 "$W5" "MVP demo URL and two-minute screen recording"

add_issue "Gate 5" gate-5 "$W6" "Disparity report for all 50 wards and every tract with >= 5 lines; suppression enforced and tested"
add_issue "Gate 5" gate-5 "$W6" "Scorecard PDF generated automatically for every ward"
add_issue "Gate 5" gate-5 "$W6" "Three sample scorecards reviewed by a ward office, community org, or reporter"
add_issue "Gate 5" gate-5 "$W6" "Disparity report page with CSV downloads"
add_issue "Gate 5" gate-5 "$W6" "Methodology page linked from every page footer"

add_issue "Gate 6" gate-6 "$W7" "Utility edition end to end on two non-Chicago Illinois inventories"
add_issue "Gate 6" gate-6 "$W7" "Five resident test sessions logged; top five issues fixed"
add_issue "Gate 6" gate-6 "$W7" "Error monitoring and uptime check on"
add_issue "Gate 6" gate-6 "$W7" "Version 1.0 tagged and deployed to production URL with final model card"
add_issue "Gate 6" gate-6 "$W7" "Utility edition page and methods memo template"
add_issue "Gate 6" gate-6 "$W7" "Feature flag separating free resident flow from paid utility flow"
add_issue "Gate 6" gate-6 "$W7" "User test log"

add_issue "Backlog" week-8 "$W8" "Zero open critical or high-severity bugs"
add_issue "Backlog" week-8 "$W8" "README, deployment runbook, and data dictionary complete"
add_issue "Backlog" week-8 "$W8" "Handoff call held with ChiEAC; handoff memo with next-quarter roadmap"
add_issue "Backlog" week-8 "$W8" "Three-minute demo video"
add_issue "Backlog" week-8 "$W8" "Closing LinkedIn post: retrospective and thanks"

echo "Done. In the project UI, set the board view to group by the 'Gate' field."
