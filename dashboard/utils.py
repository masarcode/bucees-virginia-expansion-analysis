"""Shared loaders + helpers for the Streamlit dashboard."""

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utils.config import load_config          # noqa: E402
from scripts.utils.db import get_engine               # noqa: E402
from scripts.utils import viz_theme as vt             # noqa: E402

ACCENT = vt.SERIES[0]
STORE_COLOR = vt.SERIES[1]

SCENARIO_LABELS = {
    "balanced": "Balanced",
    "highway": "Highway-first",
    "growth": "Growth-chasing",
    "affluent": "Affluent markets",
    "underserved": "Underserved markets",
}

COMPONENT_LABELS = {
    "market_demand": "Market demand",
    "growth": "Growth",
    "purchasing_power": "Purchasing power",
    "highway_opportunity": "Highway opportunity",
    "accessibility": "Accessibility",
    "commercial_activity": "Commercial activity",
    "competition": "Low competition",
    "overlap_risk": "Low overlap risk",
}


@st.cache_data
def config():
    return load_config()


@st.cache_data
def county_profile() -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM v_county_profile", get_engine())
    feats = pd.read_parquet(PROJECT_ROOT / "data/processed/spatial_features.parquet")
    df = df.merge(feats, on="geoid", how="left")
    df["short_name"] = (df["county_name"]
                        .str.replace(" County", "", regex=False)
                        .str.replace(" city", " (city)", regex=False))
    return df


@st.cache_data
def market_scores() -> pd.DataFrame:
    return pd.read_parquet(PROJECT_ROOT / "data/processed/market_scores.parquet")


@st.cache_data
def scenario_rankings() -> pd.DataFrame:
    return pd.read_parquet(PROJECT_ROOT / "data/processed/scenario_rankings.parquet")


@st.cache_data
def bucees_stores() -> pd.DataFrame:
    return pd.read_parquet(PROJECT_ROOT / "data/processed/bucees_locations.parquet")


@st.cache_data
def county_geojson() -> dict:
    gdf = gpd.read_parquet(
        PROJECT_ROOT / "data/processed/va_counties.geoparquet").to_crs("EPSG:4326")
    return json.loads(gdf[["geoid", "geometry"]].to_json())


@st.cache_data
def validation_summary() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT stage, check_name, status, details, last_run "
        "FROM v_validation_latest ORDER BY stage, check_name", get_engine())


@st.cache_data
def recommendations() -> pd.DataFrame:
    df = pd.read_parquet(PROJECT_ROOT / "data/processed/recommendations.parquet")
    df["short_name"] = (df["county_name"]
                        .str.replace(" County", "", regex=False)
                        .str.replace(" city", " (city)", regex=False))
    return df


@st.cache_data
def corridors() -> pd.DataFrame:
    return pd.read_csv(PROJECT_ROOT / "outputs/tables/corridor_recommendations.csv")


@st.cache_data
def holdout() -> pd.DataFrame:
    return pd.read_csv(PROJECT_ROOT / "outputs/tables/holdout_check.csv")


# Recommendation statuses, ordered strongest to weakest, with the colour
# used for map and table treatment.
STATUS_ORDER = [
    "Priority candidate",
    "Secondary candidate",
    "Watchlist",
    "Reference case",
    "Overlap constrained",
    "Feasibility constrained",
    "Traffic data unavailable",
    "Ineligible: no interstate access",
]

STATUS_HELP = {
    "Priority candidate": "Clears every screen, ranks in the top 25, and holds that in at least 4 of 5 scenarios.",
    "Secondary candidate": "Clears every screen and ranks in the top 45.",
    "Watchlist": "Clears every screen but ranks outside the cutoffs.",
    "Reference case": "Already has an open, announced or locally approved store.",
    "Overlap constrained": "Within 30 miles of an existing or planned store.",
    "Feasibility constrained": "Too dense for an interchange-scale site of roughly 30 acres.",
    "Traffic data unavailable": "An interstate crosses it, but the VDOT extract holds no mainline record.",
    "Ineligible: no interstate access": "No interstate crosses the jurisdiction.",
}

SOURCE_FOOTER = (
    "**Sources:** U.S. Census Bureau ACS 5-year estimates, 2014-2018 and "
    "2019-2023; County Business Patterns 2023; VDOT Traffic Volume 2024; "
    "TIGER/Line 2023; BLS CPI-U; official Buc-ee's, local government and "
    "cited news sources for store status. Access dates and URLs are in the "
    "source inventory and citations file."
)

DISCLAIMER_FOOTER = (
    "Portfolio analysis. Not affiliated with Buc-ee's Ltd. County-level "
    "screening only. Not a parcel-level site recommendation."
)


def page_footer() -> None:
    """Source and disclaimer footer, shown on every page."""
    st.divider()
    st.caption(SOURCE_FOOTER)
    st.caption(DISCLAIMER_FOOTER)


def weighted_scores(weights: dict) -> pd.DataFrame:
    """Score every county under an arbitrary weight vector (sums to 1)."""
    s = market_scores()
    comps = list(weights)
    out = s[["geoid"]].copy()
    out["weighted_score"] = sum(weights[c] * s[c] for c in comps)
    out = out.sort_values(["weighted_score", "geoid"],
                          ascending=[False, True]).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out
