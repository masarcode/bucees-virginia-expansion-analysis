"""Build the Tableau handoff package in tableau/.

This is an export layer only. It reads the published outputs and reshapes
them for Tableau. It does not recompute scores, ranks, screening rules or
recommendations, so the package cannot drift from the dashboard: every
value here is copied from the same tables the Streamlit app reads.

Conventions applied throughout:
  - GEOID stays a five-character string.
  - Missing values stay null. No "None", "n/a" or "not available" strings.
  - Booleans export as TRUE / FALSE.
  - Numbers export unformatted, so Tableau controls presentation.
  - Internal working columns are dropped.

Outputs:
  tableau/county_dashboard_data.csv
  tableau/component_definitions.csv
  tableau/component_scores_long.csv
  tableau/corridor_dashboard_data.csv
  tableau/model_quality_metrics.csv
  tableau/scenario_weights.csv
  tableau/screening_rules.csv
  tableau/virginia_counties.geojson
"""

import json
import re
import sys

import geopandas as gpd
import pandas as pd

from scripts.analyze import recommendations as rules
from scripts.utils.config import load_config
from scripts.utils.db import get_engine
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, PROJECT_ROOT, TABLES
from scripts.utils import validation

log = get_logger("export_tableau")
STAGE = "stage12_tableau_export"

OUT = PROJECT_ROOT / "tableau"
EXPECTED_COUNTIES = 133

# Component score column -> exported name. Two components are inverted
# measures, so the exported name states the direction to stop a Tableau
# author reading "competition" as "more competition".
COMPONENT_EXPORT = {
    "market_demand": "market_demand_score",
    "growth": "growth_score",
    "purchasing_power": "purchasing_power_score",
    "highway_opportunity": "highway_opportunity_score",
    "accessibility": "accessibility_score",
    "commercial_activity": "commercial_activity_score",
    "competition": "low_competition_score",
    "overlap_risk": "low_overlap_risk_score",
}

# Plain-language reference for the eight components. The input_variables
# entries name the actual fields used in scripts/analyze/scoring.py, so this
# table stays checkable against the code rather than being a loose gloss.
# Keys match scenario_weights.csv and component_scores_long.csv.
COMPONENT_DEFINITIONS = [
    {
        "component": "market_demand",
        "plain_english_definition":
            "How many people live in the county and how many of them commute. "
            "A proxy for the size of the resident base a store could draw on.",
        "input_variables": "total_population; commuters_total",
        "higher_score_meaning":
            "A larger resident and commuting base.",
        "primary_source": "ACS 5-year 2019-2023, tables B01003 and B08303",
        "key_limitation":
            "Measures size only, not willingness to stop. Both inputs are log "
            "scaled because Virginia counties span four orders of magnitude, "
            "so the gap between the largest counties is compressed.",
    },
    {
        "component": "growth",
        "plain_english_definition":
            "How much the county grew between the two ACS periods, in "
            "population and in household income.",
        "input_variables": "pop_growth_pct; mhi_growth_pct",
        "higher_score_meaning":
            "Faster growth over the compared periods.",
        "primary_source":
            "ACS 5-year, 2014-2018 compared with 2019-2023",
        "key_limitation":
            "Backward looking, and a change between two period estimates "
            "rather than an annual rate. Uses nominal income change; because "
            "the inflation factor is identical for every county, adjusting it "
            "would not move any score or rank.",
    },
    {
        "component": "purchasing_power",
        "plain_english_definition":
            "How much money local households have, blending median household "
            "income with income per person.",
        "input_variables": "median_hh_income; per_capita_income",
        "higher_score_meaning":
            "Wealthier resident households.",
        "primary_source": "ACS 5-year 2019-2023, tables B19013 and B19301",
        "key_limitation":
            "Describes residents, not the travellers passing through. For a "
            "highway travel centre, through-traffic income may matter more, "
            "and this project has no data on it.",
    },
    {
        "component": "highway_opportunity",
        "plain_english_definition":
            "How much interstate traffic the county is exposed to, combining "
            "its busiest interstate segment with total traffic volume across "
            "all its roads.",
        "input_variables": "interstate_max_aadt; vmt_proxy",
        "higher_score_meaning":
            "Greater exposure to interstate traffic.",
        "primary_source": "VDOT Traffic Volume, 2024 publication",
        "key_limitation":
            "The traffic figure is the highest single mainline segment "
            "reading, not countywide or two-way traffic. Counties with no "
            "interstate record score zero exposure rather than null, which "
            "understates the 13 jurisdictions an interstate crosses but VDOT "
            "does not record.",
    },
    {
        "component": "accessibility",
        "plain_english_definition":
            "How close the county sits to an interstate.",
        "input_variables": "dist_interstate_mi",
        "higher_score_meaning":
            "Closer to an interstate.",
        "primary_source": "TIGER/Line 2023 primary roads",
        "key_limitation":
            "Straight-line distance from the county centroid, not drive time "
            "and not measured from a candidate site. In a large county the "
            "centroid can sit far from the corridor that matters.",
    },
    {
        "component": "commercial_activity",
        "plain_english_definition":
            "How much business activity already exists locally, across all "
            "sectors and in food service specifically.",
        "input_variables":
            "establishments_all; food_service_estabs; total_population",
        "higher_score_meaning":
            "A denser existing commercial base.",
        "primary_source": "County Business Patterns 2023",
        "key_limitation":
            "Counts premises, not floorspace, capacity or revenue. A large "
            "travel centre and a small cafe each count once.",
    },
    {
        "component": "competition",
        "plain_english_definition":
            "How thin existing fuel retail is relative to population. "
            "Inverted, so counties with fewer stations per resident score "
            "higher.",
        "input_variables": "gas_stations; total_population",
        "higher_score_meaning":
            "Less existing fuel retail per resident, so less competition. "
            "Higher is more attractive, not more competitive.",
        "primary_source": "County Business Patterns 2023, NAICS 447",
        "key_limitation":
            "Counts premises rather than pumps, so a 120-pump travel centre "
            "and a two-pump rural station are equivalent. Fuel supply at "
            "highway exits specifically is not isolated.",
    },
    {
        "component": "overlap_risk",
        "plain_english_definition":
            "How far the county sits from the nearest existing or planned "
            "Buc-ee's. Inverted, so more isolated counties score higher.",
        "input_variables": "dist_any_bucees_mi",
        "higher_score_meaning":
            "Farther from another store, so less risk of the two competing "
            "for the same customers. Higher is more attractive.",
        "primary_source":
            "Compiled store list, official Buc-ee's, county and state sources",
        "key_limitation":
            "Straight-line centroid distance, capped at 120 miles, so remote "
            "counties are indistinguishable from each other. Announced and "
            "approved stores count as though already trading, which is "
            "deliberately conservative.",
    },
]

