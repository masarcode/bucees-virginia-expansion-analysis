"""Acquire TIGER/Line geography: US county cartographic boundaries (500k)
and national primary roads. Downloads to data/raw/tiger/, inspects each
shapefile (driver, CRS, feature count, columns), records the manifest.
Raw zips are preserved as downloaded."""

import sys

import geopandas as gpd

from scripts.utils.config import load_config
from scripts.utils.download import download_file, record_manifest
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_RAW
from scripts.utils import validation

log = get_logger("fetch_tiger")
STAGE = "stage2_acquire"


def main() -> int:
    cfg = load_config()["tiger"]
    dest_dir = DATA_RAW / "tiger"

    for label, url in [("counties", cfg["counties_url"]),
                       ("primary_roads", cfg["primary_roads_url"]),
                       ("va_places", cfg["va_places_url"])]:
        dest = dest_dir / url.rsplit("/", 1)[-1]
        download_file(url, dest)

        gdf = gpd.read_file(f"zip://{dest}")
        log.info("%s: %d features | CRS=%s | columns=%s",
                 label, len(gdf), gdf.crs, list(gdf.columns))

        if label == "counties":
            va = gdf[gdf["STATEFP"] == "51"]
            ok = validation.record(
                STAGE, "tiger_va_county_count", len(va) == 133,
                f"{len(va)} VA county-equivalents (expected 133)")
            if not ok:
                return 1
            validation.record(
                STAGE, "tiger_counties_geoid_unique",
                gdf["GEOID"].is_unique, f"{gdf['GEOID'].nunique()}/{len(gdf)} unique")
        elif label == "primary_roads":
            rttyps = gdf["RTTYP"].value_counts(dropna=False).to_dict()
            log.info("primary roads RTTYP distribution: %s", rttyps)
            validation.record(
                STAGE, "tiger_primary_roads_has_interstates",
                (gdf["RTTYP"] == "I").sum() > 0,
                f"{(gdf['RTTYP'] == 'I').sum()} interstate features nationally")
        elif label == "va_places":
            lsads = gdf["LSAD"].value_counts(dropna=False).to_dict()
            log.info("VA places LSAD distribution: %s", lsads)
            validation.record(
                STAGE, "tiger_va_places_has_towns", (gdf["LSAD"] == "43").sum() > 100,
                f"{(gdf['LSAD'] == '43').sum()} incorporated towns (LSAD 43)")

        record_manifest(dest.name, "US Census TIGER/Line", url,
                        dest.stat().st_size, f"{len(gdf)} features",
                        f"{label}; CRS={gdf.crs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
