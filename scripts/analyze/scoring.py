"""Stage 6 - component scoring model.

Eight components per county, each min-max normalized to 0-100 across the
133 Virginia county-equivalents (higher = more attractive for a Buc-ee's
travel center). Input transforms and blend weights are documented here and
in docs/methodology (Stage 10):

  market_demand       0.5·mm(log10 population) + 0.5·mm(log10 commuters)
                      (log compresses the Fairfax-to-Highland 4-OoM spread)
  growth              0.7·mm(pop growth %) + 0.3·mm(median-HH-income growth %)
  purchasing_power    0.6·mm(median HH income) + 0.4·mm(per-capita income)
  highway_opportunity 0.6·mm(interstate max AADT, no-interstate → 0)
                      + 0.4·mm(log10 VMT proxy)
  accessibility       mm(−distance to nearest interstate)
  commercial_activity 0.5·mm(log10 all-sector establishments)
                      + 0.5·mm(food-service establishments per 10k)
  competition         mm(−gas stations per 10k)   [higher = thinner fuel retail]
  overlap_risk        mm(distance to nearest open/announced Buc-ee's,
                      capped at 120 mi = 2× the 60-mi trade radius, A3)
                      [higher = less cannibalization risk]

Blended components are re-normalized after blending (A13). A weighted sum
of two separately min-maxed inputs does not span 0-100, because the county
holding the minimum of one input rarely holds the minimum of the other.
Left uncorrected, a component with a compressed span exerts less influence
than its nominal weight implies (measured: growth 7.9% actual vs 10.0%
nominal under balanced weights). Re-normalizing is monotonic - it cannot
reorder counties within a component - and makes the configured weights
mean what they say.

Output: market_scores table + data/processed/market_scores.parquet
"""

import sys

import numpy as np
import pandas as pd
from sqlalchemy import text

from scripts.utils.config import load_config
from scripts.utils.db import get_engine
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED
from scripts.utils import validation

log = get_logger("scoring")
STAGE = "stage6_scoring"


def mm(s: pd.Series) -> pd.Series:
    """Min-max to 0-100. NaNs must be resolved by the caller first."""
    rng = s.max() - s.min()
    if rng == 0:
        return pd.Series(50.0, index=s.index)
    return 100.0 * (s - s.min()) / rng


def build_scores() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM v_county_profile", engine)
    feats = pd.read_parquet(DATA_PROCESSED / "spatial_features.parquet")
    demo = pd.read_sql(
        "SELECT geoid, commuters_total FROM demographics "
        "WHERE acs_period = '2019-2023'", engine)
    df = df.merge(feats, on="geoid").merge(demo, on="geoid")

    s = pd.DataFrame({"geoid": df["geoid"]})

    s["market_demand"] = 0.5 * mm(np.log10(df["total_population"])) \
                       + 0.5 * mm(np.log10(df["commuters_total"].clip(lower=1)))
    s["growth"] = 0.7 * mm(df["pop_growth_pct"]) + 0.3 * mm(df["mhi_growth_pct"])
    s["purchasing_power"] = 0.6 * mm(df["median_hh_income"]) \
                          + 0.4 * mm(df["per_capita_income"])
    s["highway_opportunity"] = 0.6 * mm(df["interstate_max_aadt"].fillna(0.0)) \
                             + 0.4 * mm(np.log10(df["vmt_proxy"].clip(lower=1)))
    s["accessibility"] = mm(-df["dist_interstate_mi"])
    food_per_10k = 10000 * df["food_service_estabs"].fillna(0) / df["total_population"]
    s["commercial_activity"] = 0.5 * mm(np.log10(df["establishments_all"].clip(lower=1))) \
                             + 0.5 * mm(food_per_10k)
    gas_per_10k = 10000 * df["gas_stations"].fillna(0) / df["total_population"]
    s["competition"] = mm(-gas_per_10k)
    s["overlap_risk"] = mm(df["dist_any_bucees_mi"].clip(upper=120.0))

    # Re-normalize blended components so every component spans a full
    # 0-100 range and the configured weights carry their stated influence
    # (see module docstring / assumption A13). Monotonic: ordering within
    # each component is unchanged.
    for c in ("market_demand", "growth", "purchasing_power",
              "highway_opportunity", "commercial_activity"):
        s[c] = mm(s[c])

    return s, df


def main() -> int:
    cfg = load_config()
    s, df = build_scores()
    components = cfg["scoring"]["components"]

    ok = validation.record(STAGE, "scores_row_count", len(s) == 133, f"{len(s)} rows")
    ok &= validation.record(STAGE, "scores_all_components_present",
                            set(components) <= set(s.columns),
                            f"missing: {set(components) - set(s.columns)}")
    vals = s[components]
    ok &= validation.record(STAGE, "scores_no_missing", vals.notna().all().all(),
                            f"{dict(vals.isna().sum()[vals.isna().sum() > 0])}")
    ok &= validation.record(STAGE, "scores_in_range",
                            bool(((vals >= 0) & (vals <= 100.000001)).all().all()),
                            f"min={vals.min().min():.2f} max={vals.max().max():.2f}")
    # Every component must span the full 0-100 range, so configured weights
    # carry their stated influence (A13).
    spans = {c: round(vals[c].max() - vals[c].min(), 4) for c in components}
    ok &= validation.record(
        STAGE, "scores_span_full_range",
        all(abs(v - 100.0) < 1e-6 for v in spans.values()),
        f"spreads: {spans}")
    # Direction sanity: each component must correlate positively with its
    # driving raw input (or negatively for inverse components).
    checks = {
        "market_demand_up_with_pop":
            s["market_demand"].corr(df["total_population"].rank()) > 0.9,
        "competition_down_with_gas_density":
            s["competition"].corr(
                (10000 * df["gas_stations"].fillna(0) / df["total_population"])) < -0.9,
        "overlap_up_with_distance":
            s["overlap_risk"].corr(df["dist_any_bucees_mi"]) > 0.9,
        "accessibility_down_with_distance":
            s["accessibility"].corr(df["dist_interstate_mi"]) < -0.9,
    }
    for name, passed in checks.items():
        ok &= validation.record(STAGE, f"scores_direction_{name}", bool(passed), "")

    s.to_parquet(DATA_PROCESSED / "market_scores.parquet", index=False)
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM market_scores"))
        s[["geoid"] + components].to_sql("market_scores", conn,
                                         if_exists="append", index=False)
        n = conn.execute(text("SELECT COUNT(*) FROM market_scores")).scalar()
        ok &= validation.record(STAGE, "scores_db_loaded", n == 133,
                                f"{n} rows", conn=conn)

    top = (s.assign(mean_score=s[components].mean(axis=1))
           .merge(df[["geoid", "county_name"]], on="geoid")
           .nlargest(5, "mean_score")[["county_name", "mean_score"]])
    log.info("unweighted top-5:\n%s", top.to_string(index=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
