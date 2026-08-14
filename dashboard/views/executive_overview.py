"""Executive Overview.

Run from the project root: streamlit run dashboard/app.py
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (SCENARIO_LABELS, STATUS_HELP, STORE_COLOR, bucees_stores,
                   config, corridors, county_geojson, county_profile,
                   page_footer, recommendations, scenario_rankings, vt,
                   weighted_scores)

st.title("Buc-ee's Virginia Expansion Analysis")
st.caption(
    "Where should Buc-ee's look next in Virginia? All 133 county-equivalents "
    "screened on public data, then filtered by development status, trade-area "
    "overlap, interstate access and site feasibility."
)

profile = county_profile()
rec = recommendations()
corr = corridors()
cfg = config()
scenarios = cfg["scoring"]["scenarios"]

st.info(
    "**Highest score does not automatically mean best site.** Final "
    "recommendations also consider existing and planned stores, likely "
    "overlap, development status, and limitations of county-level public data."
)

# ---------------- headline numbers ----------------
priority = rec[rec["recommendation_status"] == "Priority candidate"].sort_values(
    "attractiveness_rank")
top_priority = priority.iloc[0]
top_raw = rec.sort_values("attractiveness_rank").iloc[0]
va_stores = bucees_stores().query("state == 'VA'")
n_open = int((va_stores["status"] == "open").sum())
n_reference = int((rec["recommendation_status"] == "Reference case").sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Top actionable recommendation", top_priority["short_name"],
          f"rank {int(top_priority['attractiveness_rank'])} · "
          f"{top_priority['corridor']}")
k2.metric("Top raw attractiveness score", top_raw["short_name"],
          f"score {top_raw['weighted_score']:.1f} · "
          f"{top_raw['recommendation_status'].lower()}")
k3.metric("Eligible candidates", f"{len(priority)} priority",
          f"{int((rec['recommendation_status'] == 'Secondary candidate').sum())} secondary")
k4.metric("Virginia sites today", f"{n_open} open",
          f"{n_reference - n_open} announced or approved")

st.markdown(
    f"**{top_raw['short_name']} holds the highest model score in Virginia and "
    f"is not a candidate.** {top_raw['reason']}"
)

# ---------------- scenario control ----------------
left, right = st.columns([2.2, 1])
with left:
    scenario = st.radio("Strategy scenario", options=list(scenarios),
                        format_func=lambda s: SCENARIO_LABELS.get(s, s),
                        horizontal=True)
with right:
    with st.expander("Customize weights"):
        st.caption("Sliders are re-normalized to sum to 1.")
        raw = {c: st.slider(c.replace("_", " "), 0.0, 1.0, float(w), 0.05,
                            key=f"w_{c}")
               for c, w in scenarios[scenario].items()}
        total = sum(raw.values()) or 1.0
        custom = {c: v / total for c, v in raw.items()}
        use_custom = st.checkbox("Use custom weights", value=False)

weights = custom if use_custom else scenarios[scenario]
ranked = weighted_scores(weights).merge(
    rec[["geoid", "county_name", "short_name", "corridor",
         "recommendation_status", "reason", "store_status", "overlap_flag",
         "dist_any_bucees_mi"]], on="geoid")
ranked = ranked.merge(profile[["geoid", "total_population", "pop_growth_pct"]],
                      on="geoid")

st.caption(
    "Scores respond to the scenario. Recommendation status does not: it comes "
    "from the eligibility screen, which is independent of weighting."
)

# ---------------- map + table ----------------
map_col, table_col = st.columns([1.55, 1])

with map_col:
    fig = go.Figure(go.Choropleth(
        geojson=county_geojson(), locations=ranked["geoid"],
        featureidkey="properties.geoid", z=ranked["weighted_score"],
        colorscale=vt.SEQ_BLUE, marker_line_color="#ffffff",
        marker_line_width=0.5,
        colorbar=dict(title="score", tickfont=dict(color=vt.INK_MUTED)),
        customdata=ranked[["short_name", "rank", "recommendation_status"]],
        hovertemplate="%{customdata[0]}<br>Attractiveness rank "
                      "%{customdata[1]} · score %{z:.1f}"
                      "<br>%{customdata[2]}<extra></extra>"))

    # Virginia sites only, one marker style per development status.
    marker_spec = {
        "open": ("star", "Open"),
        "locally approved": ("diamond", "Locally approved"),
        "announced": ("circle-open", "Announced"),
    }
    va = va_stores.copy()
    va["dev_status"] = va["status"]
    va.loc[va["city"] == "Stafford", "dev_status"] = "locally approved"
    for key, (symbol, label) in marker_spec.items():
        sub = va[va["dev_status"] == key]
        if sub.empty:
            continue
        fig.add_scattergeo(
            lon=sub["longitude"], lat=sub["latitude"], mode="markers",
            marker=dict(size=13, color=STORE_COLOR, symbol=symbol,
                        line=dict(width=1.5, color="#ffffff")),
            name=f"{label} ({len(sub)})", text=sub["city"],
            hovertemplate="%{text}<br>" + label + "<extra></extra>")

    fig.update_geos(visible=False, bgcolor=vt.SURFACE,
                    lonaxis_range=[-84.6, -74.6], lataxis_range=[35.6, 40.1])
    fig.update_layout(
        title=f"Market attractiveness score, {SCENARIO_LABELS.get(scenario, scenario)}"
              + (" with custom weights" if use_custom else ""),
        height=520, margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(orientation="h", y=0.0, x=0.5, xanchor="center",
                    title="Virginia sites"))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Shading is the model score. Markers are the three Virginia sites. "
        "Out-of-state stores stay in the distance calculations but are not "
        "drawn here."
    )

with table_col:
    st.subheader("Highest scoring counties")
    show = ranked.head(15).copy()
    show["note"] = show.apply(
        lambda r: r["overlap_flag"] if pd.notna(r.get("overlap_flag"))
        else (f"{r['store_status']} store in county"
              if pd.notna(r["store_status"]) else
              f"{r['dist_any_bucees_mi']:.1f} mi to nearest store"), axis=1)
    table = show[["rank", "short_name", "weighted_score", "corridor",
                  "recommendation_status", "note"]].rename(columns={
        "rank": "Rank", "short_name": "County", "weighted_score": "Score",
        "corridor": "Corridor", "recommendation_status": "Status",
        "note": "Development or overlap note"})
    st.dataframe(
        table, hide_index=True, height=520,
        column_config={
            "Score": st.column_config.ProgressColumn(
                format="%.1f", min_value=0, max_value=100),
            "Status": st.column_config.TextColumn(
                help="Set by the eligibility screen, not by the score."),
        })

# ---------------- recommendations ----------------
st.subheader("Where the screen points")
c1, c2 = st.columns([1, 1])

with c1:
    st.markdown("**Priority candidates**")
    p = priority[["attractiveness_rank", "short_name", "corridor",
                  "dist_any_bucees_mi", "interstate_max_aadt"]].rename(columns={
        "attractiveness_rank": "Rank", "short_name": "County",
        "corridor": "Corridor", "dist_any_bucees_mi": "Nearest store (mi)",
        "interstate_max_aadt": "Max segment ADT"})
    st.dataframe(p, hide_index=True, column_config={
        "Nearest store (mi)": st.column_config.NumberColumn(format="%.1f"),
        "Max segment ADT": st.column_config.NumberColumn(format="localized"),
    })

with c2:
    st.markdown("**Candidate corridors**")
    cc = corr[corr["corridor_tier"] == "Candidate corridor"][
        ["corridor", "best_eligible_rank", "eligible_counties", "population",
         "eligible_min_dist_bucees_mi"]].rename(columns={
        "corridor": "Corridor", "best_eligible_rank": "Best rank",
        "eligible_counties": "Eligible", "population": "Population",
        "eligible_min_dist_bucees_mi": "Nearest store (mi)"})
    st.dataframe(cc, hide_index=True, column_config={
        "Best rank": st.column_config.NumberColumn(format="%d"),
        "Population": st.column_config.NumberColumn(format="localized"),
        "Nearest store (mi)": st.column_config.NumberColumn(format="%.1f"),
    })

with st.expander("What each status means"):
    st.dataframe(
        pd.DataFrame({"Status": list(STATUS_HELP),
                      "Meaning": list(STATUS_HELP.values()),
                      "Counties": [int((rec["recommendation_status"] == s).sum())
                                   for s in STATUS_HELP]}),
        hide_index=True)
    st.caption("Thresholds are analyst assumptions, recorded as A14 to A18 in "
               "docs/assumptions.md.")

page_footer()
