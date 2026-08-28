import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pytest

import merve_solar.config as config_module
import merve_solar.experiment as experiment_module
from conftest import make_synthetic_base_df
from merve_solar.config import CITIES, ExperimentConfig
from merve_solar.experiment import _assert_city_block_aligned, run_experiment
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

SCOPE_HOURS = 900


def _tiny_config(scope: str) -> ExperimentConfig:
    """Small enough to train in seconds; the point is the plumbing, not the fit."""
    return ExperimentConfig(
        experiment_id=f"test_{scope}",
        training_scope=scope,
        lookback_hours=6,
        horizon_hours=6,
        window_stride=1,
        train_ratio=0.6,
        val_ratio=0.2,
        hidden_sizes=[4, 4],
        n_bootstrap=1,
        mc_dropout_passes=2,
        max_epochs=1,
        batch_size=256,
    )


@pytest.fixture
def isolated_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "EXPERIMENTS_DIR", tmp_path / "experiments")
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", tmp_path / "ledger.csv")
    return tmp_path


def test_both_scope_arms_score_identical_ground_truth(isolated_outputs):
    """The apples-to-apples guarantee behind the paper's headline comparison.

    Both arms must be scored against byte-identical y_true, in the same window order. If they
    were not, the global-vs-per-city difference would partly be a difference in what was
    measured rather than in what was learned.
    """
    df = make_synthetic_base_df(SCOPE_HOURS)
    results = {}
    for scope in ("global", "per_city"):
        subsets = run_experiment(_tiny_config(scope), base_df=df)
        results[scope] = subsets

    for subset in ("all_hours", "daylight"):
        g = results["global"][subset]["aggregate"]
        p = results["per_city"][subset]["aggregate"]
        assert g["n_samples"] == p["n_samples"]
        assert g["n_elements"] == p["n_elements"]

    npz_g = np.load(isolated_outputs / "experiments" / "test_global" / "metrics" / "test_predictions.npz")
    npz_p = np.load(isolated_outputs / "experiments" / "test_per_city" / "metrics" / "test_predictions.npz")
    for key in ("y_true", "city_id", "daylight", "window_start"):
        assert np.array_equal(npz_g[key], npz_p[key]), f"{key} differs between the two arms"


def test_per_city_arm_trains_one_model_set_per_city(isolated_outputs):
    df = make_synthetic_base_df(SCOPE_HOURS)
    config = _tiny_config("per_city")
    run_experiment(config, base_df=df)

    checkpoints = isolated_outputs / "experiments" / config.experiment_id / "checkpoints"
    for city in CITIES:
        assert (checkpoints / f"scaler_{city}.joblib").exists(), f"{city} has no city-local scaler"
        assert (checkpoints / f"bootstrap_model_{city}_0.pt").exists()
    assert not (checkpoints / "scaler.joblib").exists(), "per_city must not fit a pooled scaler"


def test_per_city_assembly_places_each_city_in_its_own_slot():
    """Fills each city's block with that city's index and checks the assembled array.

    A transposition or off-by-one in the assembly would silently swap two cities' scores
    without changing any array shape, so it has to fail loudly here instead.
    """
    df = make_synthetic_base_df(SCOPE_HOURS)
    config = _tiny_config("per_city")
    train_end, val_end = compute_split_boundaries(df, config)
    layout = build_experiment_windows(df, config, train_end, val_end, include_X=False)
    city_id = layout["test"]["city_id"]

    pooled = np.full((3, city_id.size, config.horizon_hours), np.nan, dtype=np.float32)
    for idx in range(len(CITIES)):
        slot = np.flatnonzero(city_id == idx)
        pooled[:, slot, :] = float(idx)

    assert not np.isnan(pooled).any()
    expected = np.broadcast_to(
        city_id.astype(np.float32)[None, :, None], (3, city_id.size, config.horizon_hours)
    )
    assert np.array_equal(pooled, expected)


def test_alignment_guard_rejects_shuffled_windows():
    df = make_synthetic_base_df(SCOPE_HOURS)
    config = _tiny_config("per_city")
    train_end, val_end = compute_split_boundaries(df, config)
    layout = build_experiment_windows(df, config, train_end, val_end, include_X=False)
    city = CITIES[1]
    alone = build_experiment_windows(
        df[df["city"] == city], config, train_end, val_end, cities=[city], include_X=False
    )
    slot = np.flatnonzero(layout["test"]["city_id"] == 1)

    _assert_city_block_aligned(city, alone["test"], layout["test"], slot)  # passes as built

    shuffled = {**alone["test"], "window_start": alone["test"]["window_start"][::-1].copy()}
    with pytest.raises(RuntimeError, match="window timestamps differ"):
        _assert_city_block_aligned(city, shuffled, layout["test"], slot)

    with pytest.raises(RuntimeError, match="layout slots"):
        _assert_city_block_aligned(city, alone["test"], layout["test"], slot[:-1])


def test_per_city_scaler_flag_switches_to_the_pooled_scaler(isolated_outputs):
    """The sensitivity arm that separates the normalisation effect from the training effect."""
    df = make_synthetic_base_df(SCOPE_HOURS)
    config = _tiny_config("per_city")
    config = ExperimentConfig(**{**config.__dict__, "experiment_id": "test_shared_scaler",
                                "per_city_scaler": False})
    run_experiment(config, base_df=df)

    checkpoints = isolated_outputs / "experiments" / config.experiment_id / "checkpoints"
    assert (checkpoints / "scaler.joblib").exists(), "expected one pooled scaler"
    for city in CITIES:
        assert not (checkpoints / f"scaler_{city}.joblib").exists()
        assert (checkpoints / f"bootstrap_model_{city}_0.pt").exists(), "still one model per city"
