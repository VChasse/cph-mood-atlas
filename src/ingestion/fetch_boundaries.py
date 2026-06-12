"""Fetch official Copenhagen district polygons from Open Data DK.

This script is intentionally manual/offline. It downloads a GeoJSON boundary file
and caches it under data/raw so the Streamlit app never calls public APIs at
runtime.

Default source: Open Data DK / City of Copenhagen "Bydele" dataset.
The script first tries CKAN metadata, then falls back to scraping the dataset page
for a GeoJSON resource link. You can always pass --url with a direct GeoJSON URL.

Usage:
    python -m src.ingestion.fetch_boundaries
    python -m src.ingestion.fetch_boundaries --force
    python -m src.ingestion.fetch_boundaries --url "https://wfs-kbhkort.kk.dk/..."
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from src.utils.config import BOUNDARIES_RAW_PATH, CPH_BOUNDARIES_DATASET_PAGE, CPH_BOUNDARIES_GEOJSON_URL

USER_AGENT = "CopenhagenMoodAtlas/0.1 (portfolio project; contact: GitHub repo owner)"
REQUEST_TIMEOUT_SECONDS = 45
CKAN_PACKAGE_CANDIDATES = ("bydele", "city-ofcopenhagen-bydele", "city-of-copenhagen-bydele")
CKAN_API_URL = "https://www.opendata.dk/api/3/action/package_show"


def _request_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def _request_text(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.text


def _find_geojson_resource_from_ckan() -> str | None:
    """Return the first GeoJSON resource URL from Open Data DK CKAN metadata."""
    for package_id in CKAN_PACKAGE_CANDIDATES:
        try:
            payload = _request_json(CKAN_API_URL, params={"id": package_id})
        except requests.RequestException:
            continue

        result = payload.get("result") or {}
        resources = result.get("resources") or []
        for resource in resources:
            fmt = str(resource.get("format") or "").lower()
            name = str(resource.get("name") or "").lower()
            url = resource.get("url")
            if url and ("geojson" in fmt or name.endswith(".geojson") or str(url).lower().endswith(".geojson")):
                return str(url)
    return None


def _find_geojson_resource_from_page(page_url: str = CPH_BOUNDARIES_DATASET_PAGE) -> str | None:
    """Fallback: find a GeoJSON-looking link on the public dataset page."""
    try:
        html = _request_text(page_url)
    except requests.RequestException:
        return None

    matches = re.findall(r'href=["\']([^"\']+?\.geojson(?:\?[^"\']*)?)["\']', html, flags=re.I)
    if not matches:
        matches = re.findall(r'https?://[^"\'<>\s]+?\.geojson(?:\?[^"\'<>\s]*)?', html, flags=re.I)
    if not matches:
        return None
    return urljoin(page_url, matches[0])


def resolve_boundary_geojson_url(explicit_url: str | None = None) -> str:
    """Resolve a direct GeoJSON URL, preferring an explicit user-provided URL."""
    if explicit_url:
        return explicit_url

    # The Open Data DK page exposes the GeoJSON as a WFS download link.
    # Prefer the known public endpoint so local runs are not blocked by
    # occasional CKAN metadata/search changes.
    if CPH_BOUNDARIES_GEOJSON_URL:
        return CPH_BOUNDARIES_GEOJSON_URL

    ckan_url = _find_geojson_resource_from_ckan()
    if ckan_url:
        return ckan_url

    page_url = _find_geojson_resource_from_page()
    if page_url:
        return page_url

    raise RuntimeError(
        "Could not resolve the Copenhagen Bydele GeoJSON URL automatically. "
        "Open https://www.opendata.dk/city-ofcopenhagen/bydele, copy the bydele.geojson download URL, "
        "then rerun with `python -m src.ingestion.fetch_boundaries --url <URL>`."
    )


def fetch_geojson(url: str) -> dict[str, Any]:
    """Download and validate a GeoJSON FeatureCollection."""
    payload = _request_json(url)
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise RuntimeError("Boundary source did not return a valid GeoJSON FeatureCollection.")
    return payload


def write_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch official Copenhagen district boundaries as GeoJSON.")
    parser.add_argument("--force", action="store_true", help="Overwrite the cached boundary GeoJSON.")
    parser.add_argument("--url", default=None, help="Direct GeoJSON URL. Use this if automatic discovery fails.")
    parser.add_argument("--output", type=Path, default=BOUNDARIES_RAW_PATH, help="Raw GeoJSON cache path.")
    args = parser.parse_args(argv)

    if args.output.exists() and not args.force:
        print(f"Using cached boundary GeoJSON: {args.output}")
        print("Pass --force to refresh it.")
        return 0

    print("Resolving Copenhagen boundary GeoJSON URL...")
    url = resolve_boundary_geojson_url(args.url)
    print(f"Fetching boundaries from: {url}")
    time.sleep(0.5)

    payload = fetch_geojson(url)
    payload["_copenhagen_mood_atlas_source_url"] = url
    write_json(payload, args.output)

    print(f"Wrote {len(payload.get('features', [])):,} boundary features to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
