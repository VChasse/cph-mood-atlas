"""Reusable Streamlit renderers for the Copenhagen Mood Atlas app."""

from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.recommendation.explanations import preference_contributions, top_strengths
from src.recommendation.recommender import parse_smart_search_details, rank_neighbourhoods
from src.utils.config import BOUNDARIES_RAW_PATH, DISPLAY_SCORE_NAMES, SCORE_COLUMNS, SCORE_FORMULAS


BOUNDARY_NAME_KEYS = [
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

MOOD_META = {
    "hygge_score": {
        "emoji": "🕯️",
        "label": "Hygge",
        "short": "Coffee, reading, bakeries, benches and cosy social time",
        "class": "hygge",
        "color": "#F4A261",
        "ink": "#8A4A16",
        "soft": "rgba(244,162,97,0.18)",
        "colorscale": [[0.0, "#FFF2DA"], [0.35, "#FFD6A6"], [0.72, "#F4A261"], [1.0, "#A85516"]],
    },
    "youth_pulse_score": {
        "emoji": "⚡",
        "label": "Youth Pulse",
        "short": "Young adult energy, cafés, bars and culture nearby",
        "class": "youth",
        "color": "#FF4D6D",
        "ink": "#9B1732",
        "soft": "rgba(255,77,109,0.16)",
        "colorscale": [[0.0, "#FFE4EA"], [0.35, "#FF9AAD"], [0.72, "#FF4D6D"], [1.0, "#A4133C"]],
    },
    "rainy_day_index": {
        "emoji": "☔",
        "label": "Rainy Day Comfort",
        "short": "Indoor options like cafés, libraries, cinemas and museums",
        "class": "rain",
        "color": "#7B8CFF",
        "ink": "#3842A8",
        "soft": "rgba(123,140,255,0.16)",
        "colorscale": [[0.0, "#E9ECFF"], [0.35, "#BDC6FF"], [0.72, "#7B8CFF"], [1.0, "#3B46B8"]],
    },
    "international_friendliness_score": {
        "emoji": "🌍",
        "label": "International Feel",
        "short": "Diversity, daily services and cultural access",
        "class": "global",
        "color": "#22C7B8",
        "ink": "#08766C",
        "soft": "rgba(34,199,184,0.16)",
        "colorscale": [[0.0, "#DFFFFB"], [0.35, "#9EF3EA"], [0.72, "#22C7B8"], [1.0, "#08766C"]],
    },
    "calm_score": {
        "emoji": "🌿",
        "label": "Calm",
        "short": "Green space, lower nightlife pressure and easy rhythm",
        "class": "calm",
        "color": "#76BA4B",
        "ink": "#3F7625",
        "soft": "rgba(118,186,75,0.18)",
        "colorscale": [[0.0, "#EEF8E7"], [0.35, "#CDEDB8"], [0.72, "#76BA4B"], [1.0, "#3F7625"]],
    },
    "daily_convenience_score": {
        "emoji": "🛒",
        "label": "Daily Convenience",
        "short": "Shops, pharmacies, transit and bike parking for errands",
        "class": "daily",
        "color": "#FFD166",
        "ink": "#8B6509",
        "soft": "rgba(255,209,102,0.24)",
        "colorscale": [[0.0, "#FFF7D8"], [0.35, "#FFE8A3"], [0.72, "#FFD166"], [1.0, "#B77902"]],
    },
    "family_friendliness_score": {
        "emoji": "🧸",
        "label": "Family Living",
        "short": "Calm, green space, daily services and indoor friendly options",
        "class": "family",
        "color": "#FF9F9A",
        "ink": "#9B3F3A",
        "soft": "rgba(255,159,154,0.20)",
        "colorscale": [[0.0, "#FFE8E6"], [0.35, "#FFC9C5"], [0.72, "#FF9F9A"], [1.0, "#B94842"]],
    },
}

PREF_TO_SCORE = {
    "hygge": "hygge_score",
    "calm": "calm_score",
    "youth_pulse": "youth_pulse_score",
    "daily_convenience": "daily_convenience_score",
    "rainy_day": "rainy_day_index",
    "family_friendliness": "family_friendliness_score",
    "international_friendliness": "international_friendliness_score",
}

PREF_LABELS = {
    "hygge": "Hygge",
    "calm": "Calm",
    "youth_pulse": "Youth Pulse",
    "daily_convenience": "Daily Convenience",
    "rainy_day": "Rainy Day Comfort",
    "family_friendliness": "Family Living",
    "international_friendliness": "International Feel",
}

DEFAULT_THEME = {
    "emoji": "🗺️",
    "label": "Mood Fit",
    "short": "A simple district comparison score",
    "class": "atlas",
    "color": "#6C5CE7",
    "ink": "#35224A",
    "soft": "rgba(108,92,231,0.16)",
    "colorscale": [[0.0, "#F1E7DB"], [0.35, "#D5C6FF"], [0.72, "#8A6CFF"], [1.0, "#4B2E83"]],
}



def _safe(value: object) -> str:
    return html.escape(str(value))



def _clean_unsafe_html(fragment: str) -> str:
    """Remove Markdown code block indentation from HTML passed to st.markdown."""
    lines = [line.strip() for line in str(fragment).splitlines()]
    return "\n".join(line for line in lines if line)


_ORIGINAL_ST_MARKDOWN = st.markdown


def _atlas_markdown(body: Any, *args: Any, **kwargs: Any) -> Any:
    if kwargs.get("unsafe_allow_html") and isinstance(body, str):
        body = _clean_unsafe_html(body)
    return _ORIGINAL_ST_MARKDOWN(body, *args, **kwargs)


if not getattr(st.markdown, "_atlas_html_cleaned", False):
    _atlas_markdown._atlas_html_cleaned = True  # type: ignore[attr-defined]
    st.markdown = _atlas_markdown



def _pct(value: float) -> str:
    return f"{float(value):.0%}"



def _score_columns_in(df: pd.DataFrame) -> list[str]:
    return [col for col in SCORE_COLUMNS if col in df.columns]



def _meta(score_col: str) -> dict[str, Any]:
    return MOOD_META.get(score_col, DEFAULT_THEME)



def _normalise_name(value: object) -> str:
    """Normalize district names across KK Statbank and Open Data DK naming quirks."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = text.replace("district - ", "")
    text = re.sub(r"[/_–—-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()



def _boundary_name(properties: dict[str, Any], fallback: str) -> str:
    """Find a readable district name from varied Danish GeoJSON schemas."""
    for key in BOUNDARY_NAME_KEYS:
        value = properties.get(key)
        if value:
            return str(value).strip()
    for key, value in properties.items():
        if "navn" in str(key).lower() and value:
            return str(value).strip()
    return fallback


@st.cache_data(show_spinner=False)
def _load_boundary_geojson(boundaries_path: str) -> dict[str, Any] | None:
    """Load cached Copenhagen district polygons and attach stable feature IDs."""
    path = Path(boundaries_path)
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    features: list[dict[str, Any]] = []
    for idx, feature in enumerate(payload.get("features", []), start=1):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        properties = dict(feature.get("properties") or {})
        name = _boundary_name(properties, fallback=f"Boundary {idx}")
        key = _normalise_name(name)
        properties["atlas_name"] = name
        properties["atlas_key"] = key
        features.append({"type": "Feature", "id": key, "properties": properties, "geometry": geometry})

    if not features:
        return None
    return {"type": "FeatureCollection", "features": features}



def _map_rows_for_geojson(df: pd.DataFrame, geojson: dict[str, Any], score_col: str) -> pd.DataFrame:
    feature_keys = {feature.get("id") for feature in geojson.get("features", [])}
    map_df = df.copy()
    map_df["boundary_key"] = map_df["neighbourhood"].map(_normalise_name)
    map_df = map_df[map_df["boundary_key"].isin(feature_keys)].copy()
    map_df["score_percent"] = (map_df[score_col].astype(float) * 100).round(1)
    map_df["population_label"] = map_df["population"].map(lambda x: f"{int(x):,}")
    map_df["density_label"] = map_df["population_density"].map(lambda x: f"{float(x):,.0f}/km²")
    return map_df



def _quality(value: float) -> tuple[str, str]:
    value = float(value)
    if value >= 0.85:
        return "Dream match", "elite"
    if value >= 0.70:
        return "Great match", "great"
    if value >= 0.55:
        return "Good match", "good"
    if value >= 0.40:
        return "Mixed fit", "mixed"
    return "Light fit", "low"



def _strength_label(value: float) -> str:
    value = float(value)
    if value >= 0.85:
        return "dominant"
    if value >= 0.70:
        return "very strong"
    if value >= 0.55:
        return "strong"
    if value >= 0.40:
        return "present"
    return "subtle"



def _score_bar(value: float, score_col: str | None = None, *, height: int = 10) -> str:
    value = max(0.0, min(1.0, float(value)))
    pct = int(round(value * 100))
    meta = _meta(score_col or "")
    return (
        f'<div class="atlas-data-bar" style="height:{height}px">'
        f'<span style="width:{pct}%; background:{meta["color"]};"></span>'
        f'</div>'
    )



def _score_pill(score_col: str, value: float, *, show_label: bool = True) -> str:
    meta = _meta(score_col)
    label = meta["label"] if show_label else _strength_label(value).title()
    quality, quality_class = _quality(value)
    return (
        f'<span class="atlas-mood-pill {meta["class"]} {quality_class}">'
        f'<b>{meta["emoji"]}</b> {_safe(label)} <strong>{_pct(value)}</strong>'
        f'<em>{_safe(quality)}</em>'
        f'</span>'
    )



def _simple_pill(text: str, class_name: str = "atlas") -> str:
    return f'<span class="atlas-mood-pill {class_name}">{_safe(text)}</span>'



def _top_mood_pills(row: pd.Series, n: int = 3) -> str:
    return "".join(_score_pill(col, value) for col, value in top_strengths(row, n))



def _lowest_moods(row: pd.Series, n: int = 2) -> list[tuple[str, float]]:
    items = [(col, float(row[col])) for col in SCORE_COLUMNS if col in row and pd.notna(row[col])]
    items.sort(key=lambda item: item[1])
    return items[:n]



def _district_story(row: pd.Series) -> str:
    strengths = top_strengths(row, 3)
    if not strengths:
        return "This district has a balanced profile across the available mood signals."
    top_names = [_meta(col)["label"] for col, _ in strengths]
    first = _safe(str(row["neighbourhood"]))
    if len(top_names) == 1:
        return f"{first} is clearest when you want {top_names[0].lower()}."
    if len(top_names) == 2:
        return f"{first} feels strongest for {top_names[0].lower()} and {top_names[1].lower()}."
    return f"{first} is a strong pick for {top_names[0].lower()}, with clear {top_names[1].lower()} and {top_names[2].lower()} signals too."



def _preference_bars(preferences: dict[str, float]) -> str:
    max_value = max([float(v) for v in preferences.values()] + [1.0])
    rows: list[str] = []
    for pref_key, value in preferences.items():
        score_col = PREF_TO_SCORE.get(pref_key, "")
        meta = _meta(score_col)
        pct = int(round((float(value) / max_value) * 100)) if max_value else 0
        rows.append(
            f"""
            <div class="atlas-preference-row">
                <span>{meta['emoji']} {_safe(PREF_LABELS.get(pref_key, pref_key))}</span>
                <div class="atlas-preference-track"><b style="width:{pct}%; background:{meta['color']};"></b></div>
                <strong>{int(value)}/10</strong>
            </div>
            """
        )
    return "".join(rows)





def _mood_guide_grid() -> str:
    """Small visible guide so the sliders make immediate sense."""
    ordered_scores = [
        "hygge_score",
        "calm_score",
        "daily_convenience_score",
        "rainy_day_index",
        "youth_pulse_score",
        "family_friendliness_score",
        "international_friendliness_score",
    ]
    items: list[str] = []
    for score_col in ordered_scores:
        meta = _meta(score_col)
        items.append(
            f'<div class="atlas-mood-guide-pill {meta["class"]}">'
            f'<strong>{meta["emoji"]} {_safe(meta["label"])}</strong>'
            f'<span>{_safe(meta["short"])}</span>'
            f'</div>'
        )
    return "<div class='atlas-mood-guide-grid'>" + "".join(items) + "</div>"


def _mood_slider(label: str, score_col: str, value: int) -> int:
    meta = _meta(score_col)
    return st.slider(
        f"{meta['emoji']} {label}",
        0,
        10,
        int(value),
        help=meta["short"],
        label_visibility="visible",
        format="%d/10",
    )


def _profile_fit_score(row: pd.Series, preferences: dict[str, float]) -> float:
    """Return an absolute 0 to 1 fit based on distance from selected mood levels."""
    weighted_error = 0.0
    total_weight = 0.0

    for pref_key, raw_value in preferences.items():
        value = max(0.0, float(raw_value))
        if value <= 0:
            continue

        score_col = PREF_TO_SCORE.get(pref_key)
        if not score_col or score_col not in row:
            continue

        target = value / 10.0
        actual = max(0.0, min(1.0, float(row.get(score_col, 0.0))))
        miss = max(0.0, target - actual)
        extra = max(0.0, actual - target)
        distance = miss + 0.45 * extra
        weight = max(value, 1.0)
        weighted_error += weight * distance * distance
        total_weight += weight

    if total_weight <= 0:
        return 0.0

    rmse = (weighted_error / total_weight) ** 0.5
    return max(0.0, min(1.0, 1.0 - rmse))


def _recommend_quality(fit_score: float) -> tuple[str, str]:
    """Return the visible fit label from the same rounded score shown in the UI."""
    score = int(round(max(0.0, min(1.0, float(fit_score))) * 100))
    if score >= 92:
        return "Very close", "elite"
    if score >= 82:
        return "Close match", "great"
    if score >= 70:
        return "Good match", "good"
    if score >= 56:
        return "Some tradeoffs", "mixed"
    return "Loose match", "low"


def _match_bar(value: float, class_name: str, *, height: int = 12) -> str:
    value = max(0.0, min(1.0, float(value)))
    pct = int(round(value * 100))
    return (
        f'<div class="atlas-match-track {class_name}" style="height:{height}px">'
        f'<b style="width:{pct}%;"></b>'
        f'</div>'
    )


def _signal_bars(row: pd.Series, preferences: dict[str, float], *, max_items: int = 3) -> str:
    contributions = preference_contributions(row, preferences, max_items)
    items = [(col, score) for col, score, _ in contributions] if contributions else top_strengths(row, max_items)
    bars: list[str] = []
    for score_col, score in items:
        meta = _meta(score_col)
        bars.append(
            f'<div class="atlas-signal-row">'
            f'<span>{meta["emoji"]} {_safe(meta["label"])}</span>'
            f'{_score_bar(score, score_col, height=8)}'
            f'<strong>{_pct(score)}</strong>'
            f'</div>'
        )
    return "".join(bars)


def _compact_recommendation_row(row: pd.Series, preferences: dict[str, float]) -> str:
    fit_score = _profile_fit_score(row, preferences)
    label, quality_class = _recommend_quality(fit_score)
    score = int(round(fit_score * 100))
    return (
        f'<div class="atlas-reco-row {quality_class}">'
        f'<div class="atlas-rank-number">#{int(row["rank"])}</div>'
        f'<div class="atlas-reco-row-main">'
        f'<div class="atlas-reco-row-title"><strong>{_safe(row["neighbourhood"])}</strong><span>{_safe(label)} · {score}/100</span></div>'
        f'{_match_bar(fit_score, quality_class, height=13)}'
        f'<div class="atlas-signal-bars">{_signal_bars(row, preferences, max_items=3)}</div>'
        f'</div></div>'
    )

def _score_ladder(row: pd.Series, *, compact: bool = False) -> str:
    rows: list[str] = []
    for score_col in _score_columns_in(pd.DataFrame([row])):
        value = float(row[score_col])
        meta = _meta(score_col)
        quality, quality_class = _quality(value)
        rows.append(
            f"""
            <div class="atlas-ladder-row {quality_class}">
                <div class="atlas-ladder-label">
                    <span>{meta['emoji']}</span>
                    <strong>{_safe(meta['label'])}</strong>
                    <em>{_safe(quality)}</em>
                </div>
                <div class="atlas-ladder-meter">
                    {_score_bar(value, score_col, height=12 if not compact else 9)}
                </div>
                <b>{_pct(value)}</b>
            </div>
            """
        )
    return "".join(rows)



def _metric_snapshot(df: pd.DataFrame) -> None:
    total_population = int(df["population"].sum()) if "population" in df else 0
    top_hygge = df.sort_values("hygge_score", ascending=False).iloc[0]
    top_calm = df.sort_values("calm_score", ascending=False).iloc[0]
    top_rain = df.sort_values("rainy_day_index", ascending=False).iloc[0]
    cards = [
        ("Districts", f"{len(df)}", "Comparable areas"),
        ("People covered", f"{total_population:,}", "Cached public data"),
        ("Cosiest signal", str(top_hygge["neighbourhood"]), "Highest Hygge"),
        ("Rain plan winner", str(top_rain["neighbourhood"]), "Highest indoor comfort"),
        ("Calmest signal", str(top_calm["neighbourhood"]), "Highest Calm"),
    ]
    st.markdown(
        "<div class='atlas-snapshot-row'>"
        + "".join(
            f"""
            <div class="atlas-snapshot-card">
                <span>{_safe(label)}</span>
                <strong>{_safe(value)}</strong>
                <em>{_safe(caption)}</em>
            </div>
            """
            for label, value, caption in cards
        )
        + "</div>",
        unsafe_allow_html=True,
    )



def _render_popover_guide(context: str = "map") -> None:
    c1, c2, _ = st.columns([1, 1, 4])
    if context == "recommend":
        first_title = "👆 How to use this view"
        first_body = """
        **Recommend in three moves**

        1. Describe the everyday life you want.
        2. Tune only the moods that matter.
        3. Compare the shortlist from top to bottom.
        """
        fallback = "Describe your ideal everyday life, tune the mood mix, then compare the shortlist."
        score_body = """
        The fit score compares each district with the mood levels you picked. Higher means closer to your sliders.
        """
    else:
        first_title = "👆 How to use this view"
        first_body = """
        **Explore in three moves**

        1. Pick one mood lens.
        2. Click a district on the map.
        3. Read the signal bars.
        """
        fallback = "Pick a mood lens, then click a district to inspect it."
        score_body = """
        Scores compare Copenhagen districts. Higher means more of that mood here.
        """

    with c1:
        if hasattr(st, "popover"):
            with st.popover(first_title):
                st.markdown(first_body)
        else:
            st.info(fallback)
    with c2:
        if hasattr(st, "popover"):
            with st.popover("🧠 How to read scores"):
                st.markdown(score_body)



def _lens_picker(df: pd.DataFrame) -> str:
    score_cols = _score_columns_in(df)
    if "active_lens" not in st.session_state or st.session_state["active_lens"] not in score_cols:
        st.session_state["active_lens"] = "hygge_score" if "hygge_score" in score_cols else score_cols[0]

    with st.container(border=True):
        st.markdown(
            """
            <div class="atlas-lens-strip">
                <div>
                    <strong>Paint the map by mood</strong>
                    <span>Pick one lens, then click a district.</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selected = st.radio(
            "Mood lens",
            score_cols,
            index=score_cols.index(st.session_state["active_lens"]),
            format_func=lambda c: f"{_meta(c)['emoji']} {_meta(c)['label']}",
            horizontal=True,
            label_visibility="collapsed",
            key="active_lens",
        )
        meta = _meta(selected)
        st.markdown(
            f"""
            <div class="atlas-active-mood-note {meta['class']}">
                <strong>{meta['emoji']} {_safe(meta['label'])}</strong>
                <span>{_safe(meta['short'])}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    return selected


def _extract_selected_from_event(event: Any, map_df: pd.DataFrame) -> str | None:
    if not event:
        return None
    selection: Any = None
    if isinstance(event, dict):
        selection = event.get("selection")
    else:
        selection = getattr(event, "selection", None)
    if not selection:
        return None
    if isinstance(selection, dict):
        points = selection.get("points") or []
    else:
        points = getattr(selection, "points", []) or []
    if not points:
        return None
    point = points[0]
    if isinstance(point, dict):
        customdata = point.get("customdata")
        if customdata:
            return str(customdata[0])
        location = point.get("location")
        if location:
            match = map_df.loc[map_df["boundary_key"].eq(str(location)), "neighbourhood"]
            if not match.empty:
                return str(match.iloc[0])
    return None



def _render_polygon_map(df: pd.DataFrame, score_col: str, selected: str) -> str | None:
    geojson = _load_boundary_geojson(str(BOUNDARIES_RAW_PATH))
    if geojson is None:
        st.error("Boundary polygons are missing. Run the boundary ingestion script before launching the app.")
        return None

    map_df = _map_rows_for_geojson(df, geojson, score_col)
    if map_df.empty:
        st.error("No district rows could be matched to the boundary file. Check district names in the processed data.")
        return None

    selected_key = _normalise_name(selected)
    meta = _meta(score_col)
    customdata = map_df[["neighbourhood", "population_label", "density_label", "score_percent"]].to_numpy()

    fig = go.Figure(
        go.Choroplethmapbox(
            geojson=geojson,
            locations=map_df["boundary_key"],
            z=map_df[score_col].astype(float),
            featureidkey="id",
            customdata=customdata,
            colorscale=meta["colorscale"],
            marker_line_width=1.2,
            marker_line_color="rgba(255,255,255,0.90)",
            colorbar=dict(
                title=meta["label"],
                tickformat=".0%",
                thickness=12,
                len=0.72,
                y=0.5,
                bgcolor="rgba(255,255,255,0.86)",
                outlinewidth=0,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                + f"{meta['label']}: "
                + "%{z:.0%}<br>Population: %{customdata[1]}<br>Density: %{customdata[2]}<extra></extra>"
            ),
        )
    )

    selected_row = map_df[map_df["boundary_key"].eq(selected_key)]
    if not selected_row.empty:
        fig.add_trace(
            go.Choroplethmapbox(
                geojson=geojson,
                locations=selected_row["boundary_key"],
                z=[1],
                featureidkey="id",
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                showscale=False,
                marker_line_width=4.4,
                marker_line_color="#20182E",
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        mapbox=dict(
            style="carto-positron",
            center={"lat": float(map_df["lat"].mean()), "lon": float(map_df["lon"].mean())},
            zoom=10.0,
        ),
        height=520,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        clickmode="event+select",
    )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="atlas-map-header">
                <div>
                    <div class="atlas-kicker">{meta['emoji']} Map lens</div>
                    <h3>{_safe(meta['label'])}</h3>
                </div>
                <span class="atlas-map-click-pill">Click to inspect</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            event = st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False, "scrollZoom": True},
                on_select="rerun",
                selection_mode="points",
                key=f"district_map_{score_col}",
            )
        except TypeError:
            event = st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown(
            "<p class='atlas-under-note'>Hover for a quick preview. Click a district to update the panel.</p>",
            unsafe_allow_html=True,
        )
    return _extract_selected_from_event(event, map_df)



def _neighbourhood_profile(row: pd.Series, score_col: str) -> None:
    active_value = float(row[score_col])
    active_quality, active_class = _quality(active_value)
    active_meta = _meta(score_col)
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="atlas-profile-hero {active_meta['class']}">
                <div class="atlas-profile-topline">
                    <span class="atlas-profile-icon">{active_meta['emoji']}</span>
                    <span class="atlas-match-badge {active_class}">{_safe(active_quality)} · {_pct(active_value)}</span>
                </div>
                <h2>{_safe(row['neighbourhood'])}</h2>
                <p>{_district_story(row)}</p>
                <div class="atlas-top-pills">{_top_mood_pills(row, 3)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="atlas-profile-facts compact">
                <span>👥 {int(row['population']):,}</span>
                <span>🏙️ {float(row['population_density']):,.0f}/km²</span>
            </div>
            <div class="atlas-profile-section compact">
                <strong>Signal bars</strong>
                <span>Fastest way to read the district.</span>
            </div>
            <div class="atlas-ladder compact">{_score_ladder(row, compact=True)}</div>
            """,
            unsafe_allow_html=True,
        )


def render_hygge_map(df: pd.DataFrame) -> None:
    """Render the main map and district intelligence page."""
    st.markdown(
        """
        <div class="atlas-intro-line compact">
            <span>🗺️ Explore</span>
            <strong>Pick a mood, then click directly on the map.</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_popover_guide("map")
    score_col = _lens_picker(df)

    if "selected_district" not in st.session_state or st.session_state["selected_district"] not in df["neighbourhood"].tolist():
        st.session_state["selected_district"] = df.sort_values(score_col, ascending=False).iloc[0]["neighbourhood"]

    selected = st.session_state["selected_district"]
    left, right = st.columns([1.62, 0.88], gap="large")
    with left:
        clicked = _render_polygon_map(df, score_col, selected)
        if clicked and clicked != st.session_state.get("selected_district"):
            st.session_state["selected_district"] = clicked
            st.rerun()

    with right:
        row = df.loc[df["neighbourhood"].eq(st.session_state["selected_district"])].iloc[0]
        _neighbourhood_profile(row, score_col)


def _query_examples() -> None:
    examples = [
        ("🌳", "Quiet mornings", "parks, bakeries, reading spots, easy errands"),
        ("⚡", "Social weekend", "bars, culture, late cafés, strong youth energy"),
        ("🧸", "Family base", "green, practical, calm, low nightlife pressure"),
    ]
    st.markdown(
        "<div class='atlas-example-grid'>"
        + "".join(
            f"""
            <div class="atlas-prompt-card">
                <span>{emoji}</span>
                <strong>{_safe(title)}</strong>
                <p>{_safe(body)}</p>
            </div>
            """
            for emoji, title, body in examples
        )
        + "</div>",
        unsafe_allow_html=True,
    )



def render_recommendations(df: pd.DataFrame) -> None:
    """Render the recommendation engine."""
    st.markdown(
        """
        <div class="atlas-intro-line compact recommend">
            <span>✨ Recommend</span>
            <strong>Describe your Copenhagen life. Adjust the mood mix. Compare the matches.</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_popover_guide("recommend")

    default_preferences = {
        "hygge": 6,
        "calm": 5,
        "youth_pulse": 3,
        "daily_convenience": 5,
        "rainy_day": 3,
        "family_friendliness": 2,
        "international_friendliness": 3,
    }

    controls, results = st.columns([0.82, 1.48], gap="large")
    with controls:
        with st.container(border=True):
            st.markdown(
                """
                <div class="atlas-control-step">
                    <span>1</span>
                    <div>
                        <strong>Describe the vibe</strong>
                        <p>One sentence is enough.</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            query = st.text_area(
                "Ask Copenhagen Lite",
                placeholder="Example: calm streets, green space, good cafés, easy errands, rainy day options, not too much nightlife.",
                height=76,
                label_visibility="collapsed",
            )

        if query:
            parsed_preferences, detected_concepts = parse_smart_search_details(query)
            default_preferences.update(parsed_preferences)
        else:
            detected_concepts = []

        with st.container(border=True):
            st.markdown(
                """
                <div class="atlas-control-step compact-mix">
                    <span>2</span>
                    <div>
                        <strong>Tune the mood mix</strong>
                        <p>Hover a slider for the mood meaning.</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            mood_cards = [
                ("hygge", "Hygge", "hygge_score", int(default_preferences["hygge"])),
                ("calm", "Calm", "calm_score", int(default_preferences["calm"])),
                ("daily_convenience", "Daily", "daily_convenience_score", int(default_preferences["daily_convenience"])),
                ("rainy_day", "Rain", "rainy_day_index", int(default_preferences["rainy_day"])),
                ("youth_pulse", "Youth", "youth_pulse_score", int(default_preferences["youth_pulse"])),
                ("family_friendliness", "Family", "family_friendliness_score", int(default_preferences["family_friendliness"])),
                ("international_friendliness", "Global", "international_friendliness_score", int(default_preferences["international_friendliness"])),
            ]
            preferences = {}
            slider_cols = st.columns(2, gap="medium")
            for idx, (pref_key, label, score_col, default_value) in enumerate(mood_cards):
                with slider_cols[idx % 2]:
                    preferences[pref_key] = _mood_slider(label, score_col, default_value)

        if detected_concepts:
            concept_pills = "".join(_simple_pill(concept, "global") for concept in detected_concepts[:5])
            st.markdown(
                f"""
                <div class="atlas-detected-strip">
                    <strong>Detected</strong>
                    <div>{concept_pills}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    ranked = rank_neighbourhoods(df, preferences, top_n=len(df)).copy()
    if not ranked.empty:
        ranked["profile_fit_score"] = ranked.apply(lambda row: _profile_fit_score(row, preferences), axis=1)
        ranked = ranked.sort_values(
            ["profile_fit_score", "recommendation_score"],
            ascending=[False, False],
            kind="mergesort",
        ).head(6).reset_index(drop=True)
        ranked["rank"] = ranked.index + 1

    with results:
        st.markdown(
            """
            <div class="atlas-section-shell top-results compact">
                <div class="atlas-control-step results-head">
                    <span>3</span>
                    <div>
                        <strong>Compare the shortlist</strong>
                        <p>Fit bars compare districts with your selected mood levels.</p>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for _, row in ranked.iterrows():
            st.markdown(_compact_recommendation_row(row, preferences), unsafe_allow_html=True)

def render_methodology(df: pd.DataFrame) -> None:
    """Render the methodology page."""
    st.markdown(
        """
        <div class="atlas-method-hero">
            <div class="atlas-kicker">🔍 Method</div>
            <h2>How the scores work</h2>
            <p>Cached public data, cleaned once, then turned into mood scores.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    source_cards = [
        ("OpenStreetMap", "Cafés, shops, libraries, culture, transit and similar places."),
        ("Open Data DK", "District boundaries for the map."),
        ("KK Statistikbank", "Population, age, citizenship and family indicators."),
    ]
    st.markdown(
        "<div class='atlas-source-grid'>"
        + "".join(
            f"""
            <div class="atlas-source-card">
                <span>Source</span>
                <strong>{_safe(title)}</strong>
                <p>{_safe(body)}</p>
            </div>
            """
            for title, body in source_cards
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    rows = [
        ("hygge_score", "Cafés, bakeries, libraries, benches and bike access."),
        ("calm_score", "Green space, low nightlife pressure and lower density."),
        ("youth_pulse_score", "Young adults, bars, cafés and culture."),
        ("daily_convenience_score", "Shops, pharmacies, transit, toilets and bike parking."),
        ("rainy_day_index", "Cafés, libraries, cinemas, museums and culture."),
        ("family_friendliness_score", "Families, green space, calm, errands and indoor options."),
        ("international_friendliness_score", "Citizenship diversity, daily services and culture."),
    ]
    st.markdown(
        "<div class='atlas-method-grid'>"
        + "".join(
            f"""
            <div class="atlas-method-card {_meta(score_col)['class']}">
                <span>{_meta(score_col)['emoji']}</span>
                <strong>{_safe(_meta(score_col)['label'])}</strong>
                <p>{_safe(signal)}</p>
            </div>
            """
            for score_col, signal in rows
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    formula_rows = []
    for score_col in SCORE_COLUMNS:
        weights = SCORE_FORMULAS.get(score_col, {})
        formula_rows.append(
            {
                "Score": DISPLAY_SCORE_NAMES.get(score_col, score_col),
                "Formula weights": " + ".join(
                    f"{feature.replace('_norm', '').replace('_', ' ')} ({weight:.0%})" for feature, weight in weights.items()
                ),
            }
        )

    st.markdown(
        """
        <div class="atlas-card">
            <div class="atlas-kicker">Formula audit</div>
            <h3>Score weights</h3>
            <p>The exact ingredients behind each score.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(pd.DataFrame(formula_rows), use_container_width=True, hide_index=True)

    mode = df["data_mode"].iloc[0] if "data_mode" in df.columns else "unknown"
    st.markdown(
        f"""
        <div class="atlas-card atlas-dataset-card">
            <div class="atlas-kicker">Current dataset</div>
            <p>Rows: <strong>{len(df)}</strong></p>
            <p>Mode: <strong>{_safe(mode)}</strong></p>
            <p>Data rule: no mock values are shown.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Current processed columns"):
        st.write(list(df.columns))


# Backward compatible aliases for older page files or imports.
def render_overview(df: pd.DataFrame) -> None:
    render_hygge_map(df)



def render_explorer(df: pd.DataFrame) -> None:
    render_hygge_map(df)
