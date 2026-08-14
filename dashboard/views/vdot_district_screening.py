"""VDOT district screening: an intermediate geographic view, not the answer."""

import pandas as pd
import streamlit as st

from utils import PROJECT_ROOT, corridors, page_footer

st.title("VDOT District Screening")

st.warning(
    "**These are administrative highway districts, not retail trade areas.** "
    "VDOT construction districts exist to organise road maintenance. They are "
    "used here as an intermediate way to group counties geographically. The "
    "final recommendation is made at corridor level, on the Corridor "
    "Recommendations page."
)

summary = pd.read_csv(PROJECT_ROOT / "outputs/tables/regional_summary.csv")

st.subheader("Districts ranked by their strongest counties")
st.caption(
    "Ranked by the mean balanced score of each district's top three counties. "
    "This ignores whether those counties are actually available, which is why "
    "it is a screening view rather than a recommendation."
)

show = summary[["region", "mean_top3_score", "counties_in_top15", "population",
                "pop_growth_pct", "max_interstate_aadt",
                "min_dist_any_bucees_mi", "top_counties"]].rename(columns={
    "region": "District", "mean_top3_score": "Mean top-3 score",
    "counties_in_top15": "In statewide top 15", "population": "Population",
    "pop_growth_pct": "Population change %",
    "max_interstate_aadt": "Max segment ADT",
    "min_dist_any_bucees_mi": "Nearest store (mi)",
    "top_counties": "Leading counties"})
st.dataframe(show, hide_index=True, use_container_width=True, column_config={
    "Mean top-3 score": st.column_config.NumberColumn(format="%.1f"),
    "Population": st.column_config.NumberColumn(format="localized"),
    "Population change %": st.column_config.NumberColumn(format="%.1f"),
    "Max segment ADT": st.column_config.NumberColumn(format="localized"),
    "Nearest store (mi)": st.column_config.NumberColumn(format="%.1f"),
})

st.caption(
    "District names describe road administration, not markets. The Staunton "
    "district stretches from Winchester to Augusta County, so Frederick "
    "County's market is labelled Northern I-81 / Winchester in the corridor "
    "view rather than Staunton."
)

st.subheader("District map")
map_html = (PROJECT_ROOT / "outputs/maps/map_regions.html").read_text()
st.components.v1.html(map_html, height=580, scrolling=False)

st.subheader("Final corridor recommendations")
st.caption(
    "The recommendation that actually follows from this analysis is made at "
    "corridor level. Summary below, full detail on the Corridor "
    "Recommendations page."
)
corr = corridors()
cand = corr[corr["corridor_tier"].isin(["Candidate corridor", "Watchlist corridor"])][
    ["corridor", "corridor_tier", "best_eligible_rank", "eligible_counties",
     "population", "eligible_min_dist_bucees_mi"]].rename(columns={
    "corridor": "Corridor", "corridor_tier": "Tier",
    "best_eligible_rank": "Best rank", "eligible_counties": "Eligible counties",
    "population": "Population", "eligible_min_dist_bucees_mi": "Nearest store (mi)"})
st.dataframe(cand, hide_index=True, use_container_width=True, column_config={
    "Best rank": st.column_config.NumberColumn(format="%d"),
    "Population": st.column_config.NumberColumn(format="localized"),
    "Nearest store (mi)": st.column_config.NumberColumn(format="%.1f"),
})

page_footer()
