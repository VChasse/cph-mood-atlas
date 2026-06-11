# Copenhagen Mood Atlas

**Copenhagen Mood Atlas** is a Streamlit data product for exploring Copenhagen districts through everyday lifestyle fit: cosy cafés, calm streets, practical errands, rainy-day options, social energy, family living, and international feel.

It combines an interactive district map, lifestyle scoring, natural-language recommendations, transparent methodology, and cached public data in a deployment-ready portfolio project.

---

## Overview

Choosing where to spend time in a city is rarely only about distance. People compare neighbourhoods through routines, preferences, trade-offs, and small daily rituals: where to get coffee, where to walk on a rainy Sunday, where errands are easy, or where the streets feel quieter.

Copenhagen Mood Atlas turns those preferences into a guided exploration tool:

1. **Choose a lifestyle lens** such as Hygge, Calm, Daily Convenience, or Rainy-day Comfort.
2. **Inspect a district** through score chips, a profile card, a polygon map, and a compact radar view.
3. **Ask for a recommendation** in natural language and get ranked district matches with plain-English explanations.

The product uses a warm, editorial interface with clear cards, compact scoring, step-based navigation, and a restrained Copenhagen-inspired visual system.

---

## What This Project Demonstrates

| Area | What it shows |
| --- | --- |
| **Product design** | Guided flow, clear hierarchy, ranked cards, onboarding, and low-friction exploration. |
| **Streamlit frontend** | Custom CSS design system, responsive layout, tabs, expanders, Plotly charts, and polished UI components. |
| **Data product thinking** | Proxy score design, caveats, source transparency, cached data, and an auditable Method tab. |
| **Recommendation logic** | Deterministic natural-language parsing with synonyms, related concepts, negation handling, compatibility adjustments, and explainable outputs. |
| **Engineering hygiene** | Modular app structure, reproducible scripts, local processed data, lightweight tests, and deployment-friendly dependencies. |

---

## Features

- **Interactive Copenhagen district map** built from official district polygons.
- **Lifestyle lenses** for Hygge, Calm, Youth Pulse, Daily Convenience, Rainy-day Comfort, Family Living, and International Feel.
- **Natural-language district matcher** for prompts such as `calm, cafés, parks, easy transit, not too loud`.
- **Explainable ranking cards** showing the strongest signals behind each match.
- **Methodology tab** with score definitions, source notes, and formulas rendered from the code config.
- **Real-data-first runtime** that stops with setup guidance when required processed files are missing.
- **Offline ingestion pipeline** for OpenStreetMap amenities, official district boundaries, and demographic exports.
- **Deployment-friendly architecture** with cached local data and no paid model APIs.

---

## Interface System

The app uses a compact product interface built around mapped exploration, ranked recommendation cards, and readable score explanations.

### Main flow

- 🧭 **Step 1 · Choose a map lens**
- 👆 **Step 2 · Inspect a district**
- ✨ **Step 3 · Get a match**

### Visual tokens

| Token | Role | Hex |
| --- | --- | --- |
| Warm canvas | App background | `#F7F3EA` |
| Surface | Cards and panels | `#FFFFFF` / translucent white |
| Ink | Primary text | `#17201E` |
| Muted | Secondary text | `#6F766F` |
| Deep teal | Main product accent | `#0F5557` |
| Sage | Soft positive highlight | `#DDE7D3` |
| Amber | Kicker / status accent | `#C9892B` |
| Clay | Secondary warmth | `#D98568` |

---

## Recommendation Engine

The recommendation engine is deterministic and does **not** call an LLM API. It is lightweight, reproducible, and easy to deploy.

It uses:

- concept rules with synonyms and regex word boundaries
- related concept expansion, for example family also boosts calm, convenience, green access, and rainy-day comfort
- negation handling for phrases such as `no nightlife`, `too loud`, and `avoid nightlife`
- compatibility adjustments, for example strong family or calm searches are slightly penalised by nightlife pressure
- explanations based on the strongest user-weighted signals

Example output:

> Indre By ranks **#1** with a match score of **100%**. For your query, the strongest matching signals are: **Rainy-day Comfort** 100%; **Hygge** 87%; **Calm** 46%.

---

## Data Sources

The app uses cached local data and does not query public services at runtime.

| Source | Used for |
| --- | --- |
| **Open Data DK** | Official Copenhagen district boundary polygons. |
| **OpenStreetMap via Overpass** | Amenity signals such as cafés, bakeries, libraries, museums, bars, benches, bike parking, and practical services. |
| **KK Statistikbank** | District-level population, age, citizenship, and family indicators from official CSV exports. |

### Data Notes

The scores are **explainable proxy indices**, not official statistics. They are designed for exploration and comparison, not for absolute claims about neighbourhood quality, safety, or desirability.

---

## Project Structure

