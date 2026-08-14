"""Stage 8 - regional market analysis.

Regional definition: VDOT construction districts (official, highway-
oriented, complete state coverage). Each county's district is derived from
its own VDOT segments (mode of FROM_DISTRICT after the same jurisdiction
mapping used in cleaning), so the assignment is data-driven and
reproducible.

Districts are an intermediate screening geography, not retail trade areas
and not the final recommendation, which is made at corridor level in
scripts/analyze/recommendations.py. Per district this aggregates market
fundamentals and the balanced-scenario standing of its counties, bands the
districts by score, and writes:
- geography.region (DB + geography.parquet updated)
- outputs/tables/regional_summary.csv
- outputs/reports/vdot_district_screening.md (screening view, not a recommendation)
- outputs/maps/map_regions.html/png
"""

import json
import sys

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text

from scripts.clean.clean_vdot import resolve_geoids
from scripts.utils.db import get_engine
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW, MAPS, REPORTS, TABLES
from scripts.utils import validation
from scripts.utils import viz_theme as vt

log = get_logger("regions")
STAGE = "stage8_regions"


def county_districts() -> pd.Series:
    """geoid -> VDOT district, by mode of that county's segment records."""
    pages = sorted((DATA_RAW / "vdot").glob("page_*.json"))
    df = pd.concat(
        [pd.DataFrame([f["attributes"] for f in json.loads(p.read_text())["features"]])
         for p in pages], ignore_index=True)[
        ["OBJECTID", "FROM_JURISDICTION", "FROM_DISTRICT"]]
    df["geoid"] = resolve_geoids(df)
    df = df.dropna(subset=["geoid", "FROM_DISTRICT"])
    return df.groupby("geoid")["FROM_DISTRICT"].agg(lambda s: s.mode().iloc[0])


