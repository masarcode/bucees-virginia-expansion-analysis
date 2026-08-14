# Data Dictionary

Definitions for every table in `database/bucees_va.sqlite` (schema:
[sql/schema.sql](../sql/schema.sql)). Source-file dictionaries are added per
dataset during Stage 2/3 as each raw schema is inspected - nothing here is
assumed in advance of inspection.

## geography
One row per Virginia county-equivalent.

| Column | Type | Description | Source |
|---|---|---|---|
| geoid | TEXT PK | 5-digit FIPS (state 51 + county) | TIGER/Line |
| county_name | TEXT | Official name (e.g. "Henrico County", "Richmond city") | TIGER/Line |
| state_fips | TEXT | Always "51" | TIGER/Line |
| county_fips | TEXT | 3-digit county FIPS | TIGER/Line |
| is_independent_city | INTEGER | 1 if independent city (FIPS ≥ 510) | derived |
| aland_sqmi / awater_sqmi | REAL | Land / water area, sq mi | TIGER ALAND/AWATER |
| centroid_lat / centroid_lon | REAL | Geographic centroid (EPSG:4326) | derived |
| region | TEXT | Regional market label | Stage 8 |

## demographics
One row per county-equivalent per ACS 5-year period.

| Column | Type | Description | Source |
|---|---|---|---|
| geoid, acs_period | PK | e.g. ("51087", "2019-2023") | - |
| total_population | INTEGER | ACS B01003_001E* | ACS 5-yr |
| median_hh_income | REAL | ACS B19013_001E* | ACS 5-yr |
| per_capita_income | REAL | ACS B19301_001E* | ACS 5-yr |
| median_age | REAL | ACS B01002_001E* | ACS 5-yr |
| labor_force / employed | INTEGER | ACS B23025_002E/004E* | ACS 5-yr |
| median_home_value | REAL | ACS B25077_001E* | ACS 5-yr |
| households | INTEGER | ACS B11001_001E* | ACS 5-yr |
| commuters_total | INTEGER | ACS B08303_001E* | ACS 5-yr |

*Variable codes verified against the ACS API variable list at acquisition;
any code that fails verification is corrected here and in config.yaml.

## business_activity
One row per county × year × NAICS code (County Business Patterns).

| Column | Type | Description |
|---|---|---|
| geoid, year, naics_code | PK | NAICS codes per config (all sectors, gasoline stations, food service, retail) |
| naics_desc | TEXT | Official NAICS label from CBP |
| establishments | INTEGER | Establishment count |
| employment | INTEGER | Mid-March employment (NULL when withheld) |
| annual_payroll | INTEGER | Annual payroll, $1,000s (NULL when withheld) |
| emp_suppressed | INTEGER | 1 when employment withheld/noise-flagged by Census |

## traffic_summary
County-level rollup of VDOT AADT segments.

| Column | Type | Description |
|---|---|---|
| geoid, year | PK | - |
| segment_count | INTEGER | VDOT segments assigned to the county (FROM_JURISDICTION) |
| max_aadt / mean_aadt | REAL | Max / mean ADT; VDOT publishes bidirectional totals |
| interstate_max_aadt | REAL | Max ADT among interstate mainline segments (see A11) |
| interstate_miles | REAL | **Directional route-miles** of interstate mainline: each carriageway (Master Prime / Non-Prime), C-D road, and express-lane facility counts separately, so ≈2× centerline miles (A12). Scale-consistent across counties; used only in normalized scores. |
| vmt_proxy | REAL | Σ(ADT × corrected segment miles). Divided highways contribute both carriageways with bidirectional ADT (~2× vs undivided roads) - an exposure *proxy*, not VMT (A12). |

## bucees_locations
Existing and announced Buc-ee's stores (all US), each with a citation.

| Column | Type | Description |
|---|---|---|
| location_id | INTEGER PK | Surrogate key |
| name, city, state | TEXT | Store identity |
| status | TEXT | open / under_construction / announced |
| latitude, longitude | REAL | EPSG:4326 |
| opened_date | TEXT | ISO date when known |
| source_url, accessed_date | TEXT | Per-row citation (required) |

## market_scores
One row per county-equivalent; every component normalized 0-100
(higher = more attractive). See docs/architecture.md for component inputs.

## scenario_rankings
(scenario, geoid) → weighted_score, rank (1 = best within scenario).

## validation_results
Append-only log of automated checks: run_ts (UTC), stage, check_name,
status (pass/warn/fail), details.
