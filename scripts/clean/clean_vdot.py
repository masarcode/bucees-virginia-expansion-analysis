"""Clean VDOT 2024 traffic segments → county traffic_summary.

- County assignment: FROM_JURISDICTION name → GEOID ('City of Roanoke' →
  'Roanoke city'; 'Warren County' as-is), matched against TIGER NAMELSAD.
  Special cases (verified by inspection 2026-08-04):
    * 'Accomac County' = VDOT's historical spelling of Accomack County.
    * Maintenance areas named for pre-consolidation jurisdictions map to
      their successor cities: Norfolk MA → Norfolk city; Princess Anne MA →
      Virginia Beach city (county absorbed 1963); Nansemond MA → Suffolk
      city (merged 1974). These rows carry the I-64/I-264 urban segments.
    * 'Town of X' (47 towns, 2,213 rows): Virginia towns are county
      subdivisions; each is assigned to the county holding the largest
      share of the town polygon's area (TIGER VA places, LSAD 47).
    * 'Statewide' (149 rows, e.g. VA-267 Dulles Toll Road): not
      attributable to one county - dropped, counted, documented (A10).
- Interstate mainline: ROUTE_COMMON_NAME starts 'I-<digits>' and is not a
  ramp/rest area/weigh station/other facility (rules logged & validated).
- Lengths: Shape__Length is EPSG:3857 meters; corrected by cos(latitude)
  of the county centroid (Web Mercator inflation ~26% at VA latitudes),
  then converted to miles (assumption A8).
- vmt_proxy = Σ(ADT × corrected miles) over segments with ADT.

Output: data/processed/traffic_summary.parquet
"""

import json
import re
import sys

import numpy as np
import pandas as pd

from scripts.utils.config import load_config
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_PROCESSED, DATA_RAW
from scripts.utils import validation

log = get_logger("clean_vdot")
STAGE = "stage3_clean"

MAINLINE_RE = re.compile(r"^I-\d+")
NON_MAINLINE_TOKENS = ("ramp", "rest area", "weigh", "scale", "welcome",
                       "wayside", "parking", "turnaround", "crossover", "cd ")
METERS_PER_MILE = 1609.344

ALIASES = {
    "Accomac County": "Accomack County",
}
DROP_JURISDICTIONS = {"Statewide"}

# VDOT files the South Hampton Roads interstate network under these legacy
# maintenance areas rather than under the modern independent cities. Each
# area spans several cities, so segments are resolved individually from
# geometry (see scripts/acquire/fetch_vdot_maintenance_geom.py) rather than
# by mapping a whole area to one city.
MAINTENANCE_AREAS = {"Norfolk Maintenance Area",
                     "Princess Anne Maintenance Area",
                     "Nansemond Maintenance Area"}


def jurisdiction_to_name(j: str) -> str | None:
    if not isinstance(j, str) or not j.strip():
        return None
    j = j.strip()
    if j in DROP_JURISDICTIONS or j in MAINTENANCE_AREAS:
        return None
    if j in ALIASES:
        return ALIASES[j]
    if j.lower().startswith("city of "):
        return j[8:].strip() + " city"
    return j


def resolve_geoids(df: pd.DataFrame) -> pd.Series:
    """Resolve every VDOT record to a county GEOID.

    Ordinary jurisdiction names go through the name rules. Records filed
    under a legacy maintenance area are matched individually against the
    geometry-derived lookup, because those areas span several cities."""
    cfg = load_config()
    geography = pd.read_parquet(DATA_PROCESSED / "geography.parquet")
    name_to_geoid = dict(zip(geography["county_name"], geography["geoid"]))
    towns = town_to_county(cfg["analysis"]["crs_analysis"])

    def by_name(j):
        if isinstance(j, str) and j.strip() in towns:
            return name_to_geoid.get(towns[j.strip()])
        name = jurisdiction_to_name(j)
        return name_to_geoid.get(name) if name else None

    geoids = df["FROM_JURISDICTION"].map(by_name)

    maint_path = DATA_PROCESSED / "vdot_maintenance_geoid.parquet"
    if maint_path.exists() and "OBJECTID" in df.columns:
        lookup = pd.read_parquet(maint_path).set_index("OBJECTID")["geoid"]
        is_maint = df["FROM_JURISDICTION"].isin(MAINTENANCE_AREAS)
        geoids = geoids.mask(is_maint, df["OBJECTID"].map(lookup))
        log.info("resolved %d maintenance-area records from geometry",
                 int(is_maint.sum()))
    return geoids


def town_to_county(crs_analysis: str) -> dict[str, str]:
    """Map 'Town of X' → county NAMELSAD via largest-area overlap of the
    town polygon (TIGER VA incorporated places) with county polygons."""
    import geopandas as gpd

    places = gpd.read_file(f"zip://{DATA_RAW / 'tiger' / 'cb_2023_51_place_500k.zip'}")
    towns = places[places["LSAD"] == "43"].to_crs(crs_analysis)  # 43 = town
    counties = gpd.read_parquet(DATA_PROCESSED / "va_counties.geoparquet").to_crs(crs_analysis)

    overlay = gpd.overlay(towns[["NAME", "geometry"]],
                          counties[["county_name", "geometry"]], how="intersection")
    overlay["area"] = overlay.geometry.area
    best = (overlay.sort_values("area", ascending=False)
            .drop_duplicates("NAME").set_index("NAME")["county_name"])
    return {f"Town of {name}": county for name, county in best.items()}