def main() -> int:
    engine = get_engine()
    districts = county_districts()

    profile = pd.read_sql("SELECT * FROM v_county_profile", engine)
    feats = pd.read_parquet(DATA_PROCESSED / "spatial_features.parquet")
    balanced = pd.read_sql(
        "SELECT geoid, weighted_score, rank FROM scenario_rankings "
        "WHERE scenario = 'balanced'", engine)
    df = (profile.merge(feats, on="geoid").merge(balanced, on="geoid"))
    df["region"] = df["geoid"].map(districts)

    ok = validation.record(STAGE, "regions_all_counties_assigned",
                           df["region"].notna().all(),
                           f"unassigned: {df.loc[df['region'].isna(), 'county_name'].tolist()}")
    n_regions = df["region"].nunique()
    ok &= validation.record(STAGE, "regions_count_plausible", 7 <= n_regions <= 10,
                            f"{n_regions} districts: {sorted(df['region'].unique())}")

    # Persist region on geography (DB + parquet).
    with engine.begin() as conn:
        for geoid, region in df.set_index("geoid")["region"].items():
            conn.execute(text("UPDATE geography SET region = :r WHERE geoid = :g"),
                         {"r": region, "g": geoid})
        n_set = conn.execute(text(
            "SELECT COUNT(*) FROM geography WHERE region IS NOT NULL")).scalar()
        ok &= validation.record(STAGE, "regions_db_updated", n_set == 133,
                                f"{n_set} rows", conn=conn)
    geo_pq = pd.read_parquet(DATA_PROCESSED / "geography.parquet")
    geo_pq["region"] = geo_pq["geoid"].map(districts)
    geo_pq.to_parquet(DATA_PROCESSED / "geography.parquet", index=False)

    # ---------------- regional aggregation ----------------
    def agg(group: pd.DataFrame) -> pd.Series:
        top3 = group.nsmallest(3, "rank")
        return pd.Series({
            "counties": len(group),
            "population": group["total_population"].sum(),
            "pop_growth_pct": 100 * (group["total_population"].sum()
                / (group["total_population"].sum()
                   / (1 + group["pop_growth_pct"] / 100).mean()) - 1),
            "max_interstate_aadt": group["interstate_max_aadt"].max(),
            "best_balanced_rank": group["rank"].min(),
            "counties_in_top15": int((group["rank"] <= 15).sum()),
            "counties_in_top25": int((group["rank"] <= 25).sum()),
            "mean_top3_score": top3["weighted_score"].mean(),
            "min_dist_any_bucees_mi": group["dist_any_bucees_mi"].min(),
            "top_counties": ", ".join(
                top3.sort_values("rank")["county_name"].str.replace(
                    " County", "", regex=False)),
        })

    regional = (df.groupby("region").apply(agg, include_groups=False)
                .sort_values("mean_top3_score", ascending=False).reset_index())

    # Simple population-weighted growth (replace the convoluted formula).
    wg = (df.assign(w=df["total_population"] * df["pop_growth_pct"])
          .groupby("region").apply(
              lambda g: g["w"].sum() / g["total_population"].sum(),
              include_groups=False))
    regional["pop_growth_pct"] = regional["region"].map(wg).round(2)
    regional.to_csv(TABLES / "regional_summary.csv", index=False)

    # ---------------- classification ----------------
    # Bands describe score standing only. They are not recommendations:
    # a district can lead here while containing no county that could host
    # a store. The recommendation lives in scripts/analyze/recommendations.py.
    regional["tier"] = "lower"
    regional.loc[regional.index[:2], "tier"] = "highest"
    regional.loc[regional.index[2:4], "tier"] = "middle"
    ok &= validation.record(
        STAGE, "regions_tiers_assigned",
        set(regional["tier"]) == {"highest", "middle", "lower"},
        regional[["region", "tier"]].to_string(index=False).replace("\n", " | "))

    # ---------------- narrative report ----------------
    lines = [
        "# VDOT District Screening",
        "",
        "**These are administrative highway districts, not retail trade areas,**",
        "and this file is a screening view rather than a recommendation. VDOT",
        "construction districts exist to organise road maintenance. They are used",
        "here only as an intermediate way to group counties geographically.",
        "",
        "The actual recommendation is made at corridor level and accounts for",
        "which markets are already taken. See",
        "[corridor_recommendations.md](corridor_recommendations.md).",
        "",
        "Districts below are ordered by the mean balanced score of their top three",
        "counties. That ordering ignores whether those counties could host a store,",
        "which is exactly why it is not the answer: the Northern Virginia district",
        "leads on score and contains no eligible site. County-level detail is in",
        "outputs/tables/regional_summary.csv.",
        "",
    ]
    tier_titles = {"highest": "## Highest scoring districts",
                   "middle": "## Middle band",
                   "lower": "## Lower band"}
    for tier in ["highest", "middle", "lower"]:
        lines.append(tier_titles[tier])
        for _, r in regional[regional["tier"] == tier].iterrows():
            lines += [
                f"### {r['region']} district",
                f"- Leading counties (balanced scenario): {r['top_counties']}",
                f"- Mean top-3 balanced score: {r['mean_top3_score']:.1f}; "
                f"best county rank: {int(r['best_balanced_rank'])}; "
                f"{r['counties_in_top15']} county(ies) in statewide top 15",
                f"- Population {r['population']:,.0f}; weighted growth "
                f"{r['pop_growth_pct']:.1f}%; max interstate AADT "
                f"{r['max_interstate_aadt']:,.0f}"
                if pd.notna(r["max_interstate_aadt"]) else
                f"- Population {r['population']:,.0f}; weighted growth "
                f"{r['pop_growth_pct']:.1f}%; no interstate mainline",
                f"- Nearest existing/announced Buc-ee's: "
                f"{r['min_dist_any_bucees_mi']:.0f} mi from closest county centroid",
                "",
            ]
    lines += [
        "## Why this is not the recommendation",
        "",
        "- District score bands ignore development status. A district can lead "
        "here while every strong county in it already has a store or could not "
        "host one.",
        "- District names describe road administration, not markets. The "
        "Staunton district runs from Winchester to Augusta County, so Frederick "
        "County's market is labelled Northern I-81 / Winchester in the corridor "
        "view.",
        "- A store near a district edge draws customers across the boundary, "
        "which district totals cannot represent.",
        "- Every scoring-model limitation still applies. See "
        "docs/assumptions.md and limitations_report.md.",
    ]
    (REPORTS / "vdot_district_screening.md").write_text("\n".join(lines))

    # ---------------- region map ----------------
    gdf = gpd.read_parquet(DATA_PROCESSED / "va_counties.geoparquet").to_crs("EPSG:4326")
    gdf["region"] = gdf["geoid"].map(districts)
    geojson = json.loads(gdf[["geoid", "geometry"]].to_json())
    regions_sorted = sorted(gdf["region"].unique())
    # 9 regions vs 8 categorical slots: the 9th takes neutral gray rather
    # than cycling a hue; region names are also direct-labeled on the map
    # so identity never depends on color alone.
    palette = vt.SERIES + ["#898781"]
    color_by_region = {r: palette[i] for i, r in enumerate(regions_sorted)}
    fig = go.Figure()
    for r in regions_sorted:
        sub = gdf[gdf["region"] == r]
        fig.add_choropleth(
            geojson=geojson, locations=sub["geoid"],
            featureidkey="properties.geoid", z=[1] * len(sub),
            colorscale=[[0, color_by_region[r]], [1, color_by_region[r]]],
            showscale=False, marker_line_color="#ffffff",
            marker_line_width=0.6, name=r, showlegend=True,
            customdata=sub["county_name"],
            hovertemplate="%{customdata}<br>" + r + "<extra></extra>")
    label_pts = (gdf.to_crs("EPSG:26918").dissolve("region").representative_point()
                 .to_crs("EPSG:4326"))
    fig.add_scattergeo(
        lon=label_pts.x, lat=label_pts.y, mode="text",
        text=list(label_pts.index), showlegend=False, hoverinfo="skip",
        textfont=dict(size=11, color=vt.INK,
                      family=vt.FONT, weight=600))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor=vt.SURFACE)
    fig.update_layout(title="Regional markets (VDOT construction districts)",
                      height=560, margin=dict(l=10, r=10, t=60, b=10),
                      legend=dict(orientation="h", y=0.0, x=0.5, xanchor="center"))
    vt.save_fig(fig, MAPS / "map_regions.html")

    log.info("regional summary:\n%s",
             regional[["region", "tier", "mean_top3_score", "counties_in_top15",
                       "top_counties"]].to_string(index=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
