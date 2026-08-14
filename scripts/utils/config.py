"""Load config/config.yaml and .env values."""

import os
from functools import lru_cache

import yaml

from scripts.utils.paths import CONFIG_FILE, ENV_FILE


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env() -> dict:
    """Parse KEY=VALUE lines from .env (if present) into os.environ and return them.
    Values already set in the environment win."""
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            values[key] = os.environ.get(key, val)
            os.environ.setdefault(key, val)
    return values


def census_api_key() -> str | None:
    load_env()
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    return key or None
