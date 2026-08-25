# Work Log - Buc-ee's Virginia Expansion Analysis

Chronological record of all work, decisions, issues, and fixes.
Newest entries at the bottom of each stage section.

---

## Stage 1 - Project initialization (2026-08-03)

**Status: COMPLETE**

- Inspected project directory: empty at start. Python 3.11.4 at /usr/local/bin/python3.
- Created full directory tree (config, data/{raw,interim,processed}, database,
  docs, notebooks, scripts/{acquire,clean,analyze,utils}, sql, dashboard/pages,
  outputs/{figures,maps,tables,reports}, tests).
- Wrote `requirements.txt`, `.gitignore`, `.env.example`, `LICENSE` (MIT).
- Wrote `config/config.yaml`: data source parameters (ACS 2019-2023 vs
  2014-2018 for growth, CBP 2023, TIGER 2023, VDOT AADT), analysis CRS
  (EPSG:26918), and scoring weights for 5 scenarios (each sums to 1.0).
- Wrote `sql/schema.sql`: geography, demographics, business_activity,
  traffic_summary, bucees_locations, market_scores, scenario_rankings,
  validation_results (+ indexes).
- Wrote shared utilities: paths.py, config.py, logging_setup.py, db.py
  (SQLAlchemy engine + idempotent schema init), validation.py (persists every
  check to validation_results).
- Wrote `scripts/run_pipeline.py` orchestrator (ordered stage registry,
  stops on first failure, reports unimplemented modules).
- Started background creation of `.venv` + dependency install.

**Decisions**
- Unit of analysis: Virginia counties AND independent cities (both are
  county-equivalents with own FIPS codes; VA has 133 total).
- Growth measured between non-overlapping ACS 5-year windows (2014-2018 vs
  2019-2023) per Census guidance on comparing overlapping periods.
- ACS/CBP variable codes listed in config are candidates only; each is
  verified against the API's own metadata at acquisition time.
- Raw data preserved and gitignored (re-downloadable); MANIFEST.md in
  data/raw records URL, access date, and row counts for every file.

- Created `.venv` (Python 3.11.4); all requirements installed cleanly ("ENV OK").
- Wrote `tests/test_foundations.py` (config loads, scenario weights sum to 1.0,
  schema applies to a fresh DB).
- **Issue found & fixed:** schema DDL was split on ";" before execution, which
  broke on a semicolon inside a SQL comment ("…demographics; one row per…"),
  raising `near "one": syntax error`. Fix: apply schema via sqlite3
  `executescript` in both `scripts/utils/db.py` and the test.
- Verification: `pytest` 3/3 passed; `python -m scripts.run_pipeline` runs and
  correctly reports 15 not-yet-implemented stage modules; real database
  initialized at `database/bucees_va.sqlite` with all 8 tables.

**Unresolved issues**
- VDOT AADT endpoint must be located and verified during Stage 2. *(resolved in Stage 2)*
- Buc-ee's has no official machine-readable location list; will compile from
  public sources with per-row citations in Stage 2. *(resolved in Stage 2)*

---

## Stage 2 - Data acquisition (2026-08-03 → 2026-08-04)

**Status: COMPLETE**

**Discovery that changed the plan:** api.census.gov data queries now require
an API key (HTTP 302 → "Missing Key", verified 2026-08-03). Switched ACS and
CBP acquisition to the official bulk summary files on www2.census.gov, which
need no key (assumption A9). Metadata endpoints (variables.json) remain open
and were used to verify all 9 ACS variable codes exist.

**Acquired and validated (30/30 checks pass):**
- **TIGER/Line 2023**: `cb_2023_us_county_500k.zip` (3,235 counties, exactly
  133 VA county-equivalents ✓, GEOIDs unique ✓); `tl_2023_us_primaryroads.zip`
  (17,458 features, 5,599 interstate features ✓). CRS EPSG:4269.
