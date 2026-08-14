"""SQLite access via SQLAlchemy. The database file lives at the path given in
config.yaml (paths.database) and its schema is defined in sql/schema.sql."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from scripts.utils.config import load_config
from scripts.utils.paths import PROJECT_ROOT, SQL_DIR


def db_path():
    cfg = load_config()
    return PROJECT_ROOT / cfg["paths"]["database"]


def get_engine() -> Engine:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}")


def init_schema(engine: Engine | None = None) -> None:
    """Apply sql/schema.sql (idempotent - all CREATE IF NOT EXISTS).

    Uses sqlite3's executescript so semicolons inside comments/strings are
    parsed correctly (naive split-on-';' breaks on them)."""
    engine = engine or get_engine()
    ddl = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.connection.driver_connection.executescript(ddl)
