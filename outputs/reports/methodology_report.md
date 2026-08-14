# Methodology

## 1. Unit of analysis

Virginia's 133 county-equivalents: 95 counties and 38 independent cities,
keyed by 5-digit GEOID. Independent cities are kept separate because they
carry their own FIPS codes in every source and interrupt county geography on
most Virginia corridors. They are grouped into corridors at the final step.

## 2. Two layers, kept apart

The project deliberately separates two things that are easy to conflate.

**Market attractiveness rank** is what the model computes. It measures
relative standing within Virginia on eight components.

**Recommendation status** is an analyst screen applied afterwards. It asks
whether a store already exists in the county, whether a new one would sit
inside an existing store's trade area, whether an interstate is present, and
whether density makes an interchange-scale site implausible.

A raw rank is never presented as advice. Fairfax County holds the highest
attractiveness score in the state and is not a candidate, because a 30-acre
site near a Northern Virginia interchange is the binding constraint rather
than demand.

## 3. Pipeline

Seven acquisition scripts, five cleaning scripts, a database load, then
analysis. `scripts/run_pipeline.py` runs them in order. Every script is
idempotent and independently runnable, and every transformation records
pass, warn or fail checks into a `validation_results` table. Raw files are
never modified after download and are cataloged in `data/raw/MANIFEST.md`
with URL, access time, size and row counts.

Three acquisition decisions are worth noting.

Census API endpoints began requiring a key, verified on 3 August 2026 when
data requests redirected to a "Missing Key" page. ACS and CBP therefore come
from the official bulk files, which need no credentials. The 2014-2018 period
uses the legacy sequence-file format; the extraction was checked by
reconciling county sums against the state row embedded in the same files,
which matched exactly in both periods.

VDOT publishes 123,766 traffic segments. These are downloaded attribute-only
and assigned to counties using the jurisdiction field, with documented rules
for historical spellings, towns and statewide records. The South Hampton
Roads interstate network is an exception: it is filed under three legacy
maintenance areas that each span several cities. Mapping a whole maintenance
area to one city put Chesapeake's and Portsmouth's interstate mileage in
Norfolk. Those 556 records are therefore downloaded with geometry and
assigned individually to whichever jurisdiction holds most of each segment.

Buc-ee's has no official machine-readable location list, and its location
page does not separate open stores from planned ones [1]. Twenty stores and
sites east of the Mississippi were compiled with a source URL for each and
geocoded through Nominatim, then validated point-in-expected-state against
TIGER. Development status comes from county and state sources [3, 5, 7]
rather than from the company list.

## 4. Features

- **Growth** compares the non-overlapping ACS 5-year windows 2014-2018 and
  2019-2023, following Census guidance against comparing overlapping periods
  [10]. These are period estimates, so growth is a change between two
  estimates rather than an annual population change.
- **Income** is reported in nominal and real terms. ACS states money values
  in the final year of each period, so the 2014-2018 figures are restated in
  2023 dollars using CPI-U annual averages, a factor of 1.21343 [11]. Because
  that factor is identical for every county, and min-max normalization is
  invariant to a positive affine transform, the adjustment changes no score
  and no rank. It changes only how the number should be described.
- **Traffic** gives county maximum and mean ADT, interstate mainline maximum
  ADT with ramps and rest areas excluded by rule, directional interstate
  route-miles, and a VMT proxy. These are exposure proxies. VDOT records each
  carriageway separately with differing values, so a segment maximum is
  neither a two-way count nor a countywide average.
- **Spatial** measures centroid distance to the nearest interstate, using
  TIGER primary roads within 100 miles of Virginia so border interstates
  count, and to the nearest open or planned store. A separate flag records
  whether an interstate physically crosses each jurisdiction, which
  distinguishes a genuine absence of interstate from a gap in the traffic
  extract.
- **Business** counts establishments in all sectors, gasoline stations
  (NAICS 447), food service (722) and retail (44-45), plus per-capita
  densities.

