from __future__ import annotations

import pandas as pd

from src.processing.build_scores import calculate_all_scores


def test_calculate_all_scores_adds_expected_columns():
    df = pd.DataFrame(
        {
            "cafe_density": [1, 2],
            "bakery_density": [1, 2],
            "library_access": [1, 2],
            "green_space_access": [1, 2],
            "bench_density": [1, 2],
            "indoor_culture_density": [1, 2],
            "bike_accessibility": [0.2, 0.8],
            "bar_density": [1, 2],
            "nightlife_density": [1, 2],
            "supermarket_density": [1, 2],
            "pharmacy_density": [1, 2],
            "transit_stop_density": [1, 2],
            "public_toilet_density": [1, 2],
            "bike_parking_density": [1, 2],
            "cinema_density": [1, 2],
            "museum_density": [1, 2],
            "share_age_20_34": [0.2, 0.6],
            "share_families_with_children": [0.5, 0.3],
            "share_international_background": [0.1, 0.5],
            "population_density": [100, 200],
        }
    )
    scored = calculate_all_scores(df)
    for column in ["hygge_score", "calm_score", "youth_pulse_score", "daily_convenience_score"]:
        assert column in scored.columns
        assert scored[column].between(0, 1).all()
