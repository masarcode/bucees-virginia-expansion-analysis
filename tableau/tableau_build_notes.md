# Tableau Build Notes

Practical notes for building the workbook. Field definitions are in
`tableau_data_dictionary.md`.

## What is in the package

| File | Rows | Grain | Size |
|---|---|---|---|
| `county_dashboard_data.csv` | 133 | One Virginia county-equivalent | 69 KB |
| `component_definitions.csv` | 8 | One model component | 4 KB |
| `component_scores_long.csv` | 1,064 | One county per component, 133 x 8 | 110 KB |
| `corridor_dashboard_data.csv` | 15 | One analyst-defined corridor | 4 KB |
| `scenario_weights.csv` | 9 (8 components plus TOTAL) | One component | < 1 KB |
| `virginia_counties.geojson` | 133 features | One county-equivalent, with geometry and all 41 county attributes | 1.3 MB |

## Validation results

All 15 export checks passed. Regenerate with
`python -m scripts.export_tableau`, which writes results to the project's
`validation_results` table alongside the pipeline's own checks.

| Check | Result |
|---|---|
| County row count | 133, as expected |
| GEOID uniqueness | 133 distinct of 133 |
| GEOID format | All five-character strings |
| Balanced rank matches the published recommendations table | Exact |
| Recommendation status matches the published table | Exact |
| Attractiveness score matches the published score | Exact, no rounding applied |
| All eight component scores match `market_scores` | Exact |
| Long component row count | 1,064, exactly 133 x 8 |
| Long component key uniqueness | 0 duplicates on `geoid` + `component` |
| Long component score is numeric | float64, 0 nulls, range 0.00 to 100.00 |
| Long component values match the wide file | All 1,064 identical |
| Long component key joins to the weights file | Exact match on all eight keys |
| Definitions cover every component, in model order | 8 rows |
| Definitions have no blank cells | All 48 cells populated |
| Declared input variables are real fields | All 13 exist in the source tables |
| Definitions flag the inverted components | `competition` and `overlap_risk` only |
| Corridor set matches the corridor report | 15 corridors, same set |
| Scenario weights sum to 1.0 | All five scenarios |
| GeoJSON feature count | 133 |
| GeoJSON geometry validity | 0 invalid, 0 missing |
| GeoJSON CRS | EPSG:4326 |
| No placeholder strings in text columns | None found |
| Booleans are TRUE / FALSE only | Confirmed |
| GeoJSON survives a round trip | 133 features, GEOIDs still strings |

### Expected nulls

These are real absences, not export faults. Do not fill them.

| Field | Nulls | Why |
|---|---|---|
| `development_status` | 130 | Only three jurisdictions contain a store |
| `max_interstate_segment_adt` | 90 | VDOT holds a mainline record for 43 jurisdictions |
| `gas_stations`, `gas_stations_per_10k` | 5 | County Business Patterns publishes no NAICS 447 row |
| `food_service_establishments` | 1 | Same reason |
| Corridor fields for reference and non-candidate corridors | 5 rows | No eligible member county exists to measure |

No nulls in `geoid`, `latitude`, `longitude`, `balanced_rank`,
`market_attractiveness_score` or `recommendation_status`.

## Which file to connect first

**Connect `virginia_counties.geojson` first.** It carries the geometry *and*
all 41 county attributes, so one connection powers the map, the ranking
tables and the county detail views. Tableau reads GeoJSON natively and will
create a Geometry field automatically.

Then add `corridor_dashboard_data.csv` as a second table, related on
`corridor`. Add `scenario_weights.csv` as a separate, unrelated data source
for a methodology sheet.

Use `county_dashboard_data.csv` instead of the GeoJSON only if you want a
lighter extract for a workbook with no map. The two carry identical values,
so mixing them in one workbook is redundant and risks two sources of truth.

## Relationships

| From | To | Key | Cardinality |
|---|---|---|---|
| County (GeoJSON or CSV) | Corridor CSV | `corridor` | Many to one |
| County (GeoJSON or CSV) | Component long CSV | `geoid` | One to many |
| Component long CSV | Scenario weights CSV | `component` | Many to one |
| Component long CSV | Component definitions CSV | `component` | Many to one |

Use a **relationship**, not a join, for the corridor link. Sixty counties
carry `Not in a screened corridor`, which has no row in the corridor file. A
relationship keeps them; an inner join silently drops nearly half of Virginia.