- **ACS 2019-2023** (table-based SF): 8 tables (B01003, B19013, B19301,
  B01002, B23025, B25077, B11001, B08303), each with exactly 133 VA county
  rows ✓. Layout: `GEO_ID|B01003_E001|B01003_M001…`; margins use -555555555
  sentinel for controlled estimates.
- **ACS 2014-2018** (legacy sequence files, VA): table lookup located all 8
  tables ✓ (sequences 3, 28, 36, 59, 65, 79, 115); geography file g20185va.csv
  (12,051 rows; summary level col 2, LOGRECNO col 4, GEOID col 48).
- **CBP 2023** county bulk file: 41,251 VA rows across 134 fipscty codes
  (133 real + '999' statewide catch-all, dropped in Stage 3). **Coding
  discovery:** NAICS 2017 basis; sector roots pad with dashes ('44----' =
  retail trade 44-45), subsectors with slashes ('447///', '722///'),
  all-sectors is '------'. Initial 44-45 check failed on this; fixed the
  file-code mapping and re-ran - all NAICS checks pass. Suppression flags:
  emp_nf / ap_nf columns.
- **VDOT Traffic Volume 2024** (ArcGIS): all 123,766 segment attribute
  records in 62 preserved JSON pages (count matches service ✓). Fields incl.
  ADT, AAWDT, truck %, FROM_JURISDICTION, Shape__Length (EPSG:3857 m).
  Notable: interstate records include ramps/rest areas ('I-81N Ramp 19A') -
  mainline filtering needed in Stage 3; cities appear as 'City of Roanoke'.
- **Buc-ee's locations**: 20 rows compiled (17 open east-of-Mississippi
  stores from buc-ees.com/locations + Stafford VA approved 2026-05-19,
  New Kent VA delayed to 2031, Mebane NC under construction - each with news
  citation). 20/20 geocoded via Nominatim (16 POI-precision, 2 address, 2
  city); raw geocoder responses preserved. Scope assumption A6.

**Raw data footprint:** ~300 MB in data/raw/, all recorded in MANIFEST.md.

**Unresolved issues**
- VDOT mainline-vs-ramp classification rules to be defined in Stage 3. *(resolved)*
- CBP fipscty '999' and jurisdiction name→GEOID mapping handled in Stage 3. *(resolved)*

---

## Stage 3 - Data cleaning (2026-08-04)

**Status: COMPLETE** - 5 cleaning scripts, 38 validation checks, all passing.

**Outputs (data/processed/):** geography.parquet + va_counties.geoparquet
(133 county-equivalents, 38 independent cities, centroids, valid geometry),
interstates_region.geoparquet (829 TIGER interstate features within VA+100mi,
I-81/I-95 verified present), demographics.parquet (266 rows = 133 × 2
periods), business_activity.parquet (526 rows = 133 counties × 4 NAICS),
traffic_summary.parquet (133 counties, 41 with interstate mainline),
bucees_locations.parquet (20 stores, all spatially validated).

**Key validations:**
- ACS county sums reconcile EXACTLY with state rows extracted from the same
  files, both periods (2019-23: pop 8,657,499; 2014-18: 8,413,774) - proves
  the 2018 sequence-file positional extraction is correct. Cross-period
  county population correlation r=0.9992. Zero missing values in either
  period across all 9 variables.
- CBP: zero disclosure-suppressed rows for VA in our 4 NAICS groups (only
  noise flags G/H/J observed); suppression handling code in place regardless.
- VDOT: 133/133 county coverage; every jurisdiction mapped; statewide max
  AADT 260,000 (plausible); 1,068 interstate mainline segments.
- Buc-ee's: every point falls in its recorded state; Mount Crawford verified
  inside Rockingham County (51165).

**Issues found & fixed:**
1. clean_acs: set_index used the unfiltered lookup series (length mismatch
   29,456 vs 1,154) - fixed by indexing the filtered frame.
2. VDOT unmapped jurisdictions (4,098 rows): added alias map (Accomac;
   3 maintenance areas → successor cities), town→county assignment via
   TIGER VA places largest-overlap (189 towns; required adding
   cb_2023_51_place_500k.zip to fetch_tiger), dropped 'Statewide' rows
   (149) + null jurisdiction (17) = 0.13% of segments. Assumptions A10/A11.
