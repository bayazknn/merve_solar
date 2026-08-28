import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pytest

import merve_solar.experiment as experiment_module
from merve_solar.config import ExperimentConfig
from merve_solar.experiment import LEDGER_COLUMNS, _append_ledger_row, _ledger_row

METRIC_KEYS = ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
               "n_samples", "n_elements")


def _fake_subsets():
    block = {k: 1.0 for k in METRIC_KEYS}
    return {
        "all_hours": {"aggregate": dict(block)},
        "daylight": {"aggregate": dict(block)},
    }


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "experiments_ledger.csv"
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", path)
    return path


def test_ledger_row_keys_match_the_declared_schema_exactly():
    """Schema is testable without training anything, which is the point of _ledger_row."""
    row = _ledger_row(ExperimentConfig(experiment_id="x"), _fake_subsets(), {}, 1.0)
    assert tuple(row) == LEDGER_COLUMNS


def test_new_file_gets_a_header(ledger_path):
    _append_ledger_row(_ledger_row(ExperimentConfig(experiment_id="a"), _fake_subsets(), {}, 1.0))
    assert tuple(pd.read_csv(ledger_path).columns) == LEDGER_COLUMNS


def test_matching_schema_appends_without_a_second_header(ledger_path):
    for name in ("a", "b"):
        _append_ledger_row(_ledger_row(ExperimentConfig(experiment_id=name), _fake_subsets(), {}, 1.0))
    written = pd.read_csv(ledger_path)
    assert list(written["experiment_id"]) == ["a", "b"]


def test_schema_mismatch_raises_and_leaves_the_file_byte_identical(ledger_path):
    """The 'file untouched' half is the important one.

    The old behaviour appended a misaligned row and carried on, silently corrupting the file
    the paper's tables are built from. Raising is only useful if nothing was written first.
    """
    ledger_path.write_text("experiment_id,RMSE,CP\nold_run,1.0,0.5\n")
    before = ledger_path.read_bytes()

    with pytest.raises(ValueError, match="Ledger schema mismatch"):
        _append_ledger_row(_ledger_row(ExperimentConfig(experiment_id="new"), _fake_subsets(), {}, 1.0))

    assert ledger_path.read_bytes() == before


def test_row_with_unexpected_keys_is_rejected(ledger_path):
    row = _ledger_row(ExperimentConfig(experiment_id="x"), _fake_subsets(), {}, 1.0)
    row["surprise_column"] = 1
    with pytest.raises(ValueError, match="do not match LEDGER_COLUMNS"):
        _append_ledger_row(row)


def test_scope_and_family_reach_the_ledger():
    """A run that changed one of these axes must be distinguishable in the table."""
    row = _ledger_row(
        ExperimentConfig(experiment_id="x", training_scope="per_city"), _fake_subsets(), {}, 1.0
    )
    assert row["training_scope"] == "per_city"
    assert row["model_family"] == "lstm"


def test_excluded_cities_and_loss_function_reach_the_ledger():
    """Same rule as above: two runs differing only on these must not look identical in the table."""
    config = ExperimentConfig(
        experiment_id="x", excluded_cities=["Van", "Rize"], loss_function="mae"
    )
    row = _ledger_row(config, _fake_subsets(), {}, 1.0)
    # A stable, greppable string, not a Python list repr.
    assert row["excluded_cities"] == "Rize|Van"
    assert row["loss_function"] == "mae"

    default = _ledger_row(ExperimentConfig(experiment_id="y"), _fake_subsets(), {}, 1.0)
    assert default["excluded_cities"] == ""
    assert default["loss_function"] == "mse"


def test_the_new_axes_survive_a_round_trip_through_the_csv(ledger_path):
    """An empty excluded_cities must read back as an empty string, not as NaN-shaped surprise."""
    for config in (
        ExperimentConfig(experiment_id="plain"),
        ExperimentConfig(experiment_id="excl", excluded_cities=["Rize"], loss_function="mae"),
    ):
        _append_ledger_row(_ledger_row(config, _fake_subsets(), {}, 1.0))

    written = pd.read_csv(ledger_path, keep_default_na=False)
    assert list(written["excluded_cities"]) == ["", "Rize"]
    assert list(written["loss_function"]) == ["mse", "mae"]
