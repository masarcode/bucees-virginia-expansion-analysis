"""Stage 11 - eligibility screening, corridor assignment, and the
retrospective holdout check.

The scoring model measures market attractiveness. It does not know which
markets are already taken, whether a 30-acre interchange parcel could
plausibly be assembled, or how close a new store would sit to an existing
one. This script applies those filters explicitly so that a raw model rank
is never presented as a business recommendation on its own.

Every threshold below is an analyst assumption, recorded in
docs/assumptions.md (A14 to A18) and printed in the outputs.

Eligibility rules, applied in order. The first rule that matches sets the
status and reason:

  R1 Reference case      county already contains an open, announced, or
                         locally approved store
  R2 Overlap constrained centroid within 30 miles of such a store
                         (half the 60-mile assumed trade radius, A3)
  R3 No interstate       no interstate mainline segment in the county
  R4 Feasibility         population density at or above 2,000 per square
                         mile, where assembling an interchange-scale site
                         is a severe constraint
  otherwise eligible, then tiered by balanced rank and cross-scenario
  consistency into priority candidate, secondary candidate, or watchlist.

Corridors are analyst-reviewed groupings of eligible counties that share an
interstate and a travel market. Membership is checked against the processed
VDOT mainline records, so no corridor is asserted without a route behind it.

Outputs:
  data/processed/recommendations.parquet
  outputs/tables/county_recommendations.csv
  outputs/tables/corridor_recommendations.csv
  outputs/tables/holdout_check.csv
"""

import sys

import pandas as pd
from sqlalchemy import text

from scripts.utils.config import load_config
from scripts.utils.db import get_engine
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, TABLES
from scripts.utils import validation

log = get_logger("recommendations")
STAGE = "stage11_recommendations"

# Analyst assumptions (documented in docs/assumptions.md)
OVERLAP_MILES = 30.0          # A15: half the 60-mile assumed trade radius
URBAN_DENSITY_PER_SQMI = 2000 # A16: interchange-scale parcel constraint
PRIORITY_RANK = 25            # A17: tiering cutoffs among eligible counties
SECONDARY_RANK = 45
ROBUST_SCENARIOS = 4          # of 5, for priority tier

STATUS_REFERENCE = "Reference case"
STATUS_OVERLAP = "Overlap constrained"
STATUS_NO_INTERSTATE = "Ineligible: no interstate access"
STATUS_DATA_GAP = "Traffic data unavailable"
STATUS_FEASIBILITY = "Feasibility constrained"
STATUS_PRIORITY = "Priority candidate"
STATUS_SECONDARY = "Secondary candidate"
STATUS_WATCHLIST = "Watchlist"
STATUS_REVIEW = "Further overlap review required"

# Corridor definitions. Each entry lists the counties an analyst grouped
# into a travel market and the interstate that justifies the grouping.
# Membership is validated against processed VDOT mainline records.
CORRIDORS = {
    "I-64 / I-264 Hampton Roads": {
        "route": "I-64",
        "counties": ["Virginia Beach city", "Norfolk city", "Chesapeake city",
                     "Suffolk city", "Newport News city", "Hampton city",
                     "York County", "James City County", "Portsmouth city",
                     "Isle of Wight County"],
    },
    "I-95 Richmond South": {
        "route": "I-95",
        "counties": ["Chesterfield County", "Colonial Heights city",
                     "Petersburg city", "Prince George County",
                     "Dinwiddie County"],
    },
    "I-95 Richmond North": {
        "route": "I-95",
        "counties": ["Hanover County", "Henrico County", "Richmond city"],
    },
    "I-64 Richmond West": {
        "route": "I-64",
        "counties": ["Goochland County", "Louisa County"],
    },
    "I-64 Richmond East / New Kent": {
        "route": "I-64",
        "counties": ["New Kent County", "Charles City County"],
    },
    "I-95 Fredericksburg / Stafford": {
        "route": "I-95",
        "counties": ["Stafford County", "Spotsylvania County",
                     "Caroline County", "Fredericksburg city"],
    },
    "I-95 / I-66 Northern Virginia": {
        "route": "I-95",
        "counties": ["Fairfax County", "Prince William County",
                     "Arlington County", "Alexandria city", "Fairfax city",
                     "Manassas city", "Manassas Park city", "Falls Church city"],
    },
    "I-81 Winchester / Frederick": {
        "route": "I-81",
        "counties": ["Frederick County", "Winchester city", "Shenandoah County",
                     "Warren County", "Clarke County"],
    },
    "I-81 Harrisonburg / Rockingham": {
        "route": "I-81",
        "counties": ["Rockingham County", "Harrisonburg city", "Augusta County",
                     "Staunton city", "Waynesboro city", "Page County"],
    },
    "I-81 Roanoke / Salem": {
        "route": "I-81",
        "counties": ["Roanoke County", "Roanoke city", "Salem city",
                     "Botetourt County", "Rockbridge County", "Lexington city",
                     "Bedford County"],
    },
    "I-81 New River Valley": {
        "route": "I-81",
        "counties": ["Montgomery County", "Pulaski County", "Radford city",
                     "Wythe County", "Giles County"],
    },
    "I-64 Charlottesville": {
        "route": "I-64",
        "counties": ["Albemarle County", "Charlottesville city",
                     "Fluvanna County", "Nelson County"],
    },
    "I-95 / I-85 Southside": {
        "route": "I-85",
        "counties": ["Greensville County", "Emporia city", "Brunswick County",
                     "Mecklenburg County"],
    },
    "I-81 Bristol / Southwest": {
        "route": "I-81",
        "counties": ["Washington County", "Bristol city", "Smyth County",
                     "Russell County", "Scott County"],
    },
    "I-66 Piedmont": {
        "route": "I-66",
        "counties": ["Fauquier County", "Culpeper County", "Rappahannock County"],
    },
}


