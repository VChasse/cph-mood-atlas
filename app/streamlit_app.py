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
    """Inject a minimal, product-like visual system."""
    st.markdown(
        """
        <style>
        :root {
            /* Defined Copenhagen Mood Atlas palette */
            --atlas-bg: #F7F3EA;
            --atlas-canvas: #FBFAF7;
            --atlas-surface: rgba(255,255,255,0.92);
            --atlas-surface-solid: #FFFFFF;
            --atlas-surface-warm: #FFF9EF;
            --atlas-ink: #17201E;
            --atlas-muted: #6F766F;
            --atlas-soft: #8D948C;
            --atlas-line: rgba(23,32,30,0.10);
            --atlas-line-strong: rgba(23,32,30,0.16);
            --atlas-teal: #0F5557;
            --atlas-teal-dark: #0A3F42;
            --atlas-teal-soft: rgba(15,85,87,0.10);
            --atlas-sage: #DDE7D3;
            --atlas-sage-strong: #A5BE98;
            --atlas-amber: #C9892B;
            --atlas-amber-soft: rgba(201,137,43,0.13);
            --atlas-clay: #D98568;
            --atlas-clay-soft: rgba(217,133,104,0.13);
            --atlas-shadow: 0 18px 54px rgba(23,32,30,0.07);
            --atlas-shadow-soft: 0 10px 28px rgba(23,32,30,0.045);
            --atlas-radius: 20px;
            --atlas-radius-sm: 14px;
        }

        html, body, [class*="css"] {
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 4% 0%, rgba(15,85,87,0.13), transparent 30rem),
                radial-gradient(circle at 88% 6%, rgba(201,137,43,0.12), transparent 24rem),
                linear-gradient(180deg, var(--atlas-canvas) 0%, var(--atlas-bg) 100%);
            color: var(--atlas-ink);
        }

        section[data-testid="stSidebar"] {
            background: rgba(255,255,255,0.94);
            border-right: 1px solid var(--atlas-line);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3.4rem;
            max-width: 1280px;
        }

        h1, h2, h3, h4 {
            letter-spacing: -0.035em;
            color: var(--atlas-ink);
        }

        p, li, label, span {
            color: inherit;
        }

        div[data-testid="stMetric"] {
            background: var(--atlas-surface);
            border: 1px solid var(--atlas-line);
            border-radius: 18px;
            padding: 1rem 1.05rem;
            box-shadow: var(--atlas-shadow-soft);
        }

        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--atlas-teal-dark);
            font-weight: 850;
            letter-spacing: -0.05em;
        }

        div[data-testid="stMetricLabel"] p {
            color: var(--atlas-muted);
            font-size: 0.78rem;
            font-weight: 760;
        }

        .atlas-hero {
            position: relative;
            overflow: hidden;
            border: 1px solid var(--atlas-line);
            background:
                linear-gradient(135deg, rgba(255,255,255,0.94), rgba(255,249,239,0.88)),
                radial-gradient(circle at 85% 8%, rgba(221,231,211,0.9), transparent 18rem);
            border-radius: 28px;
            padding: 1.45rem 1.55rem;
            box-shadow: var(--atlas-shadow);
            margin-bottom: 1rem;
        }

        .atlas-hero::after {
            content: "";
            position: absolute;
            right: -4rem;
            top: -5rem;
            width: 16rem;
            height: 16rem;
            border-radius: 999px;
            background: rgba(15,85,87,0.07);
            pointer-events: none;
        }

        .atlas-title {
            margin: 0;
            max-width: 12ch;
            font-size: clamp(2.3rem, 4.8vw, 4.9rem);
            letter-spacing: -0.07em;
            line-height: 0.92;
            color: var(--atlas-ink);
        }

        .atlas-subtitle {
            margin: 0.85rem 0 0 0;
            max-width: 76ch;
            color: var(--atlas-muted);
            font-size: 1.04rem;
            line-height: 1.62;
        }

        .atlas-kicker {
            color: var(--atlas-amber);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-weight: 850;
            margin-bottom: 0.45rem;
        }

        .atlas-card {
            border: 1px solid var(--atlas-line);
            background: var(--atlas-surface);
            border-radius: var(--atlas-radius);
            padding: 1rem;
            box-shadow: var(--atlas-shadow-soft);
            margin-bottom: 0.8rem;
        }

        .atlas-card h3, .atlas-card h4 {
            margin: 0 0 0.4rem 0;
        }

        .atlas-card p {
            margin: 0;
            color: var(--atlas-muted);
            line-height: 1.55;
        }

        .atlas-pill {
            display: inline-flex;
            align-items: center;
            border: 1px solid rgba(15,85,87,0.18);
            background: var(--atlas-teal-soft);
            color: var(--atlas-teal-dark);
            border-radius: 999px;
            padding: 0.34rem 0.68rem;
            font-size: 0.76rem;
            line-height: 1;
            font-weight: 820;
            margin: 0.16rem 0.22rem 0.16rem 0;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid var(--atlas-line) !important;
            background: var(--atlas-surface) !important;
            border-radius: var(--atlas-radius) !important;
            box-shadow: var(--atlas-shadow-soft);
            padding: 1rem;
        }

        .atlas-divider {
            height: 1px;
            background: var(--atlas-line);
            margin: 1.05rem 0;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.45rem;
            border-bottom: 1px solid var(--atlas-line);
            margin-bottom: 0.85rem;
        }

        .stTabs [data-baseweb="tab"] {
            border: 1px solid transparent;
            border-radius: 999px;
            padding: 0.58rem 0.92rem;
            font-weight: 780;
            background: rgba(255,255,255,0.52);
        }

        .stTabs [aria-selected="true"] {
            background: var(--atlas-surface-solid);
            border-color: var(--atlas-line-strong);
            box-shadow: 0 7px 22px rgba(23,32,30,0.06);
        }

        .atlas-feature-card {
            padding: 1.2rem 1.25rem;
            border-color: rgba(15,85,87,0.20);
            background:
                linear-gradient(135deg, rgba(15,85,87,0.075), rgba(255,255,255,0.92) 55%, rgba(255,249,239,0.92));
        }

        .atlas-feature-card h3 {
            font-size: 1.42rem;
        }

        .atlas-mini-card {
            min-height: 126px;
        }

        .atlas-proof-card {
            border-color: rgba(15,85,87,0.18);
        }

        .atlas-helper-text {
            margin: 0 0 0.8rem 0;
            color: var(--atlas-muted);
            font-size: 0.91rem;
            line-height: 1.48;
        }

        .atlas-helper-text span {
            color: var(--atlas-teal-dark);
            font-weight: 850;
        }

        .atlas-score-chip {
            border: 1px solid var(--atlas-line);
            background: rgba(255,255,255,0.72);
            border-radius: 16px;
            padding: 0.68rem 0.72rem;
            margin-bottom: 0.45rem;
        }

        .atlas-score-chip span {
            display: block;
            color: var(--atlas-muted);
            font-size: 0.72rem;
            font-weight: 760;
        }

        .atlas-score-chip strong {
            display: block;
            margin-top: 0.2rem;
            color: var(--atlas-teal-dark);
            font-size: 1.2rem;
            letter-spacing: -0.04em;
        }

        .atlas-example-card {
            border: 1px solid var(--atlas-line);
            background: rgba(255,255,255,0.76);
            border-radius: 18px;
            padding: 0.85rem 0.9rem;
            margin-bottom: 0.8rem;
            transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
        }

        .atlas-example-card:hover {
            transform: translateY(-1px);
            border-color: rgba(15,85,87,0.24);
            box-shadow: var(--atlas-shadow-soft);
        }

        .atlas-example-card span {
            color: var(--atlas-amber);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.68rem;
            font-weight: 850;
        }

        .atlas-example-card p {
            margin: 0.26rem 0 0 0;
            color: var(--atlas-ink);
            font-size: 0.91rem;
            line-height: 1.36;
        }

        .recommendation-card {
            border-left: 5px solid var(--atlas-teal);
            background: linear-gradient(90deg, rgba(15,85,87,0.07), rgba(255,255,255,0.94) 24%);
        }

        .atlas-journey-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.72rem;
            margin: 0.85rem 0 1rem 0;
        }

        .atlas-journey-step {
            display: flex;
            align-items: center;
            gap: 0.72rem;
            min-height: 76px;
            border: 1px solid var(--atlas-line);
            background: rgba(255,255,255,0.76);
            border-radius: 20px;
            padding: 0.8rem 0.9rem;
            box-shadow: var(--atlas-shadow-soft);
        }

        .atlas-journey-step span {
            display: grid;
            place-items: center;
            width: 48px;
            height: 48px;
            flex: 0 0 48px;
            border-radius: 16px;
            background: var(--atlas-teal-soft);
            font-size: 1.65rem;
        }

        .atlas-journey-step strong,
        .atlas-journey-step em {
            display: block;
            font-style: normal;
        }

        .atlas-journey-step strong {
            color: var(--atlas-amber);
            text-transform: uppercase;
            letter-spacing: 0.11em;
            font-size: 0.7rem;
            font-weight: 850;
        }

        .atlas-journey-step em {
            margin-top: 0.1rem;
            color: var(--atlas-ink);
            font-size: 0.96rem;
            font-weight: 780;
        }

        .atlas-step-label {
            display: flex;
            align-items: center;
            gap: 0.72rem;
            padding: 0.78rem 0.86rem;
            margin-bottom: 0.58rem;
            border: 1px solid rgba(15,85,87,0.18);
            background: linear-gradient(135deg, var(--atlas-teal-soft), rgba(255,255,255,0.7));
            border-radius: 18px;
        }

        .atlas-step-icon {
            display: grid;
            place-items: center;
            width: 50px;
            height: 50px;
            border-radius: 16px;
            background: var(--atlas-surface-solid);
            box-shadow: 0 8px 20px rgba(15,85,87,0.09);
            font-size: 1.85rem;
            line-height: 1;
        }

        .atlas-step-label strong,
        .atlas-step-label em {
            display: block;
            font-style: normal;
        }

        .atlas-step-label strong {
            color: var(--atlas-amber);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.72rem;
            font-weight: 880;
        }

        .atlas-step-label em {
            margin-top: 0.1rem;
            color: var(--atlas-ink);
            font-size: 1.04rem;
            font-weight: 820;
        }

        .atlas-control-label {
            color: var(--atlas-amber);
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 850;
            margin-bottom: 0.45rem;
        }

        .atlas-under-note {
            color: var(--atlas-muted);
            font-size: 0.85rem;
            line-height: 1.48;
            margin: 0.38rem 0 0.82rem 0;
            font-style: italic;
        }

        .atlas-under-note span {
            color: var(--atlas-teal-dark);
            font-weight: 850;
        }

        .atlas-lens-guide.compact {
            margin: 0.35rem 0;
            min-height: 74px;
        }

        .atlas-note {
            color: var(--atlas-muted);
            font-size: 0.85rem;
            line-height: 1.48;
            font-style: italic;
            margin: 0.25rem 0 0.75rem 0;
        }

        .atlas-lens-guide {
            border: 1px solid var(--atlas-line);
            background: rgba(255,255,255,0.68);
            border-radius: 16px;
            padding: 0.78rem 0.88rem;
            margin: 0.55rem 0 0.75rem 0;
            color: var(--atlas-muted);
            font-size: 0.89rem;
            line-height: 1.45;
        }

        .atlas-lens-guide span {
            color: var(--atlas-teal-dark);
            font-weight: 850;
        }

        .atlas-section-card {
            padding: 1.05rem 1.1rem;
        }

        .atlas-section-heading {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
        }

        .atlas-section-heading h3 {
            margin: 0 0 0.35rem 0;
            font-size: 1.35rem;
        }

        .atlas-section-heading p {
            max-width: 70ch;
        }

        .atlas-status-pill {
            display: inline-flex;
            align-items: center;
            white-space: nowrap;
            border: 1px solid rgba(201,137,43,0.24);
            background: var(--atlas-amber-soft);
            color: #8E5A13;
            border-radius: 999px;
            padding: 0.42rem 0.68rem;
            font-size: 0.75rem;
            font-weight: 850;
        }

        .atlas-rank-shell {
            margin-bottom: 0.7rem;
        }

        .atlas-ranking-row {
            display: grid;
            grid-template-columns: 64px minmax(0, 1fr) 88px;
            align-items: center;
            gap: 0.9rem;
            border: 1px solid var(--atlas-line);
            background: rgba(255,255,255,0.82);
            border-radius: 18px;
            padding: 0.82rem 0.9rem;
            margin-bottom: 0.58rem;
            box-shadow: 0 8px 22px rgba(23,32,30,0.038);
        }

        .atlas-ranking-row-large {
            align-items: flex-start;
        }

        .atlas-rank-number {
            display: grid;
            place-items: center;
            min-height: 48px;
            border-radius: 15px;
            background: linear-gradient(135deg, var(--atlas-sage), rgba(255,255,255,0.85));
            color: var(--atlas-teal-dark);
            font-size: 0.95rem;
            font-weight: 900;
        }

        .atlas-rank-copy > strong {
            display: block;
            color: var(--atlas-ink);
            font-size: 1rem;
            letter-spacing: -0.02em;
            margin-bottom: 0.18rem;
        }

        .atlas-rank-copy span {
            display: block;
            color: var(--atlas-muted);
            font-size: 0.86rem;
            line-height: 1.38;
        }

        .atlas-rank-copy span strong,
        .recommendation-card p strong {
            display: inline;
            color: var(--atlas-teal-dark);
            font-size: inherit;
            letter-spacing: inherit;
            margin: 0;
            font-weight: 850;
        }

        .atlas-score-badge {
            justify-self: end;
            border: 1px solid rgba(15,85,87,0.18);
            background: var(--atlas-teal-soft);
            color: var(--atlas-teal-dark);
            border-radius: 999px;
            padding: 0.46rem 0.64rem;
            font-weight: 900;
            letter-spacing: -0.025em;
        }

        .atlas-progress {
            width: 100%;
            height: 8px;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(23,32,30,0.08);
            margin-top: 0.55rem;
        }

        .atlas-progress span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, var(--atlas-sage-strong), var(--atlas-teal));
        }

        .sticky-preferences {
            position: sticky;
            top: 1rem;
        }

        div[data-baseweb="select"] > div,
        div[data-testid="stTextInput"] input {
            border-radius: 14px !important;
            border-color: var(--atlas-line-strong) !important;
            background: var(--atlas-surface-solid) !important;
        }

        div[data-testid="stSlider"] label p,
        div[data-testid="stTextInput"] label p {
            color: var(--atlas-ink);
            font-weight: 760;
        }

        button[kind="primary"], button[kind="secondary"] {
            border-radius: 999px;
        }

        @media (max-width: 900px) {
            .block-container {
                padding-top: 1.1rem;
            }

            .atlas-journey-strip {
                grid-template-columns: 1fr;
            }

            .atlas-section-heading {
                display: block;
            }

            .atlas-status-pill {
                margin-top: 0.7rem;
            }

            .atlas-ranking-row {
                grid-template-columns: 52px minmax(0, 1fr);
            }

            .atlas-score-badge {
                justify-self: start;
                grid-column: 2;
            }
        }
.atlas-lite-hero h3 {
    font-size: clamp(1.8rem, 3vw, 2.55rem);
    letter-spacing: -0.045em;
}

.atlas-lite-hero p {
    max-width: 780px;
    font-size: 1.03rem;
}

.atlas-lite-chat-shell {
    margin: 1.2rem 0 0.45rem;
    padding: 1rem 1.1rem;
    border: 1px solid rgba(15, 31, 34, 0.1);
    border-radius: 22px 22px 10px 10px;
    background:
        linear-gradient(135deg, rgba(15, 85, 87, 0.08), rgba(201, 137, 43, 0.08)),
        rgba(255, 252, 246, 0.92);
}

.atlas-lite-chat-header {
    display: flex;
    gap: 0.85rem;
    align-items: center;
}

.atlas-lite-avatar {
    width: 44px;
    height: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 16px;
    background: var(--atlas-teal-dark);
    color: white;
    font-size: 1.35rem;
    box-shadow: 0 10px 22px rgba(15, 85, 87, 0.18);
}

.atlas-lite-chat-header strong {
    display: block;
    color: var(--atlas-ink);
    font-size: 1rem;
    font-weight: 850;
}

.atlas-lite-chat-header em {
    display: block;
    margin-top: 0.1rem;
    color: var(--atlas-muted);
    font-size: 0.9rem;
    font-style: normal;
}

textarea {
    min-height: 150px !important;
    border-radius: 0 0 22px 22px !important;
    font-size: 1.02rem !important;
    line-height: 1.55 !important;
}

.atlas-lite-helper {
    margin: 0.15rem 0 1.2rem;
    color: var(--atlas-muted);
    font-size: 0.92rem;
}

.atlas-example-card-clickable {
    min-height: 118px;
    transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
}

.atlas-example-card-clickable:hover {
    transform: translateY(-2px);
    border-color: rgba(15, 85, 87, 0.22);
    box-shadow: 0 16px 34px rgba(15, 31, 34, 0.08);
}

.atlas-results-intro {
    margin-bottom: 0.85rem;
}

.recommendation-card-large {
    padding: 1.15rem 1.2rem;
}

.atlas-reco-topline {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
}

.atlas-rank-bubble {
    width: 42px;
    height: 42px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 14px;
    background: rgba(15, 85, 87, 0.1);
    color: var(--atlas-teal-dark);
    font-weight: 900;
}


        /* Copenhagen Lite chat UI: higher contrast, larger input, explicit send action */
        .atlas-lite-hero h3 {
            font-size: clamp(1.95rem, 3.2vw, 2.75rem);
            letter-spacing: -0.055em;
        }

        .atlas-lite-hero p {
            max-width: 820px;
            font-size: 1.08rem;
            line-height: 1.62;
        }

        .atlas-lite-chat-card {
            margin: 1.35rem 0 0.85rem;
            padding: 1.25rem;
            border-radius: 28px;
            border: 1px solid rgba(15, 31, 34, 0.16);
            background:
                radial-gradient(circle at top left, rgba(201, 137, 43, 0.22), transparent 34%),
                linear-gradient(135deg, rgba(15, 85, 87, 0.99), rgba(10, 43, 45, 0.97));
            color: #fffaf0;
            box-shadow: 0 24px 58px rgba(15, 31, 34, 0.18);
        }

        .atlas-lite-chat-top {
            display: flex;
            align-items: center;
            gap: 0.95rem;
            margin-bottom: 1.05rem;
        }

        .atlas-lite-avatar {
            width: 58px;
            height: 58px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.24);
            color: #fffaf0;
            font-size: 1.75rem;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
        }

        .atlas-lite-chat-top strong {
            display: block;
            color: #fffaf0;
            font-size: 1.24rem;
            font-weight: 920;
            letter-spacing: -0.025em;
        }

        .atlas-lite-chat-top span {
            display: block;
            margin-top: 0.14rem;
            color: rgba(255, 250, 240, 0.78);
            font-size: 0.98rem;
        }

        .atlas-lite-message-row {
            display: flex;
            width: 100%;
        }

        .atlas-lite-message-row-user {
            justify-content: flex-end;
            margin: 0.95rem 0 0.7rem;
        }

        .atlas-lite-message {
            max-width: 860px;
            border-radius: 22px;
            line-height: 1.58;
        }

        .atlas-lite-message-assistant {
            padding: 1rem 1.1rem;
            background: rgba(255, 255, 255, 0.13);
            border: 1px solid rgba(255, 255, 255, 0.18);
            color: rgba(255, 250, 240, 0.94);
            font-size: 1.06rem;
        }

        .atlas-lite-message-assistant p,
        .atlas-lite-message-user p {
            margin: 0;
        }

        .atlas-lite-message-label {
            display: block;
            margin-bottom: 0.36rem;
            font-size: 0.72rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 0.09em;
        }

        .atlas-lite-message-assistant .atlas-lite-message-label {
            color: rgba(255, 250, 240, 0.72);
        }

        .atlas-lite-message-user {
            width: min(860px, 100%);
            padding: 1rem 1.15rem;
            background: #fffaf0;
            border: 1px solid rgba(15, 31, 34, 0.10);
            color: var(--atlas-ink);
            box-shadow: 0 12px 28px rgba(15, 31, 34, 0.08);
        }

        .atlas-lite-message-user .atlas-lite-message-label {
            color: var(--atlas-teal-dark);
        }

        .atlas-lite-message-user p {
            font-size: 1.06rem;
            line-height: 1.55;
            font-weight: 650;
        }

        textarea {
            min-height: 190px !important;
            border-radius: 24px !important;
            border: 1.5px solid rgba(15, 85, 87, 0.24) !important;
            background: #fffdf8 !important;
            color: var(--atlas-ink) !important;
            font-size: 1.13rem !important;
            line-height: 1.62 !important;
            padding: 1rem 1.08rem !important;
            box-shadow: 0 13px 32px rgba(15, 31, 34, 0.065) !important;
        }

        textarea:focus {
            border-color: rgba(15, 85, 87, 0.60) !important;
            box-shadow: 0 0 0 4px rgba(15, 85, 87, 0.12) !important;
        }

        div[data-testid="stForm"] {
            border: 0;
            padding: 0;
        }

        div[data-testid="stForm"] button[kind="primary"] {
            min-height: 56px;
            border-radius: 18px;
            font-size: 1.04rem;
            font-weight: 920;
            letter-spacing: -0.015em;
            background: var(--atlas-teal-dark);
            border: 1px solid rgba(15, 85, 87, 0.90);
            box-shadow: 0 14px 30px rgba(15, 85, 87, 0.22);
        }

        div[data-testid="stForm"] button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 18px 36px rgba(15, 85, 87, 0.28);
        }

        .atlas-lite-helper {
            margin: 0.35rem 0 1.25rem;
            color: var(--atlas-muted);
            font-size: 0.96rem;
            line-height: 1.55;
        }

        .atlas-smart-search-card h3 {
            margin-top: 0.2rem;
        }

        .atlas-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.75rem 0;
        }

        .atlas-example-card-clickable {
            min-height: 118px;
            transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
        }

        .atlas-example-card-clickable:hover {
            transform: translateY(-2px);
            border-color: rgba(15, 85, 87, 0.22);
            box-shadow: 0 16px 34px rgba(15, 31, 34, 0.08);
        }

        .atlas-results-intro {
            margin-bottom: 0.85rem;
        }

        .recommendation-card-large {
            padding: 1.15rem 1.2rem;
        }

        .atlas-reco-topline {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }

        .atlas-rank-bubble {
            width: 42px;
            height: 42px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 14px;
            background: rgba(15, 85, 87, 0.10);
            color: var(--atlas-teal-dark);
            font-weight: 900;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        """
        <div class="atlas-hero">
            <div class="atlas-kicker">🧭 Copenhagen, easier to explore</div>
            <h1 class="atlas-title">Copenhagen Mood Atlas</h1>
            <p class="atlas-subtitle">
                Compare districts by everyday mood: cosy cafés, calm streets, practical errands,
                rainy-day plans and places with a bit more social energy.
            </p>
            <div style="margin-top:0.9rem;">
                <span class="atlas-pill">Choose a lens</span>
                <span class="atlas-pill">Explore the map</span>
                <span class="atlas-pill">Get a match</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
                    This version no longer falls back to mock neighbourhood values.
                    If the automatic KK Statistikbank fetch fails, export the two CSV files manually and place them in
                    <code>data/raw/</code> before rebuilding the processed dataset.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    df = calculate_all_scores(df)

    # Keep the first page focused on the user experience. Technical data-status details
    # live in the Method tab so the product does not greet users with pipeline language.

    map_tab, recommend_tab, method_tab = st.tabs(["🗺️ Explore", "✨ Recommend", "🔍 Method"])
    with map_tab:
        render_hygge_map(df)
    with recommend_tab:
        render_recommendations(df)
    with method_tab:
        render_methodology(df)


if __name__ == "__main__":
    main()
