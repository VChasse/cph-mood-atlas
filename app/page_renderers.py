"""Reusable Streamlit renderers for the production-ready Copenhagen Mood Atlas app."""

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

from src.recommendation.explanations import explain_neighbourhood, explain_recommendation
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

LENS_EXPLAINERS = {
    "hygge_score": ("🕯️", "Hygge", "cosy places for coffee, reading, meeting people and slowing down"),
    "calm_score": ("🌿", "Calm", "green space, lower nightlife pressure and a softer city rhythm"),
    "youth_pulse_score": ("⚡", "Youth pulse", "young-adult energy, cafés, bars and cultural places"),
    "daily_convenience_score": ("🛒", "Daily convenience", "shops, pharmacies, transit and bike parking for everyday errands"),
    "rainy_day_index": ("☔", "Rainy-day comfort", "indoor-friendly places like cafés, libraries, cinemas, museums and cultural spots"),
    "family_friendliness_score": ("🧸", "Family living", "calm, green space, daily services and indoor-friendly options"),
    "international_friendliness_score": ("🌍", "International feel", "a citizenship-based diversity proxy, supported by services and cultural access"),
}


def _safe(value: object) -> str:
    return html.escape(str(value))


def _pct(value: float) -> str:
    return f"{float(value):.0%}"


def _score_columns_in(df: pd.DataFrame) -> list[str]:
    return [col for col in SCORE_COLUMNS if col in df.columns]


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
    """Load cached Copenhagen district polygons and attach stable feature IDs.

    The app never calls Open Data DK at runtime. It only reads the local GeoJSON
    cached by `python -m src.ingestion.fetch_boundaries`.
    """
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
        features.append(
            {
                "type": "Feature",
                "id": key,
                "properties": properties,
                "geometry": geometry,
            }
        )

    if not features:
        return None
    return {"type": "FeatureCollection", "features": features}


def _map_rows_for_geojson(df: pd.DataFrame, geojson: dict[str, Any], score_col: str) -> pd.DataFrame:
    """Return rows that can be joined to the boundary GeoJSON."""
    feature_keys = {feature.get("id") for feature in geojson.get("features", [])}
    map_df = df.copy()
    map_df["boundary_key"] = map_df["neighbourhood"].map(_normalise_name)
    map_df = map_df[map_df["boundary_key"].isin(feature_keys)].copy()
    map_df["score_percent"] = (map_df[score_col].astype(float) * 100).round(1)
    map_df["population_label"] = map_df["population"].map(lambda x: f"{int(x):,}")
    map_df["density_label"] = map_df["population_density"].map(lambda x: f"{float(x):,.0f}/km²")
    return map_df


