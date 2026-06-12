"""Rule-based HTML explanations for recommendations and neighbourhood profiles."""

from __future__ import annotations

import html

import pandas as pd

from src.utils.config import DISPLAY_SCORE_NAMES, RECOMMENDATION_DIMENSIONS, SCORE_COLUMNS


def _safe(value: object) -> str:
    return html.escape(str(value))


def score_label(value: float) -> str:
    """Convert a 0-1 score to a readable strength label."""
    if value >= 0.75:
        return "very strong"
    if value >= 0.60:
        return "strong"
    if value >= 0.45:
        return "moderate"
    if value >= 0.30:
        return "emerging"
    return "low"


def top_strengths(row: pd.Series, n: int = 3) -> list[tuple[str, float]]:
    """Return the strongest score dimensions for one neighbourhood row."""
    available = [(col, float(row[col])) for col in SCORE_COLUMNS if col in row and pd.notna(row[col])]
    available.sort(key=lambda x: x[1], reverse=True)
    return available[:n]


def preference_contributions(row: pd.Series, preferences: dict[str, float], n: int = 3) -> list[tuple[str, float, float]]:
    """Return preference dimensions with the strongest weighted contribution."""
    total = sum(max(0.0, float(v)) for v in preferences.values()) or 1.0
    contributions: list[tuple[str, float, float]] = []
    for pref_key, raw_weight in preferences.items():
        score_col = RECOMMENDATION_DIMENSIONS.get(pref_key)
        if not score_col or score_col not in row:
            continue
        normalized_weight = max(0.0, float(raw_weight)) / total
        score = float(row[score_col])
        contributions.append((score_col, score, normalized_weight * score))
    contributions.sort(key=lambda item: item[2], reverse=True)
    return contributions[:n]


def explain_neighbourhood(row: pd.Series) -> str:
    """Create a deterministic personality-card explanation with HTML emphasis."""
    strengths = top_strengths(row, 3)
    parts = [
        f"<strong>{_safe(DISPLAY_SCORE_NAMES.get(col, col))}</strong> is {score_label(value)} ({value:.0%})"
        for col, value in strengths
    ]
    if not parts:
        return f"{_safe(row['neighbourhood'])} has a balanced mood profile across the available signals."
    return f"{_safe(row['neighbourhood'])} is strongest for " + ", ".join(parts) + "."


def explain_recommendation(row: pd.Series, preferences: dict[str, float]) -> str:
    """Explain why a neighbourhood was recommended using user-weighted metric values."""
    contributions = preference_contributions(row, preferences, 3)
    if contributions:
        metric_text = "; ".join(
            f"<strong>{_safe(DISPLAY_SCORE_NAMES.get(col, col))}</strong> {score:.0%}"
            for col, score, _ in contributions
        )
    else:
        strengths = top_strengths(row, 3)
        metric_text = "; ".join(
            f"<strong>{_safe(DISPLAY_SCORE_NAMES.get(col, col))}</strong> {value:.0%}" for col, value in strengths
        )

    score = float(row.get("recommendation_score", 0))
    adjustment = float(row.get("match_adjustment", 0))
    adjustment_text = ""
    if abs(adjustment) >= 0.015:
        direction = "lifted" if adjustment > 0 else "softened"
        adjustment_text = f" Compatibility checks {direction} the final score a little."

    return (
        f"{_safe(row['neighbourhood'])} is match <strong>#{int(row.get('rank', 0))}</strong> "
        f"at <strong>{score:.0%}</strong>. "
        f"Top signals: {metric_text}."
        f"{adjustment_text}"
    )
