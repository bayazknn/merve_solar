"""The `loss_function` axis: which criterion the point forecaster is fitted with.

Asserted on the criterion object, not on a metric: MAE going down on one seed is consistent
with L1 training and also with a lucky draw, so only the criterion itself is evidence that the
config field is wired to anything.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
import torch
import torch.nn as nn

from merve_solar.config import LOSS_FUNCTIONS, ExperimentConfig
from merve_solar.train import fit_loss, make_criterion, nonneg_penalty


def test_default_is_still_mse():
    """Every existing ledger row was produced under MSE and does not record the axis."""
    assert ExperimentConfig(experiment_id="x").loss_function == "mse"
    assert isinstance(make_criterion(ExperimentConfig(experiment_id="x")), nn.MSELoss)


def test_mae_selects_l1_loss():
    config = ExperimentConfig(experiment_id="x", loss_function="mae")
    assert isinstance(make_criterion(config), nn.L1Loss)


def test_every_declared_loss_function_is_constructible():
    for name in LOSS_FUNCTIONS:
        assert isinstance(make_criterion(ExperimentConfig(experiment_id="x", loss_function=name)),
                          nn.Module)


def test_unknown_loss_function_is_rejected_at_config_time():
    with pytest.raises(ValueError, match="loss_function must be one of"):
        ExperimentConfig(experiment_id="x", loss_function="huber")


def test_the_nonneg_penalty_is_unchanged_by_the_criterion():
    """The physics constraint is a separate term and must not move with the fit criterion."""
    pred = torch.tensor([[-2.0, 1.0]])
    y = torch.zeros_like(pred)
    penalty = nonneg_penalty(pred)
    assert penalty.item() == pytest.approx(2.0)  # mean of relu(-pred)^2 = (4 + 0) / 2

    # Criteria are element-wise now (so the daylight mask can be applied), so go through
    # fit_loss -- the path the training loop actually takes.
    all_daylight = torch.ones_like(pred, dtype=torch.bool)
    weight = 0.1
    for loss_function, expected_fit in (("mse", 2.5), ("mae", 1.5)):
        criterion = make_criterion(ExperimentConfig(experiment_id="x", loss_function=loss_function))
        fit = fit_loss(criterion, pred, y, all_daylight, False)
        assert (fit + weight * penalty).item() == pytest.approx(expected_fit + 0.2)
