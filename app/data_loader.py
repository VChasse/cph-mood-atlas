"""Data loading helpers for the Streamlit app.

The app intentionally refuses to auto-generate mock data. Real/public data must be
prepared ahead of runtime by the ingestion and processing scripts.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.processing.build_scores import calculate_all_scores
from src.utils.config import CORE_REQUIRED_COLUMNS, OSM_FEATURES_PATH, default_processed_data_path


class DataNotReadyError(FileNotFoundError):
    """Raised when the app-ready real processed dataset has not been built yet."""


@st.cache_data(show_spinner=False)
def load_processed_data(path: Path | str | None = None) -> pd.DataFrame:
    """Load the app-ready real processed feature table.

    Streamlit reads local processed files only. It does not call Overpass,
    Open Data DK or KK Statistikbank at runtime, and it no longer falls back to
    mock data.
    """
    data_path = Path(path) if path is not None else default_processed_data_path()

    if not data_path.exists():
        raise DataNotReadyError(
            "Real processed data is not ready yet. Build it with:\n"
            "  python -m src.ingestion.fetch_boundaries\n"
            "  python -m src.ingestion.fetch_osm\n"
            "  python -m src.ingestion.fetch_demographics\n"
            "  python -m src.processing.build_demographic_features\n"
            "  python -m src.processing.build_osm_features\n\n"
            f"Expected output: {OSM_FEATURES_PATH}"
        )

    df = pd.read_csv(data_path)
    missing = [column for column in CORE_REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(
            "Processed data is missing required columns: "
            + ", ".join(missing)
            + f". Check {data_path}."
        )

    if "is_mock_data" in df.columns and df["is_mock_data"].astype(bool).any():
        raise ValueError(
            f"Refusing to load mock data from {data_path}. Run the real-data pipeline or provide real source files."
        )

    if "data_mode" in df.columns:
        invalid_modes = df["data_mode"].astype(str).str.contains("mock", case=False, na=False)
        if invalid_modes.any():
            raise ValueError(
                f"Refusing to load a mock-labelled processed dataset from {data_path}. "
                "Run the real-data pipeline or provide the missing real demographic files."
            )

    df = calculate_all_scores(df)
    df["is_mock_data"] = False
    if "data_mode" not in df.columns:
        df["data_mode"] = "osm_amenities_official_boundaries_official_demographics"

    return df