3. TIGER LSAD code for VA towns is '43', not '47' - fixed filter after
   inspection (189 towns, 38 cities LSAD 25, 461 CDPs LSAD 57).

**Unresolved issues**
- None blocking. Note for Stage 6: Accomack County has no interstate
  (Eastern Shore) - accessibility scoring must handle interstate-less
  counties gracefully (US-13 corridor exists but is not an interstate).

---

## Stage 5 - Exploratory analysis (2026-08-04)

**Status: COMPLETE** - 6 tables, 6 charts, 6 maps (HTML + PNG), 7 checks pass.

- `scripts/analyze/features.py`: spatial features per county - centroid
  distance to nearest interstate (TIGER, incl. border states), to nearest
  open Buc-ee's, and to nearest open/announced. Validated: Rockingham
  centroid 11.2 mi from the Mount Crawford store; max interstate distance
  63.6 mi (Eastern Shore / Northern Neck tail).
- `scripts/analyze/eda.py`: ranked tables + Plotly charts/maps styled per
  the dataviz method (sequential blue for magnitude, diverging blue↔red
  for growth, single-series charts without legends, direct labels).
- **Fixes after visual review:** bar-chart left margin (county names were
  clipped); Buc-ee's map re-framed on Virginia (scattergeo stores had
  blown out fitbounds); alternating scatter label offsets (collisions).

**Headline findings (feed the Stage 6 narrative):**
- New Kent County is Virginia's fastest-growing county (+14.4% pop,
  +50.7% median income) - and Buc-ee's has already announced a site there.
- Stafford County: #1 interstate traffic (260k AADT), top-5 growth
  (+11.5%), and 2nd-thinnest fuel retail among 20k+ counties (1.56
  stations/10k) - Buc-ee's won approval there in May 2026. The data
  independently reproduces Buc-ee's actual siting choices.
- Growth concentrates in the NoVa→Fredericksburg→Richmond crescent plus
  exurban Richmond (Goochland +13.9%, Prince George +13.1%); Southwest VA
  is broadly declining.
- Loudoun leads purchasing power ($178.7k median HH income; US top-tier).
- Interstate accessibility is bimodal: most counties sit <15 mi from an
  interstate, but the Eastern Shore, Northern Neck, and Southside form a
  40-60+ mi tail.

---

## Stage 11 - Publication review (2026-08-04 to 2026-08-05)

**Status: COMPLETE**

**Final verification**
- Full pipeline: 19 scripts, exit 0.
- Validation: 130 distinct checks, 130 pass, 0 warn, 0 fail (906 records logged).
  Count rose from 117 as new checks were added for CPI, the maintenance-area
  resolution, interstate crossing, the eligibility screen and the holdout run.
- Tests: 8 passed.
- Every published figure cross-checked against the output files by script.
  One mismatch found and corrected: the minimum Spearman correlation is
  0.9925, which rounds to 0.993, so "the lowest was 0.992" was inaccurate.
  Restated everywhere as "never fell below 0.992", which is true and
  conservative.
- Em and en dashes: zero remaining in the repository.
- All six dashboard pages render, each with source and disclaimer footers.
- All README and report cross-links resolve.

**Deliverables changed in this stage**

New: `scripts/analyze/recommendations.py`, `scripts/acquire/fetch_cpi.py`,
`scripts/acquire/fetch_vdot_maintenance_geom.py`, `docs/citations.md`,
`docs/source_inventory.md`, `outputs/reports/corridor_recommendations.md`,
`dashboard/views/corridor_recommendations.py`, and the `recommendations` and
`cpi_annual` tables.

Rewritten: README, executive summary, methodology report, limitations report,
resume bullets, all dashboard pages, `docs/assumptions.md` (A12 superseded by
A12b; A14 to A18 added).

