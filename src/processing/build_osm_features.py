"""Transform cached OSM amenities into Copenhagen Mood Atlas feature tables.

This script reads the raw Overpass JSON cache produced by
``python -m src.ingestion.fetch_osm`` and creates:

- data/processed/osm_amenities_clean.csv
- data/processed/osm_amenities_by_neighbourhood.csv
- data/processed/neighborhood_features_osm.csv

Amenities are assigned with point-in-polygon against official Copenhagen district polygons.
The script requires real boundary and demographic files and does not fall back to mock data.

The Streamlit app never queries Overpass or boundary APIs directly. It only reads
processed local files.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from src.processing.build_scores import calculate_all_scores
from src.utils.config import (
    BOUNDARIES_CLEAN_PATH,
    BOUNDARIES_RAW_PATH,
    DEMOGRAPHICS_FEATURES_PATH,
    OSM_AGGREGATED_PATH,
    OSM_CLEAN_PATH,
    OSM_FEATURES_PATH,
    OSM_RAW_PATH,
)

CATEGORY_TO_FEATURE = {
    "cafe": "cafe_density",
    "bakery": "bakery_density",
    "library": "library_access",
    "park": "green_space_access",
    "bench": "bench_density",
    "cinema": "cinema_density",
    "museum": "museum_density",
    "bar": "bar_density",
    "pub": "bar_density",
    "nightclub": "nightlife_density",
    "restaurant": "indoor_culture_density",
    "supermarket": "supermarket_density",
    "pharmacy": "pharmacy_density",
    "toilets": "public_toilet_density",
    "bicycle_parking": "bike_parking_density",
}

AMENITY_FEATURE_COLUMNS = sorted(set(CATEGORY_TO_FEATURE.values()) | {"bike_accessibility"})
DEMOGRAPHIC_SHARE_COLUMNS = [
    "share_age_20_34",
    "share_families_with_children",
    "share_international_background",
]
DEMOGRAPHIC_REPLACEMENT_COLUMNS = ["population", *DEMOGRAPHIC_SHARE_COLUMNS]

# District-name aliases used when boundary names and KK Statistikbank names differ.
BOUNDARY_TO_BASE_ALIASES = {
    "indre by": ["Indre By", "Christianshavn"],
    "vesterbro/kongens enghave": ["Vesterbro/Kongens Enghave", "Vesterbro-Kongens Enghave"],
    "vesterbro-kongens enghave": ["Vesterbro/Kongens Enghave", "Vesterbro-Kongens Enghave"],
    "vesterbro kongens enghave": ["Vesterbro/Kongens Enghave", "Vesterbro-Kongens Enghave"],
    "amager øst": ["Amagerbro"],
    "amager ost": ["Amagerbro"],
    "amager vest": ["Islands Brygge"],
    "brønshøj-husum": ["Brønshøj-Husum"],
    "bronshoj-husum": ["Brønshøj-Husum"],
}


def _normalise_name(value: object) -> str:
    """Normalise district names across KK Statistikbank and boundary GeoJSON exports.

    The official sources are consistent conceptually but not typographically. For
    example, KK Statistikbank exports ``Vesterbro/Kongens Enghave`` while the
    Copenhagen boundary GeoJSON can expose ``Vesterbro-Kongens Enghave``. This
    function normalises punctuation and Danish characters so those names match
    without inventing or imputing any data.
    """
    text = str(value).strip().lower()
    text = text.replace("ø", "o").replace("å", "a").replace("æ", "ae")
    text = re.sub(r"^(district|bydel)\s*[-:]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[\/\-–—_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Some exports prefix areas with a numeric code, e.g. "1 Indre By".
    # Do not remove ordinary leading words such as "Test District".
    return re.sub(r"^\d+[a-z_.-]*\s+", "", text).strip()


def _category_from_tags(tags: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Map OSM tags to a project category and preserve the source tag."""
    checks = [
        ("amenity", "cafe", "cafe"),
        ("shop", "bakery", "bakery"),
        ("amenity", "library", "library"),
        ("leisure", "park", "park"),
        ("amenity", "bench", "bench"),
        ("amenity", "cinema", "cinema"),
        ("tourism", "museum", "museum"),
        ("amenity", "bar", "bar"),
        ("amenity", "pub", "pub"),
        ("amenity", "nightclub", "nightclub"),
        ("amenity", "restaurant", "restaurant"),
        ("shop", "supermarket", "supermarket"),
        ("amenity", "pharmacy", "pharmacy"),
        ("amenity", "toilets", "toilets"),
        ("amenity", "bicycle_parking", "bicycle_parking"),
    ]
    for key, value, category in checks:
        if tags.get(key) == value:
            return category, key, value
    return None, None, None