def _journey_strip() -> None:
    """Compact guidance that stays integrated with the main page flow."""
    st.markdown(
        """
        <div class="atlas-journey-strip">
            <div class="atlas-journey-step"><span>🧭</span><strong>Step 1</strong><em>Choose a map lens</em></div>
            <div class="atlas-journey-step"><span>👆</span><strong>Step 2</strong><em>Inspect a district</em></div>
            <div class="atlas-journey-step"><span>✨</span><strong>Step 3</strong><em>Get a match</em></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _lens_note(score_col: str) -> None:
    """One short explanation for the active map lens."""
    emoji, title, text = LENS_EXPLAINERS.get(
        score_col,
        ("🗺️", DISPLAY_SCORE_NAMES.get(score_col, score_col), "a simple district comparison score"),
    )
    st.markdown(
        f"""
        <p class="atlas-under-note">
            {emoji} <span>{_safe(title)}</span> shows {_safe(text)}.
            Higher means “more of this vibe here”, not “better”.
        </p>
        """,
        unsafe_allow_html=True,
    )


def _metric_cards(df: pd.DataFrame) -> None:
    total_population = int(df["population"].sum()) if "population" in df else 0
    top_hygge = df.sort_values("hygge_score", ascending=False).iloc[0]
    calmest = df.sort_values("calm_score", ascending=False).iloc[0]
    best_convenience = df.sort_values("daily_convenience_score", ascending=False).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Districts", f"{len(df)}")
    c2.metric("People covered", f"{total_population:,}")
    c3.metric("Cosiest vibe", str(top_hygge["neighbourhood"]))
    c4.metric("Easiest errands", str(best_convenience["neighbourhood"]))

    st.markdown(
        f"""
        <div class="atlas-card atlas-cheat-card">
            <div class="atlas-kicker">Quick read</div>
            <p>
                🕯️ <span class="atlas-pill">Cosy: {_safe(top_hygge['neighbourhood'])}</span>
                🌿 <span class="atlas-pill">Calm: {_safe(calmest['neighbourhood'])}</span>
                🛒 <span class="atlas-pill">Practical: {_safe(best_convenience['neighbourhood'])}</span>
            </p>
            <p class="atlas-note">
                A light summary of the strongest districts by score. Use it as a starting point, not a verdict.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _indicator_dictionary() -> None:
    """Compact explanation of every score."""
    with st.expander("🧃 Indicator guide"):
        st.markdown(
            """
            <p class="atlas-note">
                *Scores compare Copenhagen districts with each other. They are helpful signals, not official labels.
            </p>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        items = list(LENS_EXPLAINERS.values())
        for idx, (emoji, title, text) in enumerate(items):
            cols[idx % 2].markdown(
                f"""
                <div class="atlas-lens-guide compact">
                    {emoji} <span>{_safe(title)}</span><br>
                    <em>{_safe(text)}.</em>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _selected_score_summary(row: pd.Series) -> None:
    """Render four compact score callouts for the selected district."""
    score_items = [
        ("Hygge", row.get("hygge_score", 0)),
        ("Calm", row.get("calm_score", 0)),
        ("Convenience", row.get("daily_convenience_score", 0)),
        ("Rainy-day", row.get("rainy_day_index", 0)),
    ]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, score_items, strict=False):
        col.markdown(
            f"""
            <div class="atlas-score-chip">
                <span>{_safe(label)}</span>
                <strong>{_pct(float(value))}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _progress_bar(value: float) -> str:
    """Return a small HTML progress bar for normalized scores."""
    pct = max(0, min(100, int(round(float(value) * 100))))
    return (
        f'<div class="atlas-progress" aria-label="Score {pct}%">'
        f'<span style="width:{pct}%"></span>'
        f'</div>'
    )


def _render_ranked_district_cards(df: pd.DataFrame, score_col: str) -> None:
    """Replace the old bar chart with a quieter, scannable ranking stack."""
    score_name = DISPLAY_SCORE_NAMES.get(score_col, score_col)
    top = df.sort_values(score_col, ascending=False).head(6).copy()
    emoji, title, _ = LENS_EXPLAINERS.get(score_col, ("🗺️", score_name, ""))

    st.markdown(
        f"""
        <div class="atlas-card atlas-section-card atlas-rank-shell">
            <div class="atlas-section-heading">
                <div>
                    <div class="atlas-kicker">{emoji} Lens leaderboard</div>
                    <h3>Top districts for {_safe(title)}</h3>
                    <p>Six fast recommendations without the noise of a chart. Scores are relative signals across Copenhagen districts.</p>
                </div>
                <span class="atlas-status-pill">Card view</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        score = float(row[score_col])
        supporting = []
        if "population" in row:
            supporting.append(f"{int(row['population']):,} people")
        if "population_density" in row:
            supporting.append(f"{float(row['population_density']):,.0f}/km²")
        support_text = " · ".join(supporting) or "Copenhagen district"
        st.markdown(
            f"""
            <div class="atlas-ranking-row">
                <div class="atlas-rank-number">#{rank}</div>
                <div class="atlas-rank-copy">
                    <strong>{_safe(row['neighbourhood'])}</strong>
                    <span>{_safe(support_text)}</span>
                    {_progress_bar(score)}
                </div>
                <div class="atlas-score-badge">{_pct(score)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_recommendation_ranking(ranked: pd.DataFrame, preferences: dict[str, int]) -> None:
    """Render recommendations as Clay-like cards instead of a bar chart."""
    st.markdown(
        """
        <div class="atlas-card atlas-section-card atlas-rank-shell">
            <div class="atlas-section-heading">
                <div>
                    <div class="atlas-kicker">🧭 Full shortlist</div>
                    <h3>All ranked matches</h3>
                    <p>Cards keep the recommendation engine readable. Open the table below when you need the raw audit trail.</p>
                </div>
                <span class="atlas-status-pill">Shortlist</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for _, row in ranked.iterrows():
        match = float(row["recommendation_score"])
        st.markdown(
            f"""
            <div class="atlas-ranking-row atlas-ranking-row-large">
                <div class="atlas-rank-number">#{int(row['rank'])}</div>
                <div class="atlas-rank-copy">
                    <strong>{_safe(row['neighbourhood'])}</strong>
                    <span>{explain_recommendation(row, preferences)}</span>
                    {_progress_bar(match)}
                </div>
                <div class="atlas-score-badge">{_pct(match)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _neighbourhood_profile(row: pd.Series) -> None:
    """Render the selected district card and radar in one visual block."""
    score_cols = _score_columns_in(pd.DataFrame([row]))
    radar_label_overrides = {
        "hygge_score": "Hygge",
        "calm_score": "Calm",
        "daily_convenience_score": "Conven.",
        "international_friendliness_score": "Intl.",
        "family_friendliness_score": "Family",
        "youth_pulse_score": "Youth",
        "rainy_day_index": "Rainy",
    }
    radar = pd.DataFrame(
        {
            "dimension": [radar_label_overrides.get(c, DISPLAY_SCORE_NAMES.get(c, c)) for c in score_cols],
            "score": [float(row[c]) for c in score_cols],
            "full_dimension": [DISPLAY_SCORE_NAMES.get(c, c) for c in score_cols],
        }
    )
    radar_closed = pd.concat([radar, radar.iloc[[0]]], ignore_index=True)

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=radar_closed["score"],
                theta=radar_closed["dimension"],
                customdata=radar_closed["full_dimension"],
                fill="toself",
                fillcolor="rgba(15,85,87,0.16)",
                line=dict(color="#0F5557", width=3),
                marker=dict(color="#0F5557", size=7),
                name=str(row["neighbourhood"]),
                hovertemplate="%{customdata}<br>Score: %{r:.0%}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        polar=dict(
            domain=dict(x=[0.12, 0.88], y=[0.05, 0.98]),
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickformat=".0%",
                tickfont=dict(size=9),
                gridcolor="rgba(15, 31, 34, 0.14)",
            ),
            angularaxis=dict(tickfont=dict(size=10), rotation=90, direction="clockwise"),
        ),
        showlegend=False,
        height=405,
        margin=dict(l=18, r=18, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="atlas-kicker">Selected district</div>
            <h3 style="margin:0.05rem 0 0.45rem 0;">{_safe(row['neighbourhood'])}</h3>
            <p style="font-size:0.94rem; line-height:1.48; margin-bottom:0.75rem; color:var(--atlas-muted);">
                {explain_neighbourhood(row)}
            </p>
            <div class="atlas-divider"></div>
            <span class="atlas-pill">Population: {int(row['population']):,}</span>
            <span class="atlas-pill">Density: {float(row['population_density']):,.0f}/km²</span>
            <span class="atlas-pill">Source: public data</span>
            """,
            unsafe_allow_html=True,
        )
        _selected_score_summary(row)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_polygon_map(df: pd.DataFrame, score_col: str, selected: str) -> None:
    """Render the production map as official Copenhagen district polygons."""
    geojson = _load_boundary_geojson(str(BOUNDARIES_RAW_PATH))
    if geojson is None:
        st.error("Boundary polygons are missing. Run `python -m src.ingestion.fetch_boundaries` before launching the app.")
        return

    map_df = _map_rows_for_geojson(df, geojson, score_col)
    if map_df.empty:
        st.error("No district rows could be matched to the boundary GeoJSON. Check district names in the processed data.")
        return

    selected_key = _normalise_name(selected)
    score_name = DISPLAY_SCORE_NAMES.get(score_col, score_col)
    customdata = map_df[["neighbourhood", "population_label", "density_label"]].to_numpy()

    fig = go.Figure(
        go.Choroplethmapbox(
            geojson=geojson,
            locations=map_df["boundary_key"],
            z=map_df[score_col].astype(float),
            featureidkey="id",
            customdata=customdata,
            colorscale=[
                [0.00, "#EFE6D4"],
                [0.25, "#DDE7D3"],
                [0.55, "#A5BE98"],
                [0.78, "#3F837C"],
                [1.00, "#0F5557"],
            ],
            marker_line_width=1.1,
            marker_line_color="rgba(255,255,255,0.82)",
            colorbar=dict(
                title=score_name,
                tickformat=".0%",
                thickness=12,
                len=0.74,
                y=0.5,
                bgcolor="rgba(255,255,255,0.78)",
                outlinewidth=0,
            ),
            hovertemplate=(
                "%{customdata[0]}<br>"
                + f"{score_name}: "
                + "%{z:.0%}<br>"
                + "Population: %{customdata[1]}<br>"
                + "Density: %{customdata[2]}"
                + "<extra></extra>"
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
                marker_line_width=3.2,
                marker_line_color="#C9892B",
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        mapbox=dict(
            style="carto-positron",
            center={"lat": float(map_df["lat"].mean()), "lon": float(map_df["lon"].mean())},
            zoom=10.0,
        ),
        height=670,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )

    with st.container(border=True):
        emoji, _, explainer = LENS_EXPLAINERS.get(score_col, ("🗺️", score_name, "a simple score for comparing districts"))
        st.markdown(
            f"""
            <div class="atlas-kicker">{emoji} Map</div>
            <p class="atlas-helper-text">
                Darker districts score higher for <span>{_safe(score_name)}</span>. Hover for the numbers; use the selector to compare a district beside the map.
            </p>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_hygge_map(df: pd.DataFrame) -> None:
    """Render the main map and district intelligence page."""
    st.markdown(
        """
        <div class="atlas-card atlas-feature-card">
            <div class="atlas-kicker">🗺️ Explore</div>
            <h3>Find the Copenhagen district that fits the moment</h3>
            <p>
                Choose a vibe, compare the map, then inspect a district profile. The app keeps the data behind the scenes and the story up front.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _journey_strip()
    _metric_cards(df)

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    control_card_left, control_card_right = st.columns([1.4, 1.05], gap="large")
    with control_card_left:
        st.markdown(
            """
            <div class="atlas-step-label">
                <span class="atlas-step-icon">🧭</span>
                <span><strong>Step 1</strong><em>Choose a map lens</em></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        score_col = st.selectbox(
            "Choose a map lens",
            _score_columns_in(df),
            index=0,
            format_func=lambda c: DISPLAY_SCORE_NAMES.get(c, c),
            label_visibility="collapsed",
            help="The Method tab shows exact formulas.",
        )
        _lens_note(score_col)
    with control_card_right:
        st.markdown(
            """
            <div class="atlas-step-label">
                <span class="atlas-step-icon">👆</span>
                <span><strong>Step 2</strong><em>Inspect a district</em></span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selected = st.selectbox(
            "Inspect a district",
            df.sort_values(score_col, ascending=False)["neighbourhood"].tolist(),
            label_visibility="collapsed",
        )
        st.markdown(
            "<p class='atlas-under-note'>Open its profile beside the map. Radar = quick vibe check.</p>",
            unsafe_allow_html=True,
        )

    _indicator_dictionary()

    row = df.loc[df["neighbourhood"] == selected].iloc[0]
    left, right = st.columns([1.42, 1.08], gap="large")
    with left:
        _render_polygon_map(df, score_col, selected)
    with right:
        _neighbourhood_profile(row)

    st.markdown("<div class='atlas-divider'></div>", unsafe_allow_html=True)

    _render_ranked_district_cards(df, score_col)


def render_recommendations(df: pd.DataFrame) -> None:
    """Render the streamlined recommendation engine."""
    st.markdown(
        """
        <div class="atlas-card atlas-feature-card atlas-lite-hero">
            <div class="atlas-kicker">✨ Copenhagen Lite</div>
            <h3>Chat your way to the right Copenhagen district</h3>
            <p>
                Describe the kind of neighbourhood, mood, rhythm or day you want.
                Copenhagen Lite reads your message, translates it into preference signals,
                and ranks the districts with clear explanations.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    example_cols = st.columns(3)
    examples = [
        "quiet mornings, parks, bakeries, easy errands",
        "date night, wine bars, culture, late cafés",
        "family-friendly, green, practical, low nightlife",
    ]
    for col, example in zip(example_cols, examples, strict=False):
        col.markdown(
            f"""
            <div class="atlas-example-card atlas-example-card-clickable">
                <span>Prompt idea</span>
                <p>{_safe(example)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    default_preferences = {
        "hygge": 6,
        "calm": 5,
        "youth_pulse": 3,
        "daily_convenience": 5,
        "rainy_day": 3,
        "family_friendliness": 2,
        "international_friendliness": 3,
    }

    if "atlas_lite_query" not in st.session_state:
        st.session_state["atlas_lite_query"] = ""

    if "atlas_lite_query_input" not in st.session_state:
        st.session_state["atlas_lite_query_input"] = st.session_state["atlas_lite_query"]

    st.markdown(
        """
        <div class="atlas-lite-chat-card">
            <div class="atlas-lite-chat-top">
                <div class="atlas-lite-avatar">✨</div>
                <div>
                    <strong>Copenhagen Lite</strong>
                    <span>Online · ready to match your Copenhagen mood</span>
                </div>
            </div>
            <div class="atlas-lite-message-row">
                <div class="atlas-lite-message atlas-lite-message-assistant">
                    <span class="atlas-lite-message-label">Copenhagen Lite</span>
                    <p>
                        Tell me what kind of Copenhagen you want. You can mention cafés,
                        calm streets, nightlife, green areas, transit, rainy-day plans,
                        families, culture or international energy.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("copenhagen_lite_chat_form", clear_on_submit=False):
        query_input = st.text_area(
            "Message Copenhagen Lite",
            placeholder=(
                "Write your message here...\n\n"
                "Example: I want a calm neighbourhood with cosy cafés, parks, easy transit, "
                "rainy-day options, and not too much nightlife."
            ),
            height=190,
            label_visibility="collapsed",
            key="atlas_lite_query_input",
        )
        submitted = st.form_submit_button(
            "Send to Copenhagen Lite →",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        st.session_state["atlas_lite_query"] = query_input.strip()

    query = st.session_state["atlas_lite_query"]

    if query:
        st.markdown(
            f"""
            <div class="atlas-lite-message-row atlas-lite-message-row-user">
                <div class="atlas-lite-message atlas-lite-message-user">
                    <span class="atlas-lite-message-label">You</span>
                    <p>{_safe(query)}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <p class="atlas-lite-helper">
            Tip: the more specific you are, the better the match. Mention pace, noise, cafés,
            parks, culture, family needs, transport, or rainy-day plans.
        </p>
        """,
        unsafe_allow_html=True,
    )

    if query:
        parsed_preferences, detected_concepts = parse_smart_search_details(query)
        default_preferences.update(parsed_preferences)
    else:
        detected_concepts = []

    if detected_concepts:
        concept_pills = "".join(f'<span class="atlas-pill">{_safe(concept)}</span>' for concept in detected_concepts[:7])
        st.markdown(
            f"""
            <div class="atlas-card atlas-smart-search-card">
                <div class="atlas-kicker">Smart Search understood</div>
                <h3>Signals detected from your message</h3>
                <div class="atlas-pill-row">
                    {concept_pills}
                </div>
                <p>
                    Copenhagen Lite translated these words into preference weights behind the scenes.
                    You can still adjust everything manually below.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    left, right = st.columns([0.9, 1.35], gap="large")
    with left:
        st.markdown(
            """
            <div class="atlas-card sticky-preferences">
                <div class="atlas-kicker">Fine-tune</div>
                <h3>Preferences</h3>
                <p>Move the sliders to adjust the match. More green, less noise, extra coffee — your call.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        preferences = {
            "hygge": st.slider("Hygge / cafés", 0, 10, int(default_preferences["hygge"])),
            "calm": st.slider("Calm / green", 0, 10, int(default_preferences["calm"])),
            "daily_convenience": st.slider("Convenience / transit", 0, 10, int(default_preferences["daily_convenience"])),
            "youth_pulse": st.slider("Youth / social energy", 0, 10, int(default_preferences["youth_pulse"])),
            "rainy_day": st.slider("Rainy-day comfort", 0, 10, int(default_preferences["rainy_day"])),
            "family_friendliness": st.slider("Family living", 0, 10, int(default_preferences["family_friendliness"])),
            "international_friendliness": st.slider("International feel", 0, 10, int(default_preferences["international_friendliness"])),
        }

    ranked = rank_neighbourhoods(df, preferences, top_n=8)

    with right:
        st.markdown(
            """
            <div class="atlas-card atlas-results-intro">
                <div class="atlas-kicker">Best matches</div>
                <h3>Your top Copenhagen fits</h3>
                <p>
                    The strongest matches appear first. Each explanation highlights the signals
                    that mattered most for your prompt and slider weights.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for _, row in ranked.head(3).iterrows():
            st.markdown(
                f"""
                <div class="atlas-card recommendation-card recommendation-card-large">
                    <div class="atlas-reco-topline">
                        <span class="atlas-rank-bubble">#{int(row['rank'])}</span>
                        <span class="atlas-score-badge">{_pct(row['recommendation_score'])} match</span>
                    </div>
                    <h3>{_safe(row['neighbourhood'])}</h3>
                    <p>{explain_recommendation(row, preferences)}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    _render_recommendation_ranking(ranked, preferences)

    with st.expander("Open ranking table"):
        cols = [
            "rank",
            "neighbourhood",
            "district",
            "recommendation_score",
            "base_match_score",
            "match_adjustment",
        ] + _score_columns_in(df)
        st.dataframe(ranked[cols], use_container_width=True, hide_index=True)


def render_methodology(df: pd.DataFrame) -> None:
    """Render a concise methodology page."""
    st.markdown(
        """
        <div class="atlas-card atlas-feature-card">
            <div class="atlas-kicker">Method and trust</div>
            <h3>Transparent proxy scores, not official truth</h3>
            <p>
                <strong>Hygge Score is not an official statistic.</strong>
                It is an explainable portfolio index built from observable public signals.
                The app uses cached real public data only: OpenStreetMap amenities, official district boundaries,
                and KK Statistikbank demographic exports.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    source_cols = st.columns(3)
    source_cards = [
        ("OpenStreetMap", "Amenity counts are cached from Overpass, then assigned to district polygons offline."),
        ("Open Data DK", "Official Copenhagen district boundaries power the polygon map and spatial joins."),
        ("KK Statistikbank", "Population, age, citizenship and family indicators come from manual official exports."),
    ]
    for col, (title, body) in zip(source_cols, source_cards, strict=False):
        col.markdown(
            f"""
            <div class="atlas-card atlas-mini-card">
                <div class="atlas-kicker">Source</div>
                <h4>{_safe(title)}</h4>
                <p>{_safe(body)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    rows = [
        ("Hygge", "Cafés, bakeries, libraries, green space, benches, indoor culture, bike accessibility."),
        ("Calm", "Green access, low nightlife pressure, lower density, bikeability, and public seating."),
        ("Youth Pulse", "Young-adult share, bars, nightlife, cafés, and cultural density."),
        ("Daily Convenience", "Supermarkets, pharmacies, transit stops, public toilets, and bike parking."),
        ("Rainy-day Comfort", "Indoor-friendly places like cafés, libraries, cinemas, museums, and cultural venues. It does not measure weather."),
        ("Family Living", "Family presence, green access, calm, daily convenience, rainy-day options, and lower nightlife pressure."),
        ("International Feel", "Citizenship-based demographic proxy, softened by convenience and culture signals."),
    ]

    for name, signal in rows:
        st.markdown(
            f"""
            <div class="atlas-card">
                <h4>{_safe(name)}</h4>
                <p>{_safe(signal)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    formula_rows = []
    for score_col in SCORE_COLUMNS:
        weights = SCORE_FORMULAS.get(score_col, {})
        formula_rows.append(
            {
                "Score": DISPLAY_SCORE_NAMES.get(score_col, score_col),
                "Formula weights": " + ".join(
                    f"{feature.replace('_norm', '').replace('_', ' ')} ({weight:.0%})"
                    for feature, weight in weights.items()
                ),
            }
        )

    st.markdown(
        """
        <div class="atlas-card">
            <div class="atlas-kicker">Formula audit</div>
            <h3>Exact score weights</h3>
            <p>Each feature is min-max normalized from 0 to 1 before the weighted score is calculated.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(pd.DataFrame(formula_rows), use_container_width=True, hide_index=True)

    mode = df["data_mode"].iloc[0] if "data_mode" in df.columns else "unknown"
    st.markdown(
        f"""
        <div class="atlas-card">
            <div class="atlas-kicker">Current dataset</div>
            <p>Rows: <strong>{len(df)}</strong></p>
            <p>Mode: <strong>{_safe(mode)}</strong></p>
            <p>Data rule: no mock demographic or amenity values are shown. If a source file is missing, the app stops and asks for the real input.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Current processed columns"):
        st.write(list(df.columns))


# Backward-compatible aliases for older page files or imports.
def render_overview(df: pd.DataFrame) -> None:
    render_hygge_map(df)


def render_explorer(df: pd.DataFrame) -> None:
    render_hygge_map(df)
