"""Clean CBP 2023 → business_activity table.

File-code mapping verified by inspection: '------' all sectors, '44----'
retail trade (NAICS 44-45), '447///' gasoline stations, '722///' food
services & drinking places. fipscty '999' (statewide catch-all) dropped.
Suppression: *_nf noise/disclosure flags; 'D' means withheld (value is a
placeholder zero) → value set to NULL, emp_suppressed=1.

Output: data/processed/business_activity.parquet
"""

import sys
import zipfile

import numpy as np
import pandas as pd

from scripts.utils.config import load_config
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW
from scripts.utils import validation

log = get_logger("clean_cbp")
STAGE = "stage3_clean"

FILE_CODES = {
    "------": ("00", "All sectors"),
    "44----": ("44-45", "Retail trade"),
    "447///": ("447", "Gasoline stations"),
    "722///": ("722", "Food services & drinking places"),
}
KNOWN_FLAGS = {"G", "H", "J", "D", "S", ""}


def main() -> int:
    cfg = load_config()
    year = int(cfg["cbp"]["year"])

    with zipfile.ZipFile(DATA_RAW / "cbp" / "cbp23co.zip") as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f, dtype=str)

    va = df[(df["fipstate"] == "51") & (df["fipscty"] != "999")].copy()
    va = va[va["naics"].isin(FILE_CODES)].copy()
    va["geoid"] = va["fipstate"] + va["fipscty"]
    va["naics_code"] = va["naics"].map(lambda c: FILE_CODES[c][0])
    va["naics_desc"] = va["naics"].map(lambda c: FILE_CODES[c][1])
    va["year"] = year

    flags = set(va["emp_nf"].fillna("").unique()) | set(va["ap_nf"].fillna("").unique())
    validation.record(STAGE, "cbp_flags_recognized", flags <= KNOWN_FLAGS,
                      f"observed flags: {sorted(flags)}", warn_only=True)

    va["establishments"] = pd.to_numeric(va["est"], errors="coerce")
    va["employment"] = pd.to_numeric(va["emp"], errors="coerce")
    va["annual_payroll"] = pd.to_numeric(va["ap"], errors="coerce")
    va["emp_suppressed"] = va["emp_nf"].isin(["D", "S"]).astype(int)
    va.loc[va["emp_suppressed"] == 1, "employment"] = np.nan
    va.loc[va["ap_nf"].isin(["D", "S"]), "annual_payroll"] = np.nan

    geography = pd.read_parquet(DATA_PROCESSED / "geography.parquet")
    known = set(geography["geoid"])

    ok = validation.record(STAGE, "cbp_geoids_known",
                           set(va["geoid"]) <= known,
                           f"unknown: {sorted(set(va['geoid']) - known)}")
    ok &= validation.record(STAGE, "cbp_pk_unique",
                            not va.duplicated(["geoid", "year", "naics_code"]).any(), "")
    all_sect = va[va["naics_code"] == "00"]
    ok &= validation.record(STAGE, "cbp_allsector_coverage", len(all_sect) == 133,
                            f"{len(all_sect)}/133 counties have all-sector rows")
    ok &= validation.record(STAGE, "cbp_establishments_positive",
                            (all_sect["establishments"] > 0).all(), "")
    supp = int(va["emp_suppressed"].sum())
    validation.record(STAGE, "cbp_suppression_rate", True,
                      f"{supp}/{len(va)} rows employment-suppressed", warn_only=True)

    out = va[["geoid", "year", "naics_code", "naics_desc", "establishments",
              "employment", "annual_payroll", "emp_suppressed"]].reset_index(drop=True)
    out.to_parquet(DATA_PROCESSED / "business_activity.parquet", index=False)
    log.info("wrote business_activity.parquet: %d rows, %d counties, %d suppressed",
             len(out), out["geoid"].nunique(), supp)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
