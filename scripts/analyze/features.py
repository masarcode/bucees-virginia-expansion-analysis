"""Spatial features per county (used by EDA and the scoring model):

- dist_interstate_mi : county centroid → nearest interstate centerline
  (TIGER primary roads within VA+100mi, so border interstates count)
- dist_open_bucees_mi: centroid → nearest OPEN Buc-ee's store
- dist_any_bucees_mi : centroid → nearest open/under-construction/announced

Distances computed in EPSG:26918 (meters), reported in miles.
Output: data/processed/spatial_features.parquet
"""

import sys

import geopandas as gpd
import pandas as pd

from scripts.utils.config import load_config
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED
from scripts.utils import validation

log = get_logger("features")
STAGE = "stage5_eda"
METERS_PER_MILE = 1609.344


def build() -> pd.DataFrame:
    cfg = load_config()
    crs = cfg["analysis"]["crs_analysis"]

    counties = gpd.read_parquet(DATA_PROCESSED / "va_counties.geoparquet").to_crs(crs)
    centroids = counties.geometry.centroid
    interstates = gpd.read_parquet(DATA_PROCESSED / "interstates_region.geoparquet").to_crs(crs)
    inter_union = interstates.union_all()

    bucees = pd.read_parquet(DATA_PROCESSED / "bucees_locations.parquet")
    stores = gpd.GeoDataFrame(
        bucees, geometry=gpd.points_from_xy(bucees["longitude"], bucees["latitude"]),
        crs="EPSG:4326").to_crs(crs)
    open_union = stores[stores["status"] == "open"].union_all()
    any_union = stores.union_all()

    # Whether an interstate physically crosses the jurisdiction, independent
    # of whether VDOT's traffic extract happens to carry a record for it.
    # The two differ: VDOT's 2024 extract has no I-64 mainline records for
    # Newport News or Hampton, though I-64 plainly runs through both. This
    # flag keeps a data gap from being reported as an absence of interstate.
    crosses = counties.geometry.intersects(inter_union)

    out = pd.DataFrame({
        "geoid": counties["geoid"].values,
        "dist_interstate_mi": centroids.distance(inter_union) / METERS_PER_MILE,
        "dist_open_bucees_mi": centroids.distance(open_union) / METERS_PER_MILE,
        "dist_any_bucees_mi": centroids.distance(any_union) / METERS_PER_MILE,
        "interstate_crosses_county": crosses.values,
    })
    return out


def main() -> int:
    out = build()
    ok = validation.record(STAGE, "features_row_count", len(out) == 133,
                           f"{len(out)} rows")
    ok &= validation.record(STAGE, "features_no_missing",
                            out.notna().all().all(), "")
    # Rockingham County hosts the Mount Crawford store: its centroid must be
    # very close to an open store; and every distance must be < 600 mi.
    rock = out.loc[out["geoid"] == "51165", "dist_open_bucees_mi"].iloc[0]
    ok &= validation.record(STAGE, "features_rockingham_near_open_store",
                            rock < 25, f"{rock:.1f} mi")
    ok &= validation.record(STAGE, "features_distances_plausible",
                            (out["dist_any_bucees_mi"] < 600).all()
                            and (out["dist_interstate_mi"] < 120).all(),
                            f"max interstate dist {out['dist_interstate_mi'].max():.1f} mi; "
                            f"max bucees dist {out['dist_any_bucees_mi'].max():.1f} mi")
    n_cross = int(out["interstate_crosses_county"].sum())
    ok &= validation.record(STAGE, "features_interstate_crossing_plausible",
                            40 <= n_cross <= 70,
                            f"{n_cross} of 133 jurisdictions are crossed by a "
                            f"TIGER interstate")
    out.to_parquet(DATA_PROCESSED / "spatial_features.parquet", index=False)
    log.info("wrote spatial_features.parquet (%d rows)", len(out))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
