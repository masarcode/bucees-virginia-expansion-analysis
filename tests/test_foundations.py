"""Stage 1 foundation tests: configuration integrity and schema application."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.utils.config import load_config  # noqa: E402


def test_config_loads():
    cfg = load_config()
    assert cfg["project"]["state_fips"] == "51"


def test_scenario_weights_sum_to_one():
    cfg = load_config()
    components = set(cfg["scoring"]["components"])
    for name, weights in cfg["scoring"]["scenarios"].items():
        assert set(weights) == components, f"{name}: weight keys != components"
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=1e-9), f"{name} weights sum to {total}"


def test_schema_applies_to_fresh_db(tmp_path):
    from sqlalchemy import create_engine, inspect

    ddl = (PROJECT_ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.sqlite'}")
    with engine.begin() as conn:
        conn.connection.driver_connection.executescript(ddl)
    tables = set(inspect(engine).get_table_names())
    required = {"geography", "demographics", "business_activity", "traffic_summary",
                "bucees_locations", "market_scores", "scenario_rankings",
                "validation_results"}
    assert required <= tables, f"missing tables: {required - tables}"
