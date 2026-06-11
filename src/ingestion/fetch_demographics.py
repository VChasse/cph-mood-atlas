"""Fetch Copenhagen district demographics from KK Statistikbank / Statbank-style APIs.

This script is intentionally separate from Streamlit. It caches raw extracts in
``data/raw`` so the app can stay fast, deterministic, and respectful of public
services.

Primary source:
- KKBEF8: population by district, sex, 5-year age group and citizenship
- KKFAM1: families by district, family type and number of children

The KK Statistikbank site is built on the same Statbank/PX style as Statistics
Denmark, but hosted by the City of Copenhagen. The script therefore tries a
small list of compatible API endpoints and gives a clear fallback path: download
CSV manually from kk.statistikbank.dk if the hosted API endpoint is unavailable.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from src.utils.config import (
    DEMOGRAPHICS_FAMILY_RAW_PATH,
    DEMOGRAPHICS_POPULATION_RAW_PATH,
    KK_STATBANK_API_CANDIDATES,
    KK_STATBANK_FAMILY_TABLE,
    KK_STATBANK_POPULATION_TABLE,
)


@dataclass(frozen=True)
class StatbankRequest:
    """Definition of one Statbank-style table extract."""

    table_id: str
    output_path: Path
    variables: list[dict[str, Any]]


REQUESTS = [
    StatbankRequest(
        table_id=KK_STATBANK_POPULATION_TABLE,
        output_path=DEMOGRAPHICS_POPULATION_RAW_PATH,
        variables=[
            {"code": "OMRÅDE", "values": ["*"]},
            {"code": "KØN", "values": ["*"]},
            {"code": "ALDER", "values": ["*"]},
            {"code": "STATSBORGERSKAB", "values": ["*"]},
            {"code": "TID", "values": ["*"]},
        ],
    ),
    StatbankRequest(
        table_id=KK_STATBANK_FAMILY_TABLE,
        output_path=DEMOGRAPHICS_FAMILY_RAW_PATH,
        variables=[
            {"code": "OMRÅDE", "values": ["*"]},
            {"code": "FAMILIETYPE", "values": ["*"]},
            {"code": "ANTALBØRN", "values": ["*"]},
            {"code": "TID", "values": ["*"]},
        ],
    ),
]


class DemographicFetchError(RuntimeError):
    """Raised when all demographic fetch attempts fail."""


def _post_statbank_request(
    base_url: str,
    request: StatbankRequest,
    timeout_seconds: int,
) -> requests.Response:
    """POST a Statbank-style data request and return the raw response."""
    endpoint = base_url.rstrip("/")
    payload = {
        "table": request.table_id,
        "format": "CSV",
        "lang": "en",
        "valuePresentation": "CodeAndValue",
        "variables": request.variables,
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "CopenhagenMoodAtlas/0.1 portfolio data pipeline",
    }
    return requests.post(endpoint, data=json.dumps(payload), headers=headers, timeout=timeout_seconds)


def fetch_table(
    request: StatbankRequest,
    *,
    force: bool = False,
    sleep_seconds: float = 1.0,
    timeout_seconds: int = 60,
) -> Path:
    """Fetch one demographic table and cache it to disk.

    Existing cached files are reused unless ``force=True``.
    """
    if request.output_path.exists() and not force:
        print(f"Using cached {request.table_id}: {request.output_path}")
        return request.output_path

    request.output_path.parent.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for base_url in KK_STATBANK_API_CANDIDATES:
        try:
            print(f"Fetching {request.table_id} from {base_url} ...")
            response = _post_statbank_request(base_url, request, timeout_seconds)
            if response.ok and response.text.strip():
                request.output_path.write_text(response.text, encoding="utf-8")
                time.sleep(max(sleep_seconds, 0.0))
                print(f"Wrote {request.output_path}")
                return request.output_path
            errors.append(f"{base_url} -> HTTP {response.status_code}: {response.text[:240]}")
        except requests.RequestException as exc:
            errors.append(f"{base_url} -> {type(exc).__name__}: {exc}")

    guidance = f"""
Could not fetch {request.table_id} automatically.

This means no official demographic CSV has been cached yet. The pipeline will stop rather than invent values.

Continue with the manual KK Statistikbank export:
- Population: https://kk.statistikbank.dk/{KK_STATBANK_POPULATION_TABLE}
- Families:   https://kk.statistikbank.dk/{KK_STATBANK_FAMILY_TABLE}

Export CSV files and save this table here:
{request.output_path}

After both CSVs are saved, rerun:
python -m src.processing.build_demographic_features
python -m src.processing.build_osm_features

Attempts:
{chr(10).join('- ' + error for error in errors)}
""".strip()
    raise DemographicFetchError(guidance)


def fetch_demographic_tables(*, force: bool = False, sleep_seconds: float = 1.0) -> list[Path]:
    """Fetch all required raw demographic tables."""
    paths: list[Path] = []
    for request in REQUESTS:
        paths.append(fetch_table(request, force=force, sleep_seconds=sleep_seconds))
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Copenhagen district demographics from KK Statistikbank.")
    parser.add_argument("--force", action="store_true", help="Refresh cached raw CSV files.")
    parser.add_argument("--sleep", type=float, default=1.0, help="Pause between successful requests.")
    args = parser.parse_args(argv)

    try:
        paths = fetch_demographic_tables(force=args.force, sleep_seconds=args.sleep)
    except DemographicFetchError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Fetched demographic raw files:")
    for path in paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