def main() -> int:
    cfg = load_config()
    year = int(cfg["vdot"]["publication_year"])

    pages = sorted((DATA_RAW / "vdot").glob("page_*.json"))
    frames = [pd.DataFrame([f["attributes"] for f in json.loads(p.read_text())["features"]])
              for p in pages]
    df = pd.concat(frames, ignore_index=True)
    log.info("loaded %d segments from %d pages", len(df), len(pages))

    geography = pd.read_parquet(DATA_PROCESSED / "geography.parquet")
    lat_by_geoid = dict(zip(geography["geoid"], geography["centroid_lat"]))

    df["geoid"] = resolve_geoids(df)

    named = df["FROM_JURISDICTION"].map(jurisdiction_to_name)
    unmapped = df[df["geoid"].isna() & named.notna()]
    unmapped_names = unmapped["FROM_JURISDICTION"].value_counts()
    ok = validation.record(STAGE, "vdot_jurisdictions_mapped", len(unmapped_names) == 0,
                           f"unmapped names: {dict(unmapped_names.head(10))}")
    n_maint = int(df["FROM_JURISDICTION"].isin(MAINTENANCE_AREAS).sum())
    ok &= validation.record(
        STAGE, "vdot_maintenance_areas_resolved",
        int(df.loc[df["FROM_JURISDICTION"].isin(MAINTENANCE_AREAS), "geoid"].notna().sum()) == n_maint,
        f"{n_maint} legacy maintenance-area records resolved from geometry")
    n_dropped = int(df["FROM_JURISDICTION"].isin(DROP_JURISDICTIONS).sum())
    n_null = int(df["FROM_JURISDICTION"].isna().sum())
    validation.record(STAGE, "vdot_dropped_rows",
                      (n_dropped + n_null) < len(df) * 0.01,
                      f"{n_dropped} 'Statewide' + {n_null} null-jurisdiction rows dropped",
                      warn_only=True)
    df = df.dropna(subset=["geoid"]).copy()

    name = df["ROUTE_COMMON_NAME"].fillna("")
    is_interstate_route = name.str.match(MAINLINE_RE)
    lname = name.str.lower()
    is_facility = lname.str.contains("|".join(re.escape(t) for t in NON_MAINLINE_TOKENS))
    df["is_interstate_mainline"] = is_interstate_route & ~is_facility
    n_main = int(df["is_interstate_mainline"].sum())
    n_facility = int((is_interstate_route & is_facility).sum())
    ok &= validation.record(STAGE, "vdot_mainline_classification", n_main > 500,
                            f"{n_main} mainline, {n_facility} interstate facility "
                            f"(ramps/rest areas) of {int(is_interstate_route.sum())} I- rows")

    lat = df["geoid"].map(lat_by_geoid)
    df["length_mi"] = df["Shape__Length"] * np.cos(np.radians(lat)) / METERS_PER_MILE
    df["adt"] = pd.to_numeric(df["ADT"], errors="coerce")
    df["vmt_part"] = (df["adt"] * df["length_mi"]).where(df["adt"].notna())

    main_seg = df[df["is_interstate_mainline"]]
    agg = df.groupby("geoid").agg(
        segment_count=("adt", "size"),
        max_aadt=("adt", "max"),
        mean_aadt=("adt", "mean"),
        vmt_proxy=("vmt_part", "sum"),
    )
    agg["interstate_max_aadt"] = main_seg.groupby("geoid")["adt"].max()
    agg["interstate_miles"] = main_seg.groupby("geoid")["length_mi"].sum()
    agg = agg.reset_index()
    agg["year"] = year

    covered = set(agg["geoid"])
    missing = sorted(set(geography["geoid"]) - covered)
    missing_names = geography[geography["geoid"].isin(missing)]["county_name"].tolist()
    validation.record(STAGE, "vdot_county_coverage", len(missing) == 0,
                      f"{len(covered)}/133; no VDOT segments for: {missing_names}",
                      warn_only=True)
    statewide_max = agg["max_aadt"].max()
    ok &= validation.record(STAGE, "vdot_max_aadt_plausible",
                            100_000 < statewide_max < 500_000,
                            f"statewide max AADT = {statewide_max:,.0f}")
    ok &= validation.record(STAGE, "vdot_pk_unique",
                            not agg.duplicated(["geoid", "year"]).any(), "")

    cols = ["geoid", "year", "segment_count", "max_aadt", "mean_aadt",
            "interstate_max_aadt", "interstate_miles", "vmt_proxy"]
    agg[cols].to_parquet(DATA_PROCESSED / "traffic_summary.parquet", index=False)
    log.info("wrote traffic_summary.parquet: %d counties; interstate counties: %d",
             len(agg), agg["interstate_max_aadt"].notna().sum())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
