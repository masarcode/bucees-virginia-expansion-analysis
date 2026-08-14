"""Acquire ACS 5-year estimates for both study periods from the official
bulk summary files (api.census.gov requires an API key as of 2026; bulk
files do not).

2019-2023: table-based summary file - one pipe-delimited .dat per table.
2014-2018: legacy sequence-file format - VA geography file + the sequence
zips containing our tables, located via the official table lookup.

This script only downloads and INSPECTS; parsing/cleaning is Stage 3.
"""

import io
import sys
import zipfile

import pandas as pd

from scripts.utils.config import load_config
from scripts.utils.download import download_file, http_get, record_manifest
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_RAW
from scripts.utils import validation

log = get_logger("fetch_acs")
STAGE = "stage2_acquire"


def tables_needed(cfg) -> list[str]:
    """Distinct table IDs from configured variables (B23025_002E -> B23025)."""
    return sorted({v.split("_")[0] for v in cfg["acs"]["variables"]})


def fetch_2023(cfg) -> bool:
    base = cfg["acs"]["current_base_url"]
    dest_dir = DATA_RAW / "acs_2023"
    ok = True
    for table in tables_needed(cfg):
        fname = f"acsdt5y2023-{table.lower()}.dat"
        dest = download_file(f"{base}/{fname}", dest_dir / fname)
        # Inspect: pipe-delimited, must contain GEO_ID and VA county rows.
        head = pd.read_csv(dest, sep="|", dtype=str, nrows=5)
        log.info("%s columns: %s", fname, list(head.columns)[:8])
        full = pd.read_csv(dest, sep="|", dtype=str, usecols=["GEO_ID"])
        va_counties = full["GEO_ID"].str.startswith("0500000US51").sum()
        ok &= validation.record(
            STAGE, f"acs2023_{table}_va_counties", va_counties >= 133,
            f"{fname}: {len(full)} rows, {va_counties} VA county rows")
        record_manifest(fname, "ACS 2019-2023 5yr table-based SF",
                        f"{base}/{fname}", dest.stat().st_size,
                        f"{len(full)} rows", f"table {table}")
    return ok


def fetch_2018(cfg) -> bool:
    base = cfg["acs"]["prior_base_url"]
    lookup_url = cfg["acs"]["prior_lookup_url"]
    dest_dir = DATA_RAW / "acs_2018"
    ok = True

    lookup_dest = download_file(lookup_url, dest_dir / "ACS_5yr_Seq_Table_Number_Lookup.txt")
    lookup = pd.read_csv(lookup_dest, dtype=str, encoding="latin-1")
    log.info("lookup columns: %s", list(lookup.columns))
    tbl_col = next(c for c in lookup.columns if c.strip().lower() == "table id")
    seq_col = next(c for c in lookup.columns if "sequence" in c.lower())

    needed = tables_needed(cfg)
    seqs = {}
    for table in needed:
        rows = lookup[lookup[tbl_col].str.strip() == table]
        if rows.empty:
            ok &= validation.record(STAGE, f"acs2018_lookup_{table}", False,
                                    f"table {table} not in sequence lookup")
            continue
        seqs[table] = int(rows.iloc[0][seq_col])
    log.info("table -> sequence: %s", seqs)
    ok &= validation.record(STAGE, "acs2018_lookup_all_tables",
                            len(seqs) == len(needed),
                            f"{len(seqs)}/{len(needed)} tables located")

    geo_dest = download_file(f"{base}/g20185va.csv", dest_dir / "g20185va.csv")
    geo = pd.read_csv(geo_dest, dtype=str, header=None, encoding="latin-1")
    log.info("geography file: %d rows x %d cols", *geo.shape)
    ok &= validation.record(STAGE, "acs2018_geo_file_rows", len(geo) > 100,
                            f"{len(geo)} geography rows for VA")

    for seq in sorted(set(seqs.values())):
        fname = f"20185va{seq:04d}000.zip"
        dest = download_file(f"{base}/{fname}", dest_dir / fname)
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
            has_est = any(n.startswith("e2018") for n in names)
            ok &= validation.record(STAGE, f"acs2018_seq{seq}_has_estimates",
                                    has_est, f"{fname}: {names}")
        record_manifest(fname, "ACS 2014-2018 5yr sequence file (VA)",
                        f"{base}/{fname}", dest.stat().st_size, "-",
                        f"sequence {seq}: tables {[t for t, s in seqs.items() if s == seq]}")

    record_manifest("g20185va.csv", "ACS 2014-2018 5yr geography file (VA)",
                    f"{base}/g20185va.csv", geo_dest.stat().st_size,
                    f"{len(geo)} rows", "no header; positional layout")
    record_manifest("ACS_5yr_Seq_Table_Number_Lookup.txt",
                    "ACS 2018 table/sequence lookup", lookup_url,
                    lookup_dest.stat().st_size, f"{len(lookup)} rows", "")
    return ok


def main() -> int:
    cfg = load_config()
    ok = fetch_2023(cfg)
    ok &= fetch_2018(cfg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
