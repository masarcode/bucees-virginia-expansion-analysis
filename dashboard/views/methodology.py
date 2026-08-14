"""Methodology: sources, formulas, screening rules, assumptions, validation."""

import pandas as pd
import streamlit as st

from utils import PROJECT_ROOT, config, page_footer, validation_summary

st.title("Methodology and Data Quality")

tab_src, tab_model, tab_screen, tab_assume, tab_valid = st.tabs(
    ["Data sources", "Scoring model", "Screening rules",
     "Assumptions and limitations", "Validation status"])

with tab_src:
    st.markdown("""
| Source | What it provides | Vintage | How it was obtained |
|---|---|---|---|
| **ACS 5-year estimates** (U.S. Census Bureau) | Population, income, age, labour force, housing, commuting | 2019-2023 and 2014-2018, non-overlapping | Official bulk summary files. The API began requiring a key; the bulk files do not |
| **County Business Patterns** (U.S. Census Bureau) | Establishments by NAICS: all sectors, gasoline stations 447, retail 44-45, food service 722 | 2023, NAICS 2017 basis | Bulk county file `cbp23co.zip` |
| **Traffic Volume** (VDOT) | 123,766 directional segments with ADT, AAWDT, route names, jurisdictions | 2024 publication | ArcGIS feature service, paginated, attributes preserved as received |
| **TIGER/Line** (U.S. Census Bureau) | County and city boundaries, primary roads, Virginia places | 2023 | Cartographic boundary and TIGER archives |
| **CPI-U all items** (U.S. Bureau of Labor Statistics) | Annual averages, series CUUR0000SA0 | 1913-2025 | Public flat file |
| **Store locations** | 20 open and planned sites east of the Mississippi | Accessed August 2026 | Compiled by hand with a source URL per row, geocoded via Nominatim |

Development status for each Virginia site comes from county and state
sources rather than the company location page, which does not distinguish
open stores from planned ones. Every raw file is logged in
`data/raw/MANIFEST.md` with URL, access time, size and row count, and is
never modified after download.
""")
    st.caption("Numbered citations for individual claims are in docs/citations.md.")

with tab_model:
    st.markdown("""
Eight components, each scaled from 0 to 100 **relative to the other 132
Virginia jurisdictions**. A score of 80 means high within Virginia, not high
in absolute terms.

| Component | How it is built |
|---|---|
| Market demand | population and commuters, log scaled |
| Growth | population change, plus income change |
| Purchasing power | median household and per-capita income |
| Highway opportunity | maximum interstate mainline segment ADT, plus a traffic-volume proxy |
| Accessibility | distance from the county centroid to the nearest interstate |
| Commercial activity | establishments overall, plus food service per resident |
| Low competition | inverse of gas stations per resident |
| Low overlap risk | distance to the nearest open or planned store, capped at 120 miles |

Components blended from two inputs are re-normalized afterwards. A weighted
sum of two separately scaled inputs does not span the full range, because the
county holding the minimum of one input rarely holds the minimum of the
other. Uncorrected, growth carried 7.9% of the weight against a nominal 10%.
The rescaling is monotonic, so no county moves within a component.
""")
    cfg = config()
    st.markdown("**Scenario weights.** Each column sums to 1.0. These are "
                "illustrative strategic postures, not estimates of company "
                "priorities.")
    st.dataframe(pd.DataFrame(cfg["scoring"]["scenarios"]).round(3),
                 use_container_width=True)
    st.markdown("""
**Sensitivity.** Across 80 one-component weight perturbations of plus or
minus 20%, the Spearman rank correlation with the baseline never fell below
0.992, and at least 8 baseline top-10 counties remained in every tested
ranking.
This indicates stability under the tested local weight changes. It does not
validate the underlying variable selection.

**Inflation.** ACS states money values in the final year of each period, so
2014-2018 figures are restated in 2023 dollars using CPI-U, a factor of
1.21343. Because that factor is identical for every county, and min-max
scaling is invariant to a positive affine transform, the adjustment changes
no score and no rank. It changes only how the figure should be described.
""")

with tab_screen:
    st.markdown("""
The model produces a **market attractiveness rank**. A separate screen sets
each county's **actionable recommendation status**. Keeping them apart is the
point: the highest-scoring county in Virginia is not a candidate.

Rules are applied in order, and the first match wins.

| Rule | Test | Outcome |
|---|---|---|
| Reference case | County already contains an open, announced or locally approved store | Excluded, reported for context |
| Overlap constrained | Centroid within 30 miles of such a store | Excluded |
| Traffic data unavailable | An interstate crosses the county but VDOT holds no mainline record | Held back for data reasons, not on merit |
| No interstate access | No interstate crosses the county | Excluded |
| Feasibility constrained | Population density at or above 2,000 per square mile | Excluded |
| Priority candidate | Eligible, top 25 balanced, and top 25 in at least 4 of 5 scenarios | Recommended |
| Secondary candidate | Eligible, top 45 balanced | Recommended with caveats |
| Watchlist | Eligible, outside those cutoffs | Monitor |

Counties between 30 and 40 miles from a store keep their tier but carry a
"further overlap review required" flag, so a borderline case is neither
silently cleared nor silently dropped.

**Why 30 miles?** It is half the 60-mile trade radius the project assumes,
which itself comes from public reporting on how far these stores draw rather
than from customer data.

**Why 2,000 people per square mile?** The two Virginia sites the company
pursued occupy 36.18 acres in Stafford and 27.68 acres in New Kent. At that
density, land of that size near an interchange is largely built out. The
cutoff is analyst judgement, not a measurement of available land.

Corridors are analyst-defined groupings of counties sharing an interstate and
a travel market, validated against the processed VDOT records. VDOT
construction districts are maintenance administration and are not retail
trade areas, so they are kept as a screening view only.
""")

with tab_assume:
    st.markdown((PROJECT_ROOT / "docs/assumptions.md").read_text())
    st.divider()
    st.markdown("""
### The limits that matter most

- **County-level only.** No parcel availability, land cost, zoning posture or
  interchange-level suitability. The Stafford approval took a hearing running
  past midnight and a 5-2 vote. Risk of that kind is outside the model.
- **Distances are straight-line, not drive time.** A centroid in a large
  county may sit far from the corridor that matters.
- **Traffic figures are segment maxima.** VDOT records each carriageway
  separately and the two disagree: Stafford's 260,000 comes from the
  northbound record, while southbound over the same stretch reports 150,000.
  Treat these as exposure proxies, not two-way counts or county averages.
- **ACS figures are period estimates** describing a 60-month window, with
  sampling error that is larger for small counties. Margins of error were not
  propagated into the scores.
- **No public model can observe Buc-ee's site-selection criteria.** Nothing
  here should be read as reconstructing them.
""")

with tab_valid:
    v = validation_summary()
    n_pass = int((v["status"] == "pass").sum())
    st.metric("Automated checks passing", f"{n_pass} of {len(v)}")
    st.caption(
        "These tests verify data integrity and pipeline reproducibility: row "
        "counts, key uniqueness, geometry validity, referential integrity, "
        "reconciliation of county sums against published state totals, and "
        "score range invariants. They do not verify the commercial accuracy "
        "of the final site recommendations."
    )
    bad = v[v["status"] != "pass"]
    if len(bad):
        st.warning("Checks not passing:")
        st.dataframe(bad, hide_index=True, use_container_width=True)
    st.dataframe(v, hide_index=True, use_container_width=True, height=460)

page_footer()