## 5. Scoring

Eight components, each min-max scaled from 0 to 100 across the 133
jurisdictions. Log transforms compress size variables spanning four orders of
magnitude. Competition and overlap are inverted so that higher always means
more attractive. Counties without an interstate receive zero highway exposure
rather than a missing value. The direction of every component was checked
against its driving raw variable.

Components blended from two inputs are re-normalized after blending. A
weighted sum of two separately scaled inputs does not span 0 to 100, because
the county holding the minimum of one input rarely holds the minimum of the
other. Left uncorrected, such a component carries less influence than its
nominal weight implies: growth measured 7.9% actual against 10.0% nominal.
Re-normalizing is monotonic, so no county moves within a component, and it
makes the configured weights mean what they say. A check enforces it.
Correcting this moved no county in or out of the balanced top 15.

Min-max scaling measures relative standing inside Virginia. A score of 80
means high relative to other Virginia counties, not high in absolute terms.

## 6. Scenarios and sensitivity

Five weight vectors (balanced, highway, growth, affluent, underserved), each
summing to 1.0 and validated at runtime, produce five complete rankings.
These are illustrative strategic postures, not estimates of company
priorities. Seven counties appear in the top 10 of at least four scenarios.

Across 80 one-component perturbations of plus or minus 20% with weights
renormalized, the Spearman rank correlation against the baseline never fell
below 0.992, and at least 8 of the baseline top 10 counties remained in
every tested ranking. This indicates stability under the tested local weight
changes. It does not validate the underlying variable selection, which is the
larger modelling risk.

## 7. Eligibility screen

Applied in order, first match wins. Thresholds are analyst assumptions
recorded as A14 to A18 in `docs/assumptions.md`.

| Rule | Test | Result |
|---|---|---|
| Reference case | County contains an open, announced or approved store | Excluded from candidates, reported for context |
| Overlap constrained | Centroid within 30 miles of such a store, half the assumed 60-mile trade radius | Excluded |
| Traffic data unavailable | Interstate crosses the county but VDOT holds no mainline record | Held back for data reasons, not on merit |
| No interstate access | No interstate crosses the county | Excluded |
| Feasibility constrained | Population density at or above 2,000 per square mile | Excluded |
| Priority candidate | Eligible, balanced rank in the top 25, and top 25 in at least 4 of 5 scenarios | Recommended |
| Secondary candidate | Eligible, balanced rank in the top 45 | Recommended with caveats |
| Watchlist | Eligible, outside those cutoffs | Monitor |

Counties between 30 and 40 miles from a store keep their tier but carry a
"further overlap review required" flag, so a borderline case is neither
silently cleared nor silently dropped.

## 8. Corridors

Final recommendations are written at corridor level. Corridors are
analyst-defined groupings of counties sharing an interstate and a travel
market, with membership validated against the processed VDOT mainline
records. Each corridor is tiered on its best eligible county, not its
best-scoring one, so a corridor cannot lead on the strength of a county that
already has a store.

VDOT construction districts are retained as an intermediate screening view
only. They are maintenance administration and are not retail trade areas.

## 9. Retrospective holdout

The model takes store locations as an input through the overlap component, so
it cannot be said to have predicted the company's choices. To get a
face-validity signal, the scoring was re-run with the overlap component
removed and its weight redistributed, meaning no Buc-ee's data reached the
model at all. On that blinded run Stafford ranks 3rd of 133, New Kent 21st
and Rockingham 25th. This suggests the demand, growth and highway measures
track something real. It is not evidence about the company's private
site-selection criteria.

## 10. Reproducibility

`python -m scripts.run_pipeline` rebuilds everything from raw or freshly
downloaded data. `pytest` covers configuration, schema and output invariants.
`streamlit run dashboard/app.py` serves the results. No credentials are
needed at any point.

Citation numbers refer to `docs/citations.md`.
