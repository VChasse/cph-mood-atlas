"""Build Copenhagen district demographic features from cached KK Statistikbank CSVs.

Outputs an app-ready demographic table with these replacement columns:

- population
- share_age_20_34
- share_families_with_children
- share_international_background

The parser is deliberately tolerant because KK Statistikbank exports can vary by
language, value presentation, and whether the user exported from the UI or API.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.utils.config import (
    DEMOGRAPHICS_FEATURES_PATH,
    DEMOGRAPHICS_FAMILY_RAW_PATH,
    DEMOGRAPHICS_POPULATION_RAW_PATH,
)

AGE_20_34_PATTERN = re.compile(r"(^|[^0-9])(20|25|30)\s*[-–]\s*(24|29|34)([^0-9]|$)")
TOTAL_TOKENS = {"total", "tot", "i alt", "ialt", "all", "alle", "sum"}
DANISH_TOKENS = {"denmark", "danmark", "danish", "dansk", "danske", "danmark/danish"}
NO_CHILDREN_TOKENS = {"0", "0 born", "0 børn", "uden born", "uden børn", "no children", "without children"}


def _ascii(value: object) -> str:
    text = str(value).strip().lower()
    text = text.replace("ø", "o").replace("å", "a").replace("æ", "ae")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text)


def _norm_col(value: object) -> str:
    text = _ascii(value)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _clean_area_name(value: object) -> str:
    """Remove Statbank code/prefix text while preserving readable Danish names."""
    text = str(value).strip()
    text = re.sub(r"^\s*district\s*-\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*distrikt\s*-\s*", "", text, flags=re.IGNORECASE)
    # Common exports can look like "1 Indre By" or "101 Copenhagen".
    text = re.sub(r"^\s*[0-9][0-9A-Za-z_.-]*\s+", "", text) if re.match(r"^\s*[0-9][0-9A-Za-z_.-]*\s+", text) else text
    return text.strip()


def _decode_statbank_text(path: Path) -> str:
    """Decode a KK Statistikbank CSV export without assuming UTF-8."""
    raw = path.read_bytes()
    errors: list[str] = []
    for encoding in ("utf-8-sig", "cp1252", "latin1", "iso-8859-1", "utf-16"):
        try:
            return raw.decode(encoding).replace("\ufeff", "")
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError(f"Could not decode {path}. Details: {' | '.join(errors)}")


def _csv_rows_from_text(text: str) -> list[list[str]]:
    """Parse Statbank CSV text into rows, trying the export's likely dialects."""
    text = text.strip()
    if not text:
        return []
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("sep="):
        text = "\n".join(lines[1:])

    attempts: list[tuple[str, bool]] = [(",", True), (";", True), ("\t", True), (",", False), (";", False), ("\t", False)]
    last_error: Exception | None = None
    for delimiter, use_quotes in attempts:
        try:
            if use_quotes:
                reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            else:
                reader = csv.reader(io.StringIO(text), delimiter=delimiter, quoting=csv.QUOTE_NONE)
            rows = [[cell.strip() for cell in row] for row in reader]
            meaningful = [row for row in rows if any(cell.strip() for cell in row)]
            if meaningful and max(len(row) for row in meaningful) > 2:
                return meaningful
        except Exception as exc:  # noqa: BLE001 - keep parser user-friendly
            last_error = exc
    raise ValueError(f"Could not parse Statbank CSV rows. Last error: {last_error}")


def _looks_like_population_wide_export(rows: list[list[str]]) -> bool:
    joined = "\n".join(",".join(row) for row in rows[:8]).lower()
    return "population" in joined and "age total" in joined


def _looks_like_family_wide_export(rows: list[list[str]]) -> bool:
    joined = "\n".join(",".join(row) for row in rows[:8]).lower()
    return "families" in joined and "children total" in joined


def _first_index_containing(row: list[str], needle: str) -> int | None:
    needle_norm = _ascii(needle)
    for idx, cell in enumerate(row):
        if needle_norm in _ascii(cell):
            return idx
    return None