Keep the component long file in its **own data source** unless you
specifically need it beside county-level measures. Relating it to the county
table at one-to-many fans out every county measure eight times, so any
untreated `SUM([Population])` will report eight times the real figure. If you
do relate them, aggregate county measures with `MIN()` or `AVG()`, or use
`LOD` expressions such as `{FIXED [Geoid] : MIN([Population])}`.

`scenario_weights.csv` has no key to the county or corridor tables. Join it
to the component long file on `component` when you want weighted
contributions, or use it alone for a methodology sheet.

## Recommended calculated fields

```
// Is this a place we would actually recommend?
[Is Actionable]
IF [Recommendation Status] IN ("Priority candidate", "Secondary candidate")
THEN "Actionable" ELSE "Not actionable" END
```

```
// Group the eight statuses into four bands for colour.
[Status Band]
CASE [Recommendation Status]
  WHEN "Priority candidate"  THEN "1 Priority"
  WHEN "Secondary candidate" THEN "2 Secondary"
  WHEN "Watchlist"           THEN "3 Watchlist"
  WHEN "Reference case"      THEN "4 Existing or planned"
  ELSE "5 Screened out"
END
```

```
// Rank under whichever scenario the user selected.
[Selected Rank]
CASE [Scenario Parameter]
  WHEN "Balanced"    THEN [Balanced Rank]
  WHEN "Highway"     THEN [Highway Rank]
  WHEN "Growth"      THEN [Growth Rank]
  WHEN "Affluent"    THEN [Affluent Rank]
  WHEN "Underserved" THEN [Underserved Rank]
END
```

```
// Percentile, so longer bars always mean stronger.
// Use this rather than plotting rank directly.
[Selected Percentile]
(133 - [Selected Rank]) / 132 * 100
```

```
// Spread across scenarios. A small range means the county does not
// depend on one weighting to look good.
[Rank Range Across Scenarios]
MAX([Balanced Rank], [Highway Rank], [Growth Rank], [Affluent Rank], [Underserved Rank])
- MIN([Balanced Rank], [Highway Rank], [Growth Rank], [Affluent Rank], [Underserved Rank])
```

```
// Honest label for traffic, which is null for 90 jurisdictions.
[Traffic Label]
IF ISNULL([Max Interstate Segment Adt])
THEN IF [Interstate Access Flag] THEN "Interstate present, no traffic record"
     ELSE "No interstate" END
ELSE STR(ROUND([Max Interstate Segment Adt])) + " ADT" END
```

```
// Distance band against the 30-mile screen.
[Overlap Band]
IF [Nearest Store Distance Mi] < 30 THEN "Inside 30 mi screen"
ELSEIF [Nearest Store Distance Mi] < 40 THEN "30 to 40 mi, review needed"
ELSE "40+ mi, clear" END
```

On the component long file, joined to `scenario_weights.csv` on `component`:

```
// How many points this component contributes to the county's total,
// under the scenario the user selected.
[Component Contribution]
[Component Score] *
CASE [Scenario Parameter]
  WHEN "Balanced"    THEN [Balanced Weight]
  WHEN "Highway"     THEN [Highway Weight]
  WHEN "Growth"      THEN [Growth Weight]
  WHEN "Affluent"    THEN [Affluent Weight]
  WHEN "Underserved" THEN [Underserved Weight]
END
```

Summing `[Component Contribution]` across a county's eight rows reproduces
its `market_attractiveness_score` exactly, which makes a stacked bar a
genuine decomposition of the score rather than an illustration of one. This
was verified during export: the reconstruction matches the published score to
within 1.4e-14, which is floating-point noise.

Use `[Component Label]` from the weights file, not `[Component]`, on any axis
a viewer reads. The raw key says `competition`, while the label says
`Low Competition`, and only the second states the direction correctly.

Relate `component_definitions.csv` on `component` as well, and the tooltip on
any component mark can carry its definition and its caveat:

```
<Component Label>   <Component Score> of 100
<Plain English Definition>
A higher score means: <Higher Score Meaning>
Source: <Primary Source>
Caveat: <Key Limitation>
```

That is the most useful place to put a limitation, because it appears beside
the number rather than in a document nobody opens.

## Recommended parameters