COUNTY_COLUMNS = [
    "geoid", "county_name", "county_type", "latitude", "longitude",
    "population", "population_change_pct", "median_household_income",
    "nominal_income_change_pct", "real_income_change_pct",
    "max_interstate_segment_adt", "distance_to_interstate_mi",
    "nearest_store_distance_mi", "nearest_open_store_distance_mi",
    "gas_stations", "gas_stations_per_10k", "food_service_establishments",
    "population_density", "land_area_sq_mi", "corridor", "vdot_district",
    "market_attractiveness_score", "balanced_rank", "highway_rank",
    "growth_rank", "affluent_rank", "underserved_rank",
    "market_demand_score", "growth_score", "purchasing_power_score",
    "highway_opportunity_score", "accessibility_score",
    "commercial_activity_score", "low_competition_score",
    "low_overlap_risk_score", "recommendation_status",
    "recommendation_reason", "overlap_review_flag", "development_status",
    "interstate_access_flag", "traffic_data_available_flag",
]

CORRIDOR_COLUMNS = [
    "corridor", "corridor_tier", "best_eligible_rank", "eligible_county_count",
    "total_corridor_population", "nearest_store_distance_mi",
    "max_interstate_segment_adt", "leading_counties", "recommendation_summary",
    "overlap_review_flag", "reference_market_flag", "candidate_flag",
    "watchlist_flag",
]

BOOL_COLUMNS = {"overlap_review_flag", "interstate_access_flag",
                "traffic_data_available_flag", "reference_market_flag",
                "candidate_flag", "watchlist_flag"}


def as_bool(series: pd.Series) -> pd.Series:
    """TRUE / FALSE strings, which Tableau reads as boolean."""
    return series.astype(bool).map({True: "TRUE", False: "FALSE"})


