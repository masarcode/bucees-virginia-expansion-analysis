"""Stage 5 - exploratory analysis.

Reads v_county_profile (+ spatial features), writes:
- outputs/tables/  : county_profile_full.csv + ranked top/bottom tables
- outputs/figures/ : bar/scatter/histogram charts (HTML + PNG)
- outputs/maps/    : county choropleths (HTML + PNG)

Chart styling follows scripts/utils/viz_theme.py (sequential single-hue
ramps for magnitude, diverging blue↔red for growth polarity, single-series
charts carry no legend).
"""

import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from scripts.utils.db import get_engine
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, FIGURES, MAPS, TABLES
from scripts.utils import validation
from scripts.utils import viz_theme as vt

log = get_logger("eda")
STAGE = "stage5_eda"


def load_profile() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM v_county_profile", get_engine())
    feats = pd.read_parquet(DATA_PROCESSED / "spatial_features.parquet")
    df = df.merge(feats, on="geoid", how="left")
    df["short_name"] = (df["county_name"]
                        .str.replace(" County", "", regex=False)
                        .str.replace(" city", " (city)", regex=False))
    return df


def county_geojson() -> dict:
    gdf = gpd.read_parquet(DATA_PROCESSED / "va_counties.geoparquet").to_crs("EPSG:4326")
    return json.loads(gdf[["geoid", "geometry"]].to_json())


def bar_top(df, col, title, unit, fname, n=15, fmt="{:,.0f}"):
    top = df.nlargest(n, col).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top[col], y=top["short_name"], orientation="h",
        marker=dict(color=vt.SERIES[0], cornerradius=4),
        text=[fmt.format(v) for v in top[col]],
        textposition="outside", textfont=dict(color=vt.INK_SECONDARY, size=11),
        hovertemplate="%{y}: %{x:,.0f}<extra></extra>"))
    fig.update_layout(title=title, xaxis_title=unit, yaxis_title=None,
                      showlegend=False, height=520,
                      margin=dict(l=170, r=70),
                      xaxis=dict(showgrid=True), yaxis=dict(showgrid=False))
    return vt.save_fig(fig, FIGURES / fname)


def choropleth(df, geojson, col, title, fname, colorscale=None, unit="",
               diverging=False, stores=None):
    kwargs = dict(
        geojson=geojson, locations=df["geoid"], featureidkey="properties.geoid",
        z=df[col], colorscale=colorscale or vt.SEQ_BLUE,
        marker_line_color="#ffffff", marker_line_width=0.5,
        colorbar=dict(title=unit, tickfont=dict(color=vt.INK_MUTED, size=11)),
        customdata=df["short_name"],
        hovertemplate="%{customdata}: %{z:,.1f}<extra></extra>")
    if diverging:
        bound = np.nanmax(np.abs(df[col]))
        kwargs.update(zmin=-bound, zmax=bound)
    fig = go.Figure(go.Choropleth(**kwargs))
    if stores is not None:
        # Keep the map framed on Virginia: show only stores inside the
        # display window (distant stores can't be the nearest one anyway).
        window = ((stores["longitude"].between(-85.5, -74.0))
                  & (stores["latitude"].between(35.0, 40.5)))
        stores = stores[window]
        open_s = stores[stores["status"] == "open"]
        plan_s = stores[stores["status"] != "open"]
        fig.add_scattergeo(
            lon=open_s["longitude"], lat=open_s["latitude"], mode="markers",
            marker=dict(size=11, color=vt.SERIES[1], symbol="star",
                        line=dict(width=1, color="#ffffff")),
            name="Buc-ee's (open)", text=open_s["city"], hoverinfo="text+name")
        fig.add_scattergeo(
            lon=plan_s["longitude"], lat=plan_s["latitude"], mode="markers",
            marker=dict(size=10, color=vt.SERIES[1], symbol="star-open",
                        line=dict(width=1.5, color=vt.SERIES[1])),
            name="Buc-ee's (planned)", text=plan_s["city"], hoverinfo="text+name")
        fig.update_layout(legend=dict(orientation="h", y=0.02, x=0.5,
                                      xanchor="center"))
        fig.update_geos(visible=False, bgcolor=vt.SURFACE,
                        lonaxis_range=[-85.0, -74.5], lataxis_range=[35.4, 40.2])
    else:
        fig.update_geos(fitbounds="locations", visible=False, bgcolor=vt.SURFACE)
    fig.update_layout(title=title, height=560,
                      margin=dict(l=10, r=10, t=60, b=10))
    return vt.save_fig(fig, MAPS / fname)


