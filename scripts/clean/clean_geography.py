"""Clean TIGER geography → analysis-ready layers.

Outputs (data/processed/):
- va_counties.geoparquet : 133 VA county-equivalents with standardized
  columns + geometry (EPSG:4269 as shipped)
- geography.parquet      : attribute table for the DB geography table
- interstates_region.geoparquet : TIGER primary-roads interstates within
  a 100-mile buffer of Virginia (border interstates matter for
  accessibility of edge counties)
"""

import sys

import geopandas as gpd

from scripts.utils.config import load_config
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW
from scripts.utils import validation

log = get_logger("clean_geography")
STAGE = "stage3_clean"
SQM_PER_SQMI = 2_589_988.110336


def main() -> int:
    cfg = load_config()
    crs_analysis = cfg["analysis"]["crs_analysis"]
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    counties = gpd.read_file(f"zip://{DATA_RAW / 'tiger' / 'cb_2023_us_county_500k.zip'}")
    va = counties[counties["STATEFP"] == "51"].copy()

    # Standardize attributes. NAMELSAD distinguishes 'Richmond County' from
    # 'Richmond city' - required because VA has 5 such name collisions.
    va["geoid"] = va["GEOID"]
    va["county_name"] = va["NAMELSAD"]
    va["state_fips"] = va["STATEFP"]
    va["county_fips"] = va["COUNTYFP"]
    va["is_independent_city"] = (va["COUNTYFP"].astype(int) >= 510).astype(int)
    va["aland_sqmi"] = va["ALAND"].astype(float) / SQM_PER_SQMI
    va["awater_sqmi"] = va["AWATER"].astype(float) / SQM_PER_SQMI

    # Centroids computed in the metric analysis CRS, reported in EPSG:4326.
    cent = va.geometry.to_crs(crs_analysis).centroid.to_crs("EPSG:4326")
    va["centroid_lat"] = cent.y
    va["centroid_lon"] = cent.x

    ok = validation.record(STAGE, "geo_va_count", len(va) == 133, f"{len(va)} rows")
    ok &= validation.record(STAGE, "geo_geoid_unique", va["geoid"].is_unique, "")
    ok &= validation.record(STAGE, "geo_all_geoids_va",
                            va["geoid"].str.startswith("51").all(), "")
    ok &= validation.record(STAGE, "geo_valid_geometry", va.geometry.is_valid.all(),
                            f"{(~va.geometry.is_valid).sum()} invalid")
    ok &= validation.record(STAGE, "geo_independent_city_count",
                            int(va["is_independent_city"].sum()) == 38,
                            f"{int(va['is_independent_city'].sum())} independent cities (expected 38)")
    ok &= validation.record(
        STAGE, "geo_centroids_in_va_bbox",
        va["centroid_lat"].between(36.4, 39.6).all()
        and va["centroid_lon"].between(-83.8, -75.1).all(), "")

    keep = ["geoid", "county_name", "state_fips", "county_fips",
            "is_independent_city", "aland_sqmi", "awater_sqmi",
            "centroid_lat", "centroid_lon"]
    va[keep + ["geometry"]].to_parquet(DATA_PROCESSED / "va_counties.geoparquet")
    va[keep].to_parquet(DATA_PROCESSED / "geography.parquet", index=False)

    # Interstates within 100 miles of VA (for edge-county accessibility).
    roads = gpd.read_file(f"zip://{DATA_RAW / 'tiger' / 'tl_2023_us_primaryroads.zip'}")
    interstates = roads[roads["RTTYP"] == "I"].to_crs(crs_analysis)
    va_buffer = va.to_crs(crs_analysis).union_all().buffer(100 * 1609.344)
    region = interstates[interstates.intersects(va_buffer)]
    region[["FULLNAME", "RTTYP", "geometry"]].to_parquet(
        DATA_PROCESSED / "interstates_region.geoparquet")
    ok &= validation.record(STAGE, "geo_region_interstates_nonempty",
                            len(region) > 0, f"{len(region)} interstate features in VA+100mi")
    has_81 = region["FULLNAME"].str.contains("81", na=False).any()
    has_95 = region["FULLNAME"].str.contains("95", na=False).any()
    ok &= validation.record(STAGE, "geo_region_has_I81_I95", has_81 and has_95,
                            f"I-81 present={has_81}, I-95 present={has_95}")

    log.info("wrote va_counties.geoparquet (%d), geography.parquet, "
             "interstates_region.geoparquet (%d)", len(va), len(region))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