def _extract_lat_lon(element: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract coordinates from node lat/lon or way/relation center."""
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center") or {}
    if "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None, None


def parse_osm_elements(raw_path: Path = OSM_RAW_PATH) -> pd.DataFrame:
    """Convert raw Overpass JSON into a clean amenity-level table."""
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw OSM cache not found: {raw_path}. Run `python -m src.ingestion.fetch_osm` first."
        )

    with raw_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()

    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        category, source_key, source_value = _category_from_tags(tags)
        lat, lon = _extract_lat_lon(element)
        if category is None or lat is None or lon is None:
            continue

        dedupe_key = (element.get("type", "unknown"), int(element.get("id", 0)), category)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        rows.append(
            {
                "osm_type": element.get("type"),
                "osm_id": element.get("id"),
                "category": category,
                "name": tags.get("name", ""),
                "lat": lat,
                "lon": lon,
                "source_key": source_key,
                "source_value": source_value,
            }
        )

    return pd.DataFrame(rows)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two latitude/longitude points."""
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def _ring_contains_point(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-casting point-in-ring test for GeoJSON lon/lat coordinates."""
    inside = False
    if len(ring) < 4:
        return False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def _polygon_contains_point(lon: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    """Return True if point is inside polygon outer ring and not inside holes."""
    if not polygon or not _ring_contains_point(lon, lat, polygon[0]):
        return False
    return not any(_ring_contains_point(lon, lat, hole) for hole in polygon[1:])


def _geometry_contains_point(geometry: dict[str, Any], lon: float, lat: float) -> bool:
    geo_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if geo_type == "Polygon":
        return _polygon_contains_point(lon, lat, coords)
    if geo_type == "MultiPolygon":
        return any(_polygon_contains_point(lon, lat, polygon) for polygon in coords)
    return False


def _iter_geometry_points(geometry: dict[str, Any]) -> list[tuple[float, float]]:
    """Flatten Polygon/MultiPolygon coordinates into lon/lat points."""
    coords = geometry.get("coordinates") or []
    geo_type = geometry.get("type")
    points: list[tuple[float, float]] = []
    polygons = coords if geo_type == "MultiPolygon" else [coords]
    for polygon in polygons:
        if not polygon:
            continue
        for lon, lat, *_ in polygon[0]:
            points.append((float(lon), float(lat)))
    return points


def _geometry_centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    points = _iter_geometry_points(geometry)
    if not points:
        return 12.5683, 55.6761
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def _geometry_area_km2(geometry: dict[str, Any]) -> float:
    """Approximate polygon area in km² using local equirectangular projection."""
    points = _iter_geometry_points(geometry)
    if not points:
        return 0.0
    mean_lat = math.radians(sum(lat for _, lat in points) / len(points))
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * math.cos(mean_lat)

    def ring_area(ring: list[list[float]]) -> float:
        projected = [(float(lon) * km_per_deg_lon, float(lat) * km_per_deg_lat) for lon, lat, *_ in ring]
        if len(projected) < 4:
            return 0.0
        total = 0.0
        for i in range(len(projected)):
            x1, y1 = projected[i]
            x2, y2 = projected[(i + 1) % len(projected)]
            total += x1 * y2 - x2 * y1
        return abs(total) / 2

    geo_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    polygons = coords if geo_type == "MultiPolygon" else [coords]
    total_area = 0.0
    for polygon in polygons:
        if not polygon:
            continue
        total_area += ring_area(polygon[0])
        total_area -= sum(ring_area(hole) for hole in polygon[1:])
    return max(total_area, 0.0)


def _boundary_name(properties: dict[str, Any], fallback: str) -> str:
    """Find a readable district name from varied Danish/GeoJSON schemas."""
    candidates = [
        "navn",
        "NAVN",
        "bydel",
        "BYDEL",
        "district",
        "DISTRICT",
        "name",
        "Name",
        "lokaludvalgsomraade",
        "lokaludvalgsområde",
    ]
    for key in candidates:
        value = properties.get(key)
        if value:
            return str(value).strip()
    for key, value in properties.items():
        if "navn" in str(key).lower() and value:
            return str(value).strip()
    return fallback


def load_boundaries(boundaries_path: Path = BOUNDARIES_RAW_PATH) -> list[dict[str, Any]]:
    """Load official Copenhagen boundary features from cached GeoJSON."""
    if not boundaries_path.exists():
        return []
    with boundaries_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    boundaries: list[dict[str, Any]] = []
    for idx, feature in enumerate(payload.get("features", []), start=1):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        properties = feature.get("properties") or {}
        name = _boundary_name(properties, fallback=f"Boundary {idx}")
        lon, lat = _geometry_centroid(geometry)
        boundaries.append(
            {
                "boundary_name": name,
                "boundary_key": _normalise_name(name),
                "district": name,
                "lat": lat,
                "lon": lon,
                "area_km2": round(_geometry_area_km2(geometry), 3),
                "geometry": geometry,
            }
        )
    return boundaries


def write_clean_boundaries(boundaries: list[dict[str, Any]], output_path: Path = BOUNDARIES_CLEAN_PATH) -> None:
    """Write a light CSV audit of loaded boundary names and centroids."""
    if not boundaries:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{k: v for k, v in row.items() if k != "geometry"} for row in boundaries]).to_csv(output_path, index=False)




def load_demographic_features(path: Path = DEMOGRAPHICS_FEATURES_PATH) -> pd.DataFrame:
    """Load official demographic features if the processed file exists."""
    if not path.exists():
        return pd.DataFrame()
    demographics = pd.read_csv(path)
    if "neighbourhood" not in demographics.columns:
        raise ValueError(f"Demographic file is missing 'neighbourhood': {path}")
    demographics["neighbourhood_key"] = demographics["neighbourhood"].map(_normalise_name)
    return demographics


def _match_demographic_row(boundary_name: str, demographics: pd.DataFrame) -> pd.Series | None:
    """Match a boundary name to an official demographic row."""
    if demographics.empty or "neighbourhood_key" not in demographics.columns:
        return None
    key = _normalise_name(boundary_name)
    direct = demographics[demographics["neighbourhood_key"].eq(key)]
    if not direct.empty:
        return direct.iloc[0]

    aliases = BOUNDARY_TO_BASE_ALIASES.get(key, [])
    alias_keys = {_normalise_name(alias) for alias in aliases}
    if alias_keys:
        matched = demographics[demographics["neighbourhood_key"].isin(alias_keys)]
        if not matched.empty:
            return matched.iloc[0]
    return None


def _match_base_rows_for_boundary(boundary_name: str, base: pd.DataFrame) -> pd.DataFrame:
    key = _normalise_name(boundary_name)
    direct = base[
        base["neighbourhood"].map(_normalise_name).eq(key)
        | base["district"].map(_normalise_name).eq(key)
    ]
    if not direct.empty:
        return direct

    aliases = BOUNDARY_TO_BASE_ALIASES.get(key, [])
    if aliases:
        alias_keys = {_normalise_name(alias) for alias in aliases}
        matched = base[base["neighbourhood"].map(_normalise_name).isin(alias_keys)]
        if not matched.empty:
            return matched

    return base.iloc[0:0]


def build_boundary_base(
    boundaries: list[dict[str, Any]],
    demographics: pd.DataFrame,
) -> pd.DataFrame:
    """Create an app-compatible base table from official boundaries and demographics.

    This function does not invent demographic values. Every official boundary must
    match a processed KK Statistikbank demographic row, otherwise the pipeline
    stops and asks for better source data / mapping.
    """
    if not boundaries:
        raise FileNotFoundError(
            f"Official Copenhagen boundary GeoJSON not found or empty. Run `python -m src.ingestion.fetch_boundaries` first. Expected: {BOUNDARIES_RAW_PATH}"
        )
    if demographics.empty:
        raise FileNotFoundError(
            f"Processed official demographics not found. Run `python -m src.ingestion.fetch_demographics` and `python -m src.processing.build_demographic_features` first. Expected: {DEMOGRAPHICS_FEATURES_PATH}"
        )

    rows: list[dict[str, Any]] = []
    unmatched: list[str] = []

    for boundary in boundaries:
        demographic_row = _match_demographic_row(boundary["boundary_name"], demographics)
        if demographic_row is None:
            unmatched.append(boundary["boundary_name"])
            continue

        population = int(float(demographic_row.get("population", 0) or 0))
        area_km2 = float(boundary["area_km2"] or 1)
        row: dict[str, Any] = {
            "data_mode": "osm_amenities_official_boundaries_official_demographics",
            "is_mock_data": False,
            "neighbourhood": boundary["boundary_name"],
            "district": boundary["district"],
            "profile": "Official Copenhagen district boundary with OSM amenity and demographic signals.",
            "lat": boundary["lat"],
            "lon": boundary["lon"],
            "population": population,
            "area_km2": area_km2,
            "population_density": population / area_km2 if area_km2 else 0,
            "demographic_source": str(demographic_row.get("demographic_source", "KK Statistikbank")),
            "demographic_assignment_method": "official_district_name_match",
        }

        for col in DEMOGRAPHIC_SHARE_COLUMNS:
            row[col] = float(demographic_row.get(col, 0) or 0)
        rows.append(row)

    if unmatched:
        raise ValueError(
            "Some official boundary districts could not be matched to the processed demographic file: "
            + ", ".join(unmatched)
            + ". Do not guess these values; update the district-name mapping or provide the correct demographic CSV export."
        )

    return pd.DataFrame(rows)

def assign_by_boundary_polygon(amenities: pd.DataFrame, boundaries: list[dict[str, Any]]) -> pd.DataFrame:
    """Assign each amenity to the containing official boundary polygon."""
    if amenities.empty:
        return amenities.assign(
            neighbourhood=pd.Series(dtype="object"),
            district=pd.Series(dtype="object"),
            osm_assignment_method=pd.Series(dtype="object"),
        )

    assigned_rows: list[dict[str, Any]] = []
    outside_count = 0
    for amenity in amenities.to_dict("records"):
        lon = float(amenity["lon"])
        lat = float(amenity["lat"])
        match = next((b for b in boundaries if _geometry_contains_point(b["geometry"], lon, lat)), None)
        if match is None:
            outside_count += 1
            continue
        assigned_rows.append(
            {
                **amenity,
                "neighbourhood": match["boundary_name"],
                "district": match["district"],
                "distance_to_neighbourhood_km": 0.0,
                "osm_assignment_method": "official_boundary_point_in_polygon",
            }
        )

    assigned = pd.DataFrame(assigned_rows)
    if assigned.empty:
        return assigned
    assigned["osm_outside_boundary_count"] = outside_count
    return assigned


def aggregate_by_neighbourhood(amenities: pd.DataFrame, neighbourhoods: pd.DataFrame) -> pd.DataFrame:
    """Aggregate amenity counts and densities by neighbourhood."""
    base = neighbourhoods[["neighbourhood", "district", "area_km2"]].copy()

    if amenities.empty:
        for feature in AMENITY_FEATURE_COLUMNS:
            base[feature.replace("_density", "_count")] = 0
            base[feature] = 0.0
        return base

    counts = (
        amenities.groupby(["neighbourhood", "category"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    output = base.merge(counts, on="neighbourhood", how="left").fillna(0)

    for category, feature_col in CATEGORY_TO_FEATURE.items():
        count_col = feature_col.replace("_density", "_count")
        if count_col == feature_col:
            count_col = f"{feature_col}_count"
        output[count_col] = output.get(count_col, 0) + output.get(category, 0)

    output["indoor_culture_count"] = (
        output.get("restaurant", 0)
        + output.get("library", 0)
        + output.get("cinema", 0)
        + output.get("museum", 0)
    )
    output["nightlife_count"] = output.get("nightclub", 0) + output.get("bar", 0) + output.get("pub", 0)
    output["bike_accessibility_count"] = output.get("bicycle_parking", 0)

    count_columns = [col for col in output.columns if col.endswith("_count")]
    for count_col in count_columns:
        feature_col = count_col.replace("_count", "_density")
        if feature_col == "library_access_density":
            feature_col = "library_access"
        elif feature_col == "green_space_access_density":
            feature_col = "green_space_access"
        elif feature_col == "bike_accessibility_density":
            feature_col = "bike_accessibility"
        output[feature_col] = output[count_col] / output["area_km2"].replace(0, pd.NA)

    keep = ["neighbourhood", "district", "area_km2"]
    keep += sorted([col for col in output.columns if col.endswith("_count")])
    keep += sorted([col for col in AMENITY_FEATURE_COLUMNS if col in output.columns])
    keep += ["library_access", "green_space_access", "bike_accessibility"]
    keep = list(dict.fromkeys([col for col in keep if col in output.columns]))

    return output[keep].fillna(0)


def build_osm_features(
    raw_path: Path = OSM_RAW_PATH,
    clean_path: Path = OSM_CLEAN_PATH,
    aggregate_path: Path = OSM_AGGREGATED_PATH,
    output_path: Path = OSM_FEATURES_PATH,
    boundaries_path: Path = BOUNDARIES_RAW_PATH,
    demographics_path: Path = DEMOGRAPHICS_FEATURES_PATH,
) -> pd.DataFrame:
    """Build the final real OSM + official demographics feature table.

    Required inputs:
    - cached Overpass JSON
    - official Copenhagen boundary GeoJSON
    - processed KK Statistikbank demographics

    The pipeline deliberately fails when one of those inputs is missing instead
    of falling back to mock or invented values.
    """
    amenities = parse_osm_elements(raw_path)
    boundaries = load_boundaries(boundaries_path)
    demographics = load_demographic_features(demographics_path)

    write_clean_boundaries(boundaries)
    base = build_boundary_base(boundaries, demographics)
    amenities = assign_by_boundary_polygon(amenities, boundaries)
    assignment_method = "official_boundary_point_in_polygon"
    data_mode = "osm_amenities_official_boundaries_official_demographics"

    aggregated = aggregate_by_neighbourhood(amenities, base)

    clean_path.parent.mkdir(parents=True, exist_ok=True)
    amenities.to_csv(clean_path, index=False)
    aggregated.to_csv(aggregate_path, index=False)

    output = base.copy()
    output = output.drop(
        columns=[col for col in aggregated.columns if col in output.columns and col not in {"neighbourhood", "district", "area_km2"}],
        errors="ignore",
    )
    output = output.merge(
        aggregated.drop(columns=["district", "area_km2"], errors="ignore"),
        on="neighbourhood",
        how="left",
    )

    for feature in AMENITY_FEATURE_COLUMNS:
        if feature not in output.columns:
            output[feature] = 0.0
        count_col = feature.replace("_density", "_count")
        if count_col == feature:
            count_col = f"{feature}_count"
        if count_col not in output.columns:
            output[count_col] = 0

    output["data_mode"] = data_mode
    output["is_mock_data"] = False
    output["osm_assignment_method"] = assignment_method
    output["osm_amenity_count"] = len(amenities)

    if "osm_outside_boundary_count" in amenities.columns:
        output["osm_outside_boundary_count"] = int(amenities["osm_outside_boundary_count"].max())

    output = calculate_all_scores(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    return output

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build OSM-enriched Copenhagen Mood Atlas features.")
    parser.add_argument("--raw", type=Path, default=OSM_RAW_PATH, help="Cached raw Overpass JSON path.")
    parser.add_argument("--boundaries", type=Path, default=BOUNDARIES_RAW_PATH, help="Cached Copenhagen boundary GeoJSON path.")
    parser.add_argument("--demographics", type=Path, default=DEMOGRAPHICS_FEATURES_PATH, help="Processed demographic features path.")
    parser.add_argument("--output", type=Path, default=OSM_FEATURES_PATH, help="Final processed features path.")
    args = parser.parse_args(argv)

    df = build_osm_features(
        raw_path=args.raw,
        boundaries_path=args.boundaries,
        demographics_path=args.demographics,
        output_path=args.output,
    )
    print(f"Wrote OSM-enriched features to {args.output}")
    print(f"Rows: {len(df):,} | OSM amenities assigned: {int(df['osm_amenity_count'].iloc[0]):,}")
    print(f"Assignment method: {df['osm_assignment_method'].iloc[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
