"""Acquire County Business Patterns 2023 complete county file (bulk zip -
the api.census.gov route requires an API key as of 2026). Downloads,
inspects the layout, and verifies Virginia coverage and NAICS codes of
interest are present. Raw zip preserved as downloaded."""

import sys
import zipfile

import pandas as pd

from scripts.utils.config import load_config
from scripts.utils.download import download_file, record_manifest
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_RAW
from scripts.utils import validation

log = get_logger("fetch_cbp")
STAGE = "stage2_acquire"


def main() -> int:
    cfg = load_config()["cbp"]
    url = cfg["county_file_url"]
    dest = DATA_RAW / "cbp" / url.rsplit("/", 1)[-1]
    download_file(url, dest)

    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
        log.info("zip contents: %s", names)
        with zf.open(names[0]) as f:
            df = pd.read_csv(f, dtype=str)

    log.info("CBP county file: %d rows | columns=%s", len(df), list(df.columns))

    # Column names differ across CBP vintages (fipstate vs FIPSTATE etc.)
    cols = {c.lower(): c for c in df.columns}
    st_col, naics_col = cols.get("fipstate"), cols.get("naics")
    ok = validation.record(
        STAGE, "cbp_layout_has_state_and_naics",
        st_col is not None and naics_col is not None,
        f"state col={st_col}, naics col={naics_col}")
    if not ok:
        return 1

    va = df[df[st_col] == "51"]
    validation.record(STAGE, "cbp_va_rows_present", len(va) > 0,
                      f"{len(va)} VA rows, {va[cols['fipscty']].nunique()} counties")

    # CBP bulk-file NAICS coding (verified by inspection 2026-08-04):
    # all sectors = '------'; sector roots pad with dashes ('44----' covers
    # retail trade 44-45); subsectors pad with slashes ('447///', '722///').
    file_codes = {"00": "------", "447": "447///", "44-45": "44----", "722": "722///"}
    naics_raw = va[naics_col].astype(str)
    for code in load_config()["cbp"]["naics_codes"]:
        n = (naics_raw == file_codes[code]).sum()
        validation.record(STAGE, f"cbp_naics_{code}_present", n > 0,
                          f"{n} VA rows for NAICS {code} (file code {file_codes[code]!r})")

    record_manifest(dest.name, "US Census County Business Patterns 2023", url,
                    dest.stat().st_size, f"{len(df)} rows",
                    "complete US county file; NAICS2017 basis")
    return 0


if __name__ == "__main__":
    sys.exit(main())
