"""Tests for the concept-aware recommendation engine."""

from __future__ import annotations

import pandas as pd

from src.processing.build_scores import calculate_all_scores
from src.recommendation.recommender import parse_smart_search_details, rank_neighbourhoods


def _sample_scored_df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "neighbourhood": ["Calm District", "Nightlife District", "Balanced District"],
            "district": ["Calm District", "Nightlife District", "Balanced District"],
            "cafe_density": [2, 8, 5],
            "bakery_density": [2, 6, 4],
            "library_access": [3, 1, 2],
            "green_space_access": [8, 2, 5],
            "bench_density": [5, 3, 4],
            "indoor_culture_density": [2, 8, 5],
            "bike_accessibility": [7, 7, 7],
            "bar_density": [1, 9, 4],
            "nightlife_density": [1, 10, 4],
            "supermarket_density": [5, 5, 5],
            "pharmacy_density": [5, 4, 5],
            "transit_stop_density": [5, 8, 5],
            "public_toilet_density": [3, 4, 3],
            "bike_parking_density": [4, 7, 5],
            "cinema_density": [1, 5, 3],
            "museum_density": [1, 5, 3],
            "share_age_20_34": [0.22, 0.55, 0.35],
            "share_families_with_children": [0.42, 0.12, 0.25],
            "share_international_background": [0.20, 0.35, 0.28],
            "population_density": [5000, 18000, 9000],
        }
    )
    return calculate_all_scores(df)


def test_family_search_boosts_related_lifestyle_concepts() -> None:
    prefs, concepts = parse_smart_search_details("family friendly, calm, parks and easy errands")

    assert "family living" in concepts
    assert prefs["family_friendliness"] > 0
    assert prefs["calm"] > 0
    assert prefs["daily_convenience"] > 0


def test_no_nightlife_dampens_social_energy_without_positive_nightlife_label() -> None:
    prefs, concepts = parse_smart_search_details("calm, parks, no nightlife")

    assert "nightlife" not in concepts
    assert "less nightlife / noise" in concepts
    assert prefs["youth_pulse"] == 0


def test_recommendations_rank_family_query_toward_calm_areas() -> None:
    df = _sample_scored_df()
    prefs, _ = parse_smart_search_details("family friendly, calm, parks, no nightlife")
    ranked = rank_neighbourhoods(df, prefs, top_n=3)

    assert len(ranked) == 3
    assert ranked.iloc[0]["recommendation_score"] >= ranked.iloc[1]["recommendation_score"]
    assert ranked.iloc[0]["calm_score"] >= 0.55
