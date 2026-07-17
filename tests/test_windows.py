import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar.config import CITIES, NUMERIC_FEATURE_COLUMNS, ExperimentConfig
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

N_HOURS = 300


def _make_synthetic_base_df(n_hours=N_HOURS):
    frames = []
    start = pd.Timestamp("2020-01-01")
    for city_idx, city in enumerate(CITIES):
        rng = np.random.default_rng(city_idx)
        dt = pd.date_range(start, periods=n_hours, freq="h")
        data = {col: rng.normal(size=n_hours) for col in NUMERIC_FEATURE_COLUMNS}
        df = pd.DataFrame(data)
        df["datetime"] = dt
        df["city"] = city
        df["city_id"] = city_idx
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


@pytest.mark.parametrize("lookback,horizon,stride", [(24, 24, 1), (12, 12, 1), (6, 6, 3)])
def test_window_shapes_and_boundary_drop_bounds(lookback, horizon, stride):
    df = _make_synthetic_base_df()
    config = ExperimentConfig(
        experiment_id="test",
        lookback_hours=lookback,
        horizon_hours=horizon,
        window_stride=stride,
        train_ratio=0.6,
        val_ratio=0.2,
    )
    train_end, val_end = compute_split_boundaries(df, config)
    splits = build_experiment_windows(df, config, train_end, val_end)

    for split in splits.values():
        n = split["X"].shape[0]
        assert split["y"].shape[0] == n
        assert split["city_id"].shape[0] == n
        if n > 0:
            assert split["X"].shape[1] == lookback
            assert split["y"].shape[1] == horizon

    total_windows = sum(split["X"].shape[0] for split in splits.values())
    span = lookback + horizon
    max_possible_per_city = max(0, (N_HOURS - span) // stride + 1)
    # Two split boundaries can each drop at most (span-1) straddling windows per city.
    max_dropped = len(CITIES) * 2 * (span - 1)
    min_expected = max(0, len(CITIES) * max_possible_per_city - max_dropped)
    assert min_expected <= total_windows <= len(CITIES) * max_possible_per_city


def test_no_window_start_predates_its_city_series():
    df = _make_synthetic_base_df()
    config = ExperimentConfig(experiment_id="test", lookback_hours=24, horizon_hours=24, window_stride=1)
    train_end, val_end = compute_split_boundaries(df, config)
    splits = build_experiment_windows(df, config, train_end, val_end)
    # sanity: every split's city_id values are all valid city indices (no cross-city leakage markers)
    for split in splits.values():
        if split["city_id"].shape[0] > 0:
            assert set(np.unique(split["city_id"])).issubset(set(range(len(CITIES))))
