"""Load, clean, and feature-engineer the NASA POWER solar dataset.

This module is config-independent (no lookback/horizon/split here) — its
output is cached once and reused by every experiment (see windows.py for the
per-experiment windowing/split step).
"""
import numpy as np
import pandas as pd

from merve_solar.config import (
    CITIES,
    CITY_TO_ID,
    EXPECTED_TRIMMED_ROWS_PER_SHEET,
    LAST_VALID_TIMESTAMP,
    MISSING_SENTINEL,
    RAW_XLSX_PATH,
)


def _build_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    date_parts = pd.DataFrame(
        {
            "year": df["YEAR"],
            "month": df["MO"],
            "day": df["DY"],
            "hour": df["HR"],
        }
    )
    df["datetime"] = pd.to_datetime(date_parts)
    return df.sort_values("datetime").reset_index(drop=True)


def _add_cyclical_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour_sin"] = np.sin(2 * np.pi * df["HR"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["HR"] / 24)
    doy = df["datetime"].dt.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    for wd_col in ["WD10M", "WD50M"]:
        radians = np.deg2rad(df[wd_col])
        df[f"{wd_col}_sin"] = np.sin(radians)
        df[f"{wd_col}_cos"] = np.cos(radians)
    return df


def load_city_sheet(city: str) -> pd.DataFrame:
    """Load, trim, and feature-engineer a single city's sheet."""
    df = pd.read_excel(RAW_XLSX_PATH, sheet_name=city, engine="openpyxl")
    df = _build_datetime_index(df)

    before = len(df)
    df = df[df["datetime"] <= pd.Timestamp(LAST_VALID_TIMESTAMP)].reset_index(drop=True)
    removed = before - len(df)
    if removed != EXPECTED_TRIMMED_ROWS_PER_SHEET:
        raise ValueError(
            f"{city}: expected to trim exactly {EXPECTED_TRIMMED_ROWS_PER_SHEET} rows "
            f"(NASA POWER's near-real-time -999 tail), got {removed}. "
            "The source file's missing-data gap may have changed."
        )

    df = df.drop(columns=["ALLSKY_KT"])  # ~50% -999 at night (undefined), drop before the sentinel check below

    if (df.drop(columns=["datetime"]) == MISSING_SENTINEL).any().any():
        raise ValueError(f"{city}: -999 sentinel remains after trimming.")
    if df.isnull().any().any():
        raise ValueError(f"{city}: NaN values present after trimming.")
    df = _add_cyclical_features(df)
    df["city"] = city
    df["city_id"] = CITY_TO_ID[city]
    return df


def load_all_cities() -> pd.DataFrame:
    """Load and clean all 5 city sheets, concatenated (city identity preserved)."""
    frames = [load_city_sheet(city) for city in CITIES]
    return pd.concat(frames, ignore_index=True)


def save_base_features(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_base_features(path) -> pd.DataFrame:
    return pd.read_parquet(path)
