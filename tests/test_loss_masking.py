import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import torch
import torch.nn as nn

from merve_solar.bootstrap import resample_train_split
from merve_solar.config import ExperimentConfig
from merve_solar.datasets import make_dataloader
from merve_solar.train import fit_loss, make_criterion


def _config(**kw):
    return ExperimentConfig(experiment_id="t", **kw)


def test_criterion_is_elementwise_so_the_mask_can_be_applied():
    assert make_criterion(_config()).reduction == "none"
    assert isinstance(make_criterion(_config(loss_function="mae")), nn.L1Loss)


def test_unmasked_loss_is_the_plain_mean():
    pred = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
    target = torch.zeros_like(pred)
    daylight = torch.tensor([[True, False], [False, True]])
    criterion = make_criterion(_config(loss_function="mae"))
    assert fit_loss(criterion, pred, target, daylight, False).item() == 2.5  # (1+2+3+4)/4


def test_masked_loss_uses_only_the_selected_elements():
    """The flag has to change the number, or it is a ledger column that lies."""
    pred = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
    target = torch.zeros_like(pred)
    daylight = torch.tensor([[True, False], [False, True]])
    criterion = make_criterion(_config(loss_function="mae"))
    assert fit_loss(criterion, pred, target, daylight, True).item() == 2.5  # (1+4)/2
    other = torch.tensor([[False, True], [True, False]])
    assert fit_loss(criterion, pred, target, other, True).item() == 2.5  # (2+3)/2
    assert fit_loss(criterion, pred, target, torch.tensor([[True, False], [False, False]]), True).item() == 1.0


def test_a_batch_with_no_daylight_returns_none_rather_than_nan():
    pred = torch.ones(2, 2)
    criterion = make_criterion(_config())
    assert fit_loss(criterion, pred, torch.zeros(2, 2), torch.zeros(2, 2, dtype=torch.bool), True) is None


def test_dataloader_defaults_the_mask_to_all_true():
    """So the masked and unmasked paths stay one code path."""
    loader = make_dataloader(np.zeros((4, 3, 2), np.float32), np.zeros((4, 5), np.float32),
                             np.zeros(4, np.int64), batch_size=4, shuffle=False)
    _, _, _, daylight = next(iter(loader))
    assert daylight.shape == (4, 5) and daylight.all()


def test_bootstrap_resample_carries_the_daylight_mask():
    """Without this, a masked loss would see a stale mask against resampled windows."""
    n = 40
    train = {
        "X": np.arange(n * 2, dtype=np.float32).reshape(n, 2, 1),
        "y": np.arange(n, dtype=np.float32).reshape(n, 1),
        "daylight": (np.arange(n) % 2 == 0).reshape(n, 1),
        "city_id": np.zeros(n, dtype=np.int64),
    }
    out = resample_train_split(train, 8, np.random.default_rng(0))
    assert "daylight" in out
    assert out["daylight"].shape == out["y"].shape
    # The mask must still belong to the window it was resampled with.
    assert np.array_equal(out["daylight"][:, 0], (out["y"][:, 0].astype(int) % 2 == 0))
