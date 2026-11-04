# Data dictionary

One row per column per source: type, allowed values, missingness, and the canonical field it maps to. Download dates and URLs are recorded per source.

## Canonical inventory schema (Illinois EPA template based)

| Canonical field | Type | Allowed values | Required | Notes |
|---|---|---|---|---|
| line_id | string | unique | yes | |
| address | string | | no | in-memory only for resident lookups |
| pin | string (14 digits) | | no | Cook County PIN |
| utility_side_material | category | Lead, GRR, Non-Lead, Unknown | yes | |
| customer_side_material | category | Lead, GRR, Non-Lead, Unknown | yes | |
| year_built | int | 1830–current year | no | |
| install_year | int | 1830–current year | no | |
| diameter_in | float | > 0 | no | |
| verification_method | string | | no | |
| replacement_date | date | | no | |
| notification_date | date | | no | |
| snapshot_date | date | | yes | inventory snapshot date |

## Material vocabulary mapping

Implemented in `lll.schema.normalize_material`; tested in `tests/test_schema.py`. A mapping
never lowers urgency: anything galvanized becomes GRR, anything unrecognized becomes Unknown.

| Raw value (source) | Canonical |
|---|---|
| L (IEPA code; Chicago), Lead, lead, Lead - LP (Burnham 109), Suspected Lead - SLP (Burnham 200, via status field) | Lead |
| GRR, Galvanized Requiring Replacement, G (IEPA code), Galvanized, Galvanized Pipe - GP (Burnham 89) | GRR |
| NL, UNL, C, CLS, O, P (IEPA codes; Chicago), Non Lead, Unknown Not Lead, Copper, Copper No Lead Solder, Copper with Lead Solder, Cast_Ductile Iron or Transite, Plastic PVC HDPE PEX, Brass, Asbestos Cement | Non-Lead |
| U (IEPA code; Chicago), Unknown, Lead Status Unknown, Not Observed, blank | Unknown |
| Burnham `utilstatus` / `custstatus` 0 / 1 / 2 / 3 | Unknown / Lead / Non-Lead / GRR |

## Sources

All files live under `data/raw/` (gitignored). Links verified Oct 30, 2026.

