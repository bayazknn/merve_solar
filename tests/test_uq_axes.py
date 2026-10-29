"""The axes added for tuning and the uncertainty-layer ablation, and the outputs every run must
leave behind for the analysis that happens on another machine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest
import torch

import merve_solar.config as config_module
import merve_solar.experiment as experiment_module
from conftest import make_synthetic_base_df
from merve_solar.config import ExperimentConfig
from merve_solar.evaluation import EvaluationPart, evaluate_split
from merve_solar.experiment import REQUIRED_RUN_OUTPUTS, run_experiment
from merve_solar.metrics import crps_per_element, empirical_crps
from merve_solar.model import SolarLSTM
from merve_solar.scaling import fit_scaler

HOURS = 900


def _cfg(experiment_id, **overrides):
    base = dict(
        experiment_id=experiment_id, lookback_hours=6, horizon_hours=6, train_ratio=0.6,
        val_ratio=0.2, hidden_sizes=[4, 4], n_bootstrap=1, mc_dropout_passes=3, max_epochs=1,
        batch_size=256, bootstrap_block_length=12,
    )
    return ExperimentConfig(**{**base, **overrides})


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    # CPU so checkpoint comparisons are bitwise; MPS does not promise that.
    monkeypatch.setenv("MERVE_DEVICE", "cpu")
    monkeypatch.setattr(config_module, "EXPERIMENTS_DIR", tmp_path / "experiments")
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", tmp_path / "ledger.csv")
    return tmp_path


def _ledger(tmp_path):
    return pd.read_csv(tmp_path / "ledger.csv").set_index("experiment_id")


# --- config validation -------------------------------------------------------------------------

def test_deterministic_inference_requires_one_pass():
    with pytest.raises(ValueError, match="mc_dropout_passes=1"):
        ExperimentConfig(experiment_id="x", inference_mode="deterministic", mc_dropout_passes=100)


def test_zero_dropout_is_allowed_only_without_mc_dropout():
    ExperimentConfig(experiment_id="x", inference_mode="deterministic", mc_dropout_passes=1,
                     dropout_rate=0.0)
    with pytest.raises(ValueError, match="only source of MC-Dropout randomness"):
        ExperimentConfig(experiment_id="x", dropout_rate=0.0)


def test_lstm_layers_defaults_to_the_historical_coupling_and_can_be_decoupled():
    assert ExperimentConfig(experiment_id="x", hidden_sizes=[64, 32]).n_lstm_layers == 2
    config = ExperimentConfig(experiment_id="x", hidden_sizes=[64, 32], lstm_layers=3)
    model = SolarLSTM(13, 5, config)
    assert model.lstm.num_layers == 3 and model.lstm.hidden_size == 64
    assert [m.out_features for m in model.head if isinstance(m, torch.nn.Linear)] == [32, 24]


# --- end-to-end runs --------------------------------------------------------------------------

def test_a_run_leaves_every_required_output_and_validation_metrics_in_the_ledger(isolated):
    config = _cfg("full_outputs", n_bootstrap=2)
    run_experiment(config, base_df=make_synthetic_base_df(HOURS))
    exp_dir = isolated / "experiments" / "full_outputs"
    for rel in REQUIRED_RUN_OUTPUTS:
        assert (exp_dir / rel).exists(), rel
    row = _ledger(isolated).loc["full_outputs"]
    for col in ("val_RMSE_daylight", "val_CP_daylight", "val_CRPS_daylight", "CRPS_daylight",
                "PINW_daylight", "mean_best_epoch"):
        assert np.isfinite(row[col]), col
    replicas = pd.read_csv(exp_dir / "metrics" / "replicas.csv")
    assert list(replicas["replica"]) == [0, 1] and replicas["resampled"].all()
    history = pd.read_csv(exp_dir / "metrics" / "training_history.csv")
    assert set(history.columns) >= {"replica", "epoch", "train_loss", "val_loss", "lr"}


def test_daily_scores_reproduce_the_headline_daylight_metrics(isolated):
    """The paired tests are computed from daily_scores.csv on another machine, so its sums must
    give back exactly the numbers in results_summary.csv."""
    run_experiment(_cfg("daily", n_bootstrap=2), base_df=make_synthetic_base_df(HOURS))
    metrics = isolated / "experiments" / "daily" / "metrics"
    daily = pd.read_csv(metrics / "daily_scores.csv")
    summary = pd.read_csv(metrics / "results_summary.csv")
    val_summary = pd.read_csv(metrics / "val_results_summary.csv")
    for split, table in (("test", summary), ("val", val_summary)):
        d = daily[daily["split"] == split].sum(numeric_only=True)
        ref = table[(table.group == "Aggregate") & (table.subset == "daylight")].iloc[0]
        assert d["n_daylight"] == ref["n_elements"]
        assert np.sqrt(d["sum_sq_error"] / d["n_daylight"]) == pytest.approx(ref["RMSE"], rel=1e-5)
        assert d["sum_abs_error"] / d["n_daylight"] == pytest.approx(ref["MAE"], rel=1e-5)
        assert d["sum_crps"] / d["n_daylight"] == pytest.approx(ref["CRPS"], rel=1e-5)
        assert d["n_covered"] / d["n_daylight"] == pytest.approx(ref["CP"], rel=1e-9)
        assert d["sum_width"] / d["n_daylight"] == pytest.approx(ref["MPIW"], rel=1e-5)


def test_one_deterministic_network_reports_no_interval_but_keeps_crps(isolated):
    run_experiment(_cfg("det1", inference_mode="deterministic", mc_dropout_passes=1),
                   base_df=make_synthetic_base_df(HOURS))
    row = _ledger(isolated).loc["det1"]
    assert row["inference_mode"] == "deterministic"
    for col in ("CP", "PINW", "CP_daylight", "PINW_daylight", "val_CP_daylight"):
        assert np.isnan(row[col]), col
    # A one-draw predictive distribution is a point forecast, whose CRPS is its absolute error.
    assert row["CRPS_daylight"] == pytest.approx(row["MAE_daylight"], rel=1e-5)


def test_mc_and_deterministic_arms_share_their_trained_weights(isolated):
    """Same seed, same training: the two inference modes differ only in how they predict."""
    df = make_synthetic_base_df(HOURS)
    run_experiment(_cfg("arm_mc", n_bootstrap=2), base_df=df)
    run_experiment(_cfg("arm_det", n_bootstrap=2, inference_mode="deterministic",
                        mc_dropout_passes=1), base_df=df)
    ckpt = isolated / "experiments" / "{}" / "checkpoints" / "bootstrap_model_1.pt"
    a = torch.load(str(ckpt).format("arm_mc"))
    b = torch.load(str(ckpt).format("arm_det"))
    assert all(torch.equal(a[k], b[k]) for k in a)


def test_the_seed_ensemble_does_not_resample(isolated):
    run_experiment(_cfg("seed_ens", n_bootstrap=2, bootstrap_resample=False),
                   base_df=make_synthetic_base_df(HOURS))
    replicas = pd.read_csv(isolated / "experiments" / "seed_ens" / "metrics" / "replicas.csv")
    assert not replicas["resampled"].any()
    assert replicas["seed"].nunique() == 2
    assert _ledger(isolated).loc["seed_ens", "bootstrap_resample"] == False  # noqa: E712


def test_the_first_k_replicas_of_a_larger_run_are_the_smaller_run(isolated):
    """What lets scripts/14_ensemble_curves.py read B=4..16 off one B=16 run."""
    df = make_synthetic_base_df(HOURS)
    run_experiment(_cfg("b2", n_bootstrap=2), base_df=df)
    run_experiment(_cfg("b3", n_bootstrap=3), base_df=df)
    for b in range(2):
        a = torch.load(isolated / "experiments" / "b2" / "checkpoints" / f"bootstrap_model_{b}.pt")
        c = torch.load(isolated / "experiments" / "b3" / "checkpoints" / f"bootstrap_model_{b}.pt")
        assert all(torch.equal(a[k], c[k]) for k in a), f"replica {b} differs"


# --- streaming evaluation ----------------------------------------------------------------------

def test_streaming_evaluation_does_not_depend_on_the_chunk_size(isolated):
    """Chunking is exact only if every statistic is per element; deterministic inference makes
    the check bitwise rather than statistical."""
    from merve_solar.windows import build_experiment_windows, compute_split_boundaries
    from merve_solar.scaling import apply_scaler

    config = _cfg("chunks", n_bootstrap=2, inference_mode="deterministic", mc_dropout_passes=1)
    df = make_synthetic_base_df(HOURS)
    train_end, val_end = compute_split_boundaries(df, config)
    layout = build_experiment_windows(df, config, train_end, val_end, include_X=False)
    scaler = fit_scaler(df, train_end)
    splits = build_experiment_windows(apply_scaler(df, scaler), config, train_end, val_end)
    torch.manual_seed(0)
    part = EvaluationPart(
        models=[SolarLSTM(13, 5, config), SolarLSTM(13, 5, config)],
        X={"test": splits["test"]["X"]}, city_id={"test": splits["test"]["city_id"]},
        slot={"test": np.arange(len(splits["test"]["X"]))}, scaler=scaler,
    )
    big, crps_big = evaluate_split([part], "test", layout["test"], config, "cpu", chunk_elements=10**9)
    small, crps_small = evaluate_split([part], "test", layout["test"], config, "cpu", chunk_elements=7)
    for key in big:
        np.testing.assert_allclose(big[key], small[key], rtol=0, atol=1e-5)
    np.testing.assert_allclose(crps_big, crps_small, rtol=0, atol=1e-6)


def test_per_element_crps_averages_to_the_sample_crps():
    rng = np.random.default_rng(0)
    pooled = rng.normal(size=(50, 20, 4)).astype(np.float32)
    y = rng.normal(size=(20, 4)).astype(np.float32)
    assert crps_per_element(pooled, y).mean() == pytest.approx(empirical_crps(pooled, y), rel=1e-12)


def test_the_curve_tool_scores_like_the_pipeline(isolated):
    """The curve tool re-implements the percentile and CRPS reductions for speed; on the
    deterministic cell (no MC draws) they must reproduce evaluate_split's daylight numbers."""
    from merve_solar.evaluation import ensemble_curves
    from merve_solar.metrics import compute_metrics_for_subset
    from merve_solar.scaling import apply_scaler
    from merve_solar.windows import build_experiment_windows, compute_split_boundaries

    config = _cfg("curves", n_bootstrap=3, inference_mode="deterministic", mc_dropout_passes=1)
    df = make_synthetic_base_df(HOURS)
    train_end, val_end = compute_split_boundaries(df, config)
    layout = build_experiment_windows(df, config, train_end, val_end, include_X=False)
    scaler = fit_scaler(df, train_end)
    splits = build_experiment_windows(apply_scaler(df, scaler), config, train_end, val_end)
    torch.manual_seed(1)
    models = [SolarLSTM(13, 5, config) for _ in range(3)]
    X, cid = splits["test"]["X"], splits["test"]["city_id"]
    part = EvaluationPart(models=models, X={"test": X}, city_id={"test": cid},
                          slot={"test": np.arange(len(X))}, scaler=scaler)
    dist, crps = evaluate_split([part], "test", layout["test"], config, "cpu")
    day = layout["test"]["daylight"]
    ref = compute_metrics_for_subset(None, layout["test"]["y"], day, dist, crps)

    rows = ensemble_curves(models, X, cid, layout["test"]["y"], day, scaler, [2, 3], [2],
                           "cpu", "test", chunk_windows=17)
    cell = next(r for r in rows if r["inference_mode"] == "deterministic" and r["B"] == 3)
    for key in ("RMSE", "MAE", "CP", "MPIW", "CRPS", "PINW"):
        assert cell[key] == pytest.approx(ref[key], rel=1e-5), key
    assert {(r["inference_mode"], r["B"], r["T"]) for r in rows} == {
        ("mc_dropout", 2, 2), ("mc_dropout", 3, 2), ("deterministic", 2, 1), ("deterministic", 3, 1)}