Renamed: `outputs/reports/regional_recommendations.md` became
`vdot_district_screening.md` and now opens by stating it is not a
recommendation. Dashboard `pages/` became `views/` under `st.navigation`.

Audit of the Stage 10 deliverables before publication. Findings below are
listed as a fix checklist; each is marked done as it lands.

### A. Analytical issues found

| # | Issue | Where | Fix |
|---|---|---|---|
| A1 | Raw model rank presented as business recommendation. Fairfax appears as "#1 county" with no status qualifier. | dashboard, exec summary, README | Split into market attractiveness rank vs recommendation status; new eligibility layer |
| A2 | Markets that already have a store (Mount Crawford open, New Kent announced, Stafford locally approved) are presented as fresh recommendations. | exec summary, regional report, dashboard | Reclassify as reference cases; exclude from candidate set |
| A3 | Claim that the model "reproduces Buc-ee's decisions without being told them" is false: store locations and an overlap component are model inputs. | exec summary, README, dashboard callout, resume bullets | Remove; replace with a genuine blinded holdout run |
| A4 | VDOT construction districts described as retail markets. They are administrative highway maintenance districts. | regions script, dashboard, exec summary | Rename to district screening; add analyst-reviewed corridor layer |
| A5 | Fredericksburg district recommended although it contains the approved Stafford site. Richmond district recommended as one block although New Kent sits inside the adjacent I-64 corridor. | exec summary, regional report | Reclassify Fredericksburg as reference; narrow Richmond to the west/south I-64 and I-95 segments |
| A6 | Frederick County's market labelled "Staunton" (its VDOT district). Frederick is in the Winchester area, roughly 90 miles from Staunton. | regional outputs, exec summary | Separate corridor label: Northern I-81 / Winchester |
| A7 | Assumption A12 asserts VDOT ADT is a bidirectional total. Not verified and contradicted by the data. | docs/assumptions.md, data dictionary, limitations | Correct with the measured evidence (see F1) |

### B. Factual and wording issues

| # | Issue | Fix |
|---|---|---|
| B1 | "New Kent is Virginia's fastest-growing county" states a demographic fact the data does not support (ACS period estimates, not annual estimates). | Restate as highest growth in this project's comparison of the 2014-2018 and 2019-2023 ACS 5-year estimates |
| B2 | Income growth of 50.7% presented as purchasing power. Not inflation adjusted. | Add CPI-U deflation to constant 2023 dollars; report real and nominal separately |
| B3 | "Stafford has the highest Virginia interstate AADT of 260,000" overstates a single segment reading. | Restate as the highest county-level mainline segment maximum in this project's processed VDOT extract, with full provenance |
| B4 | "117 checks passing" adjacent to business conclusions implies commercial validation. | State explicitly that the checks cover data and pipeline integrity only |
| B5 | Sensitivity described as proving robustness. | Restrict claim to local rank stability under the tested perturbations |
| B6 | Em dashes throughout user-facing prose (9 README, 6 exec summary, 4 limitations, 6 resume bullets, 13 dashboard, 3 assumptions, 4 data dictionary). | Replace with hyphens or sentence breaks |
| B7 | Promotional and AI-pattern phrasing ("The answer in one paragraph", "Reality checks that build confidence", "the honest caveat", "claimed corridors"). | Rewrite in plain analyst prose |

### C. Dashboard issues

| # | Issue | Fix |
|---|---|---|
| C1 | Sidebar entry reads "app". | Rename to Executive Overview |
| C2 | Scenario rank chart draws longer bars for worse ranks, so the visual reads backwards. | Invert to percentile, so stronger performance is a longer bar |
| C3 | Out-of-state store markers (Kentucky, Tennessee, North Carolina and others) render outside the Virginia frame as loose stars. | Restrict markers to Virginia; retain out-of-state stores in distance maths |
| C4 | Open, announced and approved sites share one marker style. | Distinct symbol per development status |
| C5 | Unrounded values displayed (76.626241, 19.777790). | Round at the presentation layer |
| C6 | No source or disclaimer footer on any page. | Add to all five pages |
| C7 | Top-county table has no recommendation status or reason. | Add corridor, status, reason, overlap note |

