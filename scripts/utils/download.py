"""Download helpers: streaming HTTP download with retry, plus raw-data
manifest recording. Raw files are never overwritten silently - re-downloads
are skipped when the file already exists (delete manually to force)."""

import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from scripts.utils.logging_setup import get_logger
from scripts.utils.paths import DATA_RAW

log = get_logger("download")

MANIFEST = DATA_RAW / "MANIFEST.md"
USER_AGENT = "bucees-va-expansion-analysis (portfolio project; mxsalim@gmail.com)"


def http_get(url: str, *, retries: int = 3, timeout: int = 120, **kwargs) -> requests.Response:
    """GET with simple exponential backoff. Raises on final failure."""
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as err:  # noqa: PERF203
            last_err = err
            wait = 2 ** attempt
            log.warning("GET %s failed (%s); retry in %ds", url, err, wait)
            time.sleep(wait)
    raise RuntimeError(f"GET failed after {retries} attempts: {url}") from last_err


def download_file(url: str, dest: Path, *, skip_existing: bool = True) -> Path:
    """Stream a file to dest. Existing files are kept (raw is immutable)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if skip_existing and dest.exists() and dest.stat().st_size > 0:
        log.info("exists, skipping: %s", dest.name)
        return dest
    log.info("downloading %s -> %s", url, dest)
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True,
                      timeout=300) as resp:
        resp.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    log.info("saved %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


def record_manifest(filename: str, source: str, url: str, size_bytes: int,
                    rows: str, notes: str = "") -> None:
    """Append one row to data/raw/MANIFEST.md (skip if filename already listed)."""
    existing = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
    if f"| {filename} |" in existing:
        return
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    size_mb = f"{size_bytes / 1e6:.1f} MB"
    row = f"| {filename} | {source} | {url} | {ts} | {size_mb} | {rows} | {notes} |\n"
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(row)
