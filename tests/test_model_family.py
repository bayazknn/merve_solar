"""model_family must describe what actually ran.

run_experiment dispatches on training_scope alone and always trains an LSTM, while the ledger
copies model_family straight from the config. A config claiming a naive family would therefore
produce an LSTM run wearing a `climatology` label in the file the paper's tables come from --
a fabricated comparison, not a bug that shows up as a wrong number.

The second half of this file is the reason the guard is in run_experiment and not in
ExperimentConfig.__post_init__: the naive-baseline script legitimately builds a config with
model_family set purely as a ledger-row descriptor, having computed the forecast without ever
training anything.
"""
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

import merve_solar.config as config_module
import merve_solar.experiment as experiment_module
from conftest import make_synthetic_base_df
from merve_solar.config import MODEL_FAMILIES, ExperimentConfig
from merve_solar.experiment import _append_ledger_row, _ledger_row, run_experiment

NON_LSTM_FAMILIES = [f for f in MODEL_FAMILIES if f != "lstm"]

METRIC_KEYS = ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
               "n_samples", "n_elements")


def _fake_subsets():
    block = {k: 1.0 for k in METRIC_KEYS}
    return {"all_hours": {"aggregate": dict(block)}, "daylight": {"aggregate": dict(block)}}


@pytest.fixture
def isolated_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "EXPERIMENTS_DIR", tmp_path / "experiments")
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", tmp_path / "ledger.csv")
    return tmp_path


def _tiny_config(**kw) -> ExperimentConfig:
    """Small enough that a run would finish in seconds -- if it were allowed to start."""
    return ExperimentConfig(
        experiment_id="test_family",
        lookback_hours=6,
        horizon_hours=6,
        train_ratio=0.6,
        val_ratio=0.2,
        hidden_sizes=[4, 4],
        n_bootstrap=1,
        mc_dropout_passes=2,
        max_epochs=1,
        batch_size=256,
        **kw,
    )


@pytest.mark.parametrize("family", NON_LSTM_FAMILIES)
def test_run_experiment_refuses_to_train_a_non_lstm_family(family, isolated_outputs):
    with pytest.raises(ValueError, match="only trains model_family='lstm'"):
        run_experiment(_tiny_config(model_family=family), base_df=make_synthetic_base_df(400))


def test_the_refusal_names_the_script_that_does_score_those_families(isolated_outputs):
    """A dead end is a worse failure than a wrong number: the message must say where to go."""
    with pytest.raises(ValueError, match="03_run_naive_baselines.py"):
        run_experiment(_tiny_config(model_family="persistence"),
                       base_df=make_synthetic_base_df(400))


def test_the_guard_fires_before_any_data_is_loaded(isolated_outputs):
    """Next to assert_ledger_schema_ok, so a typo'd sweep dies in milliseconds.

    base_df=None would otherwise send run_experiment to the real parquet; reaching that far is
    itself the failure this asserts against.
    """
    with pytest.raises(ValueError, match="only trains model_family='lstm'"):
        run_experiment(_tiny_config(model_family="climatology"))


def test_the_lstm_default_is_not_blocked(isolated_outputs):
    subsets = run_experiment(_tiny_config(), base_df=make_synthetic_base_df(400))
    assert set(subsets) == {"all_hours", "daylight"}


@pytest.mark.parametrize("family", NON_LSTM_FAMILIES)
def test_a_baseline_row_descriptor_config_is_still_constructible(family):
    """The trap this guard has to avoid: 03_run_naive_baselines.py builds exactly this.

    Validating model_family in __post_init__ instead would reject it, and the naive reference
    floor -- the numbers the LSTM has to beat -- would stop reaching the ledger at all.
    """
    config = ExperimentConfig(
        experiment_id=f"baseline_{family}", model_family=family, n_bootstrap=1, mc_dropout_passes=1
    )
    assert config.model_family == family


@pytest.mark.parametrize("family", NON_LSTM_FAMILIES)
def test_a_baseline_row_descriptor_still_reaches_the_ledger(family, tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger.csv"
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", ledger_path)

    config = ExperimentConfig(
        experiment_id=f"baseline_{family}", model_family=family, n_bootstrap=1, mc_dropout_passes=1
    )
    _append_ledger_row(_ledger_row(config, _fake_subsets(), {"hit_max_epochs": 0, "n_models": 0}, 1.0))

    written = ledger_path.read_text()
    assert f"baseline_{family},{family}," in written


def test_the_baseline_script_still_imports():
    """A regression test for the guard's placement, not for the script's numbers.

    Moving the check into __post_init__ would break this script the next time anyone reran the
    naive floor, and nothing else in the suite would notice.
    """
    script = Path(__file__).resolve().parents[1] / "scripts" / "03_run_naive_baselines.py"
    spec = importlib.util.spec_from_file_location("naive_baselines_script", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # main() is behind __main__, so nothing runs
    assert callable(module.main)