### D. Citation gaps

| # | Issue | Fix |
|---|---|---|
| D1 | Store status, approval date and opening timelines have URLs in a table but no claim-level mapping. | New docs/citations.md keyed by claim |
| D2 | source_inventory.md lives only in outputs/reports. | Mirror to docs/ per required structure |
| D3 | Census methodology and VDOT traffic definitions uncited. | Add official citations |

### RESOLUTION (all items closed 2026-08-05)

**A1 to A7, analytical.** New `scripts/analyze/recommendations.py` builds an
eligibility layer that keeps market attractiveness rank separate from
actionable recommendation status. Eight statuses, each with a written reason,
stored in a new `recommendations` table and parquet. Reference cases (Mount
Crawford open, New Kent announced, Stafford locally approved) are excluded
from the candidate set. Corridors replace VDOT districts as the recommendation
unit, with membership validated against VDOT mainline records and tiering
based on each corridor's best *eligible* county. The "reproduced Buc-ee's
decisions" claim is gone, replaced by a genuine blinded holdout: with the
overlap component removed so no store data reaches the model, Stafford ranks
3rd of 133, New Kent 21st, Rockingham 25th. Frederick County is now labelled
Northern I-81 / Winchester rather than Staunton.

**B1 to B7, factual and wording.** New Kent restated as the highest growth in
this project's comparison of two ACS period estimates. CPI-U acquired from BLS
and wired through `v_county_growth`, so income growth is reported in both
nominal (50.7%) and real (24.2%) terms. AADT restated with full provenance.
Validation framed as data and pipeline integrity only. Sensitivity restated as
local stability. All em and en dashes replaced across the repository.

**C1 to C7, dashboard.** Rebuilt on `st.navigation` with six named pages, so
the sidebar no longer reads "app". Scenario chart converted to percentile so a
longer bar is always better. Map restricted to Virginia sites with a distinct
symbol per development status, out-of-state stores retained in the distance
maths. Rounding applied throughout. Source and disclaimer footers on every
page. Top-county table carries corridor, status and an overlap or development
note. New Corridor Recommendations page; regional page renamed to VDOT
District Screening and prefixed with a warning that districts are not trade
areas.

**D1 to D3, citations.** New `docs/citations.md` with 15 numbered sources
keyed to the claims they support, preferring official sources. Stafford's
status now cites the county's own planning page (approval 2026-05-19,
applications CUP24155520 and RC25156318, 36.18 acres, no opening date stated)
rather than news coverage. New Kent cites the county announcement and the VDOT
Exit 211 project page. `docs/source_inventory.md` rewritten with a
store-status table; the copy under outputs/reports now points to it.

### Two defects found while implementing the fixes

**Defect 1: VDOT maintenance areas spanned multiple cities.** The Stage 3
alias map sent all 454 "Norfolk Maintenance Area" records to Norfolk city.
Norfolk *County* became Chesapeake in 1963, not Norfolk city, and the records
carry labels in Norfolk, Portsmouth and Chesapeake alike. Downloading geometry
for the 556 affected records and assigning each individually shows the true
split: Norfolk 189, Chesapeake 159, Portsmouth 76, Virginia Beach 29, Suffolk
1. Before the fix Chesapeake and Portsmouth appeared to have no interstate at
all, which would have been published as fact in the corridor this analysis
goes on to recommend. After the fix Chesapeake is a priority candidate at rank
10 with 116,000 ADT. Counties with interstate mainline rose from 41 to 43.
New script: `scripts/acquire/fetch_vdot_maintenance_geom.py`.

**Defect 2: a data gap was being reported as an absence.** VDOT's extract
holds no I-64 mainline records for Newport News or Hampton, though I-64 plainly
runs through both. The screen was labelling them "no interstate access".
Added an `interstate_crosses_county` flag derived from TIGER interstate
geometry, so a genuine absence is distinguished from missing traffic data.
Thirteen jurisdictions are now correctly marked "traffic data unavailable"
rather than ineligible.