| Parameter | Type | Values | Purpose |
|---|---|---|---|
| `Scenario Parameter` | String list | Balanced, Highway, Growth, Affluent, Underserved | Drives `[Selected Rank]` so one map serves all five scenarios |
| `Top N` | Integer slider | 5 to 50, step 5, default 15 | Controls how many counties appear in ranking views |
| `Overlap Screen Miles` | Float slider | 15 to 60, default 30 | **Display only.** Lets a viewer see how the 30-mile assumption shades the picture. It cannot re-run the screen, so label it clearly as illustrative |

The third parameter needs care. `recommendation_status` was computed at 30
miles and will not change when the slider moves. Use it to shade or annotate
`[Nearest Store Distance Mi]`, never to relabel status, or the workbook will
contradict itself.

## Recommended filters

Dashboard level, applied to all relevant sheets:

- **Recommendation status** (multi-select). Default to Priority and Secondary
  so the dashboard opens on the answer rather than all 133 rows.
- **Corridor** (multi-select, including `Not in a screened corridor`).
- **County type** (County or Independent city).
- **Interstate access flag** (TRUE or FALSE).

Deliberately *not* recommended as a headline filter:

- **VDOT district.** It is a road-maintenance boundary, not a market. If you
  expose it, label it "VDOT district (administrative, not a trade area)".
- **Market attractiveness score** as a range filter on its own. Filtering to
  high scores alone reproduces the mistake the screening layer exists to
  prevent: Fairfax has the highest score in Virginia and is not a candidate.

## Recommended tooltips

County map and ranking views:

```
<County Name>  (<County Type>)
<Recommendation Status>
<Recommendation Reason>

Attractiveness rank <Balanced Rank> of 133   Score <Market Attractiveness Score>
Corridor: <Corridor>

Population <Population>          Change <Population Change Pct>%
Median household income <Median Household Income>
Income change: <Nominal Income Change Pct>% nominal, <Real Income Change Pct>% real
Traffic: <Traffic Label>
Nearest store: <Nearest Store Distance Mi> mi
```

Lead with status, not score. The reason field is written as a full sentence
and is the single most useful thing in the tooltip.

Corridor views:

```
<Corridor>
<Corridor Tier>
<Recommendation Summary>

Best eligible county rank <Best Eligible Rank>
Eligible counties <Eligible County Count>
Corridor population <Total Corridor Population>
Nearest store from an eligible county <Nearest Store Distance Mi> mi
```

## Recommended formatting

| Field type | Format | Note |
|---|---|---|
| Scores | 1 decimal | Matches the published dashboard. The file holds full precision |
| Percentages | 1 decimal with a `%` suffix | Values are already percentages, so do not apply Tableau's percent format, which would multiply by 100 |
| Distances | 1 decimal, suffix ` mi` | Straight-line, so more precision implies accuracy that is not there |
| Population, ADT, establishments | Whole number with thousands separator | |
| Income | Currency, no decimals | |
| Ranks | Whole number | Consider showing "of 133" for context |
| Nulls | Show as a dash or "Not available" | Do this in the view, never in the data |

Colour:

- Use a single sequential ramp for scores. Higher should be darker.
- Use a categorical palette for `[Status Band]`, with the screened-out band
  in grey so attention lands on the candidates.
- Do not colour by `market_attractiveness_score` alone on the main map
  without also encoding status. That is the visual version of presenting a
  rank as advice.

## Two things worth getting right

**Keep score and recommendation visibly separate.** The whole point of the
analysis is that they differ. Fairfax ranks 1st and is feasibility
constrained; Northern Virginia holds 2.1 million people and has no eligible
county. A dashboard that sorts by score and stops has lost the finding.

**Label traffic carefully.** `max_interstate_segment_adt` is the highest
single mainline segment reading, not countywide or two-way traffic. VDOT
records each carriageway separately with differing values: the Stafford
maximum of 260,000 comes from the northbound record, while southbound over
nearly the same stretch reports 150,000. "Peak interstate segment traffic" is
an honest axis title. "Traffic volume" is not.

## Regenerating

```bash
python -m scripts.export_tableau
```

Reads the published outputs and rewrites all four files. It does not
recompute the model, so the package cannot drift from the dashboard. Re-run
it after any pipeline change, then refresh the Tableau extracts.

## Provenance

Sources, access dates and claim-level citations are in
`docs/source_inventory.md` and `docs/citations.md`. Assumptions behind the
screening thresholds are in `docs/assumptions.md`, entries A14 to A18.

Portfolio analysis. Not affiliated with Buc-ee's Ltd. County-level screening
only. Not a parcel-level site recommendation.
