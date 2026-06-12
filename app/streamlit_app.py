"""Main Streamlit entry point for Copenhagen Mood Atlas."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data_loader import DataNotReadyError, load_processed_data
from app.page_renderers import render_hygge_map, render_methodology, render_recommendations
from src.processing.build_scores import calculate_all_scores
from src.utils.config import default_processed_data_path


st.set_page_config(
    page_title="Copenhagen Mood Atlas",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _inject_css() -> None:
    """Inject the Copenhagen Mood Atlas visual system."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800;900&family=Sora:wght@600;700;800&display=swap');

        :root {
            --atlas-bg: #FFF7EF;
            --atlas-bg-2: #F3EEFF;
            --atlas-surface: rgba(255,255,255,0.88);
            --atlas-solid: #FFFFFF;
            --atlas-ink: #20182E;
            --atlas-muted: #6F687C;
            --atlas-soft: #A59BB6;
            --atlas-line: rgba(32,24,46,0.12);
            --atlas-line-strong: rgba(32,24,46,0.20);
            --atlas-shadow: 0 22px 60px rgba(45,32,71,0.12);
            --atlas-shadow-soft: 0 12px 34px rgba(45,32,71,0.08);
            --atlas-radius: 28px;
            --mood-hygge: #F4A261;
            --mood-youth: #FF4D6D;
            --mood-rain: #7B8CFF;
            --mood-global: #22C7B8;
            --mood-calm: #76BA4B;
            --mood-daily: #FFD166;
            --mood-family: #FF9F9A;
            --mood-ink: #4B2E83;
            --mood-night: #261A37;
        }

        html, body, [class*="css"] {
            font-family: 'Manrope', Inter, ui-sans-serif, system-ui, sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 6% 5%, rgba(255,77,109,0.20), transparent 22rem),
                radial-gradient(circle at 92% 4%, rgba(34,199,184,0.20), transparent 24rem),
                radial-gradient(circle at 45% 0%, rgba(255,209,102,0.20), transparent 22rem),
                linear-gradient(145deg, #FFFCF7 0%, var(--atlas-bg) 48%, var(--atlas-bg-2) 100%);
            color: var(--atlas-ink);
        }

        .block-container {
            padding-top: 0.65rem;
            padding-bottom: 1.4rem;
            max-width: 1780px;
        }

        h1, h2, h3, h4 {
            font-family: 'Sora', 'Manrope', sans-serif;
            letter-spacing: -0.045em;
            color: var(--atlas-ink);
        }

        p, li, label, span { color: inherit; }

        div[data-testid="stVerticalBlockBorderWrapper"], .atlas-card {
            border: 1px solid rgba(255,255,255,0.72) !important;
            background: var(--atlas-surface) !important;
            border-radius: var(--atlas-radius) !important;
            box-shadow: var(--atlas-shadow-soft);
            backdrop-filter: blur(18px);
        }

        .atlas-card {
            padding: 1.05rem;
            margin-bottom: 0.9rem;
        }

        .atlas-card h3, .atlas-card h4, .atlas-card p { margin-top: 0; }
        .atlas-card p { color: var(--atlas-muted); line-height: 1.58; font-weight: 650; }

        .atlas-hero {
            position: relative;
            overflow: hidden;
            min-height: 92px;
            border: 1px solid rgba(255,255,255,0.78);
            background:
                linear-gradient(135deg, rgba(255,255,255,0.84), rgba(255,246,236,0.74)),
                radial-gradient(circle at 11% 26%, rgba(244,162,97,0.48), transparent 13rem),
                radial-gradient(circle at 76% 20%, rgba(255,77,109,0.48), transparent 13rem),
                radial-gradient(circle at 94% 78%, rgba(34,199,184,0.42), transparent 15rem),
                radial-gradient(circle at 50% 104%, rgba(123,140,255,0.35), transparent 15rem);
            border-radius: 26px;
            padding: 0.72rem 1rem;
            box-shadow: var(--atlas-shadow);
            margin-bottom: 0.55rem;
        }

        .atlas-hero:after {
            content: "";
            position: absolute;
            right: -4.4rem;
            top: -7.8rem;
            width: 14rem;
            height: 14rem;
            border-radius: 999px;
            background: conic-gradient(from 180deg, var(--mood-youth), var(--mood-hygge), var(--mood-daily), var(--mood-global), var(--mood-rain), var(--mood-youth));
            opacity: 0.20;
            pointer-events: none;
        }

        .atlas-kicker {
            color: var(--mood-ink);
            font-size: 0.70rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-weight: 900;
            margin-bottom: 0.42rem;
        }

        .atlas-title {
            position: relative;
            z-index: 1;
            max-width: 18ch;
            margin: 0;
            font-size: clamp(1.65rem, 2.7vw, 3.15rem);
            letter-spacing: -0.075em;
            line-height: 0.94;
        }

        .atlas-subtitle {
            position: relative;
            z-index: 1;
            margin: 0.28rem 0 0 0;
            max-width: 96ch;
            color: var(--atlas-muted);
            font-size: 0.84rem;
            line-height: 1.28;
            font-weight: 700;
        }

        .atlas-hero-pills { margin-top: 0.38rem; position: relative; z-index: 1; }

        .atlas-pill, .atlas-mood-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border: 1px solid rgba(32,24,46,0.10);
            border-radius: 999px;
            padding: 0.28rem 0.52rem;
            font-size: 0.68rem;
            line-height: 1;
            font-weight: 850;
            margin: 0.14rem 0.18rem 0.14rem 0;
            box-shadow: 0 8px 20px rgba(45,32,71,0.06);
            background: rgba(255,255,255,0.78);
            color: var(--atlas-ink);
            white-space: nowrap;
        }

        .atlas-mood-pill strong { font-size: 0.74rem; }
        .atlas-mood-pill em {
            font-style: normal;
            font-size: 0.67rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            opacity: 0.76;
            margin-left: 0.1rem;
        }

        .atlas-pill.hygge, .atlas-mood-pill.hygge { background: rgba(244,162,97,0.18); color: #8A4A16; }
        .atlas-pill.youth, .atlas-mood-pill.youth { background: rgba(255,77,109,0.16); color: #9B1732; }
        .atlas-pill.rain, .atlas-mood-pill.rain { background: rgba(123,140,255,0.16); color: #3842A8; }
        .atlas-pill.global, .atlas-mood-pill.global { background: rgba(34,199,184,0.16); color: #08766C; }
        .atlas-pill.calm, .atlas-mood-pill.calm { background: rgba(118,186,75,0.18); color: #3F7625; }
        .atlas-pill.daily, .atlas-mood-pill.daily { background: rgba(255,209,102,0.24); color: #8B6509; }
        .atlas-pill.family, .atlas-mood-pill.family { background: rgba(255,159,154,0.20); color: #9B3F3A; }

        .atlas-intro-line {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.25rem 0 0.48rem;
            border: 1px solid rgba(255,255,255,0.72);
            background: rgba(255,255,255,0.70);
            border-radius: 999px;
            padding: 0.52rem 0.78rem;
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-intro-line span { color: var(--mood-ink); font-weight: 900; }
        .atlas-intro-line strong { color: var(--atlas-ink); font-size: 0.92rem; }

        .atlas-snapshot-row {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.68rem;
            margin: 0.82rem 0 0.9rem;
        }
        .atlas-snapshot-card {
            min-height: 96px;
            border: 1px solid rgba(255,255,255,0.72);
            background: rgba(255,255,255,0.76);
            border-radius: 24px;
            padding: 0.85rem 0.9rem;
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-snapshot-card span, .atlas-source-card span {
            display: block;
            color: var(--mood-ink);
            font-size: 0.66rem;
            font-weight: 900;
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }
        .atlas-snapshot-card strong {
            display: block;
            margin-top: 0.26rem;
            color: var(--atlas-ink);
            font-size: 1.08rem;
            font-weight: 950;
            letter-spacing: -0.05em;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .atlas-snapshot-card em {
            display: block;
            margin-top: 0.1rem;
            color: var(--atlas-muted);
            font-size: 0.74rem;
            font-style: normal;
            font-weight: 700;
        }

        .atlas-panel-title {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.45rem;
        }
        .atlas-panel-title > span, .atlas-profile-icon, .atlas-rank-number, .atlas-rank-bubble {
            display: grid;
            place-items: center;
            width: 40px;
            height: 40px;
            flex: 0 0 40px;
            border-radius: 17px;
            background: linear-gradient(135deg, rgba(255,77,109,0.17), rgba(123,140,255,0.18));
            color: var(--mood-ink);
            font-size: 1.2rem;
            font-weight: 950;
        }
        .atlas-panel-title strong {
            display: block;
            color: var(--atlas-ink);
            font-weight: 950;
            letter-spacing: -0.02em;
        }
        .atlas-panel-title em {
            display: block;
            color: var(--atlas-muted);
            font-style: normal;
            font-size: 0.84rem;
            font-weight: 700;
        }

        .atlas-lens-note {
            border-radius: 20px;
            padding: 0.76rem 0.85rem;
            margin-top: 0.7rem;
            border: 1px solid rgba(255,255,255,0.70);
            background: rgba(255,255,255,0.72);
        }
        .atlas-lens-note strong { display: block; font-weight: 950; color: var(--atlas-ink); }
        .atlas-lens-note span { display: block; margin-top: 0.18rem; color: var(--atlas-muted); font-size: 0.88rem; font-weight: 700; line-height: 1.42; }

        .atlas-map-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.42rem;
        }
        .atlas-map-header h3 { margin: 0; font-size: 1.12rem; }
        .atlas-map-click-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.46rem 0.76rem;
            background: rgba(32,24,46,0.88);
            color: white;
            font-size: 0.76rem;
            font-weight: 900;
            white-space: nowrap;
        }
        .atlas-under-note {
            color: var(--atlas-muted);
            font-size: 0.74rem;
            line-height: 1.32;
            font-weight: 700;
            margin: 0.54rem 0 0;
        }

        .atlas-profile-hero {
            border-radius: 24px;
            padding: 0.82rem;
            background: linear-gradient(135deg, rgba(255,255,255,0.90), rgba(255,246,236,0.64));
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.68);
        }
        .atlas-profile-topline, .atlas-reco-head, .atlas-shortlist-title, .atlas-reco-footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.8rem;
        }
        .atlas-profile-hero h2, .atlas-recommend-hero h2, .atlas-method-hero h2 {
            margin: 0.48rem 0 0.26rem;
            font-size: clamp(1.35rem, 1.65vw, 1.85rem);
            line-height: 1.02;
        }
        .atlas-profile-hero p, .atlas-recommend-hero p, .atlas-method-hero p {
            margin: 0;
            color: var(--atlas-muted);
            line-height: 1.36;
            font-weight: 700;
        }
        .atlas-top-pills { margin-top: 0.72rem; }
        .atlas-top-pills.compact { margin-top: 0.48rem; }

        .atlas-match-badge, .atlas-leader-score {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.48rem 0.74rem;
            font-size: 0.76rem;
            font-weight: 950;
            white-space: nowrap;
            border: 1px solid rgba(255,255,255,0.62);
            box-shadow: 0 8px 20px rgba(45,32,71,0.08);
        }
        .atlas-match-badge.elite, .atlas-leader-row.elite .atlas-leader-score { background: rgba(34,199,184,0.18); color: #08766C; }
        .atlas-match-badge.great, .atlas-leader-row.great .atlas-leader-score { background: rgba(118,186,75,0.18); color: #3F7625; }
        .atlas-match-badge.good, .atlas-leader-row.good .atlas-leader-score { background: rgba(255,209,102,0.25); color: #8B6509; }
        .atlas-match-badge.mixed, .atlas-leader-row.mixed .atlas-leader-score { background: rgba(123,140,255,0.16); color: #3842A8; }
        .atlas-match-badge.low, .atlas-leader-row.low .atlas-leader-score { background: rgba(32,24,46,0.08); color: var(--atlas-muted); }

        .atlas-profile-facts {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.42rem;
            margin: 0.45rem 0;
        }
        .atlas-profile-facts span {
            display: block;
            border: 1px solid rgba(32,24,46,0.08);
            background: rgba(255,255,255,0.72);
            border-radius: 999px;
            padding: 0.38rem 0.46rem;
            color: var(--atlas-ink);
            font-size: 0.74rem;
            font-weight: 850;
            text-align: center;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .atlas-profile-section {
            display: flex;
            justify-content: space-between;
            gap: 0.8rem;
            align-items: flex-end;
            margin: 0.2rem 0 0.55rem;
        }
        .atlas-profile-section strong { color: var(--atlas-ink); font-weight: 950; }
        .atlas-profile-section span { color: var(--atlas-muted); font-size: 0.74rem; font-weight: 700; }

        .atlas-ladder { display: grid; gap: 0.48rem; }
        .atlas-ladder-row {
            display: grid;
            grid-template-columns: minmax(132px, 0.9fr) minmax(88px, 1fr) 44px;
            align-items: center;
            gap: 0.42rem;
            border: 1px solid rgba(32,24,46,0.08);
            background: rgba(255,255,255,0.74);
            border-radius: 16px;
            padding: 0.36rem 0.46rem;
        }
        .atlas-ladder-label { display: grid; grid-template-columns: 22px minmax(0, 1fr); column-gap: 0.36rem; align-items: center; }
        .atlas-ladder-label strong { color: var(--atlas-ink); font-size: 0.74rem; font-weight: 950; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .atlas-ladder-label em { grid-column: 2; color: var(--atlas-muted); font-size: 0.66rem; font-style: normal; font-weight: 850; text-transform: uppercase; letter-spacing: 0.08em; }
        .atlas-ladder-row b { color: var(--atlas-ink); text-align: right; font-size: 0.82rem; }

        .atlas-data-bar, .atlas-preference-track {
            width: 100%;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(32,24,46,0.08);
            box-shadow: inset 0 0 0 1px rgba(32,24,46,0.04);
        }
        .atlas-data-bar span, .atlas-preference-track b {
            display: block;
            height: 100%;
            min-width: 4px;
            border-radius: inherit;
        }

        .atlas-watchout-card {
            border: 1px dashed rgba(32,24,46,0.18);
            background: rgba(255,255,255,0.62);
            border-radius: 20px;
            padding: 0.75rem 0.85rem;
            margin-top: 0.7rem;
        }
        .atlas-watchout-card strong { color: var(--atlas-ink); font-weight: 950; }
        .atlas-watchout-card p { margin: 0.18rem 0 0; color: var(--atlas-muted); font-size: 0.86rem; line-height: 1.45; font-weight: 700; }

        .atlas-section-shell {
            margin: 1rem 0 0.7rem;
            border: 1px solid rgba(255,255,255,0.72);
            background: rgba(255,255,255,0.72);
            border-radius: 26px;
            padding: 1rem 1.08rem;
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-section-shell h3 { margin: 0; font-size: 1.35rem; }
        .atlas-section-shell p { margin: 0.24rem 0 0; color: var(--atlas-muted); font-weight: 700; }

        .atlas-leader-row, .atlas-shortlist-row {
            display: grid;
            grid-template-columns: 58px minmax(0, 1fr) 96px;
            align-items: center;
            gap: 0.82rem;
            border: 1px solid rgba(255,255,255,0.74);
            background: rgba(255,255,255,0.76);
            border-radius: 23px;
            padding: 0.82rem 0.9rem;
            margin-bottom: 0.55rem;
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-leader-copy strong { display: block; color: var(--atlas-ink); font-size: 1rem; font-weight: 950; letter-spacing: -0.03em; }
        .atlas-leader-copy span { display: block; margin: 0.1rem 0 0.45rem; color: var(--atlas-muted); font-size: 0.84rem; font-weight: 700; }
        .atlas-rank-number, .atlas-rank-bubble { font-size: 0.92rem; }

        .atlas-recommend-hero, .atlas-method-hero {
            border: 1px solid rgba(255,255,255,0.74);
            background:
                linear-gradient(135deg, rgba(255,255,255,0.86), rgba(243,238,255,0.68)),
                radial-gradient(circle at 8% 16%, rgba(255,77,109,0.16), transparent 18rem),
                radial-gradient(circle at 92% 18%, rgba(123,140,255,0.18), transparent 17rem);
            border-radius: 30px;
            padding: 1.2rem 1.3rem;
            box-shadow: var(--atlas-shadow-soft);
            margin-bottom: 0.82rem;
        }

        .atlas-example-grid, .atlas-source-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.74rem;
            margin: 0.8rem 0 0.9rem;
        }
        .atlas-prompt-card, .atlas-source-card, .atlas-method-card {
            border: 1px solid rgba(255,255,255,0.72);
            background: rgba(255,255,255,0.76);
            border-radius: 24px;
            padding: 0.92rem 1rem;
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-prompt-card span { font-size: 1.35rem; }
        .atlas-prompt-card strong, .atlas-source-card strong, .atlas-method-card strong { display: block; margin-top: 0.24rem; color: var(--atlas-ink); font-weight: 950; letter-spacing: -0.03em; }
        .atlas-prompt-card p, .atlas-source-card p, .atlas-method-card p { margin: 0.25rem 0 0; color: var(--atlas-muted); line-height: 1.44; font-weight: 700; }

        textarea {
            border-radius: 24px !important;
            min-height: 86px !important;
            background: rgba(255,255,255,0.88) !important;
            border-color: var(--atlas-line-strong) !important;
            font-size: 1rem !important;
            line-height: 1.48 !important;
        }

        div[data-baseweb="select"] > div,
        div[data-testid="stTextInput"] input,
        textarea {
            border-radius: 18px !important;
            border-color: var(--atlas-line-strong) !important;
            background: rgba(255,255,255,0.88) !important;
        }

        div[data-testid="stSlider"] label p,
        div[data-testid="stTextArea"] label p,
        div[data-testid="stSelectbox"] label p,
        div[role="radiogroup"] label p {
            color: var(--atlas-ink);
            font-weight: 900;
        }

        div[data-testid="stSlider"] [role="slider"] { background: var(--mood-ink) !important; }
        div[data-testid="stSlider"] {
            min-height: 4.85rem !important;
            padding-top: 0.08rem !important;
            padding-bottom: 0.18rem !important;
            overflow: visible !important;
        }
        div[data-testid="stSlider"] label {
            min-height: 1.35rem !important;
            margin-bottom: 0.18rem !important;
            display: flex !important;
            align-items: center !important;
        }
        div[data-testid="stSlider"] label p {
            font-size: 0.78rem !important;
            line-height: 1.15 !important;
            white-space: nowrap !important;
        }

        .atlas-slider-intro h3, .atlas-recipe-card h3 { margin: 0 0 0.25rem; }
        .atlas-slider-intro p, .atlas-recipe-card p, .atlas-understood-card p { color: var(--atlas-muted); font-weight: 700; line-height: 1.36; }
        .atlas-preference-bars { display: grid; gap: 0.52rem; margin-top: 0.75rem; }
        .atlas-preference-row { display: grid; grid-template-columns: 138px minmax(0,1fr) 42px; align-items: center; gap: 0.5rem; }
        .atlas-preference-row span { color: var(--atlas-ink); font-size: 0.74rem; font-weight: 900; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .atlas-preference-row strong { text-align: right; color: var(--atlas-muted); font-size: 0.76rem; }
        .atlas-preference-track { height: 9px; }

        .atlas-reco-card {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.75);
            background:
                linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,246,236,0.66)),
                radial-gradient(circle at 5% 10%, rgba(255,77,109,0.14), transparent 13rem),
                radial-gradient(circle at 95% 10%, rgba(34,199,184,0.14), transparent 13rem);
            border-radius: 28px;
            padding: 1rem 1.05rem;
            box-shadow: var(--atlas-shadow-soft);
            margin-bottom: 0.78rem;
        }
        .atlas-reco-card.large { padding: 1.1rem 1.18rem; }
        .atlas-reco-card h3 { margin: 0.72rem 0 0.36rem; font-size: 1.48rem; }
        .atlas-reco-card p { margin: 0.54rem 0 0; color: var(--atlas-muted); line-height: 1.5; font-weight: 700; }
        .atlas-match-meter { margin: 0.5rem 0 0.5rem; }
        .atlas-reco-block { margin-top: 0.78rem; }
        .atlas-reco-block strong { color: var(--atlas-ink); font-weight: 950; }
        .atlas-reco-block.low-bars {
            border-radius: 20px;
            padding: 0.72rem 0.8rem;
            background: rgba(255,255,255,0.62);
            border: 1px dashed rgba(32,24,46,0.14);
        }
        .atlas-reco-footer { justify-content: flex-start; margin-top: 0.72rem; }

        .atlas-shortlist-row {
            grid-template-columns: 58px minmax(0, 1fr) minmax(220px, 0.82fr);
            align-items: center;
        }
        .atlas-shortlist-title strong { color: var(--atlas-ink); font-weight: 950; letter-spacing: -0.03em; }
        .atlas-shortlist-title span { color: var(--mood-ink); font-size: 0.82rem; font-weight: 950; }
        .atlas-shortlist-note { color: var(--atlas-muted); font-size: 0.84rem; line-height: 1.42; font-weight: 700; }

        .atlas-intro-line.recommend { margin-bottom: 0.42rem; }
        .atlas-slider-intro.compact, .atlas-recipe-card.compact, .atlas-understood-card.compact {
            padding: 0.72rem 0.82rem;
            margin-bottom: 0.55rem;
        }
        .atlas-slider-intro.compact h3 {
            margin: 0;
            font-size: 1.06rem;
        }
        .atlas-preference-bars.compact { gap: 0.36rem; margin-top: 0.38rem; }
        .atlas-preference-bars.compact .atlas-preference-row {
            grid-template-columns: 104px minmax(0, 1fr) 34px;
            gap: 0.36rem;
        }
        .atlas-preference-bars.compact .atlas-preference-row span { font-size: 0.68rem; }
        .atlas-preference-bars.compact .atlas-preference-row strong { font-size: 0.68rem; }
        .atlas-section-shell.compact {
            padding: 0.68rem 0.82rem;
            margin: 0 0 0.48rem;
            border-radius: 22px;
        }
        .atlas-section-shell.compact h3 { font-size: 1.18rem; }
        .atlas-section-shell.compact p { font-size: 0.78rem; margin-top: 0.1rem; }
        .atlas-reco-row {
            display: grid;
            grid-template-columns: 48px minmax(0, 1fr);
            align-items: center;
            gap: 0.62rem;
            border: 1px solid rgba(255,255,255,0.76);
            background: rgba(255,255,255,0.78);
            border-radius: 22px;
            padding: 0.58rem 0.72rem;
            margin-bottom: 0.46rem;
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-reco-row.elite { box-shadow: 0 16px 36px rgba(34,199,184,0.14); }
        .atlas-reco-row-main { min-width: 0; }
        .atlas-reco-row-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.34rem;
        }
        .atlas-reco-row-title strong {
            color: var(--atlas-ink);
            font-size: 1.02rem;
            font-weight: 950;
            letter-spacing: -0.03em;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .atlas-reco-row-title span {
            border-radius: 999px;
            padding: 0.3rem 0.52rem;
            color: var(--atlas-ink);
            background: rgba(32,24,46,0.07);
            font-size: 0.72rem;
            font-weight: 950;
            white-space: nowrap;
        }
        .atlas-reco-row.elite .atlas-reco-row-title span { background: rgba(34,199,184,0.18); color: #08766C; }
        .atlas-reco-row.great .atlas-reco-row-title span { background: rgba(118,186,75,0.18); color: #3F7625; }
        .atlas-reco-row.good .atlas-reco-row-title span { background: rgba(255,209,102,0.24); color: #8B6509; }
        .atlas-match-track {
            width: 100%;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(32,24,46,0.08);
            box-shadow: inset 0 0 0 1px rgba(32,24,46,0.04);
        }
        .atlas-match-track b {
            display: block;
            height: 100%;
            min-width: 5px;
            border-radius: inherit;
            background: linear-gradient(90deg, #6C5CE7, #7B8CFF);
        }
        .atlas-match-track.elite b { background: linear-gradient(90deg, #22C7B8, #7B8CFF); }
        .atlas-match-track.great b { background: linear-gradient(90deg, #76BA4B, #22C7B8); }
        .atlas-match-track.good b { background: linear-gradient(90deg, #FFD166, #F4A261); }
        .atlas-match-track.mixed b { background: linear-gradient(90deg, #7B8CFF, #B6BEFF); }
        .atlas-match-track.low b { background: linear-gradient(90deg, #A59BB6, #D7CFDF); }
        .atlas-signal-bars {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.38rem;
            margin-top: 0.45rem;
        }
        .atlas-signal-row {
            display: grid;
            grid-template-columns: minmax(80px, 1fr) minmax(46px, 0.8fr) 36px;
            align-items: center;
            gap: 0.34rem;
            border: 1px solid rgba(32,24,46,0.07);
            background: rgba(255,255,255,0.64);
            border-radius: 999px;
            padding: 0.25rem 0.38rem;
        }
        .atlas-signal-row span {
            color: var(--atlas-ink);
            font-size: 0.68rem;
            font-weight: 900;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .atlas-signal-row strong {
            color: var(--atlas-muted);
            font-size: 0.68rem;
            font-weight: 950;
            text-align: right;
        }

        .atlas-method-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.74rem;
            margin: 0.9rem 0;
        }
        .atlas-method-card span { font-size: 1.48rem; }
        .atlas-dataset-card strong { color: var(--atlas-ink); }


        .atlas-top-nav {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.38rem 0 0.36rem;
            padding: 0.48rem 0.66rem;
            border-radius: 26px;
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(255,255,255,0.76);
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-top-nav strong {
            font-family: 'Sora', 'Manrope', sans-serif;
            color: var(--atlas-ink);
            font-size: 1rem;
            letter-spacing: -0.03em;
        }
        .atlas-top-nav span {
            color: var(--atlas-muted);
            font-size: 0.82rem;
            font-weight: 800;
        }
        div[data-testid="stButton"] button {
            min-height: 46px;
            border-radius: 20px !important;
            font-weight: 950 !important;
            font-size: 0.98rem !important;
            box-shadow: var(--atlas-shadow-soft);
        }
        div[data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.44rem;
            flex-wrap: wrap;
        }
        div[data-testid="stRadio"] label {
            border: 1px solid rgba(32,24,46,0.12);
            background: rgba(255,255,255,0.74);
            border-radius: 999px;
            padding: 0.35rem 0.55rem;
            box-shadow: 0 8px 18px rgba(45,32,71,0.06);
        }
        .atlas-lens-strip {
            display: flex;
            justify-content: space-between;
            gap: 0.8rem;
            align-items: center;
            margin-bottom: 0.42rem;
        }
        .atlas-lens-strip strong { color: var(--atlas-ink); font-weight: 950; }
        .atlas-lens-strip span { display: block; color: var(--atlas-muted); font-size: 0.8rem; font-weight: 800; }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.42rem;
            background: rgba(255,255,255,0.60);
            border: 1px solid rgba(255,255,255,0.72);
            padding: 0.48rem;
            border-radius: 999px;
            box-shadow: var(--atlas-shadow-soft);
            margin-bottom: 0.4rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            padding: 0.44rem 1rem;
            font-weight: 950;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(32,24,46,0.88) !important;
            color: white !important;
        }

        button[kind="primary"], button[kind="secondary"] { border-radius: 999px; }
        button[kind="primary"] {
            background: linear-gradient(135deg, #20182E, #6C5CE7) !important;
            border: 0 !important;
            color: white !important;
        }
        button[kind="secondary"] {
            background: rgba(255,255,255,0.80) !important;
            border: 1px solid rgba(32,24,46,0.14) !important;
            color: var(--atlas-ink) !important;
        }

        .atlas-profile-facts.compact { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .atlas-profile-section.compact { margin-top: 0.35rem; }
        .atlas-ladder.compact { gap: 0.38rem; }



        .atlas-active-mood-note {
            display: grid;
            grid-template-columns: auto minmax(0, 1fr);
            align-items: center;
            gap: 0.42rem;
            margin-top: 0.44rem;
            border-radius: 999px;
            padding: 0.42rem 0.62rem;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(32,24,46,0.08);
        }
        .atlas-active-mood-note strong {
            color: var(--atlas-ink);
            font-size: 0.78rem;
            font-weight: 950;
            white-space: nowrap;
        }
        .atlas-active-mood-note span {
            color: var(--atlas-muted);
            font-size: 0.76rem;
            font-weight: 800;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .atlas-active-mood-note.hygge { background: rgba(244,162,97,0.16); }
        .atlas-active-mood-note.youth { background: rgba(255,77,109,0.13); }
        .atlas-active-mood-note.rain { background: rgba(123,140,255,0.13); }
        .atlas-active-mood-note.global { background: rgba(34,199,184,0.13); }
        .atlas-active-mood-note.calm { background: rgba(118,186,75,0.15); }
        .atlas-active-mood-note.daily { background: rgba(255,209,102,0.20); }
        .atlas-active-mood-note.family { background: rgba(255,159,154,0.15); }

        .atlas-control-step {
            display: grid;
            grid-template-columns: 36px minmax(0, 1fr);
            align-items: center;
            gap: 0.62rem;
            margin-bottom: 0.62rem;
        }
        .atlas-control-step > span {
            display: grid;
            place-items: center;
            width: 36px;
            height: 36px;
            border-radius: 14px;
            background: linear-gradient(135deg, #20182E, #6C5CE7);
            color: white;
            font-size: 0.9rem;
            font-weight: 950;
        }
        .atlas-control-step strong {
            display: block;
            color: var(--atlas-ink);
            font-size: 1.02rem;
            font-weight: 950;
            letter-spacing: -0.035em;
        }
        .atlas-control-step p {
            margin: 0.08rem 0 0;
            color: var(--atlas-muted);
            font-size: 0.78rem;
            line-height: 1.24;
            font-weight: 800;
        }
        .atlas-control-step.results-head { margin-bottom: 0; }

        .atlas-mood-guide-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.36rem;
            margin: 0.42rem 0 0.72rem;
        }
        .atlas-mood-guide-pill {
            min-height: 58px;
            border: 1px solid rgba(32,24,46,0.08);
            background: rgba(255,255,255,0.70);
            border-radius: 16px;
            padding: 0.46rem 0.52rem;
            overflow: hidden;
        }
        .atlas-mood-guide-pill strong {
            display: block;
            color: var(--atlas-ink);
            font-size: 0.72rem;
            font-weight: 950;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .atlas-mood-guide-pill span {
            display: block;
            margin-top: 0.13rem;
            color: var(--atlas-muted);
            font-size: 0.66rem;
            line-height: 1.16;
            font-weight: 800;
        }
        .atlas-mood-guide-pill.hygge { background: rgba(244,162,97,0.14); }
        .atlas-mood-guide-pill.youth { background: rgba(255,77,109,0.12); }
        .atlas-mood-guide-pill.rain { background: rgba(123,140,255,0.12); }
        .atlas-mood-guide-pill.global { background: rgba(34,199,184,0.12); }
        .atlas-mood-guide-pill.calm { background: rgba(118,186,75,0.13); }
        .atlas-mood-guide-pill.daily { background: rgba(255,209,102,0.18); }
        .atlas-mood-guide-pill.family { background: rgba(255,159,154,0.13); }

        .atlas-control-step.compact-mix {
            margin-bottom: 0.12rem;
        }
        .atlas-inline-slider-label {
            display: inline-flex;
            align-items: center;
            gap: 0.28rem;
            max-width: 100%;
            margin: 0.08rem 0 0.08rem;
            padding: 0.16rem 0.42rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(32,24,46,0.08);
            box-shadow: 0 8px 18px rgba(32,24,46,0.04);
            color: var(--atlas-ink);
        }
        .atlas-inline-slider-label span {
            flex: 0 0 auto;
            font-size: 0.78rem;
            line-height: 1;
        }
        .atlas-inline-slider-label strong {
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 0.72rem;
            font-weight: 950;
            letter-spacing: -0.02em;
            line-height: 1.05;
        }
        .atlas-inline-slider-label.hygge { background: rgba(244,162,97,0.15); color: #8A4A16; }
        .atlas-inline-slider-label.youth { background: rgba(255,77,109,0.13); color: #9B1732; }
        .atlas-inline-slider-label.rain { background: rgba(123,140,255,0.13); color: #3842A8; }
        .atlas-inline-slider-label.global { background: rgba(34,199,184,0.13); color: #08766C; }
        .atlas-inline-slider-label.calm { background: rgba(118,186,75,0.15); color: #3F7625; }
        .atlas-inline-slider-label.daily { background: rgba(255,209,102,0.20); color: #8B6509; }
        .atlas-inline-slider-label.family { background: rgba(255,159,154,0.15); color: #9B3F3A; }
        div[data-testid="stVerticalBlock"]:has(.atlas-inline-slider-label) {
            gap: 0.12rem !important;
            padding: 0 !important;
            min-height: 72px;
            overflow: visible !important;
        }
        div[data-testid="stVerticalBlock"]:has(.atlas-inline-slider-label) [data-testid="stSlider"] {
            margin-top: 0 !important;
            margin-bottom: 0.36rem !important;
            overflow: visible !important;
        }
        div[data-testid="stVerticalBlock"]:has(.atlas-inline-slider-label) [data-testid="stSlider"] > div {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            overflow: visible !important;
        }
        div[data-testid="stVerticalBlock"]:has(.atlas-inline-slider-label) [data-testid="stSlider"] div[data-testid="stThumbValue"] {
            font-size: 0.64rem !important;
            font-weight: 900 !important;
        }

        .atlas-detected-strip {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.6rem;
            margin-top: 0.55rem;
            padding: 0.5rem 0.62rem;
            border-radius: 20px;
            background: rgba(255,255,255,0.70);
            border: 1px solid rgba(255,255,255,0.76);
            box-shadow: var(--atlas-shadow-soft);
        }
        .atlas-detected-strip strong {
            color: var(--atlas-ink);
            font-size: 0.74rem;
            font-weight: 950;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        .atlas-detected-strip > div {
            text-align: right;
        }

        @media (max-width: 1200px) {
            .atlas-snapshot-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .atlas-method-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .atlas-shortlist-row { grid-template-columns: 54px minmax(0, 1fr); }
            .atlas-shortlist-note { grid-column: 2; }
        }

        @media (max-width: 900px) {
            .block-container { padding-top: 0.8rem; }
            .atlas-hero { min-height: auto; padding: 1.05rem; border-radius: 28px; }
            .atlas-example-grid, .atlas-source-grid, .atlas-method-grid { grid-template-columns: 1fr; }
            .atlas-snapshot-row { grid-template-columns: 1fr; }
            .atlas-profile-facts { grid-template-columns: 1fr; }
            .atlas-ladder-row { grid-template-columns: minmax(0, 1fr); }
            .atlas-ladder-row b { text-align: left; }
            .atlas-leader-row { grid-template-columns: 52px minmax(0, 1fr); }
            .atlas-leader-score { justify-self: start; grid-column: 2; }
            .atlas-intro-line { border-radius: 22px; align-items: flex-start; flex-direction: column; }
            .atlas-map-header { display: block; }
            .atlas-map-click-pill { margin-top: 0.5rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        """
        <div class="atlas-hero">
            <div class="atlas-kicker">🧭 Mood first Copenhagen discovery</div>
            <h1 class="atlas-title">Copenhagen Mood Atlas</h1>
            <p class="atlas-subtitle">
                Explore Copenhagen by mood: cafés, calm streets, errands, rainy day plans, international feel and social energy.
            </p>
            <div class="atlas-hero-pills">
                <span class="atlas-pill hygge">🕯️ Hygge</span>
                <span class="atlas-pill youth">⚡ Youth Pulse</span>
                <span class="atlas-pill rain">☔ Rainy Comfort</span>
                <span class="atlas-pill global">🌍 International Feel</span>
                <span class="atlas-pill calm">🌿 Calm</span>
                <span class="atlas-pill daily">🛒 Daily Convenience</span>
                <span class="atlas-pill family">🧸 Family Living</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_navigation() -> str:
    pages = ["🗺️ Explore", "✨ Recommend", "🔍 Method"]
    if "atlas_navigation" not in st.session_state:
        st.session_state["atlas_navigation"] = pages[0]

    st.markdown(
        """
        <div class="atlas-top-nav">
            <strong>Choose a view</strong>
            <span>Big map, quick matches, clear method</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    nav_cols = st.columns(3, gap="medium")
    for col, page in zip(nav_cols, pages):
        active = page == st.session_state["atlas_navigation"]
        if col.button(page, use_container_width=True, type="primary" if active else "secondary"):
            st.session_state["atlas_navigation"] = page
            st.rerun()
    return st.session_state["atlas_navigation"]


def main() -> None:
    _inject_css()
    _render_hero()

    data_path = default_processed_data_path()
    try:
        df = load_processed_data(data_path)
    except DataNotReadyError as exc:
        st.error("Real data has not been built yet.")
        st.code(str(exc), language="bash")
        st.markdown(
            """
            <div class="atlas-card">
                <div class="atlas-kicker">No invented data</div>
                <p>
                    This version does not fall back to mock neighbourhood values.
                    If the automatic KK Statistikbank fetch fails, export the two CSV files manually and place them in
                    <code>data/raw/</code> before rebuilding the processed dataset.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    df = calculate_all_scores(df)

    current_page = _render_navigation()
    if current_page == "🗺️ Explore":
        render_hygge_map(df)
    elif current_page == "✨ Recommend":
        render_recommendations(df)
    else:
        render_methodology(df)


if __name__ == "__main__":
    main()