| Source | File | Rows | Snapshot | Downloaded | URL |
|---|---|---|---|---|---|
| Chicago line-level inventory (Chicago's IEPA submission, obtained via FOIA and published by Inside Climate News, Grist, and WBEZ) | `chicago/2025_inventory.xlsx` | 491,705 | 2025-04-14 | 2026-10-30 | https://raw.githubusercontent.com/InsideClimateNews/2025-08-chicago-lead-service-lines/main/data/2025_inventory.xlsx |
| Illinois EPA inventory reports (one row per system-year) | `ServiceLineMaterialInventoryReports.csv` | 9,100 | ReportingYear 2017–2025 | 2026-10-29 | https://webapps.illinois.gov/EPA/WebSiteApi/api/ServiceLineMaterialInventory/ExportReportsToCsv |
| Cook County Assessor, Parcel Universe (Current) `pabr-t5kh` | `Assessor_-_Parcel_Universe_(Current)_20261029.csv` | 1,864,446 (881,586 Chicago) | tax year 2026 | 2026-10-29 | https://datacatalog.cookcountyil.gov/api/views/pabr-t5kh/rows.csv?accessType=DOWNLOAD |
| Cook County Assessor, Parcel Addresses `3723-97qp` (Chicago, 2026; pin, pin10, address, zip only) | `assessor/addresses_chicago_2026.csv` | 883,986 | 2026 | 2026-10-30 | https://datacatalog.cookcountyil.gov/resource/3723-97qp.csv |
| Cook County Assessor, Residential improvement characteristics `x54s-btds` (Chicago townships 70–77, 2026) | `assessor/res_chars_chicago_2026.csv` | 439,538 | 2026 | 2026-10-30 | https://datacatalog.cookcountyil.gov/resource/x54s-btds.csv |
| Cook County Assessor, Condominium characteristics `3r7i-mrz4` (Chicago townships 70–77, 2026) | `assessor/condo_chars_chicago_2026.csv` | 287,531 | 2026 | 2026-10-30 | https://datacatalog.cookcountyil.gov/resource/3r7i-mrz4.csv |
| Chicago wards (2023–) `p293-wvbd` | `boundaries/wards_2023.geojson` | 50 | 2023 map | 2026-10-30 | https://data.cityofchicago.org/resource/p293-wvbd.geojson |
| Chicago community areas `igwz-8jzy` | `boundaries/community_areas.geojson` | 77 | | 2026-10-30 | https://data.cityofchicago.org/resource/igwz-8jzy.geojson |
| Chicago census tracts 2020 `7qjk-677h` | `boundaries/tracts_2020.geojson` | 789 | 2020 | 2026-10-30 | https://data.cityofchicago.org/resource/7qjk-677h.geojson |
| Burnham, IL (IL0310360) line-level inventory, ArcGIS FeatureServer | `small_systems/burnham.geojson` | 1,208 | live layer, edited 2026-10-29 | 2026-10-30 | https://services2.arcgis.com/JcgVFPqPYKhb5Qes/arcgis/rest/services/Burnham_wService_Inventory_PUBLIC/FeatureServer/0 |
| East Dundee, IL (IL0890250) line-level inventory, ArcGIS FeatureServer | `small_systems/east_dundee.geojson` | 1,497 | live layer, edited 2026-10-27 | 2026-10-30 | https://services5.arcgis.com/6lsGpLq06usvMrhg/arcgis/rest/services/Water_ServiceLine_Material_Inventory_ReadOnly_view/FeatureServer/0 |
| ACS 5-year 2024 (B19013, B03002, B09001, B25034), Cook County tracts | via API (`CENSUS_API_KEY`) | 1,332 tracts | 2020–2024 | at build time | https://api.census.gov/data/2024/acs/acs5 |

Notes:
- The Chicago file is a third-party copy of a public record. An official, current export needs a FOIA request to the Department of Water Management (https://www.chicago.gov/publicrecords, DWMfoia@cityofchicago.org).
- The Chicago inventory has no PIN, year built, or diameter. Year built and building class come from the Assessor join; diameter is not available for Chicago.
- The `ward_num` column in the Parcel Universe is also filled for 24,654 Evanston parcels; always filter on municipality before using it.
- LeadSafe Chicago moved to https://www.leadsafechicago.org/ (the old chicago.gov path returns 404).

### Chicago inventory columns (IEPA template)

| Raw column | Values | Missing | Maps to |
|---|---|---|---|
| FullAddress | "9924 S LA SALLE ST, Chicago, IL 60614" | 0% | address |
| PublSrvLnMatEPA | U, UNL, L, C, GRR, O | 0% | utility_side_material |
| PrivateSrvLnMatEPA | U, L, UNL, C, GRR, O, G | 0% | customer_side_material |
| OverallSL Code | U, L, NL, GRR | 0% | reported_line_class (equals derived line_status on 100% of rows) |
| Gooseneck | U, NL, L, C, GRR, O | 0% | gooseneck_material |
| CombinedSourceDescription | "PR: Field Verification", "PU: Construction Records, …", "… Home Built Date" | 49.6% | verification_method |
| PWS Service Install Dates | year | 96.3% | utility_install_year |
| Customer Service Install Dates | year | 96.9% | install_year |
| Customer Notified date | date | 95.1% | notification_date |
| PreviousLeadServiceReplaced | Y, N | 0% | prev_lead_replaced |
| Final Service Install Dates | date | 97.8% | replacement_date |
| MaterialOfServiceLineReplacement | C | 97.8% | (not used; always copper) |
| GalDownstreamofLead | Y | 97.9% | (not used; already reflected in GRR codes) |
| High Risk | Y, N | 1.2% | high_risk |
| ServiceNewlyIdentified | Y, N | 0% | newly_identified |
| LCRSiteID | N/A or LCR site code | 0% | (not used) |
| WaiverCustomerRefusedAccessToProperty, IDPHWaiverDate | Y / timestamp | 99.4% | (not used) |

Reader: `lll.ingest.read_iepa_template`. Line IDs are generated as `IL0316000-000001`, … in
file order.

IEPA template material codes: L Lead; GRR Galvanized Requiring Replacement; G Galvanized (never downstream of lead); C Copper, no lead solder; CLS Copper, lead solder; O Cast/ductile iron or transite; P Plastic; U Unknown; UNL Unknown, not lead; NL Non-Lead.

### Burnham inventory columns (ArcGIS layer, coded domains in `burnham_layer.json`)

Reader: `lll.sources.burnham`. Dates are ArcGIS epoch milliseconds.

| Raw column | Values | Missing | Maps to |
|---|---|---|---|
| OBJECTID | integer | 0% | line_id (`IL0310360-000001`) |
| address | "14528 MARQUETTE AVE" | 0.1% | address |
| PIN | 14-digit Cook PIN | 0.1% | pin |
| utilstatus | 0 Unknown, 1 Lead, 2 Non-Lead, 3 GRR | 0% | utility_side_material |
| custstatus | same codes | 0% | customer_side_material |
| utilmaterial, custmaterial | 0 Unknown, 1 Unknown Not Lead, 2 Suspected Non-Lead, 81 Asbestos Cement, 83 Cast Iron, 84 Copper, 88 Ductile Iron, 89 Galvanized, 93 PE, 94 PVC, 109 Lead, 110 Brass, 200 Suspected Lead | 0% / 0.3% | (detail only; status fields are authoritative) |
| utilsource, custsource | 1 Existing Records … 11 Indoor Inspection - Contractor | 0% | verification_method (`utility / customer`) |
| replacestatus | 1 Doesn't Need, 2 Needs, 3 Scheduled, 4 Replaced | 66.7% | replace_status, replaced |
| utilinstalldate, custinstalldate | epoch ms | 73.1% / 76.1% | replacement_date (later of the two, Replaced lines only) |
| UTILSCHEDDATE, CUSTSCHEDDATE | epoch ms | 73.1% / 76.1% | (not used; scheduling) |
| CONINTINSPECPERF, UTILEXPLOREPERF, UTILINTINSPECPERF | epoch ms | 60.9% / 90.9% / 100% | (not used; inspection dates) |
| NOTIFICATION1–NOTIFICATION10 | notice type (letter, flyer, visit, access agreement) | 57%–100% | (not used; outreach log) |
| CONSTRUCTION | Priority Area 1, 2 | 45.7% | (not used) |
| GlobalID | GUID | 0% | (not used) |

### East Dundee inventory columns (ArcGIS layer, domains in `east_dundee_layer.json`)

Reader: `lll.sources.east_dundee`. The only test inventory with diameter.

| Raw column | Values | Missing | Maps to |
|---|---|---|---|
| OBJECTID | integer | 0% | line_id (`IL0890250-000001`) |
| StreetAddr | "108 Barrington Ave" | 0% | address |
| LegacyPIN | 10-digit Kane County PIN | 21.0% | pin |
| SystMatlClass | Lead, Copper, Unknown, Unknown Not Lead, Galvanized, Cast_Ductile Iron or Transite, Copper No Lead Solder | 0.1% | utility_side_material |
| CustMatlClass | same vocabulary | 0.1% | customer_side_material |
| EntireMatlClass | Lead, Non Lead, Lead Status Unknown, Galvanized | 0.1% | reported_line_class (99.9% agree with derived) |
| GooseneckMatlClass | same vocabulary plus Not Observed | 0.3% | gooseneck_material |
| EstBldgYear | year | 4.3% | year_built |
| CustInstlYear | year | 89.0% | install_year |
| SystInstlYear | year | 98.1% | utility_install_year |
| ServInstlYear | year | 98.4% | (not used; duplicates the side-specific years) |
| ServSize | 3/4", 1", 2", 3" | 94.3% | diameter_in |
| CustClassBasis | Historical Record, In-Home/Meter Pit Inspection, Resident Information Survey, Installation Date After 1988, Excavation | 32.1% | verification_method |
| DateLeadServLineReplaced | epoch ms | 97.5% | replacement_date |
| PropertyType | Single-family, Multi-family, Multi-unit, Other | 30.5% | property_type |
| Duplicate | yes | 77.1% | duplicate_flag |
| FullAddress, LegacyGeocodeAddr, LegacyAcctAddr | address strings | 0%–0.5% | (not used; StreetAddr is used) |
| SystClassBasis, SystFieldVerifDate, SystFieldVerifMethod | basis / date / method | 40.8% / 96.9% / 98.3% | (not used) |
| CustFieldVerifDate, CustFieldVerifMethod | date / method | 74.6% / 75.2% | (not used) |
| PubServMatl, PrvServMatl, LegacyCustomerSideMaterial | free text materials | 99.9% / 26.3% / 26.3% | (not used; superseded by *MatlClass) |
| LagacyBuildingYear, LegacyBuildingYear2 | year | 19.9% / 22.7% | (not used; EstBldgYear is used) |
| LeadServLinePrevRptd, MatlServLineReplacement | Yes / Copper | 97.4% / 97.5% | (not used) |
| LCRRTier, SampleSite | Tier 1–5 / Yes | 40.1% / 99.8% | (not used; sampling) |
| SensitivePop, DisAdvanNeighborhood, InteriorEntryPnt | categorical | 92.8%–99.7% | (not used) |
| ServiceStatus, NewSrvcLastSubmit, ServMatlVerif, LocateID, Comments | sparse notes | 99.0%–99.9% | (not used) |
| GlobalID, GIS_ID, tempID, tempNotes, LegacyAcctNumber | identifiers / geocoding notes | 0%–0.7% | (not used) |
| MeterModel, MeterSize, MeterAge, ServInstlDate, GalvDwnstrmLead, DateCustNotifLeadServ, CustRefuseAccess, DateCustWaiverNotif, OwnrReplaceIntent, Northing, Easting | empty | 99.9%–100% | (not used) |

## Master table (`data/processed/master_chicago_<snapshot>.parquet`)

Built by `python scripts/build_master.py` (`lll.features.build_master_table`). One row per
service line; every canonical inventory column above is carried through, plus:

| Column | Description |
|---|---|
| match_method | matched_pin, matched_address, matched_nearby, geocoded_census, or empty |
| fail_reason | reason code when unmatched (see `lll.geocode.REASON_CODES`) |
| address_norm | normalized "NUMBER DIR STREET SUFFIX" used for matching |
| matched_pin | 14-digit Assessor PIN for exact matches |
| nearby_pin | PIN of the nearest same-side parcel for nearest-number matches (location only) |
| latitude, longitude | WGS84; parcel centroid or Census Geocoder point |
| census_block_geoid | block returned by the Census Geocoder (Census matches only) |
| block, block_group, tract | 2020 census GEOIDs (15, 12, 11 digits) |
| ward | 2023 ward map, spatial join (nearest within 100 m for edge points) |
| community_area | Chicago community area number, spatial join |
| in_city | False for located lines outside city limits; empty if not located |
| building_class | Assessor class (exact matches only) |
| year_built, unit_count | Assessor residential/condo characteristics by building (exact matches only) |
| line_status | whole-line class: reported class, else Lead > GRR > Unknown > Non-Lead from both sides |
| line_status_derived | the derived class, kept for QA |
| replaced | replacement date present or previously-replaced flag |
| nbr_lead_share_k10 | leave-one-out share Lead/GRR among the 10 nearest known lines within 100 m |
| nbr_known_count_k10 | number of known neighbors behind that share (0–10) |
| block_lead_share_loo | leave-one-out share Lead/GRR among other known lines on the same block |
| dist_nearest_nonlead_m | meters to the nearest other Non-Lead line |
| tract_unknown_rate | share of lines in the tract with Unknown status |

## Area aggregates (`data/processed/areas_<level>_chicago_<snapshot>.parquet`)

One file per level: block, block_group, tract, ward, community_area. Columns: total_lines,
n_lead, n_grr, n_unknown, n_nonlead, n_replaced, the matching share_* columns, and
suppressed. Any area with fewer than 5 lines has every count and share blanked and
suppressed = True (`lll.equity.suppress_small_cells`).

## Disparity report (`data/processed/equity_chicago_<snapshot>/*.csv`)

Built by `scripts/build_equity.py`; definitions in [methodology.md](methodology.md#disparity-measures).

| File | One row per | Columns beyond the area aggregate columns |
|---|---|---|
| tract.csv | tract with lines | n_needs_action, share_needs_action, ACS fields (median_income, pop_*, pct_black / latino / white / asian, kids_under3 / kids_3_4 / kids_5 and their sum kids_under6, housing_units, units_1940s / units_pre1940 and their sum units_pre1950, pct_housing_pre1950, majority_group, acs_year), income_quartile |
| ward.csv | ward | n_needs_action, share_needs_action, ward ACS fields (apportioned by area), rank_needs_action (1 = largest share to fix or check) |
| income_quartiles.csv | quartile | pooled counts and shares, areas (tracts), income_min, income_max |
| majority_group.csv | majority group | pooled counts and shares, areas (tracts) |
| disparity_ratios.csv | group × metric | comparison, group, reference, metric, group_rate, reference_rate, ratio |

ACS cache: `data/processed/acs_2024_cook_tracts.parquet` (1,332 Cook County tracts) and
`acs_2024_wards.parquet`.

## Matching report (`data/processed/matching_report_chicago_<snapshot>.csv`)

Rows and share by outcome code with a description and a matched flag; sums to 100% of lines.
