# Corridor Recommendations

Highway corridors, not administrative districts, are the unit a travel-centre
decision is actually made in. This report groups eligible counties into
corridors that share an interstate and a travel market.

Corridor membership is analyst-defined and then checked against the processed
VDOT mainline records, so no corridor is named without a route behind it.
A corridor is tiered on its best **eligible** county rather than its
best-scoring one. Otherwise a corridor would lead on the strength of a county
that already has a store or could not host one.

An earlier version of this analysis grouped counties by VDOT construction
district. Those districts are maintenance administration and do not describe
where customers travel, so they are now used only as an intermediate
screening view. See `VDOT District Screening` on the dashboard.

## Candidate corridors

| Corridor | Best eligible county | Rank | Eligible | Population | Nearest store from an eligible county | Max eligible segment ADT |
|---|---|---|---|---|---|---|
| I-64 / I-264 Hampton Roads | Virginia Beach city | 4 | 3 | 1,649,381 | 58.8 mi | 195,000 |
| I-95 Richmond South | Chesterfield County | 6 | 2 | 494,141 | 33.4 mi | 131,000 |
| I-95 Richmond North | Hanover County | 12 | 1 | 673,681 | 32.5 mi | 131,000 |
| I-81 Winchester / Frederick | Frederick County | 14 | 3 | 222,130 | 39.7 mi | 72,000 |
| I-81 Roanoke / Salem | Roanoke County | 15 | 3 | 365,074 | 46.9 mi | 78,000 |
| I-64 Charlottesville | Albemarle County | 16 | 1 | 202,087 | 30.5 mi | 55,000 |
| I-64 Richmond West | Goochland County | 18 | 2 | 64,625 | 40.9 mi | 81,000 |

**Hampton Roads is the priority.** It combines the largest population of any
candidate corridor, the highest traffic reading, three qualifying
jurisdictions, and comfortable spacing from anything already built or
announced. Nothing else on the list has all four.

The two Richmond corridors rank next on score but both sit within 35 miles of
the announced New Kent store. They are flagged for trade-area review rather
than recommended outright. Splitting Richmond into its northern, southern,
western and eastern segments matters here: treated as one market it would
look either fully taken or fully open, and neither is true.

I-81 Winchester and Frederick is the strongest option with no overlap
question attached. Spacing against Mount Crawford is 68.8 miles, which is
reasonable on a single corridor.

## Watchlist corridors

| Corridor | Best eligible county | Rank | Population | Nearest store | Note |
|---|---|---|---|---|---|
| I-81 New River Valley | Montgomery County | 21 | 194,264 | 97.3 mi | Most isolated market in the state alongside Bristol, but small |
| I-81 Bristol / Southwest | Washington County | 30 | 147,661 | 105.7 mi | Widest spacing, weakest demand and declining population |
| I-95 / I-85 Southside | Mecklenburg County | 68 | 63,236 | 64.6 mi | Through-traffic corridor with a thin local base |

## Company-selected reference markets

These corridors contain a store that is open, announced or locally approved.
They are shown for context and are not expansion recommendations.

| Corridor | Site | Status |
|---|---|---|
| I-95 Fredericksburg / Stafford | Stafford County | Locally approved 19 May 2026, no confirmed opening date [3] |
| I-64 Richmond East / New Kent | New Kent County | Announced, permit filed, opening tied to the Exit 211 interchange project [5, 6, 7] |
| I-81 Harrisonburg / Rockingham | Mount Crawford | Open since 30 June 2025 [1, 2] |

## Not current candidates

**I-95 / I-66 Northern Virginia** holds 2.1 million people and the two
highest-scoring counties in Virginia, and has no eligible jurisdiction.
Fairfax and Arlington are set aside on density, and Prince William falls
within the overlap screen of the approved Stafford site. The corridor is best
read as the demand base that supports Stafford rather than as a location in
its own right.

**I-66 Piedmont** has no eligible county, with Fauquier inside the overlap
screen at 29.2 miles.

## What would need to be true

Every corridor conclusion here rests on a straight-line overlap screen and a
density proxy for feasibility. Before any of this became a siting decision it
would need drive-time trade areas, interchange-level traffic and fuel supply,
and parcel availability with land cost. The screening narrows 133
jurisdictions to a short list. It does not choose a site.

Source numbers are in `outputs/tables/corridor_recommendations.csv` and
`outputs/tables/county_recommendations.csv`. Citation numbers refer to
`docs/citations.md`.