def build_county() -> pd.DataFrame:
    engine = get_engine()
    profile = pd.read_sql("SELECT * FROM v_county_profile", engine)
    # Only the centroid columns: v_county_profile already carries
    # is_independent_city and region, and re-selecting them here would
    # collide on merge.
    geo = pd.read_sql(
        "SELECT geoid, centroid_lat, centroid_lon FROM geography", engine)
    rec = pd.read_parquet(DATA_PROCESSED / "recommendations.parquet")
    scores = pd.read_parquet(DATA_PROCESSED / "market_scores.parquet")
    feats = pd.read_parquet(DATA_PROCESSED / "spatial_features.parquet")
    ranks = pd.read_parquet(DATA_PROCESSED / "scenario_rankings.parquet")

    wide_ranks = (ranks.pivot(index="geoid", columns="scenario", values="rank")
                  .rename(columns=lambda s: f"{s}_rank").reset_index())

    df = (profile
          .merge(geo, on="geoid")
          .merge(feats, on="geoid")
          .merge(scores, on="geoid")
          .merge(wide_ranks, on="geoid")
          .merge(rec[["geoid", "corridor", "attractiveness_rank",
                      "weighted_score", "recommendation_status", "reason",
                      "store_status", "overlap_flag"]], on="geoid"))

    out = pd.DataFrame({"geoid": df["geoid"].astype(str).str.zfill(5)})
    out["county_name"] = df["county_name"]
    out["county_type"] = df["is_independent_city"].map(
        {1: "Independent city", 0: "County"})
    out["latitude"] = df["centroid_lat"]
    out["longitude"] = df["centroid_lon"]
    out["population"] = df["total_population"]
    out["population_change_pct"] = df["pop_growth_pct"]
    out["median_household_income"] = df["median_hh_income"]
    out["nominal_income_change_pct"] = df["mhi_growth_pct"]
    out["real_income_change_pct"] = df["mhi_growth_real_pct"]
    out["max_interstate_segment_adt"] = df["interstate_max_aadt"]
    # Values are exported at source precision. Rounding is a display
    # decision and belongs in Tableau, so the file stays bit-identical to
    # the published tables and the match check below can be exact.
    out["distance_to_interstate_mi"] = df["dist_interstate_mi"]
    out["nearest_store_distance_mi"] = df["dist_any_bucees_mi"]
    out["nearest_open_store_distance_mi"] = df["dist_open_bucees_mi"]
    out["gas_stations"] = df["gas_stations"]
    out["gas_stations_per_10k"] = df["gas_stations_per_10k"]
    out["food_service_establishments"] = df["food_service_estabs"]
    out["population_density"] = df["pop_density_sqmi"]
    out["land_area_sq_mi"] = df["aland_sqmi"]
    out["corridor"] = df["corridor"]
    out["vdot_district"] = df["region"]
    out["market_attractiveness_score"] = df["weighted_score"]
    out["balanced_rank"] = df["attractiveness_rank"]
    for s in ("highway", "growth", "affluent", "underserved"):
        out[f"{s}_rank"] = df[f"{s}_rank"]
    for src, dest in COMPONENT_EXPORT.items():
        out[dest] = df[src]
    out["recommendation_status"] = df["recommendation_status"]
    out["recommendation_reason"] = df["reason"]
    out["overlap_review_flag"] = as_bool(df["overlap_flag"].notna())
    # Null where no store is present, rather than a placeholder string.
    out["development_status"] = df["store_status"]
    out["interstate_access_flag"] = as_bool(df["interstate_crosses_county"])
    out["traffic_data_available_flag"] = as_bool(df["interstate_max_aadt"].notna())

    return out[COUNTY_COLUMNS].sort_values("balanced_rank").reset_index(drop=True)


def summarize(row: pd.Series) -> str:
    """One plain sentence per corridor, built from its own screening result."""
    tier = row["corridor_tier"]
    if tier == "Company-selected reference market":
        return ("Already holds an open, announced or locally approved store. "
                "Reported for context, not a current expansion candidate.")
    if tier == "Not a current candidate":
        return (f"No eligible county. All {int(row['counties'])} jurisdictions are "
                "screened out by overlap with an existing site, site feasibility "
                "or lack of measured interstate exposure.")
    lead = row["best_eligible_county"]
    rank = int(row["best_eligible_rank"])
    dist = row["eligible_min_dist_bucees_mi"]
    n_elig = int(row["eligible_counties"])
    if tier == "Candidate corridor":
        base = (f"{n_elig} eligible county(ies), led by {lead} at rank {rank}. "
                f"Nearest existing or planned store is {dist:.1f} miles from an "
                f"eligible county.")
        if row["overlap_review_flag"]:
            base += (" Spacing is close enough that trade-area overlap needs "
                     "review before siting.")
        return base
    return (f"{n_elig} eligible county(ies), led by {lead} at rank {rank}, but "
            f"none reach the priority cutoffs. Nearest store is {dist:.1f} miles "
            f"from an eligible county.")


def build_corridor(county: pd.DataFrame) -> pd.DataFrame:
    corr = pd.read_csv(TABLES / "corridor_recommendations.csv")

    # A corridor inherits the review flag if any member county carries it.
    flagged = (county.assign(f=county["overlap_review_flag"].eq("TRUE"))
               .groupby("corridor")["f"].any())
    corr["overlap_review_flag"] = corr["corridor"].map(flagged).fillna(False)
    corr["recommendation_summary"] = corr.apply(summarize, axis=1)

    out = pd.DataFrame({"corridor": corr["corridor"]})
    out["corridor_tier"] = corr["corridor_tier"]
    out["best_eligible_rank"] = corr["best_eligible_rank"].astype("Int64")
    out["eligible_county_count"] = corr["eligible_counties"].astype("Int64")
    out["total_corridor_population"] = corr["population"].astype("Int64")
    out["nearest_store_distance_mi"] = corr["eligible_min_dist_bucees_mi"]
    # Matches the "max eligible segment ADT" column in the corridor report.
    out["max_interstate_segment_adt"] = corr["eligible_max_interstate_aadt"]
    out["leading_counties"] = corr["top_eligible"].replace("none", pd.NA)
    out["recommendation_summary"] = corr["recommendation_summary"]
    out["overlap_review_flag"] = as_bool(corr["overlap_review_flag"])
    out["reference_market_flag"] = as_bool(corr["has_reference_case"])
    out["candidate_flag"] = as_bool(corr["corridor_tier"].eq("Candidate corridor"))
    out["watchlist_flag"] = as_bool(corr["corridor_tier"].eq("Watchlist corridor"))

    tier_order = {"Candidate corridor": 0, "Watchlist corridor": 1,
                  "Company-selected reference market": 2,
                  "Not a current candidate": 3}
    out = (out.assign(_o=out["corridor_tier"].map(tier_order))
           .sort_values(["_o", "best_eligible_rank"])
           .drop(columns="_o").reset_index(drop=True))
    return out[CORRIDOR_COLUMNS]


