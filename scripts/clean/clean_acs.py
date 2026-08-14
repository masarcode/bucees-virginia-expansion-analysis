"""Clean ACS 5-year demographics for both study periods into one tidy table.

2019-2023: table-based .dat files. Column naming: API code B23025_002E maps
to file column B23025_E002 (verified by inspection).
2014-2018: legacy sequence files. Cell location = lookup 'Start Position'
+ line number - 1, 1-based over the whole row (identifiers occupy
positions 1-6; first data cell is position 7 - confirmed by B11001's
start position of 7).

ACS missing-data sentinels (negative jam values like -666666666, or '.')
are converted to NULL and counted. Controlled-estimate margin sentinel
-555555555 does not occur here because margins are not retained.

Output: data/processed/demographics.parquet, one row per (geoid, period).
"""

import sys
import zipfile

import numpy as np
import pandas as pd

from scripts.utils.config import load_config
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW
from scripts.utils import validation

log = get_logger("clean_acs")
STAGE = "stage3_clean"

JAM_THRESHOLD = -222222221  # any value <= this is an ACS sentinel, not data


def parse_var(code: str) -> tuple[str, int]:
    """'B23025_002E' -> ('B23025', 2)"""
    table, rest = code.split("_")
    return table, int(rest[:3])


def clean_numeric(s: pd.Series) -> pd.Series:
    out = pd.to_numeric(s.replace(".", np.nan), errors="coerce")
    return out.mask(out <= JAM_THRESHOLD)


def load_2023(cfg) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (county_df, state_row_df) for 2019-2023."""
    variables = cfg["acs"]["variables"]
    county_parts, state_parts = [], []
    for code, friendly in variables.items():
        table, line = parse_var(code)
        path = DATA_RAW / "acs_2023" / f"acsdt5y2023-{table.lower()}.dat"
        col = f"{table}_E{line:03d}"
        df = pd.read_csv(path, sep="|", dtype=str, usecols=["GEO_ID", col])
        county = df[df["GEO_ID"].str.startswith("0500000US51")].copy()
        county["geoid"] = county["GEO_ID"].str[-5:]
        county[friendly] = clean_numeric(county[col])
        county_parts.append(county.set_index("geoid")[[friendly]])
        state = df[df["GEO_ID"] == "0400000US51"]
        state_parts.append(pd.DataFrame(
            {friendly: clean_numeric(state[col]).values}))
    out = pd.concat(county_parts, axis=1).reset_index()
    out["acs_period"] = "2019-2023"
    return out, pd.concat(state_parts, axis=1)


def load_2018(cfg) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (county_df, state_row_df) for 2014-2018 from sequence files."""
    variables = cfg["acs"]["variables"]
    raw = DATA_RAW / "acs_2018"

    lookup = pd.read_csv(raw / "ACS_5yr_Seq_Table_Number_Lookup.txt",
                         dtype=str, encoding="latin-1")
    lookup.columns = [c.strip() for c in lookup.columns]
    starts = lookup.dropna(subset=["Start Position"]).copy()
    starts["table_id"] = starts["Table ID"].str.strip()
    starts = starts.set_index("table_id")[["Sequence Number", "Start Position"]]

    geo = pd.read_csv(raw / "g20185va.csv", dtype=str, header=None, encoding="latin-1")
    counties = geo[geo[2] == "050"][[4, 48]].rename(columns={4: "logrecno", 48: "geo_id"})
    counties["geoid"] = counties["geo_id"].str[-5:]
    state_logrec = geo[geo[2] == "040"][4].iloc[0]

    county_parts, state_parts = [], []
    seq_cache: dict[int, pd.DataFrame] = {}
    for code, friendly in variables.items():
        table, line = parse_var(code)
        seq = int(starts.loc[table, "Sequence Number"])
        start = int(starts.loc[table, "Start Position"])
        if seq not in seq_cache:
            zpath = raw / f"20185va{seq:04d}000.zip"
            with zipfile.ZipFile(zpath) as zf:
                with zf.open(f"e20185va{seq:04d}000.txt") as f:
                    seq_cache[seq] = pd.read_csv(f, dtype=str, header=None)
        edf = seq_cache[seq]
        col_idx = start + line - 2  # 1-based position -> 0-based iloc
        sub = edf[[5, col_idx]].rename(columns={5: "logrecno", col_idx: friendly})
        sub["logrecno"] = sub["logrecno"].str.zfill(7)
        sub[friendly] = clean_numeric(sub[friendly])
        merged = counties.merge(sub, on="logrecno", how="left")
        county_parts.append(merged.set_index("geoid")[[friendly]])
        state_val = sub[sub["logrecno"] == state_logrec][friendly]
        state_parts.append(pd.DataFrame({friendly: state_val.values}))

    out = pd.concat(county_parts, axis=1).reset_index()
    out["acs_period"] = "2014-2018"
    return out, pd.concat(state_parts, axis=1)


def validate_period(df: pd.DataFrame, state: pd.DataFrame, period: str) -> bool:
    ok = validation.record(STAGE, f"acs_{period}_row_count", len(df) == 133,
                           f"{len(df)} county rows")
    ok &= validation.record(STAGE, f"acs_{period}_geoid_unique",
                            df["geoid"].is_unique, "")
    # Additive totals must reconcile with the state row in the same file.
    for var in ("total_population", "households"):
        county_sum = df[var].sum()
        state_val = state[var].iloc[0]
        match = abs(county_sum - state_val) < 1e-6
        ok &= validation.record(STAGE, f"acs_{period}_{var}_sums_to_state", match,
                                f"counties={county_sum:.0f} vs state={state_val:.0f}")
    ok &= validation.record(
        STAGE, f"acs_{period}_income_range",
        df["median_hh_income"].dropna().between(20_000, 250_000).all(),
        f"min={df['median_hh_income'].min():.0f} max={df['median_hh_income'].max():.0f}")
    ok &= validation.record(
        STAGE, f"acs_{period}_median_age_range",
        df["median_age"].dropna().between(18, 65).all(),
        f"min={df['median_age'].min():.1f} max={df['median_age'].max():.1f}")
    missing = df.drop(columns=["geoid", "acs_period"]).isna().sum()
    validation.record(STAGE, f"acs_{period}_missing_values",
                      missing.sum() == 0, f"{dict(missing[missing > 0])}",
                      warn_only=True)
    return ok


def main() -> int:
    cfg = load_config()
    cur, cur_state = load_2023(cfg)
    pri, pri_state = load_2018(cfg)

    ok = validate_period(cur, cur_state, "2019-2023")
    ok &= validate_period(pri, pri_state, "2014-2018")

    # Cross-period sanity: county populations should be highly correlated.
    merged = cur.merge(pri, on="geoid", suffixes=("_cur", "_pri"))
    corr = merged["total_population_cur"].corr(merged["total_population_pri"])
    ok &= validation.record(STAGE, "acs_crossperiod_pop_correlation", corr > 0.98,
                            f"r={corr:.4f}")

    out = pd.concat([cur, pri], ignore_index=True)
    cols = ["geoid", "acs_period"] + list(cfg["acs"]["variables"].values())
    out = out[cols]
    out.to_parquet(DATA_PROCESSED / "demographics.parquet", index=False)
    log.info("wrote demographics.parquet: %d rows (%s)", len(out),
             out["acs_period"].value_counts().to_dict())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