def _parse_population_wide_export(rows: list[list[str]]) -> pd.DataFrame:
    """Parse the pivot-style KKBEF8 CSV exported from the web UI.

    The manual export is hierarchical rather than tidy: one row stores the age
    columns, separate rows store current sex/quarter/citizenship, and district
    rows contain the actual values. This converts it to a normal long table.
    """
    header_idx: int | None = None
    value_start: int | None = None
    for i, row in enumerate(rows):
        idx = _first_index_containing(row, "Age total")
        if idx is not None:
            header_idx = i
            value_start = idx
            break
    if header_idx is None or value_start is None:
        raise ValueError("Could not find the AGE header row in KKBEF8 export.")

    age_labels = [cell for cell in rows[header_idx][value_start:] if cell]
    records: list[dict[str, object]] = []
    current_sex = "Sex total"
    current_quarter = ""
    current_citizenship = "Citizenship total"

    for row in rows[header_idx + 1 :]:
        non_empty = [cell for cell in row if cell.strip()]
        if not non_empty:
            continue
        district_idx = next((idx for idx, cell in enumerate(row) if "district -" in _ascii(cell)), None)
        if district_idx is not None:
            district = row[district_idx]
            values = row[district_idx + 1 : district_idx + 1 + len(age_labels)]
            for age, value in zip(age_labels, values, strict=False):
                records.append(
                    {
                        "sex": current_sex,
                        "quarter": current_quarter,
                        "citizenship": current_citizenship,
                        "district": district,
                        "age": age,
                        "number": value,
                    }
                )
            continue

        # Hierarchy rows contain exactly one meaningful value in this export.
        marker = non_empty[-1]
        marker_ascii = _ascii(marker)
        if "sex" in marker_ascii or marker_ascii in {"men", "women", "maend", "kvinder"}:
            current_sex = marker
        elif re.fullmatch(r"\d{4}q\d", marker_ascii):
            current_quarter = marker
        elif "citizenship" in marker_ascii or marker_ascii in {"denmark", "western countries", "non-western countries"}:
            current_citizenship = marker

    if not records:
        raise ValueError("No district records found in KKBEF8 export.")
    return pd.DataFrame(records)


def _parse_family_wide_export(rows: list[list[str]]) -> pd.DataFrame:
    """Parse the pivot-style KKFAM1 CSV exported from the web UI."""
    header_idx: int | None = None
    value_start: int | None = None
    for i, row in enumerate(rows):
        idx = _first_index_containing(row, "Children total")
        if idx is not None:
            header_idx = i
            value_start = idx
            break
    if header_idx is None or value_start is None:
        raise ValueError("Could not find the CHILDREN header row in KKFAM1 export.")

    children_labels = [cell for cell in rows[header_idx][value_start:] if cell]
    records: list[dict[str, object]] = []
    current_family_type = "Family type total"
    current_quarter = ""

    for row in rows[header_idx + 1 :]:
        non_empty = [cell for cell in row if cell.strip()]
        if not non_empty:
            continue
        district_idx = next((idx for idx, cell in enumerate(row) if "district -" in _ascii(cell)), None)
        if district_idx is not None:
            district = row[district_idx]
            values = row[district_idx + 1 : district_idx + 1 + len(children_labels)]
            for child_group, value in zip(children_labels, values, strict=False):
                records.append(
                    {
                        "family_type": current_family_type,
                        "quarter": current_quarter,
                        "district": district,
                        "number_of_children": child_group,
                        "number": value,
                    }
                )
            continue

        marker = non_empty[-1]
        marker_ascii = _ascii(marker)
        if "family type" in marker_ascii or "familietype" in marker_ascii:
            current_family_type = marker
        elif re.fullmatch(r"\d{4}q\d", marker_ascii):
            current_quarter = marker

    if not records:
        raise ValueError("No district records found in KKFAM1 export.")
    return pd.DataFrame(records)


def _read_statbank_csv(path: Path) -> pd.DataFrame:
    """Read KK Statistikbank CSVs from either tidy/API or wide web exports."""
    if not path.exists():
        raise FileNotFoundError(f"Missing raw demographic file: {path}")

    text = _decode_statbank_text(path)
    rows = _csv_rows_from_text(text)

    if _looks_like_population_wide_export(rows):
        return _parse_population_wide_export(rows)
    if _looks_like_family_wide_export(rows):
        return _parse_family_wide_export(rows)

    # Fallback for tidy CSV/API-like exports.
    errors: list[str] = []
    for sep in (";", ",", "\t"):
        try:
            df = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
            df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
            df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
            if len(df.columns) > 1 and len(df) > 0:
                df.columns = [_norm_col(col) for col in df.columns]
                return df
        except Exception as exc:  # noqa: BLE001 - keep parser user-friendly
            errors.append(f"sep={sep!r}: {exc}")

    raise ValueError(f"Could not parse {path}. Details: {' | '.join(errors)}")


def _find_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    candidate_set = {_norm_col(candidate) for candidate in candidates}
    for col in df.columns:
        if col in candidate_set:
            return col
    for col in df.columns:
        if any(candidate in col for candidate in candidate_set):
            return col
    return None


