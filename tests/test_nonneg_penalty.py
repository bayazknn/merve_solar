"""The non-negativity penalty acts at 0 W/m^2, not at the scaled zero (the training mean).

The network predicts SCALED irradiance, whose zero is the training-period mean (~198 W/m^2).
Applying relu(-pred) there penalised every forecast below the mean, nights included, and biased
low forecasts upward; these tests pin the penalty to the physical boundary instead.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest
import torch

from merve_solar.config import NUMERIC_FEATURE_COLUMNS, TARGET_COLUMN, ExperimentConfig
from merve_solar.experiment import LEDGER_COLUMNS, _ledger_row
from merve_solar.scaling import fit_scaler, scaled_target_zero
from merve_solar.train import NONNEG_PENALTY_FLOOR, nonneg_penalty


def _scaler(target_values):
    n = len(target_values)
    df = pd.DataFrame({c: np.linspace(0.0, 1.0, n) for c in NUMERIC_FEATURE_COLUMNS})
    df[TARGET_COLUMN] = target_values
    df["datetime"] = pd.date_range("2020-01-01", periods=n, freq="h")
    return fit_scaler(df, df["datetime"].iloc[-1])


def _to_scaled(scaler, wm2):
    i = NUMERIC_FEATURE_COLUMNS.index(TARGET_COLUMN)
    return (np.asarray(wm2, dtype=np.float64) - scaler.mean_[i]) / scaler.scale_[i]


def test_scaled_target_zero_is_where_zero_irradiance_lands():
    scaler = _scaler(np.array([0.0, 0.0, 200.0, 600.0]))
    assert scaled_target_zero(scaler) == pytest.approx(_to_scaled(scaler, 0.0))
    assert scaled_target_zero(scaler) < 0  # the mean is positive, so 0 W/m^2 is below it


def test_no_penalty_on_any_non_negative_forecast_including_below_the_mean():
    """The bug: forecasts between 0 W/m^2 and the training mean used to be penalised."""
    scaler = _scaler(np.array([0.0, 0.0, 200.0, 600.0]))  # mean 200 W/m^2
    pred = torch.tensor(_to_scaled(scaler, [0.0, 50.0, 199.0, 800.0]), dtype=torch.float32)
    assert nonneg_penalty(pred, scaled_target_zero(scaler)).item() == pytest.approx(0.0, abs=1e-10)


def test_negative_forecasts_pay_the_squared_shortfall_below_zero_wm2():
    scaler = _scaler(np.array([0.0, 0.0, 200.0, 600.0]))
    std = scaler.scale_[NUMERIC_FEATURE_COLUMNS.index(TARGET_COLUMN)]
    pred = torch.tensor(_to_scaled(scaler, [-50.0, 300.0]), dtype=torch.float32)
    expected = ((50.0 / std) ** 2 + 0.0) / 2
    assert nonneg_penalty(pred, scaled_target_zero(scaler)).item() == pytest.approx(expected, rel=1e-5)


def test_the_ledger_records_where_the_penalty_acts():
    assert "nonneg_penalty_floor" in LEDGER_COLUMNS
    block = {k: 1.0 for k in ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC",
                              "CRPS", "n_samples", "n_elements")}
    subsets = {"all_hours": {"aggregate": block}, "daylight": {"aggregate": block}}
    lstm = _ledger_row(ExperimentConfig(experiment_id="x"), subsets, {}, 1.0)
    assert lstm["nonneg_penalty_floor"] == NONNEG_PENALTY_FLOOR == "0_wm2"
    naive = _ledger_row(ExperimentConfig(experiment_id="y", model_family="persistence"), subsets, {}, 1.0)
    assert naive["nonneg_penalty_floor"] == "n/a"
