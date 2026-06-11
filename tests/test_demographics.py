from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.processing.build_demographic_features import build_demographic_features
from src.processing.build_osm_features import build_boundary_base, load_demographic_features


def test_build_demographic_features_from_statbank_like_csv(tmp_path: Path) -> None:
    population_csv = tmp_path / "population.csv"
    family_csv = tmp_path / "families.csv"
    output_csv = tmp_path / "demographics.csv"

    population_csv.write_text(
        "district;sex;age;citizenship;quarter;number\n"
        "Nørrebro;Total;Total;Total;2025Q4;80000\n"
        "Nørrebro;Total;20-24;Total;2025Q4;9000\n"
        "Nørrebro;Total;25-29;Total;2025Q4;10000\n"
        "Nørrebro;Total;30-34;Total;2025Q4;11000\n"
        "Nørrebro;Total;Total;Denmark;2025Q4;56000\n"
        "Nørrebro;Total;Total;Foreign;2025Q4;24000\n"
        "Østerbro;Total;Total;Total;2025Q4;72000\n"
        "Østerbro;Total;20-24;Total;2025Q4;5000\n"
        "Østerbro;Total;25-29;Total;2025Q4;6000\n"
        "Østerbro;Total;30-34;Total;2025Q4;7000\n"
        "Østerbro;Total;Total;Denmark;2025Q4;60000\n"
        "Østerbro;Total;Total;Foreign;2025Q4;12000\n",
        encoding="utf-8",
    )
    family_csv.write_text(
        "district;family_type;number_of_children;quarter;number\n"
        "Nørrebro;Total;Total;2025Q4;40000\n"
        "Nørrebro;Total;0 children;2025Q4;30000\n"
        "Nørrebro;Total;1 child;2025Q4;6000\n"
        "Nørrebro;Total;2 children;2025Q4;4000\n"
        "Østerbro;Total;Total;2025Q4;36000\n"
        "Østerbro;Total;0 children;2025Q4;24000\n"
        "Østerbro;Total;1 child;2025Q4;7000\n"
        "Østerbro;Total;2 children;2025Q4;5000\n",
        encoding="utf-8",
    )

    df = build_demographic_features(population_csv, family_csv, output_csv)

    norrebro = df.loc[df["neighbourhood"] == "Nørrebro"].iloc[0]
    assert int(norrebro["population"]) == 80000
    assert round(float(norrebro["share_age_20_34"]), 3) == 0.375
    assert round(float(norrebro["share_international_background"]), 3) == 0.300
    assert round(float(norrebro["share_families_with_children"]), 3) == 0.250
    assert output_csv.exists()


def test_boundary_base_uses_official_demographics(tmp_path: Path) -> None:
    demographics_path = tmp_path / "demographics.csv"
    pd.DataFrame(
        {
            "neighbourhood": ["Nørrebro"],
            "population": [80000],
            "share_age_20_34": [0.37],
            "share_families_with_children": [0.25],
            "share_international_background": [0.30],
            "demographic_source": ["KK Statistikbank"],
        }
    ).to_csv(demographics_path, index=False)
    demographics = load_demographic_features(demographics_path)

    boundaries = [
        {
            "boundary_name": "Nørrebro",
            "district": "Nørrebro",
            "lat": 55.7,
            "lon": 12.55,
            "area_km2": 4.0,
        }
    ]
    output = build_boundary_base(boundaries, demographics)
    row = output.iloc[0]
    assert int(row["population"]) == 80000
    assert row["data_mode"] == "osm_amenities_official_boundaries_official_demographics"
    assert row["demographic_assignment_method"] == "official_district_name_match"