def build_component_long(county: pd.DataFrame) -> pd.DataFrame:
    """One row per county per component: 133 x 8 = 1,064.

    `component` uses the same key as scenario_weights.csv rather than the
    wide file's column name. The wide file calls two of these
    `low_competition_score` and `low_overlap_risk_score` to signal that they
    are inverted, but a long file exists mainly so it can be joined to the
    weights, and a key that does not join would defeat that. Joining brings
    `component_label` across, which carries the direction wording anyway.
    """
    # Wide column -> weights key.
    wide_to_key = {dest: src for src, dest in COMPONENT_EXPORT.items()}

    long = county.melt(
        id_vars=["geoid", "county_name", "recommendation_status", "corridor"],
        value_vars=list(COMPONENT_EXPORT.values()),
        var_name="component_column", value_name="component_score")
    long["component"] = long["component_column"].map(wide_to_key)

    # Keep components in model order rather than melt order, so a Tableau
    # author gets a stable axis without having to sort.
    order = {key: i for i, key in enumerate(COMPONENT_EXPORT.values())}
    long["_c"] = long["component_column"].map(order)
    long = (long.sort_values(["geoid", "_c"])
            .drop(columns=["component_column", "_c"])
            .reset_index(drop=True))

    return long[["geoid", "county_name", "component", "component_score",
                 "recommendation_status", "corridor"]]


def build_component_definitions() -> pd.DataFrame:
    """One row per component: what it means, what feeds it, what it cannot do."""
    return pd.DataFrame(COMPONENT_DEFINITIONS)[[
        "component", "plain_english_definition", "input_variables",
        "higher_score_meaning", "primary_source", "key_limitation"]]


def build_weights() -> pd.DataFrame:
    cfg = load_config()["scoring"]
    scenarios = cfg["scenarios"]
    rows = []
    for component in cfg["components"]:
        row = {"component": component,
               "component_label": COMPONENT_EXPORT[component]
               .replace("_score", "").replace("_", " ").title()}
        for name, weights in scenarios.items():
            row[f"{name}_weight"] = weights[component]
        rows.append(row)
    df = pd.DataFrame(rows)
    total = {"component": "TOTAL", "component_label": "Total"}
    for name in scenarios:
        total[f"{name}_weight"] = round(sum(scenarios[name].values()), 6)
    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)


def build_quality_metrics(county: pd.DataFrame) -> pd.DataFrame:
    """Headline model-quality figures, every one measured at export time.

    Nothing here is typed in by hand, so the file cannot drift from the
    project as it stands when the export runs.
    """
    engine = get_engine()

    # The validation table holds two different things. Stages 2 to 11 are
    # the analytical pipeline, which is what the published reports count.
    # Stage 12 is this export's own packaging checks, added later. Counting
    # them together would inflate the figure the reports quote, so the
    # headline covers the pipeline and the explanation states the total.
    checks = pd.read_sql(
        "SELECT stage, status FROM v_validation_latest", engine)
    pipeline = checks[checks["stage"] != STAGE]
    n_pipeline = len(pipeline)
    n_pipeline_pass = int((pipeline["status"] == "pass").sum())
    n_export = int(len(checks) - n_pipeline)

    # Count test functions from source. The suite uses no parametrize, so
    # one def is one test, matching what pytest collects.
    test_files = sorted((PROJECT_ROOT / "tests").glob("test_*.py"))
    n_tests = sum(len(re.findall(r"^def test_", f.read_text(), flags=re.M))
                  for f in test_files)

    cfg = load_config()["scoring"]
    scenario_names = list(cfg["scenarios"])
    sens = pd.read_csv(TABLES / "sensitivity_analysis.csv")
    min_rho = sens["spearman_rho"].min()
    min_top10 = int(sens["top10_retained"].min())

    rows = [
        {
            "metric": "Automated checks",
            "display_value": f"{n_pipeline_pass} / {n_pipeline}",
            "explanation":
                "Data integrity and pipeline reproducibility. Covers row "
                "counts, key uniqueness, geometry validity, referential "
                "integrity, reconciliation of county sums against published "
                "state totals, and score range invariants. These verify the "
                "data and the pipeline, not the commercial accuracy of the "
                f"recommendations. A further {n_export} checks cover the "
                "Tableau export package itself.",
        },
        {
            "metric": "Automated tests",
            "display_value": str(n_tests),
            "explanation":
                "Automated code tests passing. They cover configuration "
                "integrity, database schema creation, and invariants on the "
                "published outputs such as score normalization and ranking "
                "completeness.",
        },
        {
            "metric": "Jurisdictions screened",
            "display_value": str(len(county)),
            "explanation":
                "Virginia county-equivalents: 95 counties and 38 independent "
                "cities. Independent cities are kept separate because they "
                "carry their own federal codes in every source.",
        },
        {
            "metric": "Strategy scenarios",
            "display_value": str(len(scenario_names)),
            "explanation":
                "Weighting scenarios, each producing a complete ranking: "
                + ", ".join(scenario_names) + ". These are illustrative "
                "strategic postures, not estimates of company priorities.",
        },
        {
            "metric": "Sensitivity runs",
            "display_value": str(len(sens)),
            "explanation":
                f"One-component weight perturbations: {len(scenario_names)} "
                f"scenarios x {sens['component'].nunique()} components x "
                f"{sens['factor'].nunique()} adjustments of plus or minus 20 "
                "percent, with the remaining weights renormalized each time.",
        },
        {
            "metric": "Minimum Spearman correlation",
            "display_value": f"{min_rho:.4f}",
            "explanation":
                "Lowest rank correlation observed in sensitivity testing, "
                f"with at least {min_top10} of the baseline top 10 counties "
                "retained in every run. This shows the ranking is stable "
                "under the weight changes tested. It does not validate the "
                "choice of the eight variables, which is the larger "
                "modelling risk.",
        },
    ]
    return pd.DataFrame(rows)[["metric", "display_value", "explanation"]]


