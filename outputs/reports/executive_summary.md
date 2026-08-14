# Buc-ee's Virginia Expansion: Executive Summary

## Purpose

Buc-ee's has one store open in Virginia and two more in the development
pipeline. This analysis asks where the company should look next. It screens
all 133 Virginia county-equivalents on public data, then applies a second
layer of analyst judgement to separate places that merely score well from
places that could realistically host a store.

This is a portfolio exercise using public data only. It is not affiliated
with Buc-ee's Ltd, and it screens at county level rather than recommending
parcels.

## Method

Eight components describe each county: market demand, growth, purchasing
power, highway opportunity, accessibility, commercial activity, competition
and overlap risk. Each is scaled from 0 to 100 relative to the rest of
Virginia, then combined under five weighting scenarios that represent
different strategic postures. The inputs are ACS 5-year estimates for
2014-2018 and 2019-2023, County Business Patterns 2023, VDOT traffic volumes
published in 2024, and TIGER/Line boundaries and road geometry [9, 12, 13, 14].

The model produces a **market attractiveness rank**. That rank is not a
recommendation. A separate screen sets a **recommendation status** for each
county by asking whether a store is already there, whether a new store would
sit inside an existing one's trade area, whether an interstate is present,
and whether the county is dense enough that assembling a 30-acre site near an
interchange would be the binding constraint. The thresholds are analyst
judgement and are written down in `docs/assumptions.md` (A14 to A18).

The two layers disagree in useful ways. Fairfax County has the highest
attractiveness score in the state and is not a candidate.

## Retrospective reference cases

Three Virginia counties already contain a store and are excluded from the
candidate set. They are reported as reference cases, not recommendations.

| County | Corridor | Status | Basis |
|---|---|---|---|
| Rockingham (Mount Crawford) | I-81 Exit 240 | Open since 30 June 2025 | Company location page and Virginia Business [1, 2] |
| Stafford | I-95, Austin Ridge Drive | Locally approved 19 May 2026, no confirmed opening date | Stafford County Planning and Zoning [3] |
| New Kent | I-64 Exit 211 | Announced, permit filed | New Kent County; opening tied to a VDOT interchange project [5, 6, 7] |

The model was not built to predict these choices, and it could not: store
locations are one of its inputs. As a face-validity check, the scoring was
re-run with the overlap component removed entirely, so that no Buc-ee's
location data reached the model. On that blinded run, Stafford ranks 3rd of
133, New Kent 21st and Rockingham 25th. That is a reasonable sign the
underlying demand, growth and highway measures track something real. It says
nothing about the company's actual site-selection criteria, which are not
public.

## Priority opportunity: Hampton Roads

Hampton Roads is the clearest gap. It is the largest population base in
Virginia with no store in it or adjacent to it, and three of its
jurisdictions clear every screen:

| County | Attractiveness rank | Max interstate segment ADT | Distance to nearest store | Population |
|---|---|---|---|---|
| Virginia Beach city | 4 | 195,000 (I-264) | 74.6 mi | 457,066 |
| Chesapeake city | 10 | 116,000 (I-64) | 68.4 mi | 251,153 |
| Suffolk city | 17 | 87,000 (I-664) | 58.8 mi | 96,638 |

The corridor holds about 1.65 million residents. Every eligible jurisdiction
sits at least 58 miles from the nearest existing or planned store, which is
outside the 30-mile overlap screen and close to the 60-mile trade radius the
project assumes. Norfolk scores well but is set aside on feasibility at 4,412
people per square mile.

## Secondary opportunities

Two Richmond-area corridors score highly but need trade-area work before
either could be recommended cleanly, because the announced New Kent store
sits on the far side of the metro:

- **I-95 Richmond South.** Chesterfield ranks 6th with 131,000 ADT and 9.5%
  population growth, but its centroid is 33.4 miles from the nearest planned
  store. That is just outside the overlap screen, so it carries a
  further-review flag rather than a clear recommendation.
- **I-95 Richmond North.** Hanover ranks 12th on similar traffic at 32.5
  miles, with the same caveat.

The point of narrowing Richmond to its western and southern segments is that
treating the metro as one recommendation would ignore New Kent to the east.

Away from Richmond, **I-81 Winchester and Frederick** is the strongest
secondary option with no overlap complication. Frederick County ranks 14th,
grew 9.6%, and sits 68.8 miles from Mount Crawford, which is sensible spacing
on the same corridor. Traffic is lower at 72,000, so the case rests on
growth and spacing rather than volume.

## Watchlist

- **I-81 Roanoke and Salem.** Roanoke County ranks 15th and is 93.2 miles
  from the nearest store, the widest spacing among strong candidates. Traffic
  of 78,000 and 3.4% growth make it a slower play.
- **I-64 Charlottesville and I-64 Richmond West.** Albemarle ranks 16th and
  Goochland 18th. Goochland grew 13.9%, the second-fastest in the state, but
  has only 25,613 residents, so it depends on through-traffic rather than
  local demand.
- **I-81 New River Valley** and **I-81 Bristol.** The most isolated markets
  in Virginia at 97 and 106 miles from any store, but small and slow-growing.

## Why Northern Virginia is not the recommendation

Northern Virginia contains the highest-scoring counties in the state. Fairfax
ranks 1st, Arlington 3rd. The corridor holds 2.1 million people. It also
contains no eligible candidate.

Every jurisdiction there fails one of two screens. Fairfax and Arlington are
too dense for an interchange-scale site: the two Virginia stores the company
actually pursued occupy 36.18 acres in Stafford and 27.68 acres in New Kent
[3, 5], and land of that size near a Northern Virginia interchange is
largely built out. Prince William, at 19.8 miles from the approved Stafford
site, falls inside the overlap screen.

The sensible reading is that Northern Virginia is demand, not a location. It
is the population that makes the Stafford site work, and the model's high
scores there reflect the size of that catchment rather than a place to build.
A county-level model cannot price land, read a zoning map, or judge
congestion, so a high score in a dense market should be treated as a question
rather than an answer.

## Limitations and next steps

The screening is county-level and cannot substitute for site work. Centroid
distances are straight-line, not drive time. Interstate exposure is the
highest single mainline segment reading in a county, not average traffic
across it, and VDOT records each carriageway separately with differing
values, so these figures are exposure proxies rather than two-way counts.
Establishment counts treat a 120-pump travel centre and a two-pump rural
station alike. Scenario weights are illustrative postures, not company
estimates.

All 130 automated checks pass. Those checks test data integrity and pipeline
reproducibility. They say nothing about whether the commercial conclusions
are right. Across 80 one-component weight perturbations of plus or minus 20%,
the Spearman rank correlation against the baseline never fell below 0.992 and
at least 8 of the baseline top 10 counties survived every run, which indicates
stability under the tested local weight changes but does not validate the
choice of variables.

Thirteen jurisdictions, including Newport News and Hampton, are crossed by an
interstate for which the VDOT extract carries no mainline record. They are
held back for data reasons rather than screened out on the merits, and would
need a fuller traffic source before being ranked.

The next steps that would most change these conclusions, in order: a drive-time
trade-area model to replace the straight-line overlap screen; exit-level fuel
and food supply rather than county establishment counts; and parcel and
land-price data to turn the density screen into a real feasibility test.

Citations are in `docs/citations.md`. Assumptions are in
`docs/assumptions.md`. Full limitations are in `limitations_report.md`.