def main() -> int:
    for d in (FIGURES, MAPS, TABLES):
        d.mkdir(parents=True, exist_ok=True)

    df = load_profile()
    geojson = county_geojson()
    stores = pd.read_parquet(DATA_PROCESSED / "bucees_locations.parquet")
    written = []

    # ---------------- tables ----------------
    df.drop(columns=["short_name"]).to_csv(TABLES / "county_profile_full.csv", index=False)
    rank_specs = {
        "top15_population.csv": df.nlargest(15, "total_population")
            [["county_name", "total_population", "pop_density_sqmi"]],
        "top15_growth.csv": df.nlargest(15, "pop_growth_pct")
            [["county_name", "pop_growth_pct", "total_population", "mhi_growth_pct"]],
        "top15_income.csv": df.nlargest(15, "median_hh_income")
            [["county_name", "median_hh_income", "per_capita_income"]],
        "top15_interstate_aadt.csv": df.nlargest(15, "interstate_max_aadt")
            [["county_name", "interstate_max_aadt", "interstate_miles", "vmt_proxy"]],
        "thinnest15_fuel_retail.csv": df[df["total_population"] >= 20000]
            .nsmallest(15, "gas_stations_per_10k")
            [["county_name", "total_population", "gas_stations", "gas_stations_per_10k"]],
    }
    for fname, table in rank_specs.items():
        table.to_csv(TABLES / fname, index=False)

    # ---------------- charts ----------------
    written += bar_top(df, "total_population",
                       "Virginia's population concentrates in a handful of markets",
                       "Population (ACS 2019-2023)", "bar_population.html")
    written += bar_top(df, "interstate_max_aadt",
                       "Interstate traffic exposure: max AADT by county",
                       "Max interstate AADT (VDOT 2024, bidirectional)",
                       "bar_interstate_aadt.html")
    written += bar_top(df, "median_hh_income",
                       "Purchasing power: top median household incomes",
                       "Median household income ($, ACS 2019-2023)",
                       "bar_income.html", fmt="${:,.0f}")

    # Growth vs size scatter (single series; notable counties direct-labeled).
    fig = go.Figure(go.Scatter(
        x=df["total_population"], y=df["pop_growth_pct"], mode="markers",
        marker=dict(size=9, color=vt.SERIES[0], opacity=0.75,
                    line=dict(width=1, color="#ffffff")),
        customdata=df["short_name"],
        hovertemplate="%{customdata}<br>pop %{x:,.0f} | growth %{y:.1f}%<extra></extra>"))
    notable = (df[(df["pop_growth_pct"] > 8) & (df["total_population"] > 90000)]
               .sort_values("total_population"))
    for i, (_, r) in enumerate(notable.iterrows()):
        fig.add_annotation(x=np.log10(r["total_population"]), y=r["pop_growth_pct"],
                           text=r["short_name"], showarrow=False,
                           yshift=12 if i % 2 == 0 else -14,
                           font=dict(size=11, color=vt.INK_SECONDARY))
    fig.add_hline(y=0, line_color=vt.BASELINE, line_width=1)
    fig.update_xaxes(type="log", title="Population (log scale)")
    fig.update_yaxes(title="Population growth, 2014-18 → 2019-23 (%)")
    fig.update_layout(title="Where growth meets market size", showlegend=False,
                      height=560)
    written += vt.save_fig(fig, FIGURES / "scatter_growth_vs_size.html")

    # Competition: fuel retail density vs traffic exposure.
    sub = df[df["interstate_max_aadt"].notna()]
    fig = go.Figure(go.Scatter(
        x=sub["interstate_max_aadt"], y=sub["gas_stations_per_10k"],
        mode="markers",
        marker=dict(size=9, color=vt.SERIES[0], opacity=0.75,
                    line=dict(width=1, color="#ffffff")),
        customdata=sub["short_name"],
        hovertemplate="%{customdata}<br>AADT %{x:,.0f} | %{y:.2f} stations/10k<extra></extra>"))
    hot = sub[(sub["interstate_max_aadt"] > 120000) & (sub["gas_stations_per_10k"] < 2.2)]
    for _, r in hot.iterrows():
        fig.add_annotation(x=r["interstate_max_aadt"], y=r["gas_stations_per_10k"],
                           text=r["short_name"], showarrow=False, yshift=12,
                           font=dict(size=11, color=vt.INK_SECONDARY))
    fig.update_xaxes(title="Max interstate AADT (bidirectional)")
    fig.update_yaxes(title="Gas stations per 10k residents")
    fig.update_layout(
        title="High traffic, thin fuel retail - the opportunity quadrant",
        showlegend=False, height=560)
    written += vt.save_fig(fig, FIGURES / "scatter_traffic_vs_fuel.html")

    # Accessibility distribution.
    fig = go.Figure(go.Histogram(
        x=df["dist_interstate_mi"], nbinsx=24,
        marker=dict(color=vt.SERIES[0],
                    line=dict(width=2, color=vt.SURFACE)),
        hovertemplate="%{x} mi: %{y} counties<extra></extra>"))
    fig.update_xaxes(title="County centroid → nearest interstate (miles)")
    fig.update_yaxes(title="Counties")
    fig.update_layout(title="Most of Virginia sits close to an interstate - "
                            "but a long tail does not", showlegend=False,
                      height=460)
    written += vt.save_fig(fig, FIGURES / "hist_interstate_distance.html")

    # ---------------- maps ----------------
    written += choropleth(df, geojson, "total_population",
                          "Population by county (ACS 2019-2023)",
                          "map_population.html", unit="people")
    written += choropleth(df, geojson, "pop_growth_pct",
                          "Population growth, 2014-18 → 2019-23 (%)",
                          "map_growth.html", colorscale=vt.DIVERGING,
                          diverging=True, unit="%")
    written += choropleth(df, geojson, "median_hh_income",
                          "Median household income (ACS 2019-2023)",
                          "map_income.html", unit="$")
    written += choropleth(df, geojson, "max_aadt",
                          "Peak traffic volume by county (VDOT 2024)",
                          "map_max_aadt.html", unit="AADT")
    written += choropleth(df, geojson, "dist_interstate_mi",
                          "Interstate accessibility (centroid distance, miles)",
                          "map_dist_interstate.html", unit="mi")
    written += choropleth(df, geojson, "dist_any_bucees_mi",
                          "Distance to nearest existing or announced Buc-ee's",
                          "map_dist_bucees.html", unit="mi", stores=stores)

    # ---------------- validations ----------------
    ok = validation.record(STAGE, "eda_tables_written",
                           all((TABLES / f).exists() for f in rank_specs),
                           f"{len(rank_specs) + 1} tables")
    n_html = len([p for p in written if str(p).endswith(".html")])
    ok &= validation.record(STAGE, "eda_figures_written", n_html == 12,
                            f"{n_html} HTML artifacts (6 charts + 6 maps)")
    empty = [str(p) for p in written if p.stat().st_size == 0]
    ok &= validation.record(STAGE, "eda_no_empty_outputs", not empty,
                            f"empty: {empty}")
    log.info("EDA complete: %d files", len(written))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