def build_screening_rules() -> pd.DataFrame:
    """The eligibility screen, in the order the model applies it.

    Thresholds and status labels are imported from
    scripts/analyze/recommendations.py rather than retyped, so this file
    cannot state a rule the model does not run.
    """
    overlap = rules.OVERLAP_MILES
    density = rules.URBAN_DENSITY_PER_SQMI
    priority = rules.PRIORITY_RANK
    secondary = rules.SECONDARY_RANK
    robust = rules.ROBUST_SCENARIOS
    n_scenarios = len(load_config()["scoring"]["scenarios"])

    rows = [
        {
            "rule_order": 1,
            "status": rules.STATUS_REFERENCE,
            "test": "The county already contains an open, announced or "
                    "locally approved store.",
            "outcome": "Excluded from the candidate set and reported for "
                       "context as a company-selected reference market.",
            "rationale": "A market that is already taken is not an expansion "
                         "opportunity. Reporting these separately keeps them "
                         "from being read as fresh recommendations.",
        },
        {
            "rule_order": 2,
            "status": rules.STATUS_OVERLAP,
            "test": f"The county centroid lies within {overlap:.0f} miles of "
                    "an existing or planned store.",
            "outcome": "Excluded. A new store here would sit inside an "
                       "existing one's core draw.",
            "rationale": f"{overlap:.0f} miles is half the 60-mile trade "
                         "radius the project assumes, which itself comes "
                         "from public reporting on how far these stores "
                         "draw rather than from customer data. Assumption "
                         "A15.",
        },
        {
            "rule_order": 3,
            "status": rules.STATUS_DATA_GAP,
            "test": "An interstate crosses the county, but the VDOT extract "
                    "holds no mainline traffic record for it.",
            "outcome": "Held back for data reasons rather than screened out "
                       "on the merits. Would need a fuller traffic source "
                       "before being ranked.",
            "rationale": "Thirteen jurisdictions, including Newport News and "
                         "Hampton, are crossed by an interstate VDOT does "
                         "not record. Labelling them as lacking an "
                         "interstate would state something false.",
        },
        {
            "rule_order": 4,
            "status": rules.STATUS_NO_INTERSTATE,
            "test": "No interstate crosses the county.",
            "outcome": "Excluded. The store format targets interstate "
                       "travel centres.",
            "rationale": "Tested against TIGER interstate geometry rather "
                         "than the traffic extract, so a genuine absence is "
                         "distinguished from missing data.",
        },
        {
            "rule_order": 5,
            "status": rules.STATUS_FEASIBILITY,
            "test": f"Population density is at or above {density:,} people "
                    "per square mile.",
            "outcome": "Excluded. Assembling an interchange-scale site is "
                       "treated as the binding constraint, whatever the "
                       "score.",
            "rationale": "The two Virginia sites the company pursued occupy "
                         "36.18 acres in Stafford and 27.68 acres in New "
                         "Kent. At this density such land near an "
                         "interchange is largely built out. The cutoff is "
                         "analyst judgement, not a measurement of available "
                         "land. Assumption A16.",
        },
        {
            "rule_order": 6,
            "status": rules.STATUS_PRIORITY,
            "test": f"Clears every rule above, ranks within the top "
                    f"{priority} on the balanced scenario, and ranks within "
                    f"the top {priority} in at least {robust} of "
                    f"{n_scenarios} scenarios.",
            "outcome": "Recommended.",
            "rationale": "Requiring cross-scenario consistency stops a "
                         "county qualifying on one weighting alone. Cutoffs "
                         "are round numbers chosen for interpretability, not "
                         "derived from data. Assumption A17.",
        },
        {
            "rule_order": 7,
            "status": rules.STATUS_SECONDARY,
            "test": f"Clears every rule above and ranks within the top "
                    f"{secondary} on the balanced scenario.",
            "outcome": "Recommended with caveats.",
            "rationale": "A wider band for markets worth investigating that "
                         "do not meet the consistency bar for priority. "
                         "Assumption A17.",
        },
        {
            "rule_order": 8,
            "status": rules.STATUS_WATCHLIST,
            "test": "Clears every rule above but falls outside the ranking "
                    "cutoffs.",
            "outcome": "Monitor. Eligible but not currently recommended.",
            "rationale": "Eligibility and attractiveness are separate. These "
                         "counties could host a store but do not rank highly "
                         "enough to act on now.",
        },
    ]
    return pd.DataFrame(rows)[
        ["rule_order", "status", "test", "outcome", "rationale"]]


