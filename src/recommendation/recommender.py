"""Concept-aware recommendation engine for Copenhagen Mood Atlas.

The app deliberately avoids LLM APIs. Instead, this module gives the search box
some lightweight semantic behaviour: synonyms, related concepts, phrase boosts,
negation handling, and compatibility penalties.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from src.utils.config import RECOMMENDATION_DIMENSIONS


@dataclass(frozen=True)
class ConceptRule:
    """A concept detected from natural language."""

    label: str
    patterns: tuple[str, ...]
    weights: dict[str, float]
    explanation: str


PREFERENCE_KEYS = tuple(RECOMMENDATION_DIMENSIONS.keys())

# The weights below are intentionally not one-to-one. A family search, for
# example, is not only "families". It also implies calm, parks, convenience,
# rainy-day options, and less nightlife pressure.
CONCEPT_RULES: tuple[ConceptRule, ...] = (
    ConceptRule(
        label="coffee and hygge",
        patterns=(r"\bcaf[eé]s?\b", r"\bcoffee\b", r"\bbaker(y|ies)\b", r"\bcozy\b", r"\bcosy\b", r"\bhygge\b"),
        weights={"hygge": 4.0, "rainy_day": 1.4, "daily_convenience": 0.5},
        explanation="cafés, bakeries and indoor comfort",
    ),
    ConceptRule(
        label="quiet and green",
        patterns=(r"\bcalm\b", r"\bquiet\b", r"\bpeaceful\b", r"\brelaxed\b", r"\bslow\b", r"\bparks?\b", r"\bgreen\b", r"\bnature\b"),
        weights={"calm": 4.0, "hygge": 0.8, "family_friendliness": 0.7},
        explanation="calm, greenery and lower pressure",
    ),
    ConceptRule(
        label="social energy",
        patterns=(r"\bsocial\b", r"\byoung\b", r"\bstudents?\b", r"\bcreative\b", r"\bmeet people\b", r"\blively\b", r"\benergy\b"),
        weights={"youth_pulse": 3.2, "hygge": 1.0, "international_friendliness": 0.8},
        explanation="young, social and culturally active areas",
    ),
    ConceptRule(
        label="nightlife",
        patterns=(r"\bbars?\b", r"\bnightlife\b", r"\bparty\b", r"\bclubs?\b", r"\bdrinks?\b", r"\blate night\b"),
        weights={"youth_pulse": 4.0, "hygge": 0.7, "rainy_day": 0.4, "calm": -1.3, "family_friendliness": -1.2},
        explanation="bars, nightlife and late-night energy",
    ),
    ConceptRule(
        label="daily practicality",
        patterns=(r"\bpractical\b", r"\beasy\b", r"\bconvenient\b", r"\bsupermarkets?\b", r"\bpharmac(y|ies)\b", r"\bshops?\b", r"\berrands?\b"),
        weights={"daily_convenience": 4.0, "family_friendliness": 0.8, "hygge": 0.4},
        explanation="shops, pharmacies and everyday services",
    ),
    ConceptRule(
        label="commute and mobility",
        patterns=(r"\bcommute\b", r"\bmetro\b", r"\btrain\b", r"\btransit\b", r"\bbus\b", r"\bbike\b", r"\bcycling\b", r"\bwalkable\b"),
        weights={"daily_convenience": 3.0, "hygge": 0.8, "calm": 0.4},
        explanation="mobility, transit and bike access",
    ),
    ConceptRule(
        label="rainy-day comfort",
        patterns=(r"\brain(y)?\b", r"\bwinter\b", r"\bindoor\b", r"\bmuseums?\b", r"\bcinemas?\b", r"\blibrar(y|ies)\b", r"\bculture\b"),
        weights={"rainy_day": 4.0, "hygge": 1.5, "daily_convenience": 0.5},
        explanation="indoor culture, cafés and rainy-day options",
    ),
    ConceptRule(
        label="family living",
        patterns=(r"\bfamil(y|ies)\b", r"\bkids?\b", r"\bchildren\b", r"\bparent(s)?\b", r"\bschools?\b", r"\bplaygrounds?\b", r"\bstroller\b"),
        weights={"family_friendliness": 4.0, "calm": 2.0, "daily_convenience": 1.4, "rainy_day": 0.8, "youth_pulse": -1.0},
        explanation="family presence, calm, green access and practical services",
    ),
    ConceptRule(
        label="international feel",
        patterns=(r"\binternational\b", r"\bexpats?\b", r"\benglish\b", r"\bforeigners?\b", r"\bglobal\b", r"\bdiverse\b", r"\bnew to copenhagen\b"),
        weights={"international_friendliness": 3.2, "daily_convenience": 0.8, "youth_pulse": 0.7},
        explanation="international and newcomer-friendly signals",
    ),
)

NEGATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "calm": (r"\bnot quiet\b", r"\bnot calm\b", r"\btoo quiet\b", r"\bboring\b"),
    "youth_pulse": (
        r"\bnot social\b",
        r"\bnot lively\b",
        r"\btoo busy\b",
        r"\bnot too busy\b",
        r"\btoo loud\b",
        r"\bavoid nightlife\b",
        r"\bno nightlife\b",
        r"\bnot much nightlife\b",
        r"\bnot too much nightlife\b",
    ),
    "family_friendliness": (r"\bnot family\b", r"\bno kids\b", r"\bwithout kids\b"),
    "daily_convenience": (r"\bremote\b", r"\bisolated\b", r"\baway from everything\b"),
}

NEGATION_LABELS = {
    "calm": "less quiet",
    "youth_pulse": "less nightlife / noise",
    "family_friendliness": "less family-oriented",
    "daily_convenience": "more remote",
}

NEGATED_RULE_LABELS = {
    "youth_pulse": {"nightlife", "social energy"},
    "calm": {"quiet and green"},
    "family_friendliness": {"family living"},
    "daily_convenience": {"daily practicality", "commute and mobility"},
}

# Human shortcuts that set a balanced lifestyle profile rather than just one score.
PRESET_QUERIES: tuple[tuple[tuple[str, ...], dict[str, float]], ...] = (
    (("student", "students"), {"youth_pulse": 5, "hygge": 3, "daily_convenience": 2, "international_friendliness": 2}),
    (("young professional", "career", "professional"), {"daily_convenience": 4, "hygge": 3, "calm": 2, "youth_pulse": 2}),
    (("family", "kids", "children"), {"family_friendliness": 5, "calm": 3, "daily_convenience": 2, "rainy_day": 1}),
    (("rainy sunday", "sunday", "date"), {"rainy_day": 4, "hygge": 3, "calm": 1}),
    (("new here", "new to copenhagen", "just moved"), {"international_friendliness": 4, "daily_convenience": 2, "hygge": 2, "youth_pulse": 1}),
)


def _empty_weights() -> dict[str, float]:
    return {key: 0.0 for key in PREFERENCE_KEYS}


def _matches(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def normalize_preferences(preferences: dict[str, float]) -> dict[str, float]:
    """Convert slider values to non-negative normalized weights."""
    cleaned = {k: max(0.0, float(v)) for k, v in preferences.items() if k in PREFERENCE_KEYS}
    total = sum(cleaned.values())
    if total == 0:
        return {k: 1 / len(cleaned) for k in cleaned} if cleaned else {}
    return {k: v / total for k, v in cleaned.items()}


def parse_smart_search_details(query: str) -> tuple[dict[str, float], list[str]]:
    """Map natural language to preference weights and detected concept labels.

    This is intentionally deterministic. It is not an LLM, but it behaves more
    like a semantic layer than a plain keyword counter.
    """
    text = f" {query.lower().strip()} "
    weights = _empty_weights()
    detected: list[str] = []

    for triggers, preset in PRESET_QUERIES:
        if any(trigger in text for trigger in triggers):
            for key, value in preset.items():
                weights[key] += value

    negated_keys = {key for key, patterns in NEGATION_PATTERNS.items() if _matches(text, patterns)}

    for rule in CONCEPT_RULES:
        is_negated_rule = any(rule.label in NEGATED_RULE_LABELS.get(key, set()) for key in negated_keys)
        if is_negated_rule:
            continue
        if _matches(text, rule.patterns):
            detected.append(rule.label)
            for key, value in rule.weights.items():
                weights[key] += value

    # Negations dampen concepts instead of simply ignoring them. A query like
    # "calm with no nightlife" should not also show a positive nightlife concept.
    for key in negated_keys:
        weights[key] -= 3.0
        detected.append(NEGATION_LABELS.get(key, f"less {key.replace('_', ' ')}"))

    # Balance common compound intents.
    if weights["family_friendliness"] > 0:
        weights["calm"] += 1.0
        weights["daily_convenience"] += 0.8
    if weights["calm"] > 0 and weights["youth_pulse"] > 0:
        weights["hygge"] += 0.8  # bridge concept: social but not chaotic
    if weights["rainy_day"] > 0 and weights["hygge"] == 0:
        weights["hygge"] += 1.0

    # Make all weights slider-friendly and keep negatives as meaningful absence.
    weights = {key: min(10.0, max(0.0, round(value, 1))) for key, value in weights.items()}

    if not any(weights.values()):
        weights.update({"hygge": 5.0, "calm": 4.0, "daily_convenience": 4.0})
        detected.append("balanced lifestyle default")

    return weights, detected


def parse_smart_search(query: str) -> dict[str, float]:
    """Backward-compatible parser returning only weights."""
    weights, _ = parse_smart_search_details(query)
    return weights


def _apply_compatibility_adjustments(output: pd.DataFrame, preferences: dict[str, float]) -> pd.Series:
    """Adjust matches for concepts that imply avoiding other signals.

    Example: a strong family query should not over-rank areas that are practical
    but extremely nightlife-heavy. These are small nudges, not hidden rules.
    """
    adjustment = pd.Series(0.0, index=output.index)
    total_pref = max(sum(max(0.0, float(v)) for v in preferences.values()), 1.0)

    def intensity(key: str) -> float:
        return max(0.0, float(preferences.get(key, 0.0))) / total_pref

    if "youth_pulse_score" in output.columns:
        nightlife_pressure = output["youth_pulse_score"].fillna(0)
        adjustment -= 0.16 * intensity("family_friendliness") * nightlife_pressure
        adjustment -= 0.10 * intensity("calm") * nightlife_pressure

    if "calm_score" in output.columns:
        adjustment += 0.08 * intensity("family_friendliness") * output["calm_score"].fillna(0)

    if "daily_convenience_score" in output.columns:
        adjustment += 0.06 * intensity("family_friendliness") * output["daily_convenience_score"].fillna(0)

    return adjustment


def rank_neighbourhoods(
    df: pd.DataFrame,
    preferences: dict[str, float],
    top_n: int | None = None,
) -> pd.DataFrame:
    """Rank neighbourhoods using weighted proxy scores plus light compatibility logic."""
    weights = normalize_preferences(preferences)
    output = df.copy()
    output["base_match_score"] = 0.0

    for pref_key, weight in weights.items():
        score_col = RECOMMENDATION_DIMENSIONS.get(pref_key)
        if score_col and score_col in output.columns:
            output["base_match_score"] += output[score_col].fillna(0) * weight

    output["match_adjustment"] = _apply_compatibility_adjustments(output, preferences)
    output["recommendation_score"] = (output["base_match_score"] + output["match_adjustment"]).clip(0, 1)

    ranked = output.sort_values("recommendation_score", ascending=False).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    return ranked.head(top_n) if top_n else ranked