**Also fixed:** `build_database` failed on a foreign key when the new
`recommendations` table was added, the same delete-order class of bug caught
in Stage 10. Corrected.

### E. Verified during audit (no change needed)

- Pipeline reproducibility: 16 scripts, exit 0.
- 117 validation checks pass, 0 warn, 0 fail.
- ACS county sums reconcile exactly to the state row in both periods.
- Score integrity: all eight components in [0,100], full span, no missing.

### F. New evidence gathered during audit

**F1. AADT provenance (resolves A7 and B3).** The 260,000 record traced to:
route I-95N, ROUTE_NAME `R-VA IS00095NB`, EVENT_SOURCE_ID 60326, HTRIS_ID
`IS00095N`, Stafford County, mileposts 134.25 to 136.22, data date
2024-01-01, quality code G, ADT 260,000, AAWDT 250,000, directionality
"Master Prime", start label "South End Express Lanes".

The opposite carriageway over nearly the same mileposts (I-95S, Master
Non-Prime, mp 134.67 to 136.52) reports ADT 150,000, not 260,000. Equal
values would indicate a bidirectional total recorded on both carriageways.
They are not equal, so assumption A12 was wrong: this project cannot treat
ADT as a consistent two-way total. The segment also sits at the southern
terminus of the reversible 95 Express Lanes, which plausibly explains the
asymmetry. Consequence: interstate_max_aadt is a peak directional segment
reading, not countywide average traffic, and cross-county comparisons carry
this caveat. Rankings are unaffected in kind (the metric is applied
identically statewide and then normalized), but the wording and the
assumption register both need correcting.

**F2. CPI-U annual averages** (BLS series CUUR0000SA0, flat file
`cu.data.1.AllItems`): 2018 = 251.107, 2023 = 304.702. Deflator 2018 to
2023 dollars = 1.21343, i.e. 21.3% cumulative inflation. ACS 5-year money
values are expressed in the final year of each period, so the 2014-2018
estimates are in 2018 dollars and need this factor to compare with
2019-2023.

**F3. Interstate route by county** (from processed VDOT mainline records),
used to build defensible corridor labels rather than invented ones. Sample:
Stafford I-95 260k; Spotsylvania I-95 190k; Caroline I-95 104k; Henrico
I-95 160k and I-64 147k; Chesterfield I-95 131k; Hanover I-95 131k and
I-295 113k; Goochland I-64 81k; New Kent I-64 72k; York I-64 170k;
Virginia Beach I-264 195k; Norfolk I-64 177k; Suffolk I-664 87k; Frederick
I-81 72k; Rockingham I-81 59k; Augusta I-81 69k and I-64 46k; Roanoke Co
I-81 71k; Montgomery I-81 53k; Prince George I-95 112k; Dinwiddie I-85 62k;
Greensville I-95 43k.

---

## Stage 10 - Final review (2026-08-04)

**Status: COMPLETE** - full pipeline green, 117/117 checks pass, 8/8 tests
pass, 5 final reports written.

**Full pipeline execution:** `python -m scripts.run_pipeline` runs all 16
stage scripts end-to-end, exit 0, raw data intact.

**Issue found & fixed (1):** the full run failed at `build_database` with
`FOREIGN KEY constraint failed` on `DELETE FROM geography`. Earlier runs
had passed only because market_scores/scenario_rankings were empty at that
point; once populated by Stages 6-7, they held FK references to geography.
Fix: delete those two tables first in the reverse-dependency delete order.
This is exactly the class of bug a full clean re-run exists to catch.

