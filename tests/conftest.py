import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar.config import CITIES, DAYLIGHT_REFERENCE_COLUMN, NUMERIC_FEATURE_COLUMNS

N_HOURS = 300


def make_synthetic_base_df(n_hours: int = N_HOURS) -> pd.DataFrame:
    """A frame with the same columns the real pipeline sees, cheap enough for unit tests.

    The clear-sky column carries a real diurnal shape rather than noise: it defines the
    daylight mask, so a test frame where every hour is daylight would not exercise it.
    """
    frames = []
    start = pd.Timestamp("2020-01-01")
    for city_idx, city in enumerate(CITIES):
        rng = np.random.default_rng(city_idx)
        dt = pd.date_range(start, periods=n_hours, freq="h")
        df = pd.DataFrame({col: rng.normal(size=n_hours) for col in NUMERIC_FEATURE_COLUMNS})
        df["datetime"] = dt
        # Sun up between 06:00 and 17:00; zero otherwise, as NASA POWER reports it.
        hour = dt.hour.to_numpy()
        df[DAYLIGHT_REFERENCE_COLUMN] = np.where(
            (hour >= 6) & (hour <= 17), 100 + 700 * np.sin(np.pi * (hour - 6) / 11), 0.0
        )
        df["city"] = city
        df["city_id"] = city_idx
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


@pytest.fixture
def synthetic_base_df() -> pd.DataFrame:
    return make_synthetic_base_df()
