"""scripts/run_experiment.py axis overrides.

The refusal is the load-bearing test: an override that kept the config's own experiment_id
would overwrite an existing run directory and append a ledger row whose id already describes a
different configuration, which the comparability rules forbid.
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest

from merve_solar.config import ExperimentConfig


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "cli_run_experiment", ROOT / "scripts" / "run_experiment.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


def _parse(*argv):
    return cli.build_parser().parse_args(["--config", "unused.json", *argv])


@pytest.fixture
def base_config():
    return ExperimentConfig(experiment_id="config_000_smoke")


def test_exclusion_override_without_an_experiment_id_is_refused(base_config):
    with pytest.raises(SystemExit, match="no --experiment-id"):
        cli.apply_overrides(base_config, _parse("--exclude-city", "Rize"))


def test_loss_override_without_an_experiment_id_is_refused(base_config):
    with pytest.raises(SystemExit, match="no --experiment-id"):
        cli.apply_overrides(base_config, _parse("--loss", "mae"))


def test_no_override_runs_the_config_untouched(base_config):
    assert cli.apply_overrides(base_config, _parse()) == base_config


def test_a_bare_rename_is_allowed(base_config):
    renamed = cli.apply_overrides(base_config, _parse("--experiment-id", "other"))
    assert renamed.experiment_id == "other"
    assert renamed.excluded_cities == [] and renamed.loss_function == "mse"


def test_overrides_land_on_the_config_that_will_be_run(base_config):
    """They are applied before run_experiment, so the config.json in the run directory --
    the thing the result has to be reproducible from -- is the effective one."""
    args = _parse("--exclude-city", "Rize", "--loss", "mae", "--experiment-id", "smoke_excl_mae")
    overridden = cli.apply_overrides(base_config, args)

    assert overridden.experiment_id == "smoke_excl_mae"
    assert overridden.excluded_cities == ["Rize"]
    assert overridden.loss_function == "mae"
    assert overridden.active_cities == ["Ankara", "Antalya", "Konya", "Van"]
    assert base_config.experiment_id == "config_000_smoke", "the loaded config was mutated"


def test_exclude_city_is_repeatable(base_config):
    args = _parse("--exclude-city", "Rize", "--exclude-city", "Van", "--experiment-id", "x")
    assert cli.apply_overrides(base_config, args).active_cities == ["Ankara", "Antalya", "Konya"]


def test_an_invalid_override_is_rejected_before_anything_runs(base_config):
    args = _parse("--exclude-city", "Izmir", "--experiment-id", "x")
    with pytest.raises(ValueError, match="unknown province"):
        cli.apply_overrides(base_config, args)


def test_an_unknown_loss_is_rejected_by_the_parser():
    with pytest.raises(SystemExit):
        _parse("--loss", "huber", "--experiment-id", "x")
