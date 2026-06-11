from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.processing.build_osm_features import (
    assign_by_boundary_polygon,
    build_boundary_base,
    load_boundaries,
)


def _write_sample_boundaries(path: Path) -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"navn": "Test District"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [12.0, 55.0],
                            [13.0, 55.0],
                            [13.0, 56.0],
                            [12.0, 56.0],
                            [12.0, 55.0],
                        ]
                    ],
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_boundaries_and_assign_point_in_polygon(tmp_path: Path) -> None:
    boundaries_path = tmp_path / "boundaries.geojson"
    _write_sample_boundaries(boundaries_path)

    boundaries = load_boundaries(boundaries_path)
    assert len(boundaries) == 1
    assert boundaries[0]["boundary_name"] == "Test District"
    assert boundaries[0]["area_km2"] > 0

    amenities = pd.DataFrame(
        [
            {"category": "cafe", "lat": 55.5, "lon": 12.5, "name": "Inside"},
            {"category": "cafe", "lat": 57.0, "lon": 12.5, "name": "Outside"},
        ]
    )
    assigned = assign_by_boundary_polygon(amenities, boundaries)

    assert len(assigned) == 1
    assert assigned.iloc[0]["name"] == "Inside"
    assert assigned.iloc[0]["neighbourhood"] == "Test District"
    assert assigned.iloc[0]["osm_assignment_method"] == "official_boundary_point_in_polygon"
    assert int(assigned.iloc[0]["osm_outside_boundary_count"]) == 1


def test_build_boundary_base_requires_official_demographics() -> None:
    boundaries = [
        {
            "boundary_name": "Test District",
            "district": "Test District",
            "lat": 55.66,
            "lon": 12.54,
            "area_km2": 10.0,
            "geometry": {},
        }
    ]
    demographics = pd.DataFrame(
        {
            "neighbourhood": ["Test District"],
            "neighbourhood_key": ["test district"],
            "population": [30_000],
            "share_age_20_34": [0.30],
            "share_families_with_children": [0.23],
            "share_international_background": [0.20],
            "demographic_source": ["KK Statistikbank"],
        }
    )

    boundary_base = build_boundary_base(boundaries, demographics)

    assert boundary_base.iloc[0]["neighbourhood"] == "Test District"
    assert int(boundary_base.iloc[0]["population"]) == 30_000
    assert boundary_base.iloc[0]["demographic_source"] == "KK Statistikbank"
