"""Record automated validation checks to the validation_results table and log
them. Every stage that transforms data registers its checks through here."""

from datetime import datetime, timezone

from sqlalchemy import text

from scripts.utils.db import get_engine, init_schema
from scripts.utils.logging_setup import get_logger

log = get_logger("validation")


def record(stage: str, check_name: str, passed: bool, details: str = "",
           warn_only: bool = False, conn=None) -> bool:
    """Persist one validation result. Returns `passed` so callers can chain.

    Pass `conn` when calling inside an open transaction on the same SQLite
    database - SQLite allows only one writer, so opening a second
    connection here would deadlock ("database is locked")."""
    status = "pass" if passed else ("warn" if warn_only else "fail")
    params = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "stage": stage, "check_name": check_name, "status": status,
              "details": details[:2000]}
    stmt = text("INSERT INTO validation_results (run_ts, stage, check_name, status, details) "
                "VALUES (:ts, :stage, :check_name, :status, :details)")
    if conn is not None:
        conn.execute(stmt, params)
    else:
        engine = get_engine()
        init_schema(engine)
        with engine.begin() as new_conn:
            new_conn.execute(stmt, params)
    level = log.info if passed else (log.warning if warn_only else log.error)
    level("[%s] %s: %s %s", stage, check_name, status.upper(), details)
    return passed