def _value_column(df: pd.DataFrame) -> str:
    candidates = ["number", "antal", "value", "indhold", "content", "obs_value", "data"]
    col = _find_column(df, candidates)
    if col is not None:
        return col
    numeric_cols = [col for col in df.columns if _to_number_series(df[col]).notna().mean() > 0.75]
    if not numeric_cols:
        raise ValueError("Could not find a numeric value column in demographic CSV.")
    return numeric_cols[-1]


def _to_number_series(series: pd.Series) -> pd.Series:
    """Convert Statbank number strings to numeric values without inventing data."""
    cleaned = (
        series.astype(str)
        .str.replace("\xa0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _district_column(df: pd.DataFrame) -> str:
    col = _find_column(df, ["district", "distrikt", "omrade", "område", "bydel", "area"])
    if col is None:
        raise ValueError("Could not find district/area column in demographic CSV.")
    return col


def _latest_period_filter(df: pd.DataFrame) -> pd.DataFrame:
    period_col = _find_column(df, ["quarter", "kvartal", "tid", "time", "year", "aar", "år"])
    if period_col is None:
        return df.copy()
    periods = df[period_col].dropna().astype(str)
    if periods.empty:
        return df.copy()
    latest = sorted(periods.unique())[-1]
    return df[df[period_col].astype(str) == latest].copy()


def _is_total(value: object) -> bool:
    text = _ascii(value)
    return text in TOTAL_TOKENS or text.startswith("total") or text.startswith("i alt") or text.endswith(" total") or " total" in text


def _is_age_20_34(value: object) -> bool:
    return bool(AGE_20_34_PATTERN.search(_ascii(value)))


def _is_danish_category(value: object) -> bool:
    text = _ascii(value)
    return any(token in text for token in DANISH_TOKENS)


def _is_non_danish_background(value: object) -> bool:
    text = _ascii(value)
    if _is_total(text):
        return False
    if _is_danish_category(text) and not any(marker in text for marker in ["foreign", "non", "immigrant", "descendant"]):
        return False
    return any(marker in text for marker in ["foreign", "non", "western countries", "vestlige", "ikke", "immigrant", "descendant", "udland", "indvandr", "efterkommer"])


def _filter_totals(df: pd.DataFrame, columns: list[str | None]) -> pd.DataFrame:
    output = df.copy()
    for col in columns:
        if col and col in output.columns:
            total_rows = output[col].map(_is_total)
            if total_rows.any():
                output = output[total_rows]
    return output


def build_population_features(population_raw_path: Path = DEMOGRAPHICS_POPULATION_RAW_PATH) -> pd.DataFrame:
    """Build population, young-adult share and international-background share."""
    df = _latest_period_filter(_read_statbank_csv(population_raw_path))
    value_col = _value_column(df)
    district_col = _district_column(df)
    age_col = _find_column(df, ["age", "alder", "5_ars_aldersklasser", "5_year_age_groups"])
    sex_col = _find_column(df, ["sex", "kon", "køn"])
    citizenship_col = _find_column(df, ["citizenship", "statsborgerskab", "nationality"])
    ancestry_col = _find_column(df, ["ancestry", "herkomst", "origin"])
    background_col = ancestry_col or citizenship_col

    df[value_col] = _to_number_series(df[value_col]).fillna(0)

    total_base = _filter_totals(df, [sex_col, citizenship_col, ancestry_col])
    if age_col:
        age_total_rows = total_base[age_col].map(_is_total)
        population_rows = total_base[age_total_rows] if age_total_rows.any() else total_base
    else:
        population_rows = total_base

    population = population_rows.groupby(district_col, as_index=False)[value_col].sum()
    population = population.rename(columns={district_col: "neighbourhood", value_col: "population"})
    population["neighbourhood"] = population["neighbourhood"].map(_clean_area_name)

    if age_col:
        young_rows = _filter_totals(df, [sex_col, citizenship_col, ancestry_col])
        young_rows = young_rows[young_rows[age_col].map(_is_age_20_34)]
        young = young_rows.groupby(district_col, as_index=False)[value_col].sum()
        young = young.rename(columns={district_col: "neighbourhood", value_col: "population_age_20_34"})
        young["neighbourhood"] = young["neighbourhood"].map(_clean_area_name)
    else:
        young = population[["neighbourhood"]].assign(population_age_20_34=0)

    output = population.merge(young, on="neighbourhood", how="left").fillna({"population_age_20_34": 0})
    output["share_age_20_34"] = (output["population_age_20_34"] / output["population"].replace(0, pd.NA)).fillna(0)

    if background_col:
        background_base = _filter_totals(df, [sex_col, age_col])
        non_danish = background_base[background_base[background_col].map(_is_non_danish_background)]
        if non_danish.empty and citizenship_col:
            citizenship_base = _filter_totals(df, [sex_col, age_col])
            total_by_district = citizenship_base[citizenship_base[citizenship_col].map(_is_total)].groupby(district_col)[value_col].sum()
            danish_by_district = citizenship_base[citizenship_base[citizenship_col].map(_is_danish_category)].groupby(district_col)[value_col].sum()
            international = (total_by_district - danish_by_district).clip(lower=0).reset_index()
            international = international.rename(columns={district_col: "neighbourhood", value_col: "population_international_background"})
            international["neighbourhood"] = international["neighbourhood"].map(_clean_area_name)
        else:
            international = non_danish.groupby(district_col, as_index=False)[value_col].sum()
            international = international.rename(columns={district_col: "neighbourhood", value_col: "population_international_background"})
            international["neighbourhood"] = international["neighbourhood"].map(_clean_area_name)
    else:
        international = output[["neighbourhood"]].assign(population_international_background=0)

    output = output.merge(international, on="neighbourhood", how="left").fillna({"population_international_background": 0})
    output["share_international_background"] = (
        output["population_international_background"] / output["population"].replace(0, pd.NA)
    ).fillna(0)
    return output


def _has_children(value: object) -> bool:
    text = _ascii(value)
    if _is_total(text):
        return False
    if any(token in text for token in NO_CHILDREN_TOKENS):
        return False
    return bool(re.search(r"[1-9]", text)) or any(token in text for token in ["children", "born", "børn", "with children"])


def build_family_features(family_raw_path: Path = DEMOGRAPHICS_FAMILY_RAW_PATH) -> pd.DataFrame:
    """Build family-with-children share by district."""
    df = _latest_period_filter(_read_statbank_csv(family_raw_path))
    value_col = _value_column(df)
    district_col = _district_column(df)
    family_type_col = _find_column(df, ["family_type", "familietype"])
    children_col = _find_column(df, ["number_of_children", "antal_born", "antal_børn", "children"])

    df[value_col] = _to_number_series(df[value_col]).fillna(0)
    total_base = _filter_totals(df, [family_type_col])

    if children_col:
        total_children_rows = total_base[children_col].map(_is_total)
        denominator_rows = total_base[total_children_rows] if total_children_rows.any() else total_base
        numerator_rows = total_base[total_base[children_col].map(_has_children)]
    else:
        denominator_rows = total_base
        numerator_rows = total_base[total_base.astype(str).agg(" ".join, axis=1).map(_has_children)]

    denominator = denominator_rows.groupby(district_col, as_index=False)[value_col].sum()
    numerator = numerator_rows.groupby(district_col, as_index=False)[value_col].sum()
    denominator = denominator.rename(columns={district_col: "neighbourhood", value_col: "families_total"})
    numerator = numerator.rename(columns={district_col: "neighbourhood", value_col: "families_with_children"})
    denominator["neighbourhood"] = denominator["neighbourhood"].map(_clean_area_name)
    numerator["neighbourhood"] = numerator["neighbourhood"].map(_clean_area_name)
    output = denominator.merge(numerator, on="neighbourhood", how="left").fillna({"families_with_children": 0})
    output["share_families_with_children"] = (
        output["families_with_children"] / output["families_total"].replace(0, pd.NA)
    ).fillna(0)
    return output


def build_demographic_features(
    population_raw_path: Path = DEMOGRAPHICS_POPULATION_RAW_PATH,
    family_raw_path: Path = DEMOGRAPHICS_FAMILY_RAW_PATH,
    output_path: Path = DEMOGRAPHICS_FEATURES_PATH,
) -> pd.DataFrame:
    """Build the final demographic feature table used by the OSM pipeline."""
    population = build_population_features(population_raw_path)
    families = build_family_features(family_raw_path)
    output = population.merge(families, on="neighbourhood", how="left")
    output["share_families_with_children"] = output["share_families_with_children"].fillna(0)
    output["demographic_source"] = "KK Statistikbank"
    output["data_mode"] = "official_demographics"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Copenhagen demographic features from cached KK Statistikbank CSVs.")
    parser.add_argument("--population", type=Path, default=DEMOGRAPHICS_POPULATION_RAW_PATH)
    parser.add_argument("--families", type=Path, default=DEMOGRAPHICS_FAMILY_RAW_PATH)
    parser.add_argument("--output", type=Path, default=DEMOGRAPHICS_FEATURES_PATH)
    args = parser.parse_args(argv)

    df = build_demographic_features(args.population, args.families, args.output)
    print(f"Wrote demographic features to {args.output}")
    print(f"Rows: {len(df):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
