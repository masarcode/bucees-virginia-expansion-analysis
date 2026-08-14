# Resume Bullets

Every figure below comes from the project's own outputs. Pick the two or
three that fit the role rather than using all of them.

## Full versions

- Built an end-to-end market screening pipeline in Python and SQL covering
  all 133 Virginia county-equivalents, integrating five public datasets (ACS
  5-year estimates for two periods, County Business Patterns, VDOT traffic
  volumes, TIGER/Line geography and BLS CPI-U) with 130 automated data-integrity
  checks written to a SQLite validation table.

- Designed an eight-component scoring model normalized 0 to 100 and evaluated
  it under five weighting scenarios, then ran an 80-case sensitivity sweep
  perturbing each weight by plus or minus 20% (Spearman correlation never below
  0.992, at least 8 of 10 top-ranked counties retained) to establish how far
  the ranking could be trusted.

- Separated model output from business judgement by adding an eligibility
  screen covering development status, trade-area overlap, interstate access
  and site feasibility, so that the highest-scoring county in the state was
  correctly excluded from the recommendation set rather than presented as the
  answer.

- Wrote the final recommendation at highway-corridor level rather than by
  administrative district after establishing that VDOT construction districts
  are maintenance boundaries and not retail trade areas, and identified
  Hampton Roads (about 1.65 million residents, no store within 58 miles) as
  the clearest unserved market.

- Found and fixed a geographic data defect in which VDOT files the South
  Hampton Roads interstate network under legacy maintenance areas spanning
  several cities; resolving 556 segments individually from geometry moved 159
  segments to Chesapeake and 76 to Portsmouth, changing the eligibility
  outcome for a corridor that the analysis went on to recommend.

- Built a five-page Streamlit dashboard with an interactive Virginia map,
  scenario selector, per-county component breakdown and a methodology section
  exposing live validation status, sourced and captioned so a non-technical
  reader can follow both the result and its limits.

## Short versions

- Screened 133 Virginia county-equivalents for retail expansion using Python,
  SQL, GeoPandas and Streamlit, combining five public datasets behind a
  reproducible pipeline with 130 automated validation checks.

- Built an eight-component, five-scenario scoring model with sensitivity
  analysis, then layered an explicit eligibility screen on top so raw model
  ranks were never published as business recommendations.

- Traced a jurisdiction-coding defect in state traffic data that had hidden
  interstate access for two cities, corrected it with a spatial join, and
  documented the effect on the final recommendation.

## Talking points for interviews

- Why the highest-scoring county is not the recommendation, and how the
  eligibility screen makes that visible instead of hiding it.
- Why the model cannot be described as having predicted the company's actual
  site choices, and what a blinded re-run without store data shows instead
  (Stafford 3rd of 133, New Kent 21st, Rockingham 25th).
- How a weighting flaw was caught by a failing test: blended components did
  not span the full 0 to 100 range, so one component carried 7.9% influence
  against its 10% nominal weight.
- Why inflation adjustment changed the reported income figure but no rank,
  and how that follows from min-max normalization being invariant to a
  constant deflator.
