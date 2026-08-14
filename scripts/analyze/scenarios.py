"""Stage 7 - scenario analysis.

For each strategy scenario in config (balanced / highway / growth /
affluent / underserved):
  weighted_score = Σ weight_c · component_c   (weights sum to 1.0)
  rank           = 1..133, deterministic (ties broken by geoid)

Also produces:
- stability metrics per county across scenarios (mean/best/worst rank,
  spread, #scenarios in top 10) → scenario_stability.csv
- sensitivity analysis: each component weight perturbed ±20% (renormalized)
  per scenario; Spearman ρ vs baseline ranking and top-10 retention
  → sensitivity_analysis.csv
- scenario rank heatmap (top counties × scenarios)

Loads scenario_rankings table + parquet.
"""

import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text

from scripts.utils.config import load_config
from scripts.utils.db import get_engine
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, FIGURES, TABLES
from scripts.utils import validation
from scripts.utils import viz_theme as vt

log = get_logger("scenarios")
STAGE = "stage7_scenarios"


def weighted_ranking(scores: pd.DataFrame, weights: dict) -> pd.DataFrame:
    ws = sum(w * scores[c] for c, w in weights.items())
    out = pd.DataFrame({"geoid": scores["geoid"], "weighted_score": ws})
    out = out.sort_values(["weighted_score", "geoid"],
                          ascending=[False, True]).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def spearman(rank_a: pd.Series, rank_b: pd.Series) -> float:
    return float(rank_a.corr(rank_b, method="spearman"))


def main() -> int:
    cfg = load_config()
    scenarios = cfg["scoring"]["scenarios"]
    components = cfg["scoring"]["components"]
    scores = pd.read_parquet(DATA_PROCESSED / "market_scores.parquet")
    names = pd.read_sql("SELECT geoid, county_name FROM geography", get_engine())

    ok = True
    for name, w in scenarios.items():
        ok &= validation.record(STAGE, f"weights_sum_{name}",
                                abs(sum(w.values()) - 1.0) < 1e-9,
                                f"sum={sum(w.values()):.6f}")

    # ---------- rankings ----------
    all_ranks = []
    for name, w in scenarios.items():
        r = weighted_ranking(scores, w)
        r["scenario"] = name
        all_ranks.append(r)
    rankings = pd.concat(all_ranks, ignore_index=True)

    for name in scenarios:
        sub = rankings[rankings["scenario"] == name]
        ok &= validation.record(STAGE, f"ranks_unique_{name}",
                                sub["rank"].is_unique and len(sub) == 133,
                                f"{len(sub)} rows")

    rankings.to_parquet(DATA_PROCESSED / "scenario_rankings.parquet", index=False)
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM scenario_rankings"))
        rankings[["scenario", "geoid", "weighted_score", "rank"]].to_sql(
            "scenario_rankings", conn, if_exists="append", index=False)
        n = conn.execute(text("SELECT COUNT(*) FROM scenario_rankings")).scalar()
        ok &= validation.record(STAGE, "rankings_db_loaded",
                                n == 133 * len(scenarios), f"{n} rows", conn=conn)

    for name in scenarios:
        top = (rankings[rankings["scenario"] == name].nsmallest(15, "rank")
               .merge(names, on="geoid"))
        top[["rank", "county_name", "weighted_score"]].to_csv(
            TABLES / f"scenario_{name}_top15.csv", index=False)

    # ---------- stability ----------
    pivot = rankings.pivot(index="geoid", columns="scenario", values="rank")
    stability = pd.DataFrame({
        "mean_rank": pivot.mean(axis=1),
        "best_rank": pivot.min(axis=1),
        "worst_rank": pivot.max(axis=1),
        "rank_spread": pivot.max(axis=1) - pivot.min(axis=1),
        "n_scenarios_top10": (pivot <= 10).sum(axis=1),
        "n_scenarios_top15": (pivot <= 15).sum(axis=1),
    }).reset_index().merge(names, on="geoid").sort_values("mean_rank")
    stability.to_csv(TABLES / "scenario_stability.csv", index=False)
    consensus = stability[stability["n_scenarios_top10"] >= 4]
    ok &= validation.record(STAGE, "stability_consensus_exists",
                            len(consensus) >= 3,
                            f"{len(consensus)} counties in top-10 of ≥4 scenarios: "
                            f"{consensus['county_name'].head(8).tolist()}")

    # ---------- sensitivity ----------
    rows = []
    for name, w in scenarios.items():
        base = weighted_ranking(scores, w).set_index("geoid")["rank"]
        base_top10 = set(base[base <= 10].index)
        for comp in components:
            for factor in (0.8, 1.2):
                w2 = dict(w)
                w2[comp] = w[comp] * factor
                total = sum(w2.values())
                w2 = {c: v / total for c, v in w2.items()}
                pert = weighted_ranking(scores, w2).set_index("geoid")["rank"]
                rows.append({
                    "scenario": name, "component": comp, "factor": factor,
                    "spearman_rho": spearman(base, pert),
                    "top10_retained": len(base_top10 & set(pert[pert <= 10].index)),
                })
    sens = pd.DataFrame(rows)
    sens.to_csv(TABLES / "sensitivity_analysis.csv", index=False)
    worst = sens.groupby("scenario")[["spearman_rho", "top10_retained"]].min()
    log.info("sensitivity worst-case per scenario:\n%s", worst.to_string())
    ok &= validation.record(STAGE, "sensitivity_rankings_stable",
                            (sens["spearman_rho"] > 0.95).all()
                            and (sens["top10_retained"] >= 7).all(),
                            f"min rho={sens['spearman_rho'].min():.3f}, "
                            f"min top10 retained={sens['top10_retained'].min()}")

    # ---------- heatmap ----------
    focus = stability.nsmallest(18, "mean_rank")
    hm = pivot.loc[focus["geoid"]]
    labels = focus.set_index("geoid").loc[hm.index, "county_name"].str.replace(
        " County", "", regex=False).str.replace(" city", " (city)", regex=False)
    fig = go.Figure(go.Heatmap(
        z=hm.values, x=list(hm.columns), y=labels.values,
        colorscale=[[0, vt.SEQ_BLUE[-1]], [0.5, vt.SEQ_BLUE[5]], [1, vt.SEQ_BLUE[0]]],
        text=hm.values.astype(int), texttemplate="%{text}",
        textfont=dict(size=11),
        colorbar=dict(title="rank", tickfont=dict(color=vt.INK_MUTED)),
        hovertemplate="%{y} | %{x}: rank %{z}<extra></extra>", xgap=2, ygap=2))
    fig.update_layout(
        title="County rank by strategy scenario (1 = best)",
        height=620, margin=dict(l=150),
        yaxis=dict(autorange="reversed"), xaxis=dict(side="top"))
    vt.save_fig(fig, FIGURES / "scenario_rank_heatmap.html")

    log.info("scenario analysis complete")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
