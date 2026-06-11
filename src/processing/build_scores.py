"""Feature normalization and transparent proxy score calculation."""

from __future__ import annotations

import pandas as pd

from src.utils.config import SCORE_FORMULAS


FEATURE_COLUMNS = [
    "cafe_density",
    "bakery_density",
    "library_access",
    "green_space_access",
    "bench_density",
    "indoor_culture_density",
    "bike_accessibility",
    "bar_density",
    "nightlife_density",
    "supermarket_density",
    "pharmacy_density",
    "transit_stop_density",
    "public_toilet_density",
    "bike_parking_density",
    "cinema_density",
    "museum_density",
    "share_age_20_34",
    "share_families_with_children",
    "share_international_background",
    "population_density",
]


def minmax_normalize(series: pd.Series) -> pd.Series:
    """Normalize a numeric pandas Series to 0-1, returning 0.5 for constants."""
    numeric = pd.to_numeric(series, errors="coerce")
    min_value = numeric.min()
    max_value = numeric.max()
    if pd.isna(min_value) or pd.isna(max_value):
        return pd.Series(0.0, index=series.index)
    if max_value == min_value:
        return pd.Series(0.5, index=series.index)
    return (numeric - min_value) / (max_value - min_value)


def ensure_norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Create *_norm columns for expected raw feature columns if missing."""
    output = df.copy()
    for col in FEATURE_COLUMNS:
        norm_col = f"{col}_norm"
        if col in output.columns and norm_col not in output.columns:
            output[norm_col] = minmax_normalize(output[col])
    return output


def weighted_sum(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Calculate a 0-1 weighted sum from normalized columns.

    Missing columns contribute 0. This keeps the app resilient while real data
    sources are being connected, but the Method tab still exposes the intended
    formula so data gaps are visible.
    """
    total_weight = sum(weights.values())
    if total_weight == 0:
        return pd.Series(0.0, index=df.index)

    score = pd.Series(0.0, index=df.index)
    for column, weight in weights.items():
        if column in df.columns:
            score += pd.to_numeric(df[column], errors="coerce").fillna(0) * weight
    return (score / total_weight).clip(0, 1)


def inverse(series: pd.Series) -> pd.Series:
    """Return an inverse 0-1 signal, preserving the index."""
    return (1 - series.fillna(0)).clip(0, 1)


def calculate_all_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate all transparent Copenhagen Mood Atlas proxy scores."""
    output = ensure_norm_columns(df)

    output["hygge_score"] = weighted_sum(output, SCORE_FORMULAS["hygge_score"])

    nightlife_pressure = weighted_sum(output, SCORE_FORMULAS["nightlife_pressure"])
    output["nightlife_pressure"] = nightlife_pressure
    output["low_nightlife_pressure"] = inverse(nightlife_pressure)
    output["low_population_pressure"] = inverse(
        output.get("population_density_norm", pd.Series(0, index=output.index))
    )

    output["calm_score"] = weighted_sum(output, SCORE_FORMULAS["calm_score"])
    output["youth_pulse_score"] = weighted_sum(output, SCORE_FORMULAS["youth_pulse_score"])
    output["daily_convenience_score"] = weighted_sum(output, SCORE_FORMULAS["daily_convenience_score"])
    output["rainy_day_index"] = weighted_sum(output, SCORE_FORMULAS["rainy_day_index"])

    # Family Living is a lifestyle-fit proxy, not a safety/school-quality metric.
    output["family_friendliness_score"] = weighted_sum(
        output,
        SCORE_FORMULAS["family_friendliness_score"],
    )

    if "share_international_background_norm" in output.columns:
        output["international_friendliness_score"] = weighted_sum(
            output,
            SCORE_FORMULAS["international_friendliness_score"],
        )
        output["international_friendliness_available"] = True
    else:
        output["international_friendliness_score"] = 0.0
        output["international_friendliness_available"] = False

    return output
