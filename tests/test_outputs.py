"""Integrity tests over pipeline outputs (run after the pipeline)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utils.config import load_config  # noqa: E402

PROCESSED = PROJECT_ROOT / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (PROCESSED / "market_scores.parquet").exists(),
    reason="pipeline outputs not built yet")


def test_geography_complete():
    geo = pd.read_parquet(PROCESSED / "geography.parquet")
    assert len(geo) == 133
    assert geo["geoid"].is_unique
    assert geo["geoid"].str.startswith("51").all()


def test_demographics_two_periods():
    d = pd.read_parquet(PROCESSED / "demographics.parquet")
    assert d.groupby("acs_period").size().to_dict() == {
        "2014-2018": 133, "2019-2023": 133}
    assert not d.duplicated(["geoid", "acs_period"]).any()


def test_scores_normalized():
    cfg = load_config()
    s = pd.read_parquet(PROCESSED / "market_scores.parquet")
    comps = cfg["scoring"]["components"]
    assert len(s) == 133
    for c in comps:
        assert s[c].between(0, 100.000001).all(), c
        assert s[c].notna().all(), c
        # Every component spans the full range, including blended ones,
        # which are re-normalized after blending so the configured weights
        # carry their stated influence (assumption A13).
        assert s[c].min() == pytest.approx(0, abs=1e-6), c
        assert s[c].max() == pytest.approx(100, abs=1e-6), c


def test_rankings_complete_and_unique():
    cfg = load_config()
    r = pd.read_parquet(PROCESSED / "scenario_rankings.parquet")
    scenarios = set(cfg["scoring"]["scenarios"])
    assert set(r["scenario"]) == scenarios
    for name, sub in r.groupby("scenario"):
        assert len(sub) == 133
        assert sorted(sub["rank"]) == list(range(1, 134)), name


def test_database_row_counts():
    from sqlalchemy import text
    from scripts.utils.db import get_engine
    with get_engine().connect() as conn:
        for table, expected in [("geography", 133), ("demographics", 266),
                                ("business_activity", 526),
                                ("traffic_summary", 133),
                                ("market_scores", 133),
                                ("scenario_rankings", 665)]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            assert n == expected, f"{table}: {n} != {expected}"
