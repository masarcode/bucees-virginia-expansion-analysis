"""Side-by-side comparison of two to four markets."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (COMPONENT_LABELS, county_profile, market_scores,
                   page_footer, recommendations, vt)

st.title("Market Comparison")
st.caption("Compare candidate markets against each other, or against the "
           "counties the company has already chosen.")

profile = county_profile()
scores = market_scores()
rec = recommendations()

defaults = ["Virginia Beach city", "Chesterfield County", "Stafford County"]
picks = st.multiselect(
    "Choose two to four jurisdictions",
    profile.sort_values("county_name")["county_name"],
    default=[d for d in defaults if d in set(profile["county_name"])],
    max_selections=4)

if len(picks) < 2:
    st.info("Pick at least two to compare.")
    st.stop()

sel = (profile[profile["county_name"].isin(picks)]
       .merge(scores, on="geoid")
       .merge(rec[["geoid", "recommendation_status", "corridor",
                   "attractiveness_rank", "reason"]], on="geoid"))

# Fixed slot order, so colour follows the county rather than its position
# in the pick list.
order = sorted(picks)
color = {name: vt.SERIES[i] for i, name in enumerate(order)}

status_cols = st.columns(len(order))
for col, name in zip(status_cols, order):
    r = sel[sel["county_name"] == name].iloc[0]
    with col:
        st.markdown(f"**{r['short_name']}**")
        st.caption(f"Rank {int(r['attractiveness_rank'])} of 133  ·  "
                   f"{r['corridor']}")
        st.markdown(f"`{r['recommendation_status']}`")

comps = list(COMPONENT_LABELS)
fig = go.Figure()
for name in order:
    r = sel[sel["county_name"] == name].iloc[0]
    fig.add_bar(x=[COMPONENT_LABELS[c] for c in comps],
                y=[r[c] for c in comps], name=r["short_name"],
                marker=dict(color=color[name], cornerradius=4),
                hovertemplate="%{x}: %{y:.1f}<extra>" + r["short_name"] + "</extra>")
fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08,
                  title="Component scores, 0 to 100 within Virginia",
                  height=460, yaxis=dict(range=[0, 105]),
                  legend=dict(orientation="h", y=1.08, x=0))
st.plotly_chart(fig, use_container_width=True)

rows = {
    "Population, 2019-2023": ("total_population", "{:,.0f}"),
    "Population change": ("pop_growth_pct", "{:.1f}%"),
    "Median household income": ("median_hh_income", "${:,.0f}"),
    "Income change, nominal": ("mhi_growth_pct", "{:.1f}%"),
    "Income change, real": ("mhi_growth_real_pct", "{:.1f}%"),
    "Max interstate segment ADT": ("interstate_max_aadt", "{:,.0f}"),
    "Distance to an interstate": ("dist_interstate_mi", "{:.1f} mi"),
    "Nearest store, any status": ("dist_any_bucees_mi", "{:.1f} mi"),
    "Gas stations per 10k residents": ("gas_stations_per_10k", "{:.2f}"),
    "Food service establishments": ("food_service_estabs", "{:,.0f}"),
    "Population density per sq mi": ("pop_density_sqmi", "{:,.0f}"),
}
table = {"Metric": list(rows)}
for name in order:
    r = sel[sel["county_name"] == name].iloc[0]
    table[r["short_name"]] = [
        "not available" if pd.isna(r[col]) else fmt.format(r[col])
        for col, fmt in rows.values()]
st.dataframe(table, hide_index=True, use_container_width=True)

st.subheader("Why each is or is not a candidate")
for name in order:
    r = sel[sel["county_name"] == name].iloc[0]
    st.markdown(f"**{r['short_name']}** · {r['recommendation_status']}. {r['reason']}")

page_footer()
