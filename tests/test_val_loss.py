"""The validation loss the ledger records, and the fact that it is the RIGHT one.

train_model restores the weights from the best epoch, but the log line reported the LAST
epoch's loss -- up to early_stop_patience epochs of non-improvement later. Anything that
selected an architecture on that number would be ranking models by weights that were thrown
away. The ledger column exists so that architecture can be chosen on validation loss instead
of on the test metric (methodology 16), which is only safe if the number means what it says.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

import merve_solar.experiment as experiment_module
from merve_solar.config import ExperimentConfig
from merve_solar.experiment import (
    LEDGER_COLUMNS,
    _append_ledger_row,
    _best_val_loss,
    _ledger_row,
    assert_ledger_schema_ok,
)

METRIC_KEYS = ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
               "n_samples", "n_elements")


def _fake_subsets():
    block = {k: 1.0 for k in METRIC_KEYS}
    return {"all_hours": {"aggregate": dict(block)}, "daylight": {"aggregate": dict(block)}}


def _history(*losses):
    return [{"epoch": i, "train_loss": 0.0, "val_loss": v} for i, v in enumerate(losses)]


def test_the_recorded_loss_is_the_best_epochs_not_the_last():
    """The whole point: early stopping means the last epoch is not the model that was kept."""
    assert _best_val_loss(_history(0.9, 0.4, 0.5, 0.6, 0.7)) == 0.4


def test_a_run_that_improved_to_the_end_is_unaffected():
    assert _best_val_loss(_history(0.9, 0.4, 0.2)) == 0.2


def test_best_val_loss_is_part_of_the_declared_schema():
    assert "best_val_loss" in LEDGER_COLUMNS


def test_the_value_reaches_the_ledger_row_as_the_mean_over_models():
    """A run trains B (or 5B) models and the row is one line; the mean is that summary."""
    row = _ledger_row(
        ExperimentConfig(experiment_id="x"), _fake_subsets(),
        {"hit_max_epochs": 0, "n_models": 2, "best_val_losses": [0.1, 0.3]}, 1.0,
    )
    assert row["best_val_loss"] == 0.2
    assert tuple(row) == LEDGER_COLUMNS


def test_a_row_built_without_a_loss_says_so_loudly():
    """Blank would read as 'not applicable'. 'unknown' is greppable and obviously a bug."""
    row = _ledger_row(ExperimentConfig(experiment_id="x"), _fake_subsets(), {}, 1.0)
    assert row["best_val_loss"] == "unknown"


def test_a_run_that_trained_nothing_is_marked_differently_from_one_that_lost_the_number():
    """The naive baselines fit no model at all -- 'no such quantity', not 'failed to record'."""
    row = _ledger_row(
        ExperimentConfig(experiment_id="baseline_persistence", model_family="persistence"),
        _fake_subsets(), {"hit_max_epochs": 0, "n_models": 0, "best_val_losses": []}, 1.0,
    )
    assert row["best_val_loss"] == "n/a"


def test_the_column_survives_a_round_trip_through_the_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", tmp_path / "ledger.csv")
    for name, stats in (
        ("trained", {"hit_max_epochs": 0, "n_models": 1, "best_val_losses": [0.25]}),
        ("naive", {"hit_max_epochs": 0, "n_models": 0, "best_val_losses": []}),
    ):
        _append_ledger_row(_ledger_row(
            ExperimentConfig(experiment_id=name), _fake_subsets(), stats, 1.0
        ))
    written = pd.read_csv(tmp_path / "ledger.csv", keep_default_na=False)
    assert list(written["best_val_loss"]) == ["0.25", "n/a"]
    # A plain read (pandas treats "n/a" as NA) gives a float column, so the ledger can be sorted
    # on it directly. "unknown" is not an NA string and would turn the column to object -- which
    # is the point: a run that failed to record its loss cannot pass unnoticed.
    numeric = pd.read_csv(tmp_path / "ledger.csv")["best_val_loss"]
    assert numeric.dtype == "float64"
    assert numeric[0] == 0.25 and pd.isna(numeric[1])


def test_the_migrated_ledger_still_matches_the_declared_schema():
    """Adding a column to LEDGER_COLUMNS orphans the real file until it is migrated too."""
    assert_ledger_schema_ok()


def test_the_rows_that_predate_the_column_are_left_empty_rather_than_backfilled():
    """log.txt holds the LAST epoch's loss, so there is nothing on disk to backfill with.

    Filling those cells from the logs would put two different quantities in one column -- the
    failure this column was added to avoid. Empty means 'ran before the column existed'.
    """
    if not experiment_module.LEDGER_PATH.exists():
        return
    written = pd.read_csv(experiment_module.LEDGER_PATH, keep_default_na=False)
    legacy = written[written["experiment_id"].isin([
        "abl_rize_all5_s42_l1", "abl_loss_mse_s42_b1", "abl_parity_cpu_s42",
    ])]
    assert len(legacy) == 3
    assert set(legacy["best_val_loss"]) == {""}
    baselines = written[written["model_family"] != "lstm"]
    assert set(baselines["best_val_loss"]) == {"n/a"}
