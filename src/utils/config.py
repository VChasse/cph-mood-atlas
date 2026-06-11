"""Central configuration for Copenhagen Mood Atlas."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Real OSM pipeline outputs. The Streamlit app reads processed files only.
OSM_RAW_PATH = RAW_DATA_DIR / "osm_copenhagen_amenities_raw.json"
OSM_CLEAN_PATH = PROCESSED_DATA_DIR / "osm_amenities_clean.csv"
OSM_AGGREGATED_PATH = PROCESSED_DATA_DIR / "osm_amenities_by_neighbourhood.csv"
OSM_FEATURES_PATH = PROCESSED_DATA_DIR / "neighborhood_features_osm.csv"


# Official Copenhagen district boundaries from Open Data DK / City of Copenhagen.
BOUNDARIES_RAW_PATH = RAW_DATA_DIR / "copenhagen_bydels_boundaries_raw.geojson"
BOUNDARIES_CLEAN_PATH = PROCESSED_DATA_DIR / "copenhagen_bydels_boundaries_clean.csv"
CPH_BOUNDARIES_DATASET_PAGE = "https://www.opendata.dk/city-ofcopenhagen/bydele"
CPH_BOUNDARIES_GEOJSON_URL = (
    "https://wfs-kbhkort.kk.dk/k101/ows?"
    "SRSNAME=EPSG%3A4326&outputFormat=json&request=GetFeature&"
    "service=WFS&typeName=k101%3Abydel&version=1.0.0"
)


# Official demographic pipeline outputs. Run manually; Streamlit reads processed files only.
DEMOGRAPHICS_POPULATION_RAW_PATH = RAW_DATA_DIR / "kkbef8_population_by_district_age_citizenship.csv"
DEMOGRAPHICS_FAMILY_RAW_PATH = RAW_DATA_DIR / "kkfam1_families_by_district_children.csv"
DEMOGRAPHICS_FEATURES_PATH = PROCESSED_DATA_DIR / "copenhagen_demographic_features.csv"

# KK Statistikbank tables used for district demographics.
KK_STATBANK_POPULATION_TABLE = "KKBEF8"
KK_STATBANK_FAMILY_TABLE = "KKFAM1"
# Candidate Statbank-style API endpoints. The fetcher tries each and gives manual
# CSV-download guidance if the hosted API is unavailable.
KK_STATBANK_API_CANDIDATES = [
    "https://kk.statistikbank.dk/api/v1/data",
    "https://kk.statistikbank.dk/statbank5a/api/v1/data",
]

# Overpass expects bbox order: south, west, north, east.
# This deliberately covers central Copenhagen plus close neighbouring urban areas.
OVERPASS_BBOX = (55.615, 12.43, 55.735, 12.68)
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"

# App runtime uses only the final real app-ready dataset. No mock fallback.
def default_processed_data_path() -> Path:
    return OSM_FEATURES_PATH

SCORE_COLUMNS = [
    "hygge_score",
    "calm_score",
    "youth_pulse_score",
    "daily_convenience_score",
    "rainy_day_index",
    "family_friendliness_score",
    "international_friendliness_score",
]

RECOMMENDATION_DIMENSIONS = {
    "hygge": "hygge_score",
    "calm": "calm_score",
    "youth_pulse": "youth_pulse_score",
    "daily_convenience": "daily_convenience_score",
    "rainy_day": "rainy_day_index",
    "family_friendliness": "family_friendliness_score",
    "international_friendliness": "international_friendliness_score",
}

DISPLAY_SCORE_NAMES = {
    "hygge_score": "Hygge",
    "calm_score": "Calm",
    "youth_pulse_score": "Youth Pulse",
    "daily_convenience_score": "Daily Convenience",
    "rainy_day_index": "Rainy-day Comfort",
    "family_friendliness_score": "Family Living",
    "international_friendliness_score": "International Feel",
}

# One source of truth for formulas shown in the Method tab and used by scoring.
# All weights are normalized inside src.processing.build_scores.weighted_sum.
SCORE_FORMULAS = {
    "hygge_score": {
        "cafe_density_norm": 0.25,
        "bakery_density_norm": 0.15,
        "library_access_norm": 0.15,
        "green_space_access_norm": 0.15,
        "bench_density_norm": 0.10,
        "indoor_culture_density_norm": 0.10,
        "bike_accessibility_norm": 0.10,
    },
    "nightlife_pressure": {
        "bar_density_norm": 0.45,
        "nightlife_density_norm": 0.35,
        "population_density_norm": 0.20,
    },
    "calm_score": {
        "green_space_access_norm": 0.38,
        "low_nightlife_pressure": 0.30,
        "low_population_pressure": 0.17,
        "bike_accessibility_norm": 0.10,
        "bench_density_norm": 0.05,
    },
    "youth_pulse_score": {
        "share_age_20_34_norm": 0.40,
        "bar_density_norm": 0.20,
        "nightlife_density_norm": 0.20,
        "cafe_density_norm": 0.10,
        "indoor_culture_density_norm": 0.10,
    },
    "daily_convenience_score": {
        "supermarket_density_norm": 0.25,
        "pharmacy_density_norm": 0.20,
        "transit_stop_density_norm": 0.25,
        "public_toilet_density_norm": 0.10,
        "bike_parking_density_norm": 0.20,
    },
    "rainy_day_index": {
        "cafe_density_norm": 0.25,
        "library_access_norm": 0.20,
        "cinema_density_norm": 0.15,
        "museum_density_norm": 0.20,
        "indoor_culture_density_norm": 0.20,
    },
    "family_friendliness_score": {
        "share_families_with_children_norm": 0.23,
        "green_space_access_norm": 0.22,
        "calm_score": 0.22,
        "daily_convenience_score": 0.18,
        "rainy_day_index": 0.08,
        "low_nightlife_pressure": 0.07,
    },
    "international_friendliness_score": {
        "share_international_background_norm": 0.65,
        "daily_convenience_score": 0.15,
        "youth_pulse_score": 0.10,
        "rainy_day_index": 0.10,
    },
}

CORE_REQUIRED_COLUMNS = [
    "neighbourhood",
    "district",
    "lat",
    "lon",
    "population",
    "population_density",
]

DEMOGRAPHIC_COLUMNS = [
    "population",
    "share_age_20_34",
    "share_families_with_children",
    "share_international_background",
]
