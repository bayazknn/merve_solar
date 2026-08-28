"""run_experiment(config): the single orchestrator for one facet/configuration run.

n_bootstrap=1 doubles as a fast sanity-check mode (no resampling, just a plain
trained LSTM, still scored via MC-Dropout alone) — the same code path as the
full B-replica ensemble, just with B=1.
"""
import time

import numpy as np
import pandas as pd
import torch

from merve_solar.bootstrap import resample_train_split
from merve_solar.config import BASE_FEATURES_PATH, CITIES, LEDGER_PATH, NUMERIC_FEATURE_COLUMNS
from merve_solar.data import load_base_features
from merve_solar.mc_dropout import mc_dropout_predict
from merve_solar.metrics import (
    compute_metric_subsets,
    results_by_horizon_dataframe,
    results_summary_dataframe,
    summarize_predictive_distribution,
)
from merve_solar.model import SolarLSTM
from merve_solar.scaling import apply_scaler, fit_scaler, inverse_transform_target, save_scaler
from merve_solar.train import train_model
from merve_solar.utils import get_device, plot_forecast_with_ci, plot_metric_vs_horizon, set_seed
from merve_solar.windows import build_experiment_windows, compute_split_boundaries


# The ledger is the source of the paper's tables, and _append_ledger_row appends without a
# header -- so any change to the row dict silently misaligns every column of the new row
# against the existing header. Declaring the schema makes that a loud failure instead.
LEDGER_COLUMNS: tuple[str, ...] = (
    "experiment_id", "model_family", "training_scope",
    "lookback_hours", "horizon_hours", "window_stride", "n_features",
    "hidden_sizes", "dropout_rate", "city_embedding_dim",
    "train_ratio", "val_ratio",
    "n_bootstrap", "mc_dropout_passes", "max_epochs", "early_stop_patience",
    "loss_daylight_only", "seed",
    "RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
    "n_samples", "n_elements",
    "RMSE_daylight", "MAE_daylight", "R2_daylight", "CP_daylight", "n_elements_daylight",
    "hit_max_epochs", "n_models_trained", "training_time_sec",
)


def _ledger_schema_on_disk() -> tuple[str, ...] | None:
    if not LEDGER_PATH.exists():
        return None
    return tuple(pd.read_csv(LEDGER_PATH, nrows=0).columns)


def assert_ledger_schema_ok() -> None:
    """Called first thing in run_experiment: fail in milliseconds, not after hours of training."""
    existing = _ledger_schema_on_disk()
    if existing is not None and existing != LEDGER_COLUMNS:
        raise ValueError(
            f"Ledger schema mismatch at {LEDGER_PATH}.\n"
            f"  only on disk: {sorted(set(existing) - set(LEDGER_COLUMNS))}\n"
            f"  only in code: {sorted(set(LEDGER_COLUMNS) - set(existing))}\n"
            "Appending would misalign every column. Move the old ledger aside and rerun."
        )


def _append_ledger_row(row: dict) -> None:
    if tuple(row) != LEDGER_COLUMNS:
        raise ValueError(f"ledger row keys do not match LEDGER_COLUMNS: {set(row) ^ set(LEDGER_COLUMNS)}")
    assert_ledger_schema_ok()
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_row = pd.DataFrame([row], columns=list(LEDGER_COLUMNS))
    df_row.to_csv(LEDGER_PATH, mode="a", header=not LEDGER_PATH.exists(), index=False)


def _ledger_row(config, subsets: dict, run_stats: dict, training_time_sec: float) -> dict:
    """Pure function over a finished run -- unit-testable without training anything."""
    agg = subsets["all_hours"]["aggregate"]
    day = subsets.get("daylight", {}).get("aggregate", {})
    return {
        "experiment_id": config.experiment_id,
        "model_family": config.model_family,
        "training_scope": config.training_scope,
        "lookback_hours": config.lookback_hours,
        "horizon_hours": config.horizon_hours,
        "window_stride": config.window_stride,
        "n_features": len(NUMERIC_FEATURE_COLUMNS),
        "hidden_sizes": str(config.hidden_sizes),
        "dropout_rate": config.dropout_rate,
        "city_embedding_dim": config.city_embedding_dim,
        "train_ratio": config.train_ratio,
        "val_ratio": config.val_ratio,
        "n_bootstrap": config.n_bootstrap,
        "mc_dropout_passes": config.mc_dropout_passes,
        "max_epochs": config.max_epochs,
        "early_stop_patience": config.early_stop_patience,
        "loss_daylight_only": config.loss_daylight_only,
        "seed": config.seed,
        **{k: agg.get(k) for k in
           ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
            "n_samples", "n_elements")},
        "RMSE_daylight": day.get("RMSE"),
        "MAE_daylight": day.get("MAE"),
        "R2_daylight": day.get("R2"),
        "CP_daylight": day.get("CP"),
        "n_elements_daylight": day.get("n_elements"),
        "hit_max_epochs": run_stats.get("hit_max_epochs"),
        "n_models_trained": run_stats.get("n_models"),
        "training_time_sec": training_time_sec,
    }


def _plot_representative_forecasts(pooled_preds, y_true, city_id_test, config, exp_dir) -> None:
    horizon_axis = np.arange(1, config.horizon_hours + 1)
    for city_idx, city in enumerate(CITIES):
        mask = city_id_test == city_idx
        if not mask.any():
            continue
        sample_idx = np.where(mask)[0][0]
        sample_preds = pooled_preds[:, sample_idx : sample_idx + 1, :]
        dist = summarize_predictive_distribution(sample_preds)
        plot_forecast_with_ci(
            horizon_axis,
            y_true[sample_idx],
            dist["mean"][0],
            dist["lower"][0],
            dist["upper"][0],
            title=f"{city}: representative 24h forecast with 95% CI",
            save_path=exp_dir / "figures" / f"forecast_ci_{city}.png",
        )


