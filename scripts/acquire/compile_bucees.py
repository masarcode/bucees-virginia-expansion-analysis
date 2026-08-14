"""Compile Buc-ee's locations relevant to the Virginia analysis.

Buc-ee's publishes no machine-readable location list, so records are
compiled from the official location page and news coverage; every row
carries its source URL and access date. Scope: all official stores EAST of
the Mississippi River plus announced/under-construction sites near
Virginia. West-of-Mississippi stores (31 TX + AZ/CO/MO on the official
page) are excluded - the nearest is >900 miles from Virginia and cannot
influence any VA county's overlap metric (assumption A6).

Coordinates come from Nominatim (OpenStreetMap) POI/address geocoding with
documented fallback queries; every raw geocoder response is preserved in
data/raw/bucees/geocode/. Output: data/raw/bucees/bucees_locations.csv.
"""

import csv
import json
import sys
import time

from scripts.utils.download import http_get, record_manifest
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_RAW
from scripts.utils import validation

log = get_logger("compile_bucees")
STAGE = "stage2_acquire"

OFFICIAL = "https://buc-ees.com/locations/"
ACCESSED = "2026-08-03"

# (store_no, city_label, state, address, status, opened_date, source_url)
# All "open" rows: official location page. Announced rows: cited news.
RECORDS = [
    ("57", "Athens", "AL", "2328 Lindsay Lane South, Athens, AL", "open", "", OFFICIAL),
    ("58", "Auburn", "AL", "2500 Buc-ee's Blvd, Auburn, AL", "open", "", OFFICIAL),
    ("43", "Leeds", "AL", "6900 Buc-ee's Blvd, Leeds, AL", "open", "", OFFICIAL),
    ("42", "Loxley", "AL", "20403 County Rd. 68, Robertsdale, AL", "open", "", OFFICIAL),
    ("47", "Daytona Beach", "FL", "2330 Gateway North Drive, Daytona Beach, FL", "open", "", OFFICIAL),
    ("46", "Saint Augustine", "FL", "200 World Commerce Pkwy, Saint Augustine, FL", "open", "", OFFICIAL),
    ("63", "Brunswick", "GA", "6900 Hwy 99, Brunswick, GA", "open", "", OFFICIAL),
    ("52", "Calhoun", "GA", "601 Union Grove Rd. SE, Adairsville, GA", "open", "", OFFICIAL),
    ("51", "Warner Robins", "GA", "7001 Russell Parkway, Fort Valley, GA", "open", "", OFFICIAL),
    ("55", "Richmond", "KY", "1013 Buc-ee's Boulevard, Richmond, KY", "open", "", OFFICIAL),
    ("56", "Smiths Grove", "KY", "4001 Smiths Grove-Scottsville Road, Smiths Grove, KY", "open", "", OFFICIAL),
    ("61", "Pass Christian", "MS", "8245 Firetower Road, Pass Christian, MS", "open", "", OFFICIAL),
    ("71", "Huber Heights", "OH", "8000 State Route 235, Huber Heights, OH", "open", "", OFFICIAL),
    ("53", "Florence", "SC", "3390 North Williston Road, Florence, SC", "open", "", OFFICIAL),
    ("50", "Crossville", "TN", "2045 Genesis Road, Crossville, TN", "open", "", OFFICIAL),
    ("45", "Sevierville", "TN", "170 Buc-ee's Blvd, Kodak, TN", "open", "", OFFICIAL),
    ("69", "Mount Crawford", "VA", "6500 Buc-ee's Blvd, Mount Crawford, VA", "open",
     "2025-06-30", "https://virginiabusiness.com/virginia-buc-ees-opening-mount-crawford/"),
    ("", "Stafford", "VA", "Courthouse Road and Austin Ridge Drive, Stafford, VA (I-95 Exit 140)",
     "announced", "",
     "https://www.potomaclocal.com/2026/05/20/beaver-fever-sweeps-stafford-supervisors-approve-buc-ees/"),
    ("", "New Kent", "VA", "I-64 Exit 211, New Kent County, VA", "announced", "",
     "https://virginiabusiness.com/buc-ees-pushes-new-kent-location-opening-2031/"),
    ("", "Mebane", "NC", "1425 Trollingwood-Hawfields Road, Mebane, NC", "under_construction", "",
     "https://www.cstoredive.com/news/buc-ees-breaks-ground-in-north-carolina/822421/"),
]

