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
    compute_all_metrics,
    results_by_horizon_dataframe,
    results_summary_dataframe,
    summarize_predictive_distribution,
)
from merve_solar.model import SolarLSTM
from merve_solar.scaling import apply_scaler, fit_scaler, inverse_transform_target, save_scaler
from merve_solar.train import train_model
from merve_solar.utils import plot_forecast_with_ci, plot_metric_vs_horizon, set_seed
from merve_solar.windows import build_experiment_windows, compute_split_boundaries


def _append_ledger_row(row: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_row = pd.DataFrame([row])
    if LEDGER_PATH.exists():
        df_row.to_csv(LEDGER_PATH, mode="a", header=False, index=False)
    else:
        df_row.to_csv(LEDGER_PATH, mode="w", header=True, index=False)


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


def run_experiment(config, base_df: pd.DataFrame | None = None) -> dict:
    start_time = time.time()
    set_seed(config.seed)

    exp_dir = config.experiment_dir
    (exp_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    (exp_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (exp_dir / "figures").mkdir(parents=True, exist_ok=True)
    config.to_json(exp_dir / "config.json")

    if base_df is None:
        base_df = load_base_features(BASE_FEATURES_PATH)

    train_end, val_end = compute_split_boundaries(base_df, config)
    scaler = fit_scaler(base_df, train_end)
    scaled_df = apply_scaler(base_df, scaler)
    save_scaler(scaler, exp_dir / "checkpoints" / "scaler.joblib")

    splits = build_experiment_windows(scaled_df, config, train_end, val_end)

    log_lines = [f"train_end={train_end} val_end={val_end}"]
    for name, d in splits.items():
        log_lines.append(f"{name}: {d['X'].shape[0]} windows")

    rng = np.random.default_rng(config.seed)
    bootstrap_preds = []
    for b in range(config.n_bootstrap):
        set_seed(config.seed + b + 1)
        if config.n_bootstrap == 1:
            replica_train = splits["train"]
        else:
            replica_train = resample_train_split(splits["train"], config.bootstrap_block_length, rng)

        model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), len(CITIES), config)
        model, history = train_model(model, replica_train, splits["val"], config)
        torch.save(model.state_dict(), exp_dir / "checkpoints" / f"bootstrap_model_{b}.pt")

        preds = mc_dropout_predict(model, splits["test"]["X"], splits["test"]["city_id"], config.mc_dropout_passes)
        bootstrap_preds.append(preds)
        log_lines.append(f"replica {b}: final val_loss={history[-1]['val_loss']:.4f} epochs={len(history)}")

    pooled_preds_scaled = np.concatenate(bootstrap_preds, axis=0)
    pooled_preds = inverse_transform_target(scaler, pooled_preds_scaled)
    y_true = inverse_transform_target(scaler, splits["test"]["y"])
    city_id_test = splits["test"]["city_id"]

    all_metrics = compute_all_metrics(pooled_preds, y_true, city_id_test, CITIES)

    summary_df = results_summary_dataframe(all_metrics)
    horizon_df = results_by_horizon_dataframe(all_metrics)
    summary_df.to_csv(exp_dir / "metrics" / "results_summary.csv", index=False)
    horizon_df.to_csv(exp_dir / "metrics" / "results_by_horizon.csv", index=False)

    _plot_representative_forecasts(pooled_preds, y_true, city_id_test, config, exp_dir)
    plot_metric_vs_horizon(horizon_df, "RMSE", "RMSE vs horizon", exp_dir / "figures" / "rmse_vs_horizon.png")
    plot_metric_vs_horizon(horizon_df, "CP", "CP vs horizon", exp_dir / "figures" / "cp_vs_horizon.png")

    training_time_sec = time.time() - start_time
    log_lines.append(f"total_training_time_sec={training_time_sec:.1f}")
    (exp_dir / "log.txt").write_text("\n".join(log_lines) + "\n")

    _append_ledger_row(
        {
            "experiment_id": config.experiment_id,
            "lookback_hours": config.lookback_hours,
            "horizon_hours": config.horizon_hours,
            "window_stride": config.window_stride,
            "hidden_sizes": str(config.hidden_sizes),
            "dropout_rate": config.dropout_rate,
            "train_ratio": config.train_ratio,
            "val_ratio": config.val_ratio,
            "n_bootstrap": config.n_bootstrap,
            "mc_dropout_passes": config.mc_dropout_passes,
            **all_metrics["aggregate"],
            "training_time_sec": training_time_sec,
        }
    )

    return all_metrics