def corridor_lookup() -> dict[str, str]:
    out = {}
    for corridor, spec in CORRIDORS.items():
        for county in spec["counties"]:
            out[county] = corridor
    return out


def classify(row, ref_geoids: set[str]) -> tuple[str, str]:
    """Return (status, reason) for one county. First matching rule wins."""
    if row["geoid"] in ref_geoids:
        return STATUS_REFERENCE, f"Existing or planned store in county ({row['store_status']})"
    if pd.notna(row["dist_any_bucees_mi"]) and row["dist_any_bucees_mi"] < OVERLAP_MILES:
        return (STATUS_OVERLAP,
                f"Centroid {row['dist_any_bucees_mi']:.1f} mi from an existing or "
                f"planned store, inside the {OVERLAP_MILES:.0f} mi screen")
    if pd.isna(row["interstate_max_aadt"]):
        if row.get("interstate_crosses_county"):
            # An interstate physically crosses the jurisdiction but VDOT's
            # extract carries no mainline record for it. Reporting this as
            # "no interstate access" would be false, so it is held back for
            # data reasons rather than screened out on the merits.
            return (STATUS_DATA_GAP,
                    "An interstate crosses this jurisdiction but the VDOT extract "
                    "holds no mainline traffic record for it, so highway exposure "
                    "could not be measured")
        return STATUS_NO_INTERSTATE, "No interstate crosses this jurisdiction"
    if pd.notna(row["pop_density_sqmi"]) and row["pop_density_sqmi"] >= URBAN_DENSITY_PER_SQMI:
        return (STATUS_FEASIBILITY,
                f"Population density {row['pop_density_sqmi']:,.0f} people per sq mi. "
                f"Assembling an interchange-scale site of roughly 30 acres is a "
                f"severe constraint.")
    return "", ""


