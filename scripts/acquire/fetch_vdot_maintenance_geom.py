"""Fetch geometry for VDOT segments filed under legacy maintenance areas.

VDOT files the South Hampton Roads interstate network under three historical
maintenance-area jurisdictions rather than under the modern independent
cities. Non-interstate roads in the same cities are filed under "City of X"
as normal, so the maintenance areas are the only place the interstate
mileage appears.

Mapping a whole maintenance area to one city is wrong. "Norfolk Maintenance
Area" is named for the former Norfolk County, which merged with South
Norfolk in 1963 to become Chesapeake, and its records carry labels in
Norfolk, Portsmouth and Chesapeake alike. Assigning all of it to Norfolk
city both inflates Norfolk and leaves Chesapeake and Portsmouth looking as
though they have no interstate at all.

Only 556 records are affected, so this script downloads their geometry and
assigns each segment to the county or city holding the greatest share of its
length. The result is a lookup consumed by scripts/clean/clean_vdot.py.

Output: data/raw/vdot_maintenance/segments.geojson
        data/processed/vdot_maintenance_geoid.parquet
"""

import json
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from scripts.utils.config import load_config
from scripts.utils.download import http_get, record_manifest
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW
from scripts.utils import validation

log = get_logger("fetch_vdot_maint")
STAGE = "stage2_acquire"

MAINTENANCE_AREAS = ["Norfolk Maintenance Area",
                     "Princess Anne Maintenance Area",
                     "Nansemond Maintenance Area"]


def main() -> int:
    cfg = load_config()
    url = cfg["vdot"]["feature_service_url"]
    crs_analysis = cfg["analysis"]["crs_analysis"]
    raw_dir = DATA_RAW / "vdot_maintenance"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "segments.geojson"

    where = "FROM_JURISDICTION IN ({})".format(
        ",".join(f"'{m}'" for m in MAINTENANCE_AREAS))

    if raw_path.exists() and raw_path.stat().st_size > 0:
        payload = json.loads(raw_path.read_text())
        log.info("using preserved download: %s", raw_path.name)
    else:
        resp = http_get(f"{url}/query", params={
            "where": where,
            "outFields": "OBJECTID,FROM_JURISDICTION,ROUTE_COMMON_NAME",
            "returnGeometry": "true", "outSR": "4326", "f": "json",
            "resultRecordCount": 5000,
        })
        payload = resp.json()
        raw_path.write_text(resp.text)

    feats = payload.get("features", [])
    log.info("downloaded %d maintenance-area segments with geometry", len(feats))

    rows = []
    for f in feats:
        paths = f.get("geometry", {}).get("paths") or []
        if not paths:
            continue
        # A record may hold several path parts; keep the longest.
        line = max((LineString(p) for p in paths if len(p) >= 2),
                   key=lambda g: g.length, default=None)
        if line is None:
            continue
        rows.append({**f["attributes"], "geometry": line})

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(crs_analysis)
    ok = validation.record(
        STAGE, "vdot_maint_geometry_downloaded", len(gdf) > 500,
        f"{len(gdf)} segments with usable geometry of {len(feats)} returned")

    counties = gpd.read_parquet(DATA_PROCESSED / "va_counties.geoparquet").to_crs(crs_analysis)
    # Assign each segment to the jurisdiction holding most of its length.
    parts = gpd.overlay(
        gdf[["OBJECTID", "FROM_JURISDICTION", "geometry"]],
        counties[["geoid", "county_name", "geometry"]],
        how="intersection", keep_geom_type=False)
    parts = parts[parts.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    parts["seg_len"] = parts.geometry.length
    best = (parts.sort_values("seg_len", ascending=False)
            .drop_duplicates("OBJECTID")[["OBJECTID", "geoid", "county_name",
                                          "FROM_JURISDICTION"]])

    ok &= validation.record(
        STAGE, "vdot_maint_segments_assigned",
        len(best) >= 0.95 * len(gdf),
        f"{len(best)} of {len(gdf)} segments assigned to a Virginia jurisdiction")

    spread = (best.groupby(["FROM_JURISDICTION", "county_name"]).size()
              .rename("segments").reset_index()
              .sort_values(["FROM_JURISDICTION", "segments"], ascending=[True, False]))
    log.info("maintenance area to jurisdiction split:\n%s", spread.to_string(index=False))
    # The whole point of this script: the split must not be one city per area.
    multi = spread.groupby("FROM_JURISDICTION")["county_name"].nunique()
    ok &= validation.record(
        STAGE, "vdot_maint_split_is_multi_city",
        bool((multi > 1).any()),
        f"jurisdictions per maintenance area: {multi.to_dict()}")

    best[["OBJECTID", "geoid"]].to_parquet(
        DATA_PROCESSED / "vdot_maintenance_geoid.parquet", index=False)
    record_manifest("vdot_maintenance/segments.geojson",
                    "VDOT Traffic Volume 2024, maintenance-area segments with geometry",
                    url, raw_path.stat().st_size, f"{len(feats)} segments",
                    "geometry fetched to resolve legacy maintenance areas to cities")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
