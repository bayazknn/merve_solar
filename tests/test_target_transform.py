"""Regressing the clearness index instead of the irradiance itself.

The naive baselines get the target hour's clear-sky envelope for free -- smart persistence
multiplies the carried-forward kt by CLRSKY(t+h), the climatology cell memorises the same
geometry -- and the model was denied it, which is the leading explanation for losing daylight
MAE in four of five provinces (ABLATION.md 3.6). This axis hands the model the same geometry
without making CLRSKY a feature: it learns the attenuation, the transform supplies the envelope.

CLRSKY is pure astronomy with no weather term, so this is not leakage. What these tests protect
is that "raw" is untouched, that the round trip is exact, and that night stays exactly zero.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar.config import (
    DAYLIGHT_REFERENCE_COLUMN,
    TARGET_COLUMN,
    TARGET_TRANSFORMS,
    ExperimentConfig,
)
from merve_solar.experiment import (
    LEDGER_COLUMNS,
    apply_target_transform,
    invert_target_transform,
)


def _frame():
    """Night, twilight (the smallest clear-sky values in the real frame are ~2.4 W/m^2), noon."""
    clear = np.array([0.0, 0.0, 2.4, 120.0, 800.0, 900.0], dtype=np.float32)
    allsky = np.array([0.0, 0.0, 1.2, 60.0, 720.0, 450.0], dtype=np.float32)
    return pd.DataFrame({TARGET_COLUMN: allsky, DAYLIGHT_REFERENCE_COLUMN: clear,
                         "city": ["Ankara"] * 6})


def test_raw_returns_the_same_object_untouched():
    """The default path must allocate nothing and change nothing -- 106 ledger rows depend on it."""
    df = _frame()
    assert apply_target_transform(df, ExperimentConfig(experiment_id="x")) is df


def test_the_index_is_the_ratio_where_the_sun_is_up():
    out = apply_target_transform(_frame(), ExperimentConfig(experiment_id="x",
                                                           target_transform="clearsky_index"))
    assert out[TARGET_COLUMN].to_numpy() == pytest.approx([0.0, 0.0, 0.5, 0.5, 0.9, 0.5])


def test_night_is_zero_rather_than_a_division_by_zero():
    out = apply_target_transform(_frame(), ExperimentConfig(experiment_id="x",
                                                            target_transform="clearsky_index"))
    assert np.isfinite(out[TARGET_COLUMN].to_numpy()).all()
    assert (out[TARGET_COLUMN].to_numpy()[:2] == 0.0).all()


def test_the_source_frame_is_not_mutated():
    """A scope runner and the layout pass read the same base_df; an in-place edit would corrupt
    the canonical W/m^2 ground truth the run is scored against."""
    df = _frame()
    before = df[TARGET_COLUMN].to_numpy().copy()
    apply_target_transform(df, ExperimentConfig(experiment_id="x", target_transform="clearsky_index"))
    assert (df[TARGET_COLUMN].to_numpy() == before).all()


def test_the_round_trip_reproduces_the_irradiance():
    """apply then invert is the identity on the target, which is the whole correctness claim."""
    df = _frame()
    cfg = ExperimentConfig(experiment_id="x", target_transform="clearsky_index")
    kt = apply_target_transform(df, cfg)[TARGET_COLUMN].to_numpy()
    pooled = np.tile(kt.reshape(1, 2, 3), (4, 1, 1)).astype(np.float32)
    clear = df[DAYLIGHT_REFERENCE_COLUMN].to_numpy().reshape(2, 3)
    back = invert_target_transform(pooled, cfg, clear)
    assert back[0] == pytest.approx(df[TARGET_COLUMN].to_numpy().reshape(2, 3))


def test_inverting_raw_leaves_the_predictions_alone():
    pooled = np.arange(24, dtype=np.float32).reshape(2, 4, 3)
    out = invert_target_transform(pooled.copy(), ExperimentConfig(experiment_id="x"),
                                  np.zeros((4, 3), dtype=np.float32))
    assert (out == pooled).all()


def test_night_output_is_exactly_zero_before_any_clamping():
    """CLRSKY = 0 makes the product exactly 0, so clamp_night_to_zero becomes a no-op rather
    than a correction. That is a stronger physical statement, and worth pinning."""
    cfg = ExperimentConfig(experiment_id="x", target_transform="clearsky_index")
    pooled = np.full((3, 2, 2), 7.5, dtype=np.float32)
    clear = np.array([[0.0, 500.0], [0.0, 0.0]], dtype=np.float32)
    out = invert_target_transform(pooled, cfg, clear)
    assert (out[:, clear == 0] == 0.0).all()


def test_a_mis_shaped_clear_sky_array_raises_rather_than_broadcasting():
    """(N, horizon) against (horizon,) would broadcast silently and score a scrambled run."""
    cfg = ExperimentConfig(experiment_id="x", target_transform="clearsky_index")
    with pytest.raises(ValueError, match="clear-sky array"):
        invert_target_transform(np.ones((2, 4, 3), dtype=np.float32), cfg,
                                np.ones((3,), dtype=np.float32))


def test_a_typo_fails_at_config_load_not_three_hours_into_a_sweep():
    with pytest.raises(ValueError, match="target_transform"):
        ExperimentConfig(experiment_id="x", target_transform="clear_sky_index")


def test_the_axis_is_visible_in_the_ledger():
    assert "target_transform" in LEDGER_COLUMNS
    assert TARGET_TRANSFORMS == ("raw", "clearsky_index")
