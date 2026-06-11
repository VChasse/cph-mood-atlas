"""Fetch Copenhagen amenity data from OpenStreetMap via the Overpass API.

This script is intentionally separate from the Streamlit app. The app should only
read local processed files so deployments stay fast, deterministic, and polite to
public APIs.

Usage:
    python -m src.ingestion.fetch_osm
    python -m src.ingestion.fetch_osm --force
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

from src.utils.config import OSM_RAW_PATH, OVERPASS_API_URL, OVERPASS_BBOX

USER_AGENT = "CopenhagenMoodAtlas/0.1 (portfolio project; contact: GitHub repo owner)"
REQUEST_TIMEOUT_SECONDS = 90


# Copenhagen bounding box: south, west, north, east.
# Stored in config so it can be tightened/expanded later without touching logic.

def build_overpass_query() -> str:
    """Build a single respectful Overpass query for all MVP amenity classes."""
    south, west, north, east = OVERPASS_BBOX
    bbox = f"{south},{west},{north},{east}"

    selectors = [
        # Hygge / rainy-day / social signals
        f'nwr["amenity"="cafe"]({bbox});',
        f'nwr["shop"="bakery"]({bbox});',
        f'nwr["amenity"="library"]({bbox});',
        f'nwr["leisure"="park"]({bbox});',
        f'nwr["amenity"="bench"]({bbox});',
        f'nwr["amenity"="cinema"]({bbox});',
        f'nwr["tourism"="museum"]({bbox});',
        f'nwr["amenity"="bar"]({bbox});',
        f'nwr["amenity"="pub"]({bbox});',
        f'nwr["amenity"="nightclub"]({bbox});',
        f'nwr["amenity"="restaurant"]({bbox});',
        # Practical / family living signals
        f'nwr["shop"="supermarket"]({bbox});',
        f'nwr["amenity"="pharmacy"]({bbox});',
        f'nwr["amenity"="toilets"]({bbox});',
        f'nwr["amenity"="bicycle_parking"]({bbox});',
    ]

    return "\n".join(
        [
            "[out:json][timeout:60];",
            "(",
            *selectors,
            ");",
            # center gives lat/lon for ways and relations; tags keeps raw source context.
            "out center tags;",
        ]
    )


def fetch_overpass(query: str) -> dict[str, Any]:
    """Fetch data from Overpass with clear error messages."""
    headers = {"User-Agent": USER_AGENT}
    response = requests.post(
        OVERPASS_API_URL,
        data={"data": query},
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:800]
        raise RuntimeError(
            f"Overpass request failed with HTTP {response.status_code}. "
            f"Response preview: {detail}"
        ) from exc

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Overpass returned a non-JSON response.") from exc

    if "elements" not in payload:
        raise RuntimeError("Overpass response did not include an 'elements' field.")

    return payload


def write_json(payload: dict[str, Any], output_path: Path) -> None:
    """Write raw Overpass payload with deterministic formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Copenhagen OSM amenities via Overpass.")
    parser.add_argument("--force", action="store_true", help="Overwrite the cached raw response.")
    parser.add_argument(
        "--output",
        type=Path,
        default=OSM_RAW_PATH,
        help=f"Raw JSON cache path. Default: {OSM_RAW_PATH}",
    )
    args = parser.parse_args(argv)

    if args.output.exists() and not args.force:
        print(f"Using cached raw OSM response: {args.output}")
        print("Pass --force to refresh it. Avoid frequent refreshes; Overpass is a public service.")
        return 0

    query = build_overpass_query()
    print("Fetching OSM amenities from Overpass...")
    print("This should be run manually, not from the Streamlit app.")

    # A small pause is harmless locally and reinforces that this is not a hot-loop script.
    time.sleep(1.0)
    payload = fetch_overpass(query)
    write_json(payload, args.output)

    print(f"Wrote {len(payload.get('elements', [])):,} OSM elements to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
