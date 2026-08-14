"""Acquire CPI-U annual averages from the Bureau of Labor Statistics.

ACS money values are expressed in the final year of each period, so the
2014-2018 estimates are in 2018 dollars and the 2019-2023 estimates are in
2023 dollars. Comparing them without adjustment measures nominal change,
not purchasing power. This script pulls the official BLS series so the
deflator is reproducible rather than hard coded.

Series CUUR0000SA0 is CPI for All Urban Consumers, US city average, all
items, not seasonally adjusted. Period M13 is the annual average.

Source file: https://download.bls.gov/pub/time.series/cu/cu.data.1.AllItems
Output: data/raw/cpi/cu.data.1.AllItems + data/processed/cpi_annual.parquet
"""

import sys

import pandas as pd

from scripts.utils.config import load_config
from scripts.utils.download import download_file, record_manifest
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW
from scripts.utils import validation

log = get_logger("fetch_cpi")
STAGE = "stage2_acquire"

SERIES_ID = "CUUR0000SA0"
ANNUAL_PERIOD = "M13"


def main() -> int:
    cfg = load_config()
    url = cfg["cpi"]["all_items_url"]
    years = [int(cfg["acs"]["prior_year"]), int(cfg["acs"]["current_year"])]

    dest = download_file(url, DATA_RAW / "cpi" / "cu.data.1.AllItems")

    df = pd.read_csv(dest, sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip()
    log.info("CPI flat file: %d rows, columns=%s", len(df), list(df.columns))

    annual = df[(df["series_id"] == SERIES_ID) & (df["period"] == ANNUAL_PERIOD)].copy()
    annual["year"] = annual["year"].astype(int)
    annual["cpi"] = annual["value"].astype(float)
    annual = annual[["year", "cpi"]].sort_values("year").reset_index(drop=True)

    have = set(annual["year"])
    ok = validation.record(
        STAGE, "cpi_required_years_present", set(years) <= have,
        f"need {years}; file covers {annual['year'].min()}-{annual['year'].max()}")
    if not ok:
        return 1

    base = annual.loc[annual["year"] == years[1], "cpi"].iloc[0]
    prior = annual.loc[annual["year"] == years[0], "cpi"].iloc[0]
    deflator = base / prior
    ok &= validation.record(
        STAGE, "cpi_deflator_plausible", 1.0 < deflator < 1.5,
        f"CPI {years[0]}={prior}, {years[1]}={base}, deflator={deflator:.5f} "
        f"({100 * (deflator - 1):.1f}% cumulative inflation)")

    annual.to_parquet(DATA_PROCESSED / "cpi_annual.parquet", index=False)
    record_manifest("cpi/cu.data.1.AllItems", "BLS CPI-U all items (CUUR0000SA0)",
                    url, dest.stat().st_size, f"{len(df)} rows",
                    f"annual averages M13; {years[0]}={prior}, {years[1]}={base}")
    log.info("wrote cpi_annual.parquet; deflator %d->%d = %.5f",
             years[0], years[1], deflator)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