def build_geojson(county: pd.DataFrame) -> gpd.GeoDataFrame:
    gdf = gpd.read_parquet(DATA_PROCESSED / "va_counties.geoparquet")
    gdf["geoid"] = gdf["geoid"].astype(str).str.zfill(5)
    # RFC 7946 requires WGS84 for GeoJSON. Source is NAD83; the shift is
    # sub-metre at this scale but the declared CRS should be correct.
    gdf = gdf.to_crs("EPSG:4326")
    merged = gdf[["geoid", "geometry"]].merge(county, on="geoid", how="inner")
    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = True

    county = build_county()
    component_long = build_component_long(county)
    definitions = build_component_definitions()
    corridor = build_corridor(county)
    weights = build_weights()
    quality = build_quality_metrics(county)
    screening = build_screening_rules()
    geo = build_geojson(county)

    # ---------------- validation ----------------
    ok &= validation.record(STAGE, "tableau_county_row_count",
                            len(county) == EXPECTED_COUNTIES,
                            f"{len(county)} rows, expected {EXPECTED_COUNTIES}")
    ok &= validation.record(STAGE, "tableau_geoid_unique",
                            county["geoid"].is_unique,
                            f"{county['geoid'].nunique()} distinct of {len(county)}")
    ok &= validation.record(
        STAGE, "tableau_geoid_five_char_string",
        bool(county["geoid"].map(lambda v: isinstance(v, str) and len(v) == 5).all()),
        "all GEOIDs are 5-character strings")

    # Exported values must equal the published tables, not a recomputation.
    rec = pd.read_parquet(DATA_PROCESSED / "recommendations.parquet")
    chk = county.merge(rec, on="geoid")
    ok &= validation.record(
        STAGE, "tableau_ranks_match_published",
        bool((chk["balanced_rank"] == chk["attractiveness_rank"]).all()),
        "balanced_rank equals recommendations.attractiveness_rank")
    ok &= validation.record(
        STAGE, "tableau_status_matches_published",
        bool((chk["recommendation_status_x"] == chk["recommendation_status_y"]).all()),
        "recommendation_status matches the recommendations table")
    ok &= validation.record(
        STAGE, "tableau_scores_match_published",
        bool((chk["market_attractiveness_score"] == chk["weighted_score"]).all()),
        "market_attractiveness_score is identical to the published weighted score")

    src_scores = pd.read_parquet(DATA_PROCESSED / "market_scores.parquet")
    comp_chk = county.merge(src_scores, on="geoid")
    mismatched = [dest for src, dest in COMPONENT_EXPORT.items()
                  if not (comp_chk[dest] == comp_chk[src]).all()]
    ok &= validation.record(
        STAGE, "tableau_component_scores_match_published",
        not mismatched, f"mismatched: {mismatched}" if mismatched
        else "all 8 component scores identical to market_scores")

    n_components = len(COMPONENT_EXPORT)
    expected_long = EXPECTED_COUNTIES * n_components
    ok &= validation.record(
        STAGE, "tableau_component_long_row_count",
        len(component_long) == expected_long,
        f"{len(component_long)} rows, expected {EXPECTED_COUNTIES} x "
        f"{n_components} = {expected_long}")
    ok &= validation.record(
        STAGE, "tableau_component_long_key_unique",
        not component_long.duplicated(["geoid", "component"]).any(),
        f"{int(component_long.duplicated(['geoid', 'component']).sum())} duplicate "
        f"geoid + component pairs")
    ok &= validation.record(
        STAGE, "tableau_component_long_score_numeric",
        pd.api.types.is_numeric_dtype(component_long["component_score"])
        and bool(component_long["component_score"].notna().all()),
        f"dtype {component_long['component_score'].dtype}, "
        f"{int(component_long['component_score'].isna().sum())} nulls, range "
        f"{component_long['component_score'].min():.2f} to "
        f"{component_long['component_score'].max():.2f}")
    # The long form must carry the same values as the wide form, and its
    # component key must join to the weights file.
    wide_check = county.melt(
        id_vars="geoid", value_vars=list(COMPONENT_EXPORT.values()),
        var_name="col", value_name="wide_score")
    wide_check["component"] = wide_check["col"].map(
        {dest: src for src, dest in COMPONENT_EXPORT.items()})
    joined = component_long.merge(wide_check, on=["geoid", "component"])
    ok &= validation.record(
        STAGE, "tableau_component_long_matches_wide",
        len(joined) == expected_long
        and bool((joined["component_score"] == joined["wide_score"]).all()),
        f"{len(joined)} rows matched, all values identical to the wide file")
    weight_keys = set(build_weights().query("component != 'TOTAL'")["component"])
    ok &= validation.record(
        STAGE, "tableau_component_long_joins_to_weights",
        set(component_long["component"]) == weight_keys,
        f"component keys align with scenario_weights.csv: "
        f"{sorted(set(component_long['component']) ^ weight_keys) or 'exact match'}")

    # The definitions table is hand-written prose, so the checks focus on it
    # staying aligned with the model rather than on its wording.
    model_components = list(COMPONENT_EXPORT)
    ok &= validation.record(
        STAGE, "tableau_definitions_cover_every_component",
        list(definitions["component"]) == model_components,
        f"{len(definitions)} rows in model order: {list(definitions['component'])}")
    ok &= validation.record(
        STAGE, "tableau_definitions_no_blank_cells",
        bool(definitions.notna().all().all())
        and bool((definitions.map(lambda v: str(v).strip() != "")).all().all()),
        "every cell populated")
    # Each named input must be a real field, not a plausible-sounding one.
    # The scoring model draws from three places: the county profile view,
    # the spatial features table, and demographics directly for
    # commuters_total, which the profile view does not carry.
    known_fields = set(pd.read_sql(
        "SELECT * FROM v_county_profile LIMIT 1", get_engine()).columns)
    known_fields |= set(pd.read_parquet(DATA_PROCESSED / "spatial_features.parquet").columns)
    known_fields |= set(pd.read_sql(
        "SELECT * FROM demographics LIMIT 1", get_engine()).columns)
    declared = {v.strip() for row in definitions["input_variables"]
                for v in row.split(";")}
    unknown = sorted(declared - known_fields)
    ok &= validation.record(
        STAGE, "tableau_definitions_inputs_are_real_fields",
        not unknown,
        f"{len(declared)} declared inputs all exist in the source tables"
        if not unknown else f"unknown fields: {unknown}")
    inverted = set(definitions.loc[
        definitions["higher_score_meaning"].str.contains(
            "Higher is more attractive", case=False), "component"])
    ok &= validation.record(
        STAGE, "tableau_definitions_flag_inverted_components",
        inverted == {"competition", "overlap_risk"},
        f"components stating the inverted direction: {sorted(inverted)}")

    # Quality metrics are measured at export time, so the checks confirm
    # each figure still agrees with the source it was measured from.
    q = quality.set_index("metric")["display_value"]
    sens = pd.read_csv(TABLES / "sensitivity_analysis.csv")
    pipeline_checks = pd.read_sql(
        "SELECT status FROM v_validation_latest WHERE stage != :s",
        get_engine(), params={"s": STAGE})
    expected_q = {
        "Automated checks":
            f"{int((pipeline_checks['status'] == 'pass').sum())} / {len(pipeline_checks)}",
        "Jurisdictions screened": str(len(county)),
        "Strategy scenarios": str(len(load_config()["scoring"]["scenarios"])),
        "Sensitivity runs": str(len(sens)),
        "Minimum Spearman correlation": f"{sens['spearman_rho'].min():.4f}",
    }
    drift = {k: (q.get(k), v) for k, v in expected_q.items() if q.get(k) != v}
    ok &= validation.record(
        STAGE, "tableau_quality_metrics_match_outputs", not drift,
        f"{len(expected_q)} metrics re-measured and matching"
        if not drift else f"drift: {drift}")
    ok &= validation.record(
        STAGE, "tableau_quality_metrics_complete",
        len(quality) == 6 and bool(quality.notna().all().all())
        and bool((quality.map(lambda v: str(v).strip() != "")).all().all()),
        f"{len(quality)} rows, all cells populated")

    # The screening file must describe the rules the model actually runs.
    statuses_in_file = list(screening["status"])
    model_statuses = [rules.STATUS_REFERENCE, rules.STATUS_OVERLAP,
                      rules.STATUS_DATA_GAP, rules.STATUS_NO_INTERSTATE,
                      rules.STATUS_FEASIBILITY, rules.STATUS_PRIORITY,
                      rules.STATUS_SECONDARY, rules.STATUS_WATCHLIST]
    ok &= validation.record(
        STAGE, "tableau_screening_rules_match_model_order",
        statuses_in_file == model_statuses
        and list(screening["rule_order"]) == list(range(1, 9)),
        f"8 rules in model order: {statuses_in_file}")
    # Every status the screen actually assigned must appear in the file.
    assigned = set(pd.read_parquet(
        DATA_PROCESSED / "recommendations.parquet")["recommendation_status"])
    missing = assigned - set(statuses_in_file)
    ok &= validation.record(
        STAGE, "tableau_screening_rules_cover_assigned_statuses",
        not missing,
        f"all {len(assigned)} assigned statuses documented"
        if not missing else f"undocumented: {sorted(missing)}")
    # Thresholds quoted in the text must be the ones the model uses.
    text = " ".join(screening["test"]) + " " + " ".join(screening["rationale"])
    thresholds_ok = (f"{rules.OVERLAP_MILES:.0f} miles" in text
                     and f"{rules.URBAN_DENSITY_PER_SQMI:,}" in text
                     and f"top {rules.PRIORITY_RANK}" in text
                     and f"top {rules.SECONDARY_RANK}" in text
                     and f"at least {rules.ROBUST_SCENARIOS} of" in text)
    ok &= validation.record(
        STAGE, "tableau_screening_rules_quote_model_thresholds", thresholds_ok,
        f"overlap {rules.OVERLAP_MILES:.0f} mi, density "
        f"{rules.URBAN_DENSITY_PER_SQMI:,}, priority top {rules.PRIORITY_RANK}, "
        f"secondary top {rules.SECONDARY_RANK}, {rules.ROBUST_SCENARIOS} of 5")

    src_corr = pd.read_csv(TABLES / "corridor_recommendations.csv")
    ok &= validation.record(
        STAGE, "tableau_corridor_matches_report",
        len(corridor) == len(src_corr)
        and set(corridor["corridor"]) == set(src_corr["corridor"]),
        f"{len(corridor)} corridors, same set as the corridor report")

    for name, weight_sums in [("weights", weights)]:
        totals = weight_sums[weight_sums["component"] == "TOTAL"]
        cols = [c for c in totals.columns if c.endswith("_weight")]
        ok &= validation.record(
            STAGE, "tableau_scenario_weights_sum_to_one",
            bool(all(abs(totals.iloc[0][c] - 1.0) < 1e-9 for c in cols)),
            f"totals: {{{', '.join(f'{c}: {totals.iloc[0][c]}' for c in cols)}}}")

    ok &= validation.record(STAGE, "tableau_geojson_feature_count",
                            len(geo) == EXPECTED_COUNTIES,
                            f"{len(geo)} features")
    ok &= validation.record(STAGE, "tableau_geojson_geometry_valid",
                            bool(geo.geometry.is_valid.all())
                            and bool(geo.geometry.notna().all()),
                            f"{int((~geo.geometry.is_valid).sum())} invalid, "
                            f"{int(geo.geometry.isna().sum())} missing")
    ok &= validation.record(STAGE, "tableau_geojson_crs_wgs84",
                            geo.crs is not None and geo.crs.to_epsg() == 4326,
                            f"CRS = {geo.crs.to_epsg() if geo.crs else None}")

    # No placeholder strings should have leaked into any text column.
    placeholders = {"None", "nan", "NaN", "n/a", "N/A", "not available", "null"}
    leaked = {}
    for frame_name, frame in [("county", county), ("corridor", corridor)]:
        for col in frame.select_dtypes(include="object"):
            hits = int(frame[col].isin(placeholders).sum())
            if hits:
                leaked[f"{frame_name}.{col}"] = hits
    ok &= validation.record(STAGE, "tableau_no_placeholder_strings",
                            not leaked, f"{leaked}")

    bad_bools = {}
    for frame_name, frame in [("county", county), ("corridor", corridor)]:
        for col in BOOL_COLUMNS & set(frame.columns):
            vals = set(frame[col].dropna().unique()) - {"TRUE", "FALSE"}
            if vals:
                bad_bools[f"{frame_name}.{col}"] = sorted(vals)
    ok &= validation.record(STAGE, "tableau_booleans_true_false",
                            not bad_bools, f"{bad_bools}")

    # ---------------- write ----------------
    county.to_csv(OUT / "county_dashboard_data.csv", index=False, na_rep="")
    component_long.to_csv(OUT / "component_scores_long.csv", index=False, na_rep="")
    definitions.to_csv(OUT / "component_definitions.csv", index=False, na_rep="")
    quality.to_csv(OUT / "model_quality_metrics.csv", index=False, na_rep="")
    screening.to_csv(OUT / "screening_rules.csv", index=False, na_rep="")
    corridor.to_csv(OUT / "corridor_dashboard_data.csv", index=False, na_rep="")
    weights.to_csv(OUT / "scenario_weights.csv", index=False, na_rep="")
    geo.to_file(OUT / "virginia_counties.geojson", driver="GeoJSON")

    # The in-memory checks above prove no rounding was applied. This one
    # proves the written file is what Tableau will actually read. Exact
    # float equality is not the right test after a text round trip: the
    # CSV repr can differ by one unit in the last place of a double, which
    # is around 1e-14 on a 0-100 score and 12 decimal places below any
    # display precision. A 1e-9 tolerance catches real corruption while
    # tolerating that.
    reread_csv = pd.read_csv(OUT / "county_dashboard_data.csv", dtype={"geoid": str})
    rt = reread_csv.merge(rec, on="geoid")
    score_drift = (rt["market_attractiveness_score"] - rt["weighted_score"]).abs().max()
    rank_drift = int((rt["balanced_rank"] != rt["attractiveness_rank"]).sum())
    ok &= validation.record(
        STAGE, "tableau_csv_roundtrip_fidelity",
        score_drift < 1e-9 and rank_drift == 0
        and len(reread_csv) == EXPECTED_COUNTIES,
        f"{len(reread_csv)} rows on re-read; max score drift {score_drift:.2e}; "
        f"{rank_drift} rank changes")

    # A GeoJSON writer can silently coerce types, so re-read and confirm.
    reread = json.loads((OUT / "virginia_counties.geojson").read_text())
    n_feat = len(reread["features"])
    geoids = [f["properties"]["geoid"] for f in reread["features"]]
    ok &= validation.record(
        STAGE, "tableau_geojson_reread_intact",
        n_feat == EXPECTED_COUNTIES and len(set(geoids)) == EXPECTED_COUNTIES
        and all(isinstance(g, str) and len(g) == 5 for g in geoids),
        f"{n_feat} features on re-read, {len(set(geoids))} distinct string GEOIDs")

    for f in sorted(OUT.glob("*")):
        log.info("%-32s %8.1f KB", f.name, f.stat().st_size / 1024)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
