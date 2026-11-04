# Methodology

How Lead Line Lens turns Chicago's service line inventory into the address lookup, the
disparity report, and the ward scorecards. Every page of the app links here. Column-level
detail is in [data_dictionary.md](data_dictionary.md); data quality findings are in
[data_audit.md](data_audit.md).

## Data sources

| Source | What we use | Vintage |
|---|---|---|
| Chicago Department of Water Management (DWM) service line inventory submitted to Illinois EPA | one row per service line: address, PIN, utility-side and customer-side material, replacement date | snapshot April 14, 2025; a FOIA copy published by Inside Climate News, Grist, and WBEZ |
| Cook County Assessor parcels and residential building characteristics (Chicago Data Portal) | PIN, location, year built, building class, units | downloaded Oct 30, 2026 |
| City of Chicago boundaries | wards (2023 map, 50 wards), community areas (77), census tracts (2020) | downloaded Oct 30, 2026 |
| U.S. Census Bureau Geocoder (batch) | location and 2020 census block for addresses that did not match a parcel | at build time |
| American Community Survey (ACS) 2020-2024 5-year estimates, Cook County tracts | median household income (B19013), race and Hispanic origin (B03002), children under 6 (B09001), housing built before 1950 (B25034) | 2024 release |

The inventory is a third-party copy, not a city API. The full DWM export has been requested
by FOIA; when it arrives the same pipeline rebuilds every output. Burnham and East Dundee
inventories are used for schema tests and the utility edition, not in any Chicago number.

## Address matching and geography

Each inventory line is matched to a place in this order:

1. **PIN**: the inventory PIN matches an Assessor parcel.
2. **Exact address**: normalized street address (usaddress parsing, standard suffixes and
   directions) matches a parcel address.
3. **Nearest number**: same street, same side, house number within 10 of a parcel. This
   gives a location only; building attributes are never borrowed from a neighboring parcel.
4. **Census Geocoder**: the address is sent to the Census batch geocoder.

Of 491,705 lines, 98.28% have a location (90.97% exact address, 5.29% nearest number,
2.02% Census). The other 8,446 carry a reason code (Census timeout, no match, tie,
intersection, or unparseable address) and are left out of every area count. They are 75%
Non-Lead, so the gap mostly drops new and large buildings, not uncertain lines.

Block, block group, and tract come from the parcel record or the Census response. Ward and
community area come from a spatial join to the 2023 ward map and the community area map.
A point that falls in no polygon (usually just past an edge) takes the nearest area within
100 meters. 153 located lines fall outside city limits and have no ward.

## Material categories

Each side of a line (utility and customer) is mapped to one of four categories, following
the Illinois EPA inventory template:

| Category | Means | Includes |
|---|---|---|
| Lead | lead pipe | IEPA code L |
| GRR | galvanized requiring replacement | G and GRR (any galvanized line is treated as GRR) |
| Non-Lead | records or inspection show no lead | C, CLS, O, P, NL, UNL ("unknown, not lead") |
| Unknown | material not known | U and anything unrecognized |

The whole-line status uses the utility's reported line class when it has one. Otherwise it
takes the worst side, in the order Lead, then GRR, then Unknown, then Non-Lead. In Chicago
the reported class equals the derived class on 100% of rows. Citywide: 150,864 Lead, 10,526
GRR, 251,247 Unknown, and 79,068 Non-Lead lines; 10,640 lines are marked replaced.

**Unknown is never shown as safe.** Everywhere in the app an Unknown line reads "possibly
lead until checked". "Lead, galvanized, or unknown" (the share used for ranking) counts every
line that needs replacement or verification.

## Small-cell suppression

Any area or group with fewer than **5** service lines is suppressed. Every count, share, and
prediction for it is blank, including its total line count, so a suppressed area reveals
only that it has fewer than five lines. This applies to the app, the CSV downloads, the
API, and the scorecards. On scorecards, hundred-blocks with fewer than 5 lines are left out
of the block table and map hexagons with fewer than 5 lines stay blank. A test
(`tests/test_suppression.py`) fails if any published table has a row under 5 lines or a
suppressed row with a number in it.

