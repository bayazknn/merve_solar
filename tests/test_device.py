"""Which backend a run used, and the fact that the ledger now records it.

Reproducibility here is per-device: MPS, CUDA and CPU do not agree bitwise. Before the `device`
column the ledger could not tell them apart, so a multi-seed mean +- sd could silently average
across backends and nothing in the paper's table would show it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

import merve_solar.experiment as experiment_module
from merve_solar.config import ExperimentConfig
from merve_solar.experiment import LEDGER_COLUMNS, _append_ledger_row, _ledger_row
from merve_solar.utils import VALID_DEVICES, get_device

METRIC_KEYS = ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
               "n_samples", "n_elements")


def _fake_subsets():
    block = {k: 1.0 for k in METRIC_KEYS}
    return {"all_hours": {"aggregate": dict(block)}, "daylight": {"aggregate": dict(block)}}


def test_merve_device_overrides_the_automatic_choice(monkeypatch):
    """The point of the override: pin a run to the backend its sibling seeds used."""
    for device in VALID_DEVICES:
        monkeypatch.setenv("MERVE_DEVICE", device)
        assert get_device() == device


def test_the_override_is_case_and_whitespace_forgiving(monkeypatch):
    monkeypatch.setenv("MERVE_DEVICE", "  CPU ")
    assert get_device() == "cpu"


def test_an_unknown_device_is_rejected_rather_than_ignored(monkeypatch):
    """Silently falling back would hand back a run on the very backend the caller ruled out."""
    monkeypatch.setenv("MERVE_DEVICE", "gpu")
    with pytest.raises(ValueError, match="MERVE_DEVICE must be one of"):
        get_device()


def test_an_empty_override_falls_back_to_the_automatic_choice(monkeypatch):
    """An exported-but-empty variable is not a choice; it must not raise."""
    monkeypatch.setenv("MERVE_DEVICE", "")
    assert get_device() in VALID_DEVICES


def test_no_override_still_returns_a_real_device(monkeypatch):
    monkeypatch.delenv("MERVE_DEVICE", raising=False)
    assert get_device() in VALID_DEVICES


def test_device_is_part_of_the_declared_schema():
    assert "device" in LEDGER_COLUMNS


def test_the_device_reaches_the_ledger_row():
    row = _ledger_row(
        ExperimentConfig(experiment_id="x"), _fake_subsets(),
        {"hit_max_epochs": 0, "n_models": 1, "device": "mps"}, 1.0,
    )
    assert row["device"] == "mps"
    assert tuple(row) == LEDGER_COLUMNS


def test_a_row_built_without_a_device_says_so_loudly():
    """Blank would read as 'CPU, probably'. 'unknown' is greppable and obviously wrong."""
    row = _ledger_row(ExperimentConfig(experiment_id="x"), _fake_subsets(), {}, 1.0)
    assert row["device"] == "unknown"


def test_two_seeds_on_different_backends_are_distinguishable_in_the_table(tmp_path, monkeypatch):
    """The regression test for the hole: same arm, same id shape, different backend."""
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", tmp_path / "ledger.csv")
    for seed, device in ((42, "cpu"), (43, "mps")):
        _append_ledger_row(_ledger_row(
            ExperimentConfig(experiment_id=f"arm_s{seed}", seed=seed), _fake_subsets(),
            {"hit_max_epochs": 0, "n_models": 1, "device": device}, 1.0,
        ))
    written = pd.read_csv(tmp_path / "ledger.csv", keep_default_na=False)
    assert list(written["device"]) == ["cpu", "mps"]
