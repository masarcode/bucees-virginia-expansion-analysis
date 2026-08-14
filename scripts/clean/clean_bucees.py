"""Clean & spatially validate the compiled Buc-ee's locations.

Every point is joined against TIGER national counties; the derived state
must match the recorded state (catches geocoding errors). VA stores get
their county GEOID. Output: data/processed/bucees_locations.parquet
"""

import sys

import geopandas as gpd
import pandas as pd

from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW
from scripts.utils import validation

log = get_logger("clean_bucees")
STAGE = "stage3_clean"

VALID_STATUS = {"open", "under_construction", "announced"}


def main() -> int:
    df = pd.read_csv(DATA_RAW / "bucees" / "bucees_locations.csv", dtype=str)
    df["latitude"] = pd.to_numeric(df["latitude"])
    df["longitude"] = pd.to_numeric(df["longitude"])

    ok = validation.record(STAGE, "bucees_status_enum",
                           set(df["status"]) <= VALID_STATUS,
                           f"statuses: {sorted(set(df['status']))}")
    ok &= validation.record(STAGE, "bucees_coords_present",
                            df[["latitude", "longitude"]].notna().all().all(), "")
    ok &= validation.record(STAGE, "bucees_sources_present",
                            (df["source_url"].str.startswith("http")).all(), "")

    counties = gpd.read_file(f"zip://{DATA_RAW / 'tiger' / 'cb_2023_us_county_500k.zip'}")
    pts = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326").to_crs(counties.crs)
    joined = gpd.sjoin(pts, counties[["GEOID", "STUSPS", "NAMELSAD", "geometry"]],
                       how="left", predicate="within")

    state_match = (joined["STUSPS"] == joined["state"])
    ok &= validation.record(
        STAGE, "bucees_point_in_expected_state", state_match.all(),
        f"mismatches: {joined.loc[~state_match, ['city', 'state', 'STUSPS']].to_dict('records')}")

    joined["county_geoid"] = joined["GEOID"]
    joined["county_name"] = joined["NAMELSAD"]

    mc = joined[joined["city"] == "Mount Crawford"]
    ok &= validation.record(
        STAGE, "bucees_mount_crawford_in_rockingham",
        (mc["county_geoid"] == "51165").all(),
        f"derived county: {mc['county_name'].tolist()}")

    out = pd.DataFrame(joined.drop(columns=["geometry", "index_right", "GEOID",
                                            "STUSPS", "NAMELSAD"]))
    out.to_parquet(DATA_PROCESSED / "bucees_locations.parquet", index=False)
    log.info("wrote bucees_locations.parquet: %d rows (%s)", len(out),
             out["status"].value_counts().to_dict())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
