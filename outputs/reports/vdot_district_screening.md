# VDOT District Screening

**These are administrative highway districts, not retail trade areas,**
and this file is a screening view rather than a recommendation. VDOT
construction districts exist to organise road maintenance. They are used
here only as an intermediate way to group counties geographically.

The actual recommendation is made at corridor level and accounts for
which markets are already taken. See
[corridor_recommendations.md](corridor_recommendations.md).

Districts below are ordered by the mean balanced score of their top three
counties. That ordering ignores whether those counties could host a store,
which is exactly why it is not the answer: the Northern Virginia district
leads on score and contains no eligible site. County-level detail is in
outputs/tables/regional_summary.csv.

## Highest scoring districts
### Northern Virginia district
- Leading counties (balanced scenario): Fairfax, Prince William, Arlington
- Mean top-3 balanced score: 76.6; best county rank: 1; 4 county(ies) in statewide top 15
- Population 2,547,100; weighted growth 3.3%; max interstate AADT 254,000
- Nearest existing/announced Buc-ee's: 20 mi from closest county centroid

### Hampton Roads district
- Leading counties (balanced scenario): Virginia Beach city, Chesapeake city, Norfolk city
- Mean top-3 balanced score: 67.5; best county rank: 4; 4 county(ies) in statewide top 15
- Population 1,783,424; weighted growth 2.4%; max interstate AADT 195,000
- Nearest existing/announced Buc-ee's: 17 mi from closest county centroid

## Middle band
### Richmond district
- Leading counties (balanced scenario): Chesterfield, Henrico, Hanover
- Mean top-3 balanced score: 66.0; best county rank: 6; 3 county(ies) in statewide top 15
- Population 1,365,506; weighted growth 5.3%; max interstate AADT 160,000
- Nearest existing/announced Buc-ee's: 1 mi from closest county centroid

### Fredericksburg district
- Leading counties (balanced scenario): Stafford, Spotsylvania, Caroline
- Mean top-3 balanced score: 61.8; best county rank: 5; 2 county(ies) in statewide top 15
- Population 536,510; weighted growth 7.3%; max interstate AADT 260,000
- Nearest existing/announced Buc-ee's: 0 mi from closest county centroid

## Lower band
### Salem district
- Leading counties (balanced scenario): Roanoke, Montgomery, Roanoke city
- Mean top-3 balanced score: 54.8; best county rank: 15; 1 county(ies) in statewide top 15
- Population 693,931; weighted growth 0.3%; max interstate AADT 78,000
- Nearest existing/announced Buc-ee's: 53 mi from closest county centroid

### Culpeper district
- Leading counties (balanced scenario): Albemarle, Fauquier, Louisa
- Mean top-3 balanced score: 54.4; best county rank: 16; 0 county(ies) in statewide top 15
- Population 433,218; weighted growth 5.7%; max interstate AADT 56,000
- Nearest existing/announced Buc-ee's: 25 mi from closest county centroid

### Staunton district
- Leading counties (balanced scenario): Frederick, Rockingham, Augusta
- Mean top-3 balanced score: 53.9; best county rank: 14; 1 county(ies) in statewide top 15
- Population 571,794; weighted growth 3.9%; max interstate AADT 72,000
- Nearest existing/announced Buc-ee's: 6 mi from closest county centroid

### Bristol district
- Leading counties (balanced scenario): Washington, Wythe, Smyth
- Mean top-3 balanced score: 47.5; best county rank: 30; 0 county(ies) in statewide top 15
- Population 332,513; weighted growth -4.7%; max interstate AADT 63,000
- Nearest existing/announced Buc-ee's: 57 mi from closest county centroid

### Lynchburg district
- Leading counties (balanced scenario): Lynchburg city, Campbell, Amherst
- Mean top-3 balanced score: 41.2; best county rank: 49; 0 county(ies) in statewide top 15
- Population 393,503; weighted growth -0.9%; no interstate mainline
- Nearest existing/announced Buc-ee's: 36 mi from closest county centroid

## Why this is not the recommendation

- District score bands ignore development status. A district can lead here while every strong county in it already has a store or could not host one.
- District names describe road administration, not markets. The Staunton district runs from Winchester to Augusta County, so Frederick County's market is labelled Northern I-81 / Winchester in the corridor view.
- A store near a district edge draws customers across the boundary, which district totals cannot represent.
- Every scoring-model limitation still applies. See docs/assumptions.md and limitations_report.md.