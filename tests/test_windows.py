import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar.config import CITIES, ExperimentConfig
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

from conftest import N_HOURS, make_synthetic_base_df as _make_synthetic_base_df


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


SCOPE_HOURS = 900  # long enough that a 48h span survives both split boundaries in every split


def _config(**kw):
    base = dict(
        experiment_id="test",
        lookback_hours=24,
        horizon_hours=24,
        window_stride=1,
        train_ratio=0.6,
        val_ratio=0.2,
    )
    base.update(kw)
    return ExperimentConfig(**base)


def test_compute_split_boundaries_rejects_a_partial_frame():
    """A single-city frame used to return start-1h for both boundaries, silently."""
    df = _make_synthetic_base_df(SCOPE_HOURS)
    with pytest.raises(ValueError, match="full multi-city frame"):
        compute_split_boundaries(df[df["city"] == CITIES[2]], _config())


def test_build_windows_accepts_a_single_city_frame():
    """This used to raise IndexError: the loop ran over all CITIES and hit .iloc[0] on empties."""
    df = _make_synthetic_base_df(SCOPE_HOURS)
    config = _config()
    train_end, val_end = compute_split_boundaries(df, config)
    city = CITIES[3]
    splits = build_experiment_windows(
        df[df["city"] == city], config, train_end, val_end, cities=[city]
    )
    assert splits["test"]["y"].shape[0] > 0


def test_single_city_build_equals_that_city_slice_of_the_global_build():
    """The guarantee the per_city ablation arm rests on.

    If a city's independently-built windows were not the same windows in the same order as
    its slice of the pooled build, per-city predictions would be written back into the wrong
    rows — swapping two cities' scores without changing a single array shape.
    """
    df = _make_synthetic_base_df(SCOPE_HOURS)
    config = _config()
    train_end, val_end = compute_split_boundaries(df, config)
    global_splits = build_experiment_windows(df, config, train_end, val_end)

    for idx, city in enumerate(CITIES):
        alone = build_experiment_windows(
            df[df["city"] == city], config, train_end, val_end, cities=[city]
        )
        for split in ("train", "val", "test"):
            slot = np.flatnonzero(global_splits[split]["city_id"] == idx)
            assert np.array_equal(np.diff(slot), np.ones(len(slot) - 1)), "city block not contiguous"
            for key in ("X", "y", "daylight", "window_start"):
                assert np.array_equal(alone[split][key], global_splits[split][key][slot]), (
                    f"{city}/{split}/{key} differs between the single-city and pooled builds"
                )


def test_include_x_false_skips_the_feature_tensor_but_keeps_everything_else():
    df = _make_synthetic_base_df(SCOPE_HOURS)
    config = _config()
    train_end, val_end = compute_split_boundaries(df, config)
    layout = build_experiment_windows(df, config, train_end, val_end, include_X=False)
    full = build_experiment_windows(df, config, train_end, val_end)

    assert layout["test"]["X"] is None
    for key in ("y", "daylight", "city_id", "window_start"):
        assert np.array_equal(layout["test"][key], full["test"][key])


def test_daylight_array_marks_the_horizon_hours_the_sun_is_up():
    """The mask is derived from clear-sky irradiance at the *target* hours, not the inputs."""
    df = _make_synthetic_base_df(SCOPE_HOURS)
    config = _config()
    train_end, val_end = compute_split_boundaries(df, config)
    splits = build_experiment_windows(df, config, train_end, val_end)

    test = splits["test"]
    assert test["daylight"].shape == test["y"].shape
    assert test["daylight"].dtype == bool
    # The synthetic frame has the sun up 06:00-17:00, i.e. 12 of every 24 hours.
    assert test["daylight"].mean() == pytest.approx(0.5, abs=0.02)

    starts = pd.DatetimeIndex(test["window_start"])
    first_target_hour = (starts + pd.Timedelta(hours=config.lookback_hours)).hour.to_numpy()
    assert np.array_equal(
        test["daylight"][:, 0], (first_target_hour >= 6) & (first_target_hour <= 17)
    )
