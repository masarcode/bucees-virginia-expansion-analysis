"""Final corridor-level recommendations."""

import pandas as pd
import streamlit as st

from utils import corridors, holdout, page_footer, recommendations

st.title("Corridor Recommendations")
st.caption(
    "Highway corridors, not administrative districts, are the unit a travel "
    "centre decision is made in. Corridors group counties that share an "
    "interstate and a travel market, and each is tiered on its best eligible "
    "county rather than its best-scoring one."
)

corr = corridors()
rec = recommendations()

TIER_NOTE = {
    "Candidate corridor": "Contains at least one county that clears every screen "
                          "and ranks in the top 25.",
    "Watchlist corridor": "Contains eligible counties, but none reaching the "
                          "priority cutoffs.",
    "Company-selected reference market": "Already contains an open, announced or "
                                         "locally approved store. Shown for context, "
                                         "not recommended.",
    "Not a current candidate": "No eligible county, usually because of overlap with "
                               "an existing site or site feasibility.",
}

fmt = {
    "corridor": "Corridor", "best_eligible_rank": "Best rank",
    "eligible_counties": "Eligible", "population": "Population",
    "eligible_min_dist_bucees_mi": "Nearest store (mi)",
    "eligible_max_interstate_aadt": "Max segment ADT",
    "top_eligible": "Leading counties",
}
cols = st.column_config

for tier in ["Candidate corridor", "Watchlist corridor",
             "Company-selected reference market", "Not a current candidate"]:
    sub = corr[corr["corridor_tier"] == tier]
    if sub.empty:
        continue
    st.subheader(tier)
    st.caption(TIER_NOTE[tier])
    show = sub[list(fmt)].rename(columns=fmt)
    st.dataframe(show, hide_index=True, use_container_width=True,
                 column_config={
                     "Best rank": cols.NumberColumn(format="%d"),
                     "Population": cols.NumberColumn(format="localized"),
                     "Nearest store (mi)": cols.NumberColumn(format="%.1f"),
                     "Max segment ADT": cols.NumberColumn(format="localized"),
                 })

st.subheader("The read")
st.markdown("""
**Hampton Roads is the priority.** It combines the largest population of any
candidate corridor at about 1.65 million, the highest traffic reading, three
qualifying jurisdictions, and comfortable spacing from anything built or
announced. Nothing else on the list has all four.

**The Richmond corridors need trade-area work.** Chesterfield and Hanover rank
6th and 12th, but both sit within about 33 miles of the announced New Kent
store, just outside the 30-mile screen. They carry a review flag rather than a
clean recommendation. Splitting Richmond into segments matters here: treated as
one market it would look either fully taken or fully open, and neither is true.

**I-81 Winchester and Frederick is the cleanest option with no overlap
question**, at 68.8 miles from Mount Crawford on the same corridor.

**Northern Virginia is demand, not a location.** It holds 2.1 million people
and the two highest-scoring counties in the state, and no eligible
jurisdiction. Fairfax and Arlington are too dense for a site of roughly 30
acres, and Prince William falls inside the overlap screen for Stafford.
""")

st.subheader("Retrospective holdout check")
st.caption(
    "The model takes store locations as an input through the overlap "
    "component, so it cannot be said to have predicted the company's choices. "
    "Re-running the score with that component removed means no Buc-ee's data "
    "reaches the model at all. This is a face-validity signal, not evidence "
    "about the company's private site-selection criteria."
)
h = holdout().rename(columns={
    "county_name": "County", "store_status": "Development status",
    "blind_rank": "Rank without store data", "attractiveness_rank": "Rank in full model",
    "blind_score": "Blinded score"})
st.dataframe(h, hide_index=True, column_config={
    "Blinded score": st.column_config.NumberColumn(format="%.1f")})

with st.expander("Full county-level screening result"):
    show = rec[["attractiveness_rank", "county_name", "corridor",
                "weighted_score", "recommendation_status", "reason"]].rename(columns={
        "attractiveness_rank": "Rank", "county_name": "County",
        "corridor": "Corridor", "weighted_score": "Score",
        "recommendation_status": "Status", "reason": "Reason"})
    st.dataframe(show, hide_index=True, use_container_width=True, height=420,
                 column_config={"Score": st.column_config.NumberColumn(format="%.1f")})

page_footer()
