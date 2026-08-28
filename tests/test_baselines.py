"""The naive reference floors: climatology, persistence, smart persistence.

These rows are what the LSTM has to beat, so an unfair advantage here is worse than a bug --
it silently lowers the bar the paper clears.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pytest

from merve_solar.baselines import build_baseline_predictions
from merve_solar.config import ExperimentConfig
from merve_solar.windows import compute_split_boundaries


def _config(**kw):
    return ExperimentConfig(
        experiment_id="t", lookback_hours=6, horizon_hours=6, train_ratio=0.6, val_ratio=0.2, **kw
    )


def _build(base_df, config):
    # add_baseline_columns groups climatology on (city, MO, HR); the synthetic fixture carries
    # only `datetime`, so derive them here rather than widening the fixture for one caller.
    df = base_df.assign(MO=base_df["datetime"].dt.month, HR=base_df["datetime"].dt.hour)
    train_end, val_end = compute_split_boundaries(df, config)
    return build_baseline_predictions(df, config, train_end, val_end)


def test_night_is_clamped_when_the_config_says_it_is(synthetic_base_df):
    """The ledger records clamp_night_to_zero for these rows either way.

    Skipping the clamp here made the column describe something the run had not done, and left
    the baselines' all-hours numbers not comparable with the LSTM arms', which are clamped in
    experiment.py. The synthetic target is noise, so night predictions are nonzero unless
    something clamps them.
    """
    built = _build(synthetic_base_df, _config())
    night = ~built["layout"]["daylight"]
    assert night.any(), "the fixture must contain night hours or this proves nothing"
    for name, preds in built["predictions"].items():
        assert not preds[:, night].any(), f"{name} left nonzero predictions below the horizon"


def test_daylight_predictions_are_untouched_by_the_clamp(synthetic_base_df):
    """The clamp must be a night-only operation; a daylight change would be fitting, not physics."""
    clamped = _build(synthetic_base_df, _config())
    as_is = _build(synthetic_base_df, _config(clamp_night_to_zero=False))
    daylight = clamped["layout"]["daylight"]
    for name in clamped["predictions"]:
        np.testing.assert_array_equal(
            clamped["predictions"][name][:, daylight], as_is["predictions"][name][:, daylight]
        )


def test_the_clamp_is_opt_out(synthetic_base_df):
    """Off, at least one baseline must predict something nonzero at night, or the test above
    would pass for the wrong reason."""
    built = _build(synthetic_base_df, _config(clamp_night_to_zero=False))
    night = ~built["layout"]["daylight"]
    assert any(preds[:, night].any() for preds in built["predictions"].values())


def test_every_arm_is_scored_on_exactly_the_same_windows(synthetic_base_df):
    """Windows undefined for any one baseline are dropped from all of them together."""
    built = _build(synthetic_base_df, _config())
    n_windows = built["layout"]["y"].shape[0]
    assert n_windows > 0
    for name, preds in built["predictions"].items():
        assert preds.shape == (1, n_windows, 6), name
        assert not np.isnan(preds).any(), f"{name} carries an undefined prediction"