STATE_NAMES = {
    "AL": "Alabama", "FL": "Florida", "GA": "Georgia", "KY": "Kentucky",
    "MS": "Mississippi", "OH": "Ohio", "SC": "South Carolina",
    "TN": "Tennessee", "VA": "Virginia", "NC": "North Carolina",
}

NOMINATIM = "https://nominatim.openstreetmap.org/search"


def geocode_queries(city: str, state: str, address: str, status: str) -> list[str]:
    """Ordered queries: POI first for open stores, then address, then city."""
    q = []
    if status == "open":
        q.append(f"Buc-ee's, {city}, {STATE_NAMES[state]}")
    if address and not address.startswith("I-"):
        q.append(f"{address.split('(')[0].strip()}")
    q.append(f"{city}, {STATE_NAMES[state]}")
    return q


def geocode(row_id: str, queries: list[str], state: str, cache_dir) -> tuple:
    """Try queries in order; return (lat, lon, matched_query, precision)."""
    for i, query in enumerate(queries):
        cache = cache_dir / f"{row_id}_{i}.json"
        if cache.exists():
            results = json.loads(cache.read_text())
        else:
            resp = http_get(NOMINATIM, params={"q": query, "format": "json", "limit": 3})
            results = resp.json()
            cache.write_text(json.dumps(results, indent=1))
            time.sleep(1.1)  # Nominatim usage policy: max 1 req/s
        for r in results:
            if STATE_NAMES[state] in r.get("display_name", ""):
                precision = "poi" if "Buc-ee" in r.get("display_name", "") else (
                    "address" if i < len(queries) - 1 else "city")
                return float(r["lat"]), float(r["lon"]), query, precision
    return None, None, None, None


def main() -> int:
    out_dir = DATA_RAW / "bucees"
    cache_dir = out_dir / "geocode"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "bucees_locations.csv"

    rows, failures = [], []
    for store_no, city, state, address, status, opened, source in RECORDS:
        row_id = f"{state}_{city}".replace(" ", "_").lower()
        lat, lon, matched, precision = geocode(
            row_id, geocode_queries(city, state, address, status), state, cache_dir)
        if lat is None:
            failures.append(row_id)
            log.error("geocode FAILED: %s", row_id)
        else:
            log.info("%-22s -> %.4f, %.4f (%s)", row_id, lat, lon, precision)
        rows.append({
            "store_number": store_no, "city": city, "state": state,
            "address": address, "status": status, "opened_date": opened,
            "latitude": lat, "longitude": lon,
            "geocode_precision": precision, "geocode_query": matched,
            "source_url": source, "accessed_date": ACCESSED,
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    ok = validation.record(STAGE, "bucees_all_rows_geocoded", not failures,
                           f"{len(rows) - len(failures)}/{len(rows)} geocoded; failures: {failures}")
    va = [r for r in rows if r["state"] == "VA"]
    ok &= validation.record(STAGE, "bucees_va_locations", len(va) == 3,
                            f"{len(va)} VA rows (expect Mount Crawford open + Stafford, New Kent announced)")
    record_manifest("bucees/bucees_locations.csv",
                    "Compiled: buc-ees.com/locations + cited news", OFFICIAL,
                    out_csv.stat().st_size, f"{len(rows)} locations",
                    "east-of-Mississippi scope; Nominatim geocoded (raw responses kept)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