**Issue found & fixed (2) - scoring model weighting bias.** A new output
test (`test_scores_normalized`) failed: `growth` spanned 6.46-79.43 rather
than 0-100. Diagnosis: a weighted sum of two *separately* min-maxed inputs
does not span 0-100, because the county holding the minimum of one input
rarely holds the minimum of the other. Consequence: a component with a
compressed span exerts less influence than its nominal weight implies.
Measured under balanced weights, `growth` had **7.9% actual influence vs
10.0% nominal**, while `highway_opportunity` had 26.5% vs 25.0% - the
documented weights did not mean what they said.
Fix: re-normalize each blended component after blending (monotonic, so no
county reorders within a component), documented as assumption **A13** and
enforced by a new `scores_span_full_range` validation check (bringing the
suite to 117).
**Impact measured, not assumed:** balanced top-15 membership is identical
before and after; maximum rank shift is 2 positions (Norfolk 8→10).
Consensus set unchanged (same 7 counties).

**All downstream figures re-verified against the rebuilt data**, and one
overstated claim corrected: Stafford is **not** "top-5 in all five
scenarios" (it is #7 under the underserved strategy) - corrected to "#1
growth, #2 highway, top-7 in all five" in the executive summary, README,
dashboard callout, and resume bullets. Sensitivity restated as ρ=0.992,
≥8 of 10 top-10 retained (was 0.993 / ≥9).

**Deliverables written:** executive_summary.md, methodology_report.md,
limitations_report.md, source_inventory.md, resume_bullets.md (all in
outputs/reports/), plus tests/test_outputs.py (integrity tests over
geography, demographics, score normalization, ranking completeness, and
database row counts).

**Verification summary**
- Pipeline: 16/16 scripts, exit 0
- Validation: 117 distinct checks, 117 pass, 0 warn, 0 fail (457 records logged)
- Tests: 8 passed
- Dashboard: all 5 pages verified in-browser
- Database: 133 geography / 266 demographics / 526 business_activity /
  133 traffic_summary / 133 market_scores / 665 scenario_rankings

**Unresolved issues**
- None. Future work is listed under "What would strengthen it" in the
  limitations report (exit-level fuel POIs, parcel/land-cost layers,
  tourism and freight flows, ACS margin-of-error propagation).

---

## Stage 9 - Streamlit dashboard (2026-08-04)

**Status: COMPLETE** - 5-page dashboard, visually verified in browser.

- `dashboard/app.py` (executive overview): scenario radio + custom-weight
  sliders (re-normalized), KPI row, scored VA choropleth with Buc-ee's
  store overlay, top-15 table with score progress bars, reality-check
  callout (model reproduces Stafford/New Kent decisions).
- Pages: County Explorer (component bars + scenario ranks + full profile),
  Market Comparison (2-4 counties, grouped component bars + stat table,
  color fixed per county), Regional Markets (tier cards + region map +
  summary), Methodology (sources, formulas, scenario weight matrix,
  assumptions from docs/, live validation status from the DB).
- `.streamlit/config.toml` pins the light theme so Streamlit chrome matches
  the chart surface tokens.
- **Issues found & fixed during browser verification:** preview launcher
  couldn't spawn Python (cwd issue) → run server via shell, attach preview
  by URL; dark-theme clash → light theme config; leading-region KPI
  truncation; map window too wide (tiny VA); broken import in Regional
  Markets page; stale FAIL for tiger_va_places_has_towns (fetch_tiger had
  not been re-run after the LSAD fix) → re-ran, **116/116 checks passing**.

---

## Stage 8 - Regional analysis (2026-08-04)

**Status: COMPLETE** - 9 regional markets, tiered recommendations, 5 checks pass.

- Regions = VDOT construction districts, derived per county from the
  county's own VDOT segment records (mode of FROM_DISTRICT) - data-driven,
  official, highway-oriented. All 133 counties assigned; geography.region
  populated in DB + parquet.
- Ranking rule (documented): mean balanced-scenario score of each region's
  top-3 counties. **Top:** Northern Virginia (Fairfax/Prince William/
  Arlington, 4 counties in statewide top-15), Hampton Roads (Virginia
  Beach/Norfolk/York). **Secondary:** Richmond (Henrico/Chesterfield/
  Hanover), Fredericksburg (Stafford/Spotsylvania/Caroline - Stafford's
  approved store sits here). **Watchlist:** Salem, Staunton, Culpeper,
  Bristol, Lynchburg.
