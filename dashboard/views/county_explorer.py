"""County deep dive: component scores, profile, scenario performance."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (ACCENT, COMPONENT_LABELS, SCENARIO_LABELS, county_profile,
                   market_scores, page_footer, recommendations,
                   scenario_rankings, vt)

st.title("County Explorer")

profile = county_profile()
scores = market_scores()
ranks = scenario_rankings()
rec = recommendations()

county = st.selectbox("County or independent city",
                      profile.sort_values("county_name")["county_name"])
row = profile[profile["county_name"] == county].iloc[0]
srow = scores[scores["geoid"] == row["geoid"]].iloc[0]
rrow = rec[rec["geoid"] == row["geoid"]].iloc[0]

status = rrow["recommendation_status"]
banner = st.success if status in ("Priority candidate", "Secondary candidate") else (
    st.info if status in ("Watchlist", "Reference case") else st.warning)
banner(f"**{status}.** {rrow['reason']}")
st.caption(f"Corridor: {rrow['corridor']}  ·  Market attractiveness rank "
           f"{int(rrow['attractiveness_rank'])} of 133 "
           f"(score {rrow['weighted_score']:.1f})")

left, right = st.columns([1.2, 1])

with left:
    comps = list(COMPONENT_LABELS)
    vals = [srow[c] for c in comps]
    fig = go.Figure(go.Bar(
        x=vals, y=[COMPONENT_LABELS[c] for c in comps], orientation="h",
        marker=dict(color=ACCENT, cornerradius=4),
        text=[f"{v:.1f}" for v in vals], textposition="outside",
        textfont=dict(color=vt.INK_SECONDARY),
        hovertemplate="%{y}: %{x:.1f} of 100<extra></extra>"))
    fig.update_layout(title=f"Component scores, {county}",
                      xaxis=dict(range=[0, 112], title="score, 0 to 100"),
                      yaxis=dict(autorange="reversed"), showlegend=False,
                      height=430, margin=dict(l=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Scores are relative to other Virginia counties, not absolute.")

    # Percentile rather than raw rank, so a longer bar always means better.
    rsub = (ranks[ranks["geoid"] == row["geoid"]]
            .assign(label=lambda d: d["scenario"].map(SCENARIO_LABELS),
                    percentile=lambda d: 100 * (133 - d["rank"]) / 132))
    fig2 = go.Figure(go.Bar(
        x=rsub["percentile"], y=rsub["label"], orientation="h",
        marker=dict(color=ACCENT, cornerradius=4),
        customdata=rsub["rank"],
        text=[f"rank {int(r)}" for r in rsub["rank"]], textposition="outside",
        textfont=dict(color=vt.INK_SECONDARY),
        hovertemplate="%{y}: rank %{customdata} of 133 "
                      "(%{x:.0f}th percentile)<extra></extra>"))
    fig2.update_layout(
        title="Standing by scenario, longer is stronger",
        xaxis=dict(range=[0, 118], title="percentile within Virginia"),
        showlegend=False, height=330, margin=dict(l=10))
    st.plotly_chart(fig2, use_container_width=True)

with right:
    st.subheader("Profile")

    def fmt(value, kind):
        if pd.isna(value):
            return "not available"
        if kind == "int":
            return f"{value:,.0f}"
        if kind == "pct":
            return f"{value:.1f}%"
        if kind == "usd":
            return f"${value:,.0f}"
        if kind == "mi":
            return f"{value:.1f} mi"
        return f"{value:,.1f}"

    rows = [
        ("Corridor", rrow["corridor"]),
        ("Population, 2019-2023", fmt(row["total_population"], "int")),
        ("Population change", fmt(row["pop_growth_pct"], "pct")),
        ("Median household income", fmt(row["median_hh_income"], "usd")),
        ("Income change, nominal", fmt(row["mhi_growth_pct"], "pct")),
        ("Income change, real", fmt(row["mhi_growth_real_pct"], "pct")),
        ("Max interstate segment ADT", fmt(row["interstate_max_aadt"], "int")),
        ("Distance to an interstate", fmt(row["dist_interstate_mi"], "mi")),
        ("Nearest store, any status", fmt(row["dist_any_bucees_mi"], "mi")),
        ("Nearest open store", fmt(row["dist_open_bucees_mi"], "mi")),
        ("Gas stations", fmt(row["gas_stations"], "int")),
        ("Gas stations per 10k residents", fmt(row["gas_stations_per_10k"], "num")),
        ("Food service establishments", fmt(row["food_service_estabs"], "int")),
        ("Population density per sq mi", fmt(row["pop_density_sqmi"], "int")),
        ("Land area", f"{row['aland_sqmi']:,.0f} sq mi"),
    ]
    for label, value in rows:
        a, b = st.columns([1.25, 1])
        a.markdown(f"**{label}**")
        b.markdown(str(value))

    st.caption(
        "Population and income are ACS 5-year period estimates, so changes "
        "compare two periods rather than measuring an annual rate. Real income "
        "change restates 2014-2018 dollars in 2023 dollars using CPI-U. "
        "Interstate ADT is the highest single mainline segment reading here, "
        "not average traffic across the jurisdiction."
    )

page_footer()