def _predict_replicas(splits, config, n_cities, device, exp_dir, checkpoint_stem,
                      seed_base, rng, log_prefix, log_lines):
    """Train n_bootstrap replicas on `splits` and MC-Dropout predict the test split.

    Returns ((n_bootstrap * mc_dropout_passes, N_test, horizon) float32, SCALED units) and
    run statistics. The destination array is preallocated rather than built by appending and
    concatenating, which would double a 3.4 GB allocation at full fidelity.
    """
    passes, replicas = config.mc_dropout_passes, config.n_bootstrap
    n_test = splits["test"]["y"].shape[0]
    out = np.empty((replicas * passes, n_test, config.horizon_hours), dtype=np.float32)
    hit_cap = 0

    for b in range(replicas):
        set_seed(seed_base + b)
        # n_bootstrap=1 is the fast path, not a separate code path: no resampling, one model,
        # still scored by MC-Dropout alone.
        replica_train = (
            splits["train"] if replicas == 1
            else resample_train_split(splits["train"], config.bootstrap_block_length, rng)
        )
        model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), n_cities, config)
        model, history = train_model(model, replica_train, splits["val"], config, device=device)
        torch.save(model.state_dict(), exp_dir / "checkpoints" / f"{checkpoint_stem}_{b}.pt")

        out[b * passes:(b + 1) * passes] = mc_dropout_predict(
            model, splits["test"]["X"], splits["test"]["city_id"], passes, device=device
        )
        at_cap = len(history) >= config.max_epochs
        hit_cap += int(at_cap)
        log_lines.append(
            f"{log_prefix}replica {b}: val_loss={history[-1]['val_loss']:.4f} epochs={len(history)}"
            + ("  WARNING: hit max_epochs" if at_cap else "")
        )
        del model

    return out, {"hit_max_epochs": hit_cap, "n_models": replicas}


def run_experiment(config, base_df: pd.DataFrame | None = None) -> dict:
    start_time = time.time()
    assert_ledger_schema_ok()  # fail in milliseconds rather than after hours of training
    set_seed(config.seed)

    exp_dir = config.experiment_dir
    (exp_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    (exp_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (exp_dir / "figures").mkdir(parents=True, exist_ok=True)
    config.to_json(exp_dir / "config.json")

    if base_df is None:
        base_df = load_base_features(BASE_FEATURES_PATH)

    train_end, val_end = compute_split_boundaries(base_df, config)

    # Layout pass on the UNSCALED frame: the canonical ground truth in W/m^2, plus the daylight
    # mask and window identities. Taking y_true from here rather than inverse-transforming the
    # scaled targets keeps exact night zeros (a float32 round-trip through StandardScaler
    # returns them as +-1e-5 noise) and gives every arm a byte-identical truth to score against.
    layout = build_experiment_windows(base_df, config, train_end, val_end, include_X=False)
    y_true = layout["test"]["y"]
    daylight = layout["test"]["daylight"]
    city_id_test = layout["test"]["city_id"]

    scaler = fit_scaler(base_df, train_end)
    scaled_df = apply_scaler(base_df, scaler)
    save_scaler(scaler, exp_dir / "checkpoints" / "scaler.joblib")
    splits = build_experiment_windows(scaled_df, config, train_end, val_end)

    if not np.array_equal(splits["test"]["window_start"], layout["test"]["window_start"]):
        raise RuntimeError("scaled and unscaled window builds disagree on the test-set windows")

    device = get_device()
    log_lines = [
        f"device={device}",
        f"training_scope={config.training_scope} model_family={config.model_family}",
        f"train_end={train_end} val_end={val_end}",
    ]
    for name, d in splits.items():
        log_lines.append(f"{name}: {d['y'].shape[0]} windows")
    log_lines.append(f"test daylight elements: {int(daylight.sum())} of {daylight.size}")

    pooled_scaled, run_stats = _predict_replicas(
        splits, config, len(CITIES), device, exp_dir, "bootstrap_model",
        seed_base=config.seed + 1, rng=np.random.default_rng(config.seed),
        log_prefix="", log_lines=log_lines,
    )
    pooled_preds = inverse_transform_target(scaler, pooled_scaled)
    del pooled_scaled

    subsets = compute_metric_subsets(pooled_preds, y_true, city_id_test, CITIES, daylight=daylight)

    summary_df = results_summary_dataframe(subsets)
    horizon_df = results_by_horizon_dataframe(subsets)
    summary_df.to_csv(exp_dir / "metrics" / "results_summary.csv", index=False)
    horizon_df.to_csv(exp_dir / "metrics" / "results_by_horizon.csv", index=False)

    _plot_representative_forecasts(pooled_preds, y_true, city_id_test, config, exp_dir)
    for subset in horizon_df["subset"].unique():
        block = horizon_df[horizon_df["subset"] == subset]
        suffix = "" if subset == "all_hours" else f"_{subset}"
        for metric in ("RMSE", "CP"):
            plot_metric_vs_horizon(
                block, metric, f"{metric} vs horizon ({subset})",
                exp_dir / "figures" / f"{metric.lower()}_vs_horizon{suffix}.png",
            )

    training_time_sec = time.time() - start_time
    log_lines.append(f"total_training_time_sec={training_time_sec:.1f}")
    (exp_dir / "log.txt").write_text("\n".join(log_lines) + "\n")

    _append_ledger_row(_ledger_row(config, subsets, run_stats, training_time_sec))
    return subsets
