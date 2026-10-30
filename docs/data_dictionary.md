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

| Raw value (source) | Canonical |
|---|---|
| _TBD_ | |

## Sources

### Illinois EPA service line material inventory reports (system-level)
- File: `data/raw/ServiceLineMaterialInventoryReports.csv`
- URL / download date: _TBD_

| Column | Type | Allowed values | Missing | Maps to |
|---|---|---|---|---|
| _TBD_ | | | | |

### Cook County Assessor: Parcel Universe (Current)
- File: `data/raw/Assessor_-_Parcel_Universe_(Current)_20261029.csv`
- URL / download date: _TBD_

### Chicago service line inventory (line-level)
- Status: _TBD (pending data agent)_
