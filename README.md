# Copenhagen Mood Atlas

**Copenhagen Mood Atlas** is a portfolio-ready Streamlit data product that helps people explore Copenhagen districts by everyday lifestyle fit: cosy cafés, calm streets, practical errands, rainy-day options, social energy, family living, and international feel.

The project is intentionally built like a small product, not a notebook demo. It combines a guided UX, an interactive polygon map, deterministic recommendations, transparent scoring, and cached public data so the app is fast, explainable, and deployment-friendly.

---

## Product Story

Moving through a city is rarely just about distance. People choose neighbourhoods based on mood, habits, constraints, and small daily rituals: where to get coffee, where to walk on a rainy Sunday, where errands are easy, or where the streets feel calmer.

Copenhagen Mood Atlas turns those fuzzy preferences into a readable exploration tool:

1. **Choose a map lens** such as Hygge, Calm, Daily Convenience, or Rainy-day Comfort.
2. **Inspect a district** with score chips, a profile card, and a compact radar view.
3. **Ask for a recommendation** in natural language and get ranked matches with plain-English explanations.

The app is designed with a clean Notion/Clay-inspired interface: warm surfaces, clear cards, large visual step markers, minimal chart noise, and strong hierarchy around the next action.

---

## What This Demonstrates

This project is meant to show end-to-end product judgment, not only technical implementation.

| Area | What the project shows |
| --- | --- |
| **UX / Product Design** | Guided flow, clear information hierarchy, card-based ranking, visible onboarding, and low-friction exploration. |
| **Frontend in Streamlit** | Custom CSS design system, responsive layout, polished cards, progress indicators, tabs, expanders, and Plotly integration. |
| **Data Product Thinking** | Proxy score design, caveats, source transparency, no fake runtime fallback, and Method tab for auditability. |
| **Recommendation Logic** | Deterministic natural-language parsing with synonyms, related concepts, negation handling, compatibility adjustments, and explainable outputs. |
| **Engineering Hygiene** | Modular app structure, local processed data, lightweight tests, reproducible scripts, and deployment-friendly dependencies. |

---

## Key Features

- **Interactive Copenhagen district map** using official district polygons.
- **Lifestyle lenses** for Hygge, Calm, Youth Pulse, Daily Convenience, Rainy-day Comfort, Family Living, and International Feel.
- **Natural-language recommendation engine** for prompts such as `calm, cafés, parks, easy transit, not too loud`.
- **Explainable ranking cards** that show why a district matched instead of only returning a score.
- **Clean portfolio UI** with a defined Copenhagen-inspired palette, large step icons, card surfaces, pills, score chips, and progress bars.
- **Transparent methodology tab** rendering score formulas directly from the code config.
- **Real-data-first runtime**: the app stops with setup instructions if required processed files are missing instead of inventing values.
- **Offline ingestion pipeline** for OpenStreetMap amenities, official boundaries, and demographic exports.

---

## UX Decisions

### 1. Remove chart noise

The earlier bar charts were removed because they did not help the core user journey. The app now uses ranked cards and progress bars, which are faster to scan and feel closer to a modern product interface.

### 2. Make the journey obvious

Large step labels guide the user through the app:

- 🧭 **Step 1 · Choose a map lens**
- 👆 **Step 2 · Inspect a district**
- ✨ **Step 3 · Get a match**

This makes the experience more self-explanatory during a portfolio review or live demo.

### 3. Keep the UI calm and editorial

The visual system uses a restrained palette:

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

The goal is to feel closer to Notion or Clay than a default analytics dashboard.

### 4. Explain before asking for trust

The Method tab makes the proxy nature of the scores explicit. It shows the source stack, what each score means, and the exact weighted formula used in code.

---

## Recommendation Engine

The recommendation engine is deterministic and does **not** call an LLM API. This keeps the project lightweight, reproducible, and easy to deploy.

It uses:

- concept rules with synonyms and regex word boundaries
- related concept expansion, for example family also boosts calm, convenience, green access, and rainy-day comfort
- simple negation handling, for example `no nightlife`, `too loud`, and `avoid nightlife`
- compatibility adjustments, for example strong family or calm searches are slightly penalised by nightlife pressure
- explanations based on the strongest user-weighted signals, not only each district's generic strengths

Example output:

> Indre By ranks **#1** with a match score of **100%**. For your query, the strongest matching signals are: **Rainy-day Comfort** 100%; **Hygge** 87%; **Calm** 46%.

---

## Data Sources

The app is built around cached local data. It does not query public services at runtime.

| Source | Used for |
| --- | --- |
| **Open Data DK** | Official Copenhagen district boundary polygons. |
| **OpenStreetMap via Overpass** | Amenity signals such as cafés, bakeries, libraries, museums, bars, benches, bike parking, and practical services. |
| **KK Statistikbank** | District-level population, age, citizenship, and family indicators from official CSV exports. |

### Data Philosophy

The scores are **not official statistics**. They are explainable proxy indices created from public signals. The goal is to support exploration and comparison, not to make absolute claims about neighbourhood quality, safety, or desirability.

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

The app expects:

```text
data/processed/neighborhood_features_osm.csv
data/raw/copenhagen_bydels_boundaries_raw.geojson
```

If these files are missing, the app shows setup guidance instead of falling back to mock data.

---

## Real-data Pipeline

Run these scripts when you want to refresh the local data files.

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

Use `--force` only when you deliberately want a fresh Overpass request:

```bash
python -m src.ingestion.fetch_osm --force
```

Overpass is a public community service, so the project keeps requests manual and cached.

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

Preferred real-data labels when all real layers are available:

```text
data_mode = osm_amenities_official_boundaries_official_demographics
osm_assignment_method = official_boundary_point_in_polygon
demographic_source = KK Statistikbank
```

---

## Streamlit Community Cloud Deployment

This app is designed to deploy cleanly because it:

- uses local processed CSV and GeoJSON files at runtime
- avoids paid model APIs
- keeps dependencies light: Streamlit, pandas, numpy, plotly, requests, and pytest
- avoids heavy geospatial runtime dependencies such as GeoPandas
- includes `.streamlit/config.toml`

Deployment settings:

```text
Main file path: app/streamlit_app.py
Python version: 3.11+
```

Commit the processed CSV and boundary GeoJSON if you want the hosted app to render the full polygon map. Avoid committing large raw Overpass dumps unless you intentionally want them in the repository.

---

## Quality Checks

```bash
python -m pytest -q
python -m compileall -q app src tests
```

---

## Current Limitations

- The scores are proxy indices, not official rankings.
- Rainy-day Comfort measures indoor-friendly places, not actual weather.
- Family Living does not include schools, childcare quality, traffic safety, rent, or housing availability.
- International Feel uses citizenship-based demographic signals, which are only a partial proxy.
- Transit access is currently represented by available amenity/service features, not full network travel times.

---

## Next Improvements

- Add source freshness metadata to the UI.
- Add a small screenshot/GIF section for portfolio presentation.
- Add real transit-stop and travel-time access.
- Add stronger family-living signals such as playgrounds, schools, childcare, traffic safety, and noise.
- Add a “compare two districts” panel for side-by-side decision-making.
- Add deployment badge and live demo link once hosted.
