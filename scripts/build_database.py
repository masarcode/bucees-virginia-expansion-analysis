"""Load processed tables into SQLite and create analytical views.

Idempotent: data tables are deleted and reloaded from data/processed/;
validation_results is append-only history and is never truncated. Foreign
keys are enforced during load.
"""

import sys

import pandas as pd
from sqlalchemy import text

from scripts.utils.db import get_engine, init_schema
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, SQL_DIR
from scripts.utils import validation

log = get_logger("build_database")
STAGE = "stage4_database"

# table -> (parquet file, columns present at this stage)
LOADS = {
    "geography": ("geography.parquet",
                  ["geoid", "county_name", "state_fips", "county_fips",
                   "is_independent_city", "aland_sqmi", "awater_sqmi",
                   "centroid_lat", "centroid_lon"]),
    "demographics": ("demographics.parquet", None),
    "business_activity": ("business_activity.parquet", None),
    "traffic_summary": ("traffic_summary.parquet", None),
    "bucees_locations": ("bucees_locations.parquet",
                         ["city", "state", "status", "latitude", "longitude",
                          "opened_date", "source_url", "accessed_date"]),
    "cpi_annual": ("cpi_annual.parquet", ["year", "cpi"]),
}


def main() -> int:
    engine = get_engine()
    init_schema(engine)
    ok = True

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        # Delete in reverse dependency order. Scores/rankings reference
        # geography too (populated by later stages, rebuilt after this).
        for table in ["recommendations", "scenario_rankings", "market_scores",
                      "bucees_locations", "traffic_summary", "business_activity",
                      "demographics", "cpi_annual", "geography"]:
            conn.execute(text(f"DELETE FROM {table}"))

        for table, (fname, cols) in LOADS.items():
            df = pd.read_parquet(DATA_PROCESSED / fname)
            if table == "bucees_locations":
                df = df.rename(columns={"city": "name"})
                df["city"] = df["name"]
                cols = ["name", "status", "state", "city", "latitude",
                        "longitude", "opened_date", "source_url", "accessed_date"]
            if cols:
                df = df[[c for c in cols if c in df.columns]]
            df.to_sql(table, conn, if_exists="append", index=False)
            n_db = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            ok &= validation.record(STAGE, f"db_load_{table}", n_db == len(df),
                                    f"{n_db} rows loaded (parquet {len(df)})", conn=conn)

        # Referential integrity: no orphan geoids anywhere.
        for table in ["demographics", "business_activity", "traffic_summary"]:
            orphans = conn.execute(text(
                f"SELECT COUNT(*) FROM {table} t "
                f"LEFT JOIN geography g ON g.geoid = t.geoid "
                f"WHERE g.geoid IS NULL")).scalar()
            ok &= validation.record(STAGE, f"db_fk_{table}", orphans == 0,
                                    f"{orphans} orphan rows", conn=conn)

        conn.connection.driver_connection.executescript(
            (SQL_DIR / "views.sql").read_text(encoding="utf-8"))

        profile_rows = conn.execute(text("SELECT COUNT(*) FROM v_county_profile")).scalar()
        ok &= validation.record(STAGE, "db_view_county_profile", profile_rows == 133,
                                f"{profile_rows} rows", conn=conn)
        growth_rows = conn.execute(text(
            "SELECT COUNT(*) FROM v_county_growth WHERE pop_growth_pct IS NOT NULL")).scalar()
        ok &= validation.record(STAGE, "db_view_growth_computed", growth_rows == 133,
                                f"{growth_rows} rows with growth", conn=conn)
        top = conn.execute(text(
            "SELECT county_name, interstate_max_aadt FROM v_interstate_counties LIMIT 3"
        )).fetchall()
        ok &= validation.record(STAGE, "db_view_interstate_top_sane",
                                len(top) == 3 and top[0][1] >= top[2][1],
                                f"top-3: {[(r[0], r[1]) for r in top]}", conn=conn)

    log.info("database build complete")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