In the April 2025 snapshot, 12 of 811 tracts are suppressed. No ward is suppressed.

## Disparity measures

**Tract and ward tables.** Counts and shares of each status, the share that is lead,
galvanized, or unknown ("needs action"), and the number replaced. Wards are ranked by the
needs-action share; rank 1 is the ward with the most to fix or check.

**Pooled rates.** Group comparisons pool all lines in the group's tracts: the share is total
needs-action lines over total lines, not an average of tract shares. Large tracts therefore
count more, which matches the question "what share of lines in these neighborhoods".

**Income quartiles.** Tracts with at least 5 lines and a published ACS median household
income (781 tracts) are split into four groups of about equal tract count by income. Each line
takes its tract's quartile. 18 tracts with 5 or more lines have no published income and are
left out.
The Census top-codes income at $250,000 or more, reported as $250,001.

**Majority group.** A tract's majority group is the race or ethnicity group (Black,
Latino, White, or Asian, from B03002; Latino of any race, the others non-Latino) that is more
than half of residents. Otherwise it is "No majority". Only tracts with at least 5 lines are
included.

**Disparity ratio.** The group's pooled share divided by the reference group's share. The
reference groups are the highest-income quartile and majority-White tracts. A ratio above 1
means the group has a larger share of lines to fix or check. Ratios are computed only from
published (unsuppressed) groups.

**Ward demographics.** ACS is published for tracts, not wards. Tract counts (people,
children under 6, housing units) are split among wards in proportion to the share of the
tract's land area inside each ward. Ward median income is the population-weighted average of
tract medians. Medians cannot be added, so this is an approximation and is labeled as an
estimate on scorecards.

**Headline results (April 2025 snapshot).**

| Group | Lead, galvanized, or unknown | Ratio to reference |
|---|---|---|
| Lowest-income quartile of tracts | 88.6% | 1.19 |
| Highest-income quartile (reference) | 74.3% | |
| Majority-Black tracts | 89.9% | 1.20 |
| Majority-Latino tracts | 92.2% | 1.23 |
| Majority-White tracts (reference) | 75.2% | |

All tables are in the app's disparity report and its CSV downloads.

## Prediction model

Not built yet (Gate 2). Until model v1 is calibrated and its model card is published, every
"predicted lead among unknown lines" value reads "Pending model v1". When it is added:

- A prediction never lowers urgency. An Unknown line stays "possibly lead until checked"
  whatever its predicted probability.
- Predicted shares are suppressed under the same 5-line rule.
- Calibration, validation, and known failure modes will be in the model card.

## What residents can do

Scorecards and the lookup link to the City's free water test kit
(chicagowaterquality.org), the City's own service line lookup, the City's
equity lead service line replacement program, and EPA's basic lead information. Lead Line
Lens does not give medical advice; questions about health go to a doctor or the Chicago
Department of Public Health.

## Privacy

The app does not save addresses, survey answers, or letters on a server, and has no
third-party analytics. Published data are area summaries with small cells suppressed.

## Limitations

- **One snapshot.** Counts reflect April 14, 2025. Lines replaced or verified since then
  are not shown.
- **Third-party copy.** The inventory came from a journalist FOIA release, not the City's
  current export.
- **Unmatched lines.** 8,446 lines (1.72%) have no location and are missing from area
  counts, including 7,585 from one Census Geocoder batch that timed out.
- **Unknown is large.** Half of all lines are Unknown. Some are likely Non-Lead, so the
  needs-action share overstates lines that are actually lead or galvanized. It does not
  overstate lines that need checking.
- **Ecological comparisons.** Income and race describe tracts, not households. A
  difference between groups of tracts does not show that any household's line depends on its
  income or race.
- **Ward estimates.** Ward demographics come from area apportionment, which assumes people are
  spread evenly within a tract.
- **ACS margins of error.** Tract estimates have sampling error; margins of error are not
  shown.
- **Records, not inspection.** Half of Chicago lines list no verification method, and 5,050
  classifications cite only the building's construction date ("Home Built Date"), not an
  inspection of the pipe.