```text
app/
  streamlit_app.py                 # Streamlit entry point and visual system
  data_loader.py                   # Loads local processed data only
  page_renderers.py                # Explore, Recommend, and Method page sections
src/
  ingestion/
    fetch_osm.py                   # Overpass API ingestion, run manually
    fetch_boundaries.py            # Official Copenhagen district GeoJSON ingestion
    fetch_demographics.py          # KK Statistikbank demographic ingestion
  processing/
    build_osm_features.py          # Clean and aggregate cached OSM data
    build_demographic_features.py  # Clean official demographic CSVs
    build_scores.py                # Score calculation
  recommendation/                  # Ranking, parsing, and explanations
  utils/config.py                  # Paths, API config, labels, and formulas
data/
  raw/                             # Raw API extracts, ignored by git except .gitkeep
  processed/                       # Local app-ready data
tests/                             # Lightweight unit tests
```

---

## Local Setup

Use Python 3.11+.

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The app expects these files to exist locally:

```text
data/processed/neighborhood_features_osm.csv
data/raw/copenhagen_bydels_boundaries_raw.geojson
```

If they are missing, the app shows setup guidance instead of falling back to mock data.

---

## Data Pipeline

Run these scripts to refresh the local data files.

### 1. Fetch official Copenhagen district boundaries

```bash
python -m src.ingestion.fetch_boundaries
```

Creates:

```text
data/raw/copenhagen_bydels_boundaries_raw.geojson
data/processed/copenhagen_bydels_boundaries_clean.csv
```

If automatic discovery fails, open the Open Data DK dataset page, copy the direct `bydele.geojson` download URL, then run:

```bash
python -m src.ingestion.fetch_boundaries --url "<DIRECT_GEOJSON_URL>" --force
```

### 2. Fetch raw OpenStreetMap amenities

```bash
python -m src.ingestion.fetch_osm
```

Creates:

```text
data/raw/osm_copenhagen_amenities_raw.json
```

Use `--force` only when deliberately refreshing Overpass data:

```bash
python -m src.ingestion.fetch_osm --force
```

Overpass is a public community service, so requests are manual and cached.

### 3. Fetch and process official demographic data

```bash
python -m src.ingestion.fetch_demographics
python -m src.processing.build_demographic_features
```

The demographic layer uses KK Statistikbank district tables:

- `KKBEF8`: population by district, sex, 5-year age group, and citizenship
- `KKFAM1`: families by district, family type, and number of children

If the hosted API endpoint is unavailable, export CSVs manually from KK Statistikbank and place them at:

```text
data/raw/kkbef8_population_by_district_age_citizenship.csv
data/raw/kkfam1_families_by_district_children.csv
```

Then rerun:

```bash
python -m src.processing.build_demographic_features
```

### 4. Build final app-ready features

```bash
python -m src.processing.build_osm_features
```

Creates:

```text
data/processed/osm_amenities_clean.csv
data/processed/osm_amenities_by_neighbourhood.csv
data/processed/neighborhood_features_osm.csv
```

The OSM pipeline assigns amenities using point-in-polygon against Copenhagen district polygons. If boundary files are missing, the build step fails instead of assigning amenities to approximate or mock centroids.

Expected real-data labels when all real layers are available:

```text
data_mode = osm_amenities_official_boundaries_official_demographics
osm_assignment_method = official_boundary_point_in_polygon
demographic_source = KK Statistikbank
```

---

## Deployment

The app is ready for Streamlit Community Cloud.

Deployment settings:

```text
Main file path: app/streamlit_app.py
Python version: 3.11+
```

Runtime characteristics:

- uses local processed CSV and GeoJSON files
- avoids paid model APIs
- keeps dependencies light: Streamlit, pandas, numpy, plotly, requests, and pytest
- avoids heavy geospatial runtime dependencies such as GeoPandas
- includes `.streamlit/config.toml`

Commit the processed CSV and boundary GeoJSON for the hosted app to render the full polygon map. Avoid committing large raw Overpass dumps unless they are intentionally part of the repository.

---

## Quality Checks

```bash
python -m pytest -q
python -m compileall -q app src tests
```

---

## Limitations

- Scores are proxy indices, not official rankings.
- Rainy-day Comfort measures indoor-friendly places, not actual weather.
- Family Living does not include schools, childcare quality, traffic safety, rent, or housing availability.
- International Feel uses citizenship-based demographic signals, which are only a partial proxy.
- Transit access is currently represented by available amenity/service features, not full network travel times.

---

## Roadmap

- Add source freshness metadata to the UI.
- Add a screenshot or GIF section for portfolio presentation.
- Add transit-stop and travel-time access.
- Add stronger family-living signals such as playgrounds, schools, childcare, traffic safety, and noise.
- Add a side-by-side district comparison panel.
- Add deployment badge and live demo link once hosted.