- Outputs: regional_summary.csv, regional_recommendations.md (with
  explicit limitations incl. land cost/zoning risk and the conservative
  treatment of announced-but-unbuilt stores), region map.
- **Viz fix:** 9 regions vs 8 categorical slots - 9th region uses neutral
  gray instead of cycling a hue, and all regions are direct-labeled on the
  map so identity is not color-alone.

---

## Stage 7 - Scenario analysis (2026-08-04)

**Status: COMPLETE** - 5 scenarios ranked, stability + sensitivity done,
13 checks pass.

- scenario_rankings: 665 rows (5 × 133), deterministic unique ranks.
- Consensus (top-10 in ≥4 of 5 scenarios): Fairfax, Prince William,
  Arlington, Stafford, Virginia Beach, Chesterfield, Henrico.
- Scenario differentiation is real: Stafford #1 growth / #2 highway;
  Loudoun #3 affluent but #20 highway (no major interstate exposure);
  Norfolk #4 underserved / #24 growth; Roanoke & Montgomery surface only
  in underserved.
- Sensitivity: every component weight perturbed ±20% per scenario (80
  perturbations): worst-case Spearman ρ=0.993, ≥9/10 top-10 retained -
  rankings are robust to weight choices (mitigates assumption A5).
- Outputs: per-scenario top-15 CSVs, scenario_stability.csv,
  sensitivity_analysis.csv, scenario_rank_heatmap (HTML+PNG).

---

## Stage 6 - Scoring model (2026-08-04)

**Status: COMPLETE** - 8 components scored, 9 checks pass.

- `scripts/analyze/scoring.py`: formulas documented in the module docstring
  (log transforms for size variables; inverse metrics for competition and
  overlap; interstate-less counties get 0 interstate exposure; overlap
  distance capped at 120 mi = 2× trade radius).
- All components exactly span 0-100, no missing values; direction sanity
  checks pass (e.g. competition score falls as gas-station density rises).
- Loaded to market_scores (133 rows) + parquet.
- Unweighted mean top-5: Fairfax, Arlington, Virginia Beach, Loudoun,
  Prince William - urban skew is expected with equal weights (urban
  counties win demand/purchasing/commercial simultaneously); scenario
  weighting differentiates. **Limitation noted for Stage 10:** no land
  cost/availability component, so dense urban counties (Arlington) can
  rank despite being implausible for a 74k-sqft travel center; regional
  grouping and the highway scenario mitigate.

---

## Stage 4 - Database construction (2026-08-04)

**Status: COMPLETE** - database loaded, views created, 11 checks pass.

- `scripts/build_database.py`: idempotent load (DELETE+append in FK order)
  of geography (133), demographics (266), business_activity (526),
  traffic_summary (133), bucees_locations (20); validation_results kept
  append-only. FK integrity verified: 0 orphans in all three fact tables.
- `sql/views.sql`: v_county_growth (two-period growth %), v_county_profile
  (one row per county joining everything), v_interstate_counties,
  v_scenario_leaders, v_validation_latest.
- `sql/business_queries.sql`: 6 documented business questions (traffic
  leaders, growth×size, fuel-thin markets, affluent corridors, scenario
  leaders, data-quality report). Smoke-tested - results plausible
  (top interstate AADT: Stafford 260k, Fairfax 254k, Prince William 206k;
  top growth: Goochland +13.9%, Prince George +13.1%, Stafford +11.5%).
- **Issue found & fixed:** "database is locked" - validation.record opened
  a second SQLite connection inside build_database's open write
  transaction. Fix: validation.record now accepts conn= to reuse the
  caller's transaction.
- **Data understanding (A12):** VDOT interstate mainline rows are
  directional event records (Master Prime/Non-Prime) carrying
  bidirectional ADT; interstate_miles ≈ 2× centerline. Documented in data
  dictionary; harmless to rankings (normalized scores).

**Unresolved issues**
- None.
