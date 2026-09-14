"""Load, clean, and feature-engineer the NASA POWER solar dataset.

This module is config-independent (no lookback/horizon/split here) — its
output is cached once and reused by every experiment (see windows.py for the
per-experiment windowing/split step).
"""
import numpy as np
import pandas as pd

from merve_solar.clearsky import CLEARSKY_COLUMN, load_clearsky_reference
from merve_solar.config import (
    CIRCULAR_COLUMNS,
    CITIES,
    CITY_TO_ID,
    DROPPED_COLUMNS,
    EXPECTED_TRIMMED_ROWS_PER_SHEET,
    IRRADIANCE_COLUMNS_MJ,
    MASK_COLUMNS,
    LAST_VALID_TIMESTAMP,
    MISSING_SENTINEL,
    MJ_M2_HOUR_TO_W_M2,
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
    for wd_col in CIRCULAR_COLUMNS:
        radians = np.deg2rad(df[wd_col])
        df[f"{wd_col}_sin"] = np.sin(radians)
        df[f"{wd_col}_cos"] = np.cos(radians)
    return df


def _to_w_per_m2(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the export's MJ/m^2/hour irradiance columns to W/m^2.

    The 14-Sep-2026 export uses NASA POWER's default hourly units; the whole project, the
    reference paper and the irradiance literature are in W/m^2. The conversion is exact and
    linear (see MJ_M2_HOUR_TO_W_M2 in config.py); it is applied BEFORE the sentinel check so
    that -999 is still recognisable, hence the explicit mask.
    """
    df = df.copy()
    for col in IRRADIANCE_COLUMNS_MJ:
        if col not in df.columns:
            raise ValueError(f"irradiance column {col!r} is not in the sheet.")
        valid = df[col] != MISSING_SENTINEL
        df.loc[valid, col] = df.loc[valid, col] * MJ_M2_HOUR_TO_W_M2
    return df


def load_city_sheet(city: str) -> pd.DataFrame:
    """Load, trim, unit-convert, and feature-engineer a single city's sheet."""
    df = pd.read_excel(RAW_XLSX_PATH, sheet_name=city, engine="openpyxl")
    df = _to_w_per_m2(df)
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

    # Columns are dropped here rather than deleted from the xlsx, so the source file stays
    # the untouched NASA POWER export. Anything dropped must go before the sentinel check
    # below. DROPPED_COLUMNS is currently empty -- see config.py.
    missing = [col for col in DROPPED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{city}: expected columns are not in the sheet: {missing}")
    df = df.drop(columns=list(DROPPED_COLUMNS))

    # MASK_COLUMNS are metadata, never features (see config.py). CLRSKY_SFC_SW_DWN is no
    # longer exported, so it is merged in from the reconstruction rather than read; without
    # it there is no daylight subset and no night clamp.
    reference = load_clearsky_reference()
    df = df.merge(
        reference.loc[reference["city"] == city, ["datetime", CLEARSKY_COLUMN]],
        on="datetime", how="left", validate="one_to_one",
    )
    if df[CLEARSKY_COLUMN].isna().any():
        raise ValueError(
            f"{city}: clear-sky reference does not cover {int(df[CLEARSKY_COLUMN].isna().sum())} "
            "hours of the trimmed record."
        )
    absent = [col for col in MASK_COLUMNS if col not in df.columns]
    if absent:
        raise ValueError(f"{city}: mask columns missing after the merge: {absent}")

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