def main() -> int:
    cfg = load_config()
    engine = get_engine()

    profile = pd.read_sql("SELECT * FROM v_county_profile", engine)
    feats = pd.read_parquet(DATA_PROCESSED / "spatial_features.parquet")
    ranks = pd.read_parquet(DATA_PROCESSED / "scenario_rankings.parquet")
    stores = pd.read_parquet(DATA_PROCESSED / "bucees_locations.parquet")
    scores = pd.read_parquet(DATA_PROCESSED / "market_scores.parquet")

    balanced = (ranks[ranks["scenario"] == "balanced"]
                .rename(columns={"rank": "attractiveness_rank"})
                [["geoid", "attractiveness_rank", "weighted_score"]])
    df = profile.merge(feats, on="geoid").merge(balanced, on="geoid")

    # Counties that already contain a store, with its development status.
    va_stores = stores[stores["state"] == "VA"].copy()
    status_label = {"open": "open", "announced": "announced",
                    "under_construction": "under construction"}
    va_stores["label"] = va_stores["status"].map(status_label)
    # Stafford's site has local approval but no confirmed opening date.
    va_stores.loc[va_stores["city"] == "Stafford", "label"] = "locally approved"
    store_by_geoid = (va_stores.dropna(subset=["county_geoid"])
                      .set_index("county_geoid")["label"].to_dict())
    df["store_status"] = df["geoid"].map(store_by_geoid)
    ref_geoids = set(store_by_geoid)

    ok = validation.record(
        STAGE, "rec_reference_counties_found", len(ref_geoids) == 3,
        f"{len(ref_geoids)} VA counties contain a store: "
        f"{sorted(df.loc[df['geoid'].isin(ref_geoids), 'county_name'])}")

    # Cross-scenario consistency for the priority tier.
    piv = ranks.pivot(index="geoid", columns="scenario", values="rank")
    df["scenarios_in_top25"] = df["geoid"].map((piv <= PRIORITY_RANK).sum(axis=1))

    df["corridor"] = df["county_name"].map(corridor_lookup()).fillna("Not in a screened corridor")

    statuses, reasons = [], []
    for _, row in df.iterrows():
        s, r = classify(row, ref_geoids)
        statuses.append(s)
        reasons.append(r)
    df["recommendation_status"] = statuses
    df["reason"] = reasons

    # Tier the counties that survived every rule.
    eligible = df["recommendation_status"] == ""
    df.loc[eligible & (df["attractiveness_rank"] <= PRIORITY_RANK)
           & (df["scenarios_in_top25"] >= ROBUST_SCENARIOS),
           ["recommendation_status", "reason"]] = [
        STATUS_PRIORITY,
        f"Eligible, balanced rank within top {PRIORITY_RANK}, and top "
        f"{PRIORITY_RANK} in at least {ROBUST_SCENARIOS} of 5 scenarios"]
    still = df["recommendation_status"] == ""
    df.loc[still & (df["attractiveness_rank"] <= SECONDARY_RANK),
           ["recommendation_status", "reason"]] = [
        STATUS_SECONDARY,
        f"Eligible, balanced rank within top {SECONDARY_RANK}"]
    df.loc[df["recommendation_status"] == "", ["recommendation_status", "reason"]] = [
        STATUS_WATCHLIST, "Eligible but outside the screened ranking cutoffs"]

    # Counties just outside the overlap screen deserve an explicit flag
    # rather than a clean recommendation.
    near = (df["dist_any_bucees_mi"] >= OVERLAP_MILES) & (df["dist_any_bucees_mi"] < 40) & \
           df["recommendation_status"].isin([STATUS_PRIORITY, STATUS_SECONDARY])
    df.loc[near, "reason"] = df.loc[near].apply(
        lambda r: f"{r['reason']}. Nearest existing or planned store is only "
                  f"{r['dist_any_bucees_mi']:.1f} mi away, so trade-area overlap "
                  f"needs review before siting", axis=1)
    df.loc[near, "overlap_flag"] = STATUS_REVIEW

    ok &= validation.record(
        STAGE, "rec_every_county_classified",
        (df["recommendation_status"] != "").all() and len(df) == 133,
        f"{len(df)} counties, statuses: {df['recommendation_status'].value_counts().to_dict()}")

    # Corridor membership must be backed by an interstate actually present.
    bad = []
    for corridor, spec in CORRIDORS.items():
        members = df[df["corridor"] == corridor]
        if members.empty:
            bad.append(f"{corridor}: no counties matched")
        elif members["interstate_max_aadt"].notna().sum() == 0:
            bad.append(f"{corridor}: no member county has an interstate mainline")
    ok &= validation.record(STAGE, "rec_corridors_supported", not bad, f"{bad}")

    # ---------------- retrospective holdout check ----------------
    # Re-score with the overlap component removed, so no Buc-ee's location
    # data enters the model, and see where the company-selected counties land.
    components = [c for c in cfg["scoring"]["components"] if c != "overlap_risk"]
    w = dict(cfg["scoring"]["scenarios"]["balanced"])
    w.pop("overlap_risk")
    total = sum(w.values())
    w = {c: v / total for c, v in w.items()}
    blind = scores[["geoid"]].copy()
    blind["blind_score"] = sum(w[c] * scores[c] for c in components)
    blind = blind.sort_values(["blind_score", "geoid"], ascending=[False, True]).reset_index(drop=True)
    blind["blind_rank"] = blind.index + 1
    holdout = (blind.merge(df[["geoid", "county_name", "attractiveness_rank", "store_status"]],
                           on="geoid")
               .query("store_status.notna()")
               .sort_values("blind_rank")
               [["county_name", "store_status", "blind_rank", "attractiveness_rank",
                 "blind_score"]])
    holdout.to_csv(TABLES / "holdout_check.csv", index=False)
    log.info("retrospective holdout (overlap component removed):\n%s",
             holdout.to_string(index=False))
    ok &= validation.record(
        STAGE, "rec_holdout_ran", len(holdout) == 3,
        "; ".join(f"{r.county_name} ({r.store_status}) blind rank {int(r.blind_rank)} "
                  f"of 133, with-overlap rank {int(r.attractiveness_rank)}"
                  for r in holdout.itertuples()))

    # ---------------- corridor rollup ----------------
    def roll(group: pd.DataFrame) -> pd.Series:
        elig = group[group["recommendation_status"].isin(
            [STATUS_PRIORITY, STATUS_SECONDARY, STATUS_WATCHLIST])]
        best = group.nsmallest(1, "attractiveness_rank").iloc[0]
        # Spacing is judged on the counties that could actually host a store,
        # not on constrained ones. A corridor whose only nearby county is
        # already taken should not look crowded on that account.
        best_elig = (elig.nsmallest(1, "attractiveness_rank").iloc[0]
                     if not elig.empty else None)
        return pd.Series({
            "counties": len(group),
            "eligible_counties": len(elig),
            "population": int(group["total_population"].sum()),
            "best_attractiveness_rank": int(group["attractiveness_rank"].min()),
            "best_county": best["county_name"],
            "best_eligible_county": best_elig["county_name"] if best_elig is not None else "none",
            "best_eligible_rank": int(best_elig["attractiveness_rank"]) if best_elig is not None else pd.NA,
            "max_interstate_aadt": group["interstate_max_aadt"].max(),
            "eligible_max_interstate_aadt": elig["interstate_max_aadt"].max() if not elig.empty else pd.NA,
            "eligible_min_dist_bucees_mi": round(elig["dist_any_bucees_mi"].min(), 1) if not elig.empty else pd.NA,
            "corridor_min_dist_bucees_mi": round(group["dist_any_bucees_mi"].min(), 1),
            "has_reference_case": bool((group["recommendation_status"] == STATUS_REFERENCE).any()),
            "n_priority": int((group["recommendation_status"] == STATUS_PRIORITY).sum()),
            "top_eligible": ", ".join(
                elig.nsmallest(3, "attractiveness_rank")["county_name"]
                .str.replace(" County", "", regex=False)) or "none",
        })

    corr = (df[df["corridor"] != "Not in a screened corridor"]
            .groupby("corridor").apply(roll, include_groups=False)
            .reset_index())
    # Corridor tiering follows the best eligible county, so corridors whose
    # only strong counties are reference cases or constrained do not lead.
    corr["corridor_tier"] = "Not a current candidate"
    corr.loc[corr["has_reference_case"], "corridor_tier"] = "Company-selected reference market"
    has_elig = corr["eligible_counties"] > 0
    corr.loc[has_elig & (corr["n_priority"] > 0), "corridor_tier"] = "Candidate corridor"
    corr.loc[has_elig & (corr["n_priority"] == 0), "corridor_tier"] = "Watchlist corridor"
    corr = corr.sort_values(
        ["corridor_tier", "best_eligible_rank"],
        key=lambda s: s.map({"Candidate corridor": 0, "Watchlist corridor": 1,
                             "Company-selected reference market": 2,
                             "Not a current candidate": 3}) if s.name == "corridor_tier" else s
    ).reset_index(drop=True)
    corr.to_csv(TABLES / "corridor_recommendations.csv", index=False)

    out_cols = ["geoid", "county_name", "corridor", "attractiveness_rank",
                "weighted_score", "recommendation_status", "reason",
                "store_status", "overlap_flag", "dist_any_bucees_mi",
                "dist_open_bucees_mi", "interstate_max_aadt",
                "pop_density_sqmi", "total_population", "pop_growth_pct",
                "scenarios_in_top25"]
    for c in out_cols:
        if c not in df.columns:
            df[c] = pd.NA
    final = df[out_cols].sort_values("attractiveness_rank")
    final.to_parquet(DATA_PROCESSED / "recommendations.parquet", index=False)
    final.to_csv(TABLES / "county_recommendations.csv", index=False)

    db_cols = ["geoid", "corridor", "attractiveness_rank", "weighted_score",
               "recommendation_status", "reason", "store_status", "overlap_flag"]
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM recommendations"))
        final[db_cols].to_sql("recommendations", conn, if_exists="append", index=False)
        n = conn.execute(text("SELECT COUNT(*) FROM recommendations")).scalar()
        ok &= validation.record(STAGE, "rec_db_loaded", n == 133, f"{n} rows", conn=conn)

    log.info("status counts: %s", df["recommendation_status"].value_counts().to_dict())
    log.info("corridor tiers:\n%s",
             corr[["corridor", "corridor_tier", "best_eligible_rank",
                   "eligible_counties", "eligible_min_dist_bucees_mi",
                   "population", "top_eligible"]].to_string(index=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
