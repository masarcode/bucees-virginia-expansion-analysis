# Limitations

What this analysis can and cannot support. The assumption register with
rationale for each threshold is in `docs/assumptions.md`.

## What the model is

A county-level screen that ranks relative attractiveness within Virginia. It
narrows 133 jurisdictions to a short list of corridors worth investigating.
It is not a demand model, a revenue forecast, or a site recommendation, and
it cannot observe how the company actually chooses sites.

## Resolution

1. **County-level only.** No parcel availability, land cost, zoning posture
   or interchange-level suitability. The Stafford approval required a public
   hearing running past midnight and a 5-2 vote [4]. Risk of that kind sits
   entirely outside the model.
2. **Centroid distances are straight-line.** Overlap and accessibility use
   the distance from a county centroid, not drive time. In a large county the
   centroid may be far from the corridor that matters.
3. **The feasibility screen is a proxy.** Population density at or above
   2,000 per square mile stands in for the difficulty of assembling a 30-acre
   interchange site. It is analyst judgement calibrated against the two
   Virginia sites the company pursued, 36.18 acres in Stafford and 27.68 in
   New Kent [3, 5]. It is not a measurement of available land.

## Data

4. **ACS figures are period estimates.** The 2019-2023 values describe a
   60-month window, not a point in time, and carry sampling error that is
   larger for small counties [9]. Growth here is the change between two
   non-overlapping period estimates, following Census guidance against
   comparing overlapping ones [10]. Margins of error were not propagated into
   the scores.
5. **Income growth is reported in both nominal and real terms.** The
   2014-2018 estimates are in 2018 dollars and the 2019-2023 estimates in
   2023 dollars, so they are restated using the CPI-U annual averages, a
   factor of 1.21343 [11]. Because that factor is the same for every county,
   inflation adjustment does not change any score or rank; it changes only
   how the figure should be described.
6. **Establishment counts measure premises, not capacity.** A 120-pump travel
   centre and a two-pump rural station each count once under NAICS 447 [13].
   Highway-exit fuel supply specifically is not isolated.
7. **Traffic figures are segment maxima, not county averages.** VDOT records
   each carriageway as a separate directional event, and the two do not agree.
   The Stafford maximum of 260,000 comes from I-95N at mileposts 134.25 to
   136.22, while the southbound record over nearly the same stretch reports
   150,000 [12]. That segment is also at the southern terminus of the
   reversible 95 Express Lanes. Treat these as exposure proxies, not two-way
   counts, and not as traffic across a whole county.
8. **VDOT coverage is uneven.** Thirteen jurisdictions, including Newport
   News and Hampton, are crossed by an interstate for which the extract holds
   no mainline record. They are reported as "traffic data unavailable" rather
   than as lacking an interstate. The South Hampton Roads interstate network
   is filed under three legacy maintenance areas that each span several
   cities; those 556 records were resolved individually from geometry, which
   moved 159 segments to Chesapeake and 76 to Portsmouth that a
   name-based mapping had assigned to Norfolk.
9. **Store locations are compiled by hand.** There is no official
   machine-readable list, and the company location page does not distinguish
   open stores from planned ones [1]. Development status therefore comes from
   county and state sources [3, 5, 7]. Coordinates are geocoded to point of
   interest, address or city precision, which is immaterial against a 60-mile
   radius. Stores west of the Mississippi are excluded as the nearest is more
   than 900 miles away.

## Modelling

10. **Min-max normalization is relative and outlier-sensitive.** Scores
    describe standing within Virginia, not absolute attractiveness. One
    extreme county compresses the range for everyone else. Log transforms
    reduce this for size variables. Blended components are re-normalized so
    each spans the full range and the configured weights carry their stated
    influence.
11. **Scenario weights are illustrative postures, not company estimates.**
    Five scenarios and a sensitivity sweep show how much the answer moves,
    which is not the same as showing the weights are right.
12. **Sensitivity tests local stability only.** Across 80 one-component
    perturbations of plus or minus 20%, the Spearman correlation with the
    baseline never fell below 0.992 and at least 8 of the baseline top 10
    counties remained in every run. This says rankings are not brittle to small weight
    changes. It does not validate the choice of the eight variables, which is
    the larger modelling risk.
13. **The overlap radius is assumed.** Sixty miles for the trade area and
    thirty for the exclusion screen come from public reporting on how far
    these stores draw, not from customer data. Counties between 30 and 40
    miles are flagged for review rather than cleared or excluded.
14. **Announced and approved stores are treated as operating.** This is
    conservative for the Fredericksburg and eastern Richmond markets. New Kent
    is currently expected in December 2031 and depends on a VDOT interchange
    project scheduled to finish in 2029 [6, 7], so the assumption may hold
    the surrounding area back longer than reality warrants.

## Validation

All 130 automated checks pass. They cover data integrity and pipeline
reproducibility: row counts, key uniqueness, geometry validity, referential
integrity, reconciliation of county sums against published state totals, and
score range invariants. They do not test whether the commercial conclusions
are correct, and no number of passing checks would.

## What would strengthen it

In rough order of how much each would change the conclusions:

1. Drive-time trade areas to replace the straight-line overlap screen.
2. Exit-level fuel and food supply from point-of-interest data, instead of
   county establishment counts.
3. Parcel and land-price layers, turning the density proxy into a real
   feasibility test.
4. Tourism and freight flows to describe who is actually on the road, since
   a travel centre serves through-traffic more than residents.
5. Monte Carlo propagation of ACS margins of error into the scores.
