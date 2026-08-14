"""Canonical project paths. All scripts resolve locations through here so the
pipeline works regardless of the caller's working directory."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"
ENV_FILE = PROJECT_ROOT / ".env"

DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

DATABASE_DIR = PROJECT_ROOT / "database"
SQL_DIR = PROJECT_ROOT / "sql"
OUTPUTS = PROJECT_ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
MAPS = OUTPUTS / "maps"
TABLES = OUTPUTS / "tables"
REPORTS = OUTPUTS / "reports"
DOCS = PROJECT_ROOT / "docs"
