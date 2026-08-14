"""Acquire VDOT Traffic Volume (2024 publication) segment attributes from
the ArcGIS feature service. Geometry is NOT downloaded - county assignment
uses FROM_JURISDICTION and lengths come from Shape__Length; interstate
accessibility geometry comes from TIGER primary roads instead.

Each 2000-record page is preserved exactly as received in
data/raw/vdot/page_NNN.json, plus the service metadata."""

import json
import sys

from scripts.utils.config import load_config
from scripts.utils.download import http_get, record_manifest
from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_RAW
from scripts.utils import validation

log = get_logger("fetch_vdot")
STAGE = "stage2_acquire"


def main() -> int:
    cfg = load_config()["vdot"]
    url = cfg["feature_service_url"]
    page_size = int(cfg["page_size"])
    dest_dir = DATA_RAW / "vdot"
    dest_dir.mkdir(parents=True, exist_ok=True)

    meta = http_get(f"{url}?f=pjson").json()
    (dest_dir / "service_metadata.json").write_text(json.dumps(meta, indent=1))
    log.info("service: %s | fields: %d", meta.get("name"), len(meta.get("fields", [])))

    expected = http_get(f"{url}/query", params={
        "where": "1=1", "returnCountOnly": "true", "f": "json"}).json()["count"]
    log.info("expected records: %d", expected)

    total, offset, page = 0, 0, 0
    while True:
        existing = dest_dir / f"page_{page:03d}.json"
        if existing.exists():
            data = json.loads(existing.read_text())
        else:
            resp = http_get(f"{url}/query", params={
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "false",
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": page_size,
                "f": "json",
            })
            data = resp.json()
            if "error" in data:
                log.error("service error at offset %d: %s", offset, data["error"])
                return 1
            existing.write_text(resp.text)
        n = len(data.get("features", []))
        total += n
        if page % 10 == 0:
            log.info("page %d (offset %d): %d records (cumulative %d)", page, offset, n, total)
        if not data.get("exceededTransferLimit", False) and n < page_size:
            break
        offset += n
        page += 1

    ok = validation.record(STAGE, "vdot_record_count_matches_service",
                           total == expected, f"downloaded {total}, service reports {expected}")

    sample = json.loads((dest_dir / "page_000.json").read_text())["features"][0]["attributes"]
    has_fields = all(k in sample for k in
                     ("ADT", "ROUTE_COMMON_NAME", "FROM_JURISDICTION", "Shape__Length"))
    ok &= validation.record(STAGE, "vdot_required_fields_present", has_fields,
                            f"sample keys: {sorted(sample)[:10]}...")

    size = sum(f.stat().st_size for f in dest_dir.glob("page_*.json"))
    record_manifest("vdot/page_*.json", "VDOT Traffic Volume 2024 (ArcGIS)",
                    url, size, f"{total} segments over {page + 1} pages",
                    "attributes only; ADT/AAWDT; EPSG:3857 Shape__Length (m)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
