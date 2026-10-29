"""run_experiment(config): the single orchestrator for one facet/configuration run.

n_bootstrap=1 doubles as a fast sanity-check mode (no resampling, just a plain
trained LSTM, still scored via MC-Dropout alone) — the same code path as the
full B-replica ensemble, just with B=1.

Order of work: train every network of the run, then score the VALIDATION split, then (fitting
the conformal grid on validation if asked) the TEST split. Both splits are scored by
evaluation.evaluate_split with identical code, so the validation metrics in the ledger, which
are the tuning criterion, describe the same object as the test metrics reported in the paper.
"""
import fcntl
import time
from contextlib import contextmanager

import numpy as np
import pandas as pd
import torch

from merve_solar.bootstrap import resample_train_split
from merve_solar.config import (
    BASE_FEATURES_PATH,
    CITIES,
    CITY_TO_ID,
    LEDGER_PATH,
    NUMERIC_FEATURE_COLUMNS,
    TARGET_COLUMN,
)
from merve_solar.data import load_base_features
from merve_solar.conformal import (
    apply_conformal,
    fit_conformal_grid,
    month_stability_table,
)
from merve_solar.evaluation import EvaluationPart, draws_per_network, evaluate_split
from merve_solar.metrics import (
    TARGET_CI_COVERAGE,
    compute_metric_subsets,
    compute_metrics_for_subset,
    results_by_horizon_dataframe,
    results_summary_dataframe,
)
from merve_solar.model import SolarLSTM
from merve_solar.scaling import (
    apply_scaler,
    fit_scaler,
    inverse_transform_target,
    save_scaler,
    scaled_target_zero,
)
from merve_solar.train import NONNEG_PENALTY_FLOOR, train_model
from merve_solar.utils import get_device, plot_forecast_with_ci, plot_metric_vs_horizon, set_seed
from merve_solar.windows import build_experiment_windows, compute_split_boundaries


# The ledger is the source of the paper's tables, and _append_ledger_row appends without a
# header -- so any change to the row dict silently misaligns every column of the new row
# against the existing header. Declaring the schema makes that a loud failure instead.
LEDGER_COLUMNS: tuple[str, ...] = (
    "experiment_id", "model_family", "training_scope", "excluded_cities",
    "lookback_hours", "horizon_hours", "window_stride", "n_features",
    "hidden_sizes", "lstm_layers", "dropout_rate", "city_embedding_dim",
    "train_ratio", "val_ratio",
    "n_bootstrap", "bootstrap_block_length", "bootstrap_resample",
    "mc_dropout_passes", "inference_mode",
    "batch_size", "learning_rate", "lr_reduce_factor", "lr_reduce_patience",
    "max_epochs", "early_stop_patience",
    "loss_function", "huber_delta", "nonneg_penalty_weight", "nonneg_penalty_floor",
    "loss_daylight_only", "per_city_scaler",
    "clamp_night_to_zero", "conformal_mode", "seed", "device",
    "RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
    "n_samples", "n_elements",
    "RMSE_daylight", "MAE_daylight", "R2_daylight", "CP_daylight", "n_elements_daylight",
    "PINW_daylight", "MPIW_daylight", "CWC_daylight", "CRPS_daylight",
    "val_RMSE_daylight", "val_MAE_daylight", "val_R2_daylight", "val_CP_daylight",
    "val_PINW_daylight", "val_CRPS_daylight",
    "best_val_loss", "mean_best_epoch", "hit_max_epochs", "n_models_trained", "training_time_sec",
)

# Validation-split columns, the tuning criterion. Prefixed so they can never be mistaken for
# the test metrics beside them; computed BEFORE any conformal rescaling (validation is the
# conformal calibration split, so post-correction coverage there would be fitted, not measured).
VAL_LEDGER_METRICS = ("RMSE", "MAE", "R2", "CP", "PINW", "CRPS")

# Interval metrics, undefined for a one-draw predictive sample (deterministic inference, B=1):
# its 2.5/97.5 percentiles collapse onto the point forecast. CRPS stays defined (it is the MAE).
INTERVAL_METRICS = ("CP", "PINW", "MPIW", "Reliability", "CWC")


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


def assert_trainable_model_family(config) -> None:
    """run_experiment trains an LSTM and nothing else, so any other family would be a lie.

    SCOPE_RUNNERS dispatches on training_scope alone; model_family is only ever copied into the
    ledger row. Without this check a config saying model_family="climatology" would train an
    LSTM and append a row labelled `climatology` -- a fabricated comparison sitting in the file
    the paper's tables are built from.

    Deliberately NOT validated in ExperimentConfig.__post_init__: scripts/03_run_naive_baselines.py
    constructs an ExperimentConfig with model_family set purely as a ROW DESCRIPTOR for a forecast
    that was computed without ever going through run_experiment. There the config is metadata, not
    a training instruction, and rejecting it at construction would break a working script. The
    guard belongs where training is actually dispatched, which is here.
    """
    if config.model_family != "lstm":
        raise ValueError(
            f"run_experiment only trains model_family='lstm', got {config.model_family!r}. "
            "The non-LSTM families (climatology, persistence) are not trained "
            "at all -- they are scored through the same windows and metrics by "
            "scripts/03_run_naive_baselines.py, which writes their ledger rows directly. "
            "Running this config would train an LSTM and label the row "
            f"{config.model_family!r}."
        )


@contextmanager
def _ledger_lock():
    """Exclusive lock around the ledger's read-modify-write.

    Sweeps may run as several processes at once (run_all_experiments.py --shard). Without the
    lock, two runs finishing together could each read the file, add their row and write it
    back, and one row would be lost. flock on a side file works on macOS and Linux and is
    released if the process dies.
    """
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH.with_name(LEDGER_PATH.name + ".lock"), "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _append_ledger_row(row: dict) -> None:
    if tuple(row) != LEDGER_COLUMNS:
        raise ValueError(f"ledger row keys do not match LEDGER_COLUMNS: {set(row) ^ set(LEDGER_COLUMNS)}")
    with _ledger_lock():
        assert_ledger_schema_ok()
        df_row = pd.DataFrame([row], columns=list(LEDGER_COLUMNS))
        if LEDGER_PATH.exists():
            # A rerun under the same id has just overwritten that id's output directory, so its
            # old row no longer describes anything on disk: replace it rather than leave a
            # duplicate. Filtered as text so every other row stays byte-identical.
            prefix = f"{row['experiment_id']},"
            lines = LEDGER_PATH.read_text().splitlines(keepends=True)
            kept = lines[:1] + [line for line in lines[1:] if not line.startswith(prefix)]
            if len(kept) != len(lines):
                LEDGER_PATH.write_text("".join(kept))
        df_row.to_csv(LEDGER_PATH, mode="a", header=not LEDGER_PATH.exists(), index=False)


def _best_val_loss(history: list[dict]) -> float:
    """The validation loss of the model `train_model` actually RETURNS.

    train_model keeps a deepcopy of the weights from the epoch with the lowest validation loss
    and restores them before returning (methodology 10.2), so the model that goes on to predict
    is the argmin over `history` -- NOT the last epoch. With early_stop_patience=15 the last
    epoch is up to 15 epochs of non-improvement after the best one, so history[-1]["val_loss"]
    describes weights that were thrown away. Anything that scores or selects a run must use this.
    """
    return min(h["val_loss"] for h in history)


def _mean_best_val_loss(run_stats: dict):
    """One number per run for a ledger row that is one line: the MEAN over the run's models.

    A run trains B models in the global scope and 5B in the per-city scope; the mean is the
    obvious summary and the one that behaves sensibly as B changes. No spread column is written
    alongside it on purpose: the planned architecture sweep runs at B=1, where a spread is
    identically zero or undefined, so the column would be empty in exactly the rows that
    motivated it. The per-model values are in each run's log.txt if the spread is ever wanted,
    and a spread column can be added when a sweep actually runs B>1.

    "unknown" (not blank) when the caller supplied no losses at all -- that is a bug, and it must
    be greppable rather than read as a missing float. "n/a" for a caller that trained nothing
    (the naive baselines pass an empty list): there is no validation loss to have, which is a
    different fact from having failed to record one.
    """
    losses = run_stats.get("best_val_losses")
    if losses is None:
        return "unknown"
    if len(losses) == 0:
        return "n/a"
    return float(np.mean(losses))


def _ledger_row(config, subsets: dict, run_stats: dict, training_time_sec: float,
                val_subsets: dict | None = None) -> dict:
    """Pure function over a finished run -- unit-testable without training anything."""
    agg = subsets["all_hours"]["aggregate"]
    day = subsets.get("daylight", {}).get("aggregate", {})
    val_day = (val_subsets or {}).get("daylight", {}).get("aggregate", {})
    is_lstm = config.model_family == "lstm"
    return {
        "experiment_id": config.experiment_id,
        "model_family": config.model_family,
        "training_scope": config.training_scope,
        # A stable, greppable string ("Rize", "" when nothing is excluded) rather than a Python
        # list repr, so the column can be filtered without parsing.
        "excluded_cities": config.excluded_cities_key,
        "lookback_hours": config.lookback_hours,
        "horizon_hours": config.horizon_hours,
        "window_stride": config.window_stride,
        "n_features": len(NUMERIC_FEATURE_COLUMNS),
        "hidden_sizes": str(config.hidden_sizes),
        "lstm_layers": config.n_lstm_layers if is_lstm else "n/a",
        "dropout_rate": config.dropout_rate,
        "city_embedding_dim": config.city_embedding_dim,
        "train_ratio": config.train_ratio,
        "val_ratio": config.val_ratio,
        "n_bootstrap": config.n_bootstrap,
        "bootstrap_block_length": config.bootstrap_block_length,
        "bootstrap_resample": config.bootstrap_resample if is_lstm else "n/a",
        "mc_dropout_passes": config.mc_dropout_passes,
        "inference_mode": config.inference_mode if is_lstm else "n/a",
        # The optimizer knobs are ledger columns because they are swept: abl_arch_lr3e4* varies
        # learning_rate alone, and two rows that differ only in a field the ledger cannot see are
        # indistinguishable in the paper's tables -- the exact failure CLAUDE.md's comparability
        # rules name. Every one of these is read by train.py and changes the fitted weights.
        "batch_size": config.batch_size,
        "learning_rate": config.learning_rate,
        "lr_reduce_factor": config.lr_reduce_factor,
        "lr_reduce_patience": config.lr_reduce_patience,
        "max_epochs": config.max_epochs,
        "early_stop_patience": config.early_stop_patience,
        "loss_function": config.loss_function,
        "huber_delta": config.huber_delta,
        "nonneg_penalty_weight": config.nonneg_penalty_weight,
        # Where the penalty starts. Not a config field: it records a bug fix, so the old value
        # cannot be requested. Rows trained before the fix were backfilled "train_mean" (penalty
        # below the training-mean irradiance); untrained baselines have no penalty at all.
        "nonneg_penalty_floor": NONNEG_PENALTY_FLOOR if config.model_family == "lstm" else "n/a",
        "loss_daylight_only": config.loss_daylight_only,
        "per_city_scaler": config.per_city_scaler,
        "clamp_night_to_zero": config.clamp_night_to_zero,
        # Which conformal grid (if any) rescaled the predictive distribution before the interval
        # metrics below were computed. A ledger column rather than a note because it changes
        # CP/PINW/MPIW/Reliability/CWC/CRPS while leaving RMSE/MAE/R2 identical: two rows that
        # differ only in this are the same point forecast with different intervals, and without
        # the column they would be indistinguishable in exactly the table that reports coverage.
        "conformal_mode": config.conformal_mode,
        "seed": config.seed,
        # Which backend produced the numbers. Not a config field -- see utils.get_device. Without
        # it the ledger cannot tell a CPU row from an MPS one, and a multi-seed mean would silently
        # average across backends that do not agree bitwise.
        "device": run_stats.get("device", "unknown"),
        **{k: agg.get(k) for k in
           ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
            "n_samples", "n_elements")},
        "RMSE_daylight": day.get("RMSE"),
        "MAE_daylight": day.get("MAE"),
        "R2_daylight": day.get("R2"),
        "CP_daylight": day.get("CP"),
        "n_elements_daylight": day.get("n_elements"),
        **{f"{k}_daylight": day.get(k) for k in ("PINW", "MPIW", "CWC", "CRPS")},
        **{f"val_{k}_daylight": val_day.get(k) for k in VAL_LEDGER_METRICS},
        # The model-selection criterion, in SCALED target space. Comparable ONLY between runs
        # that share loss_function/huber_delta, loss_daylight_only and the same pooled provinces
        # (which fix the scaler): it is the right instrument for "same data, same criterion,
        # different architecture" and meaningless across anything else. Never a substitute for
        # the test metrics next to it -- it exists so architecture can be chosen without them.
        "best_val_loss": _mean_best_val_loss(run_stats),
        # Mean over the run's networks of the epoch whose weights were kept (0-based).
        "mean_best_epoch": run_stats.get("mean_best_epoch", "n/a" if not is_lstm else None),
        "hit_max_epochs": run_stats.get("hit_max_epochs"),
        "n_models_trained": run_stats.get("n_models"),
        "training_time_sec": training_time_sec,
    }



CONFORMAL_ALPHA = 1.0 - TARGET_CI_COVERAGE


def _rescaled_summary(dist: dict, factors: np.ndarray) -> dict:
    """The summary of m + k(x - m), derived rather than re-sorted.

    Exact, not an approximation: the map is affine and increasing in x, so it carries the mean
    to the transformed mean and every percentile to the transformed percentile. `std` scales by
    |k| = k. tests/test_conformal.py pins this against an actual resummarise of the rescaled
    sample, because the whole single-sort saving rests on the identity holding.
    """
    return {
        "mean": dist["mean"],
        "std": dist["std"] * factors,
        "lower": dist["mean"] + factors * (dist["lower"] - dist["mean"]),
        "upper": dist["mean"] + factors * (dist["upper"] - dist["mean"]),
    }


def _conformal_effect_frame(y_true, daylight, city_id, cities, before, after, factors):
    """What the correction did, group by group -- the before/after table the write-up needs.

    Daylight only: night elements are held at k = 1 by construction, so an all-hours row would
    dilute the effect with a subset the layer never touches. Point accuracy is deliberately
    absent: the mean is invariant under the rescaling, so RMSE/MAE/R2 are identical either side
    and a column of them would only invite the reader to look for a difference that cannot exist.
    """
    rows = []

    def _row(label, sel_rows, step):
        idx = (slice(None) if sel_rows is None else sel_rows,
               slice(None) if step is None else slice(step, step + 1))
        mask = daylight[idx]
        if not mask.any():
            return
        y = y_true[idx]
        pre = compute_metrics_for_subset(None, y, mask, {k: v[idx] for k, v in before.items()})
        post = compute_metrics_for_subset(None, y, mask, {k: v[idx] for k, v in after.items()})
        rows.append({
            "group": label,
            "horizon_step": "all" if step is None else step + 1,
            "n_elements": pre["n_elements"],
            "k_mean": float(factors[idx][mask].mean()),
            "CP_before": pre["CP"], "CP_after": post["CP"],
            "MPIW_before": pre["MPIW"], "MPIW_after": post["MPIW"],
            "Reliability_before": pre["Reliability"], "Reliability_after": post["Reliability"],
            "CWC_before": pre["CWC"], "CWC_after": post["CWC"],
        })

    _row("Aggregate", None, None)
    for city in cities:
        sel = city_id == CITY_TO_ID[city]
        if sel.any():
            _row(city, sel, None)
    for step in range(y_true.shape[1]):
        _row("Aggregate", None, step)
    return pd.DataFrame(rows)


def _fit_conformal(calibration, layout, config, city_id_test, daylight, exp_dir, log_lines):
    """Fit the conformal grid on the validation summary; return the test-split factors.

    Everything written here is a small CSV, so unlike the npz dumps it syncs through git and the
    grid itself is a publishable table. `calibration` is the validation summary in W/m^2 with
    the night clamp applied; the grid is fitted on daylight elements only, which the clamp does
    not touch.
    """
    val = layout["val"]
    # Saved before anything is fitted, so the choice of grid geometry can later be redone on the
    # CALIBRATION split alone. Gitignored with the other npz dumps.
    np.savez_compressed(
        exp_dir / "metrics" / "calibration_predictions.npz",
        mean=calibration["mean"], lower=calibration["lower"], upper=calibration["upper"],
        y_true=val["y"], city_id=val["city_id"], daylight=val["daylight"],
        window_start=val["window_start"].astype("datetime64[h]").astype(np.int64),
    )
    grid = fit_conformal_grid(
        val["y"], calibration["mean"], calibration["lower"], calibration["upper"],
        val["city_id"], val["daylight"], config.conformal_mode, CONFORMAL_ALPHA,
        window_start=val["window_start"],
    )
    grid.to_frame().to_csv(exp_dir / "metrics" / "conformal_grid.csv", index=False)
    month_stability_table(
        val["y"], calibration["mean"], calibration["lower"], calibration["upper"],
        val["daylight"], val["window_start"], CONFORMAL_ALPHA,
    ).to_csv(exp_dir / "metrics" / "conformal_month_stability.csv", index=False)

    factors = grid.factor_array(city_id_test, daylight, layout["test"]["window_start"])
    day_k = factors[daylight]
    log_lines.append(
        f"conformal_mode={config.conformal_mode} alpha={CONFORMAL_ALPHA} "
        f"pooled_k={grid.pooled_factor:.4f} (n={grid.pooled_n}) "
        f"daylight k in [{day_k.min():.4f}, {day_k.max():.4f}] mean {day_k.mean():.4f}; "
        f"{grid.n_invalid} calibration elements dropped for a degenerate half-width; "
        "calibration pass: the validation predictions scored above"
    )
    return factors


def _plot_representative_forecasts(dist, y_true, city_id_test, config, exp_dir) -> None:
    horizon_axis = np.arange(1, config.horizon_hours + 1)
    for city in config.active_cities:
        mask = city_id_test == CITY_TO_ID[city]
        if not mask.any():
            continue
        sample_idx = np.where(mask)[0][0]
        plot_forecast_with_ci(
            horizon_axis,
            y_true[sample_idx],
            dist["mean"][sample_idx],
            dist["lower"][sample_idx],
            dist["upper"][sample_idx],
            title=f"{city}: representative 24h forecast with 95% CI",
            save_path=exp_dir / "figures" / f"forecast_ci_{city}.png",
        )


def _save_test_predictions(exp_dir, dist, y_true, city_id, daylight, window_start,
                           conformal_factors=None) -> None:
    """Summary of the predictive distribution, for re-slicing a finished run.

    Stores mean/lower/upper rather than the full (S, N, horizon) sample, which is ~3.4 GB at
    full fidelity; this is ~12 MB compressed. Gitignored alongside the .pt checkpoints, which
    is why the paired tests read metrics/daily_scores.csv instead.

    `conformal_factors` is the rescaling, saved alongside so the file stays INVERTIBLE: without
    it a reader cannot tell a corrected interval from an uncorrected one.
    """
    payload = dict(
        mean=dist["mean"], lower=dist["lower"], upper=dist["upper"],
        y_true=y_true, city_id=city_id, daylight=daylight,
        window_start=window_start.astype("datetime64[h]").astype(np.int64),
    )
    if conformal_factors is not None:
        payload["conformal_k"] = conformal_factors
    np.savez_compressed(exp_dir / "metrics" / "test_predictions.npz", **payload)


def daily_scores_frame(split: str, layout_split: dict, dist: dict, crps: np.ndarray,
                       lookback_hours: int) -> pd.DataFrame:
    """Daylight scores summed per (province, forecast-origin date): the paired-test input.

    A forecast's origin is its first target hour (window_start + lookback), dated in the site's
    local solar time like every other timestamp here. One row holds the 24 windows issued that
    day x their daylight horizon steps, as SUMS, so any coarser aggregate (a season, the whole
    split) is a sum of rows and RMSE = sqrt(sse / n). This is the only per-forecast output that
    syncs through git, so it is what a paired comparison of two arms is computed from.
    """
    y, day = layout_split["y"], layout_split["daylight"]
    err = np.where(day, dist["mean"] - y, 0.0)
    inside = (y >= dist["lower"]) & (y <= dist["upper"]) & day
    width = np.where(day, dist["upper"] - dist["lower"], 0.0)
    origin = (pd.to_datetime(layout_split["window_start"])
              + pd.Timedelta(hours=lookback_hours)).normalize()
    frame = pd.DataFrame({
        "city": [CITIES[i] for i in layout_split["city_id"]],
        "origin_date": origin.strftime("%Y-%m-%d"),
        "n_daylight": day.sum(axis=1),
        "sum_error": err.sum(axis=1, dtype=np.float64),
        "sum_abs_error": np.abs(err).sum(axis=1, dtype=np.float64),
        "sum_sq_error": (err.astype(np.float64) ** 2).sum(axis=1),
        "sum_crps": np.where(day, crps, 0.0).sum(axis=1),
        "n_covered": inside.sum(axis=1),
        "sum_width": width.sum(axis=1, dtype=np.float64),
    })
    out = frame.groupby(["city", "origin_date"], sort=True, as_index=False).sum()
    out.insert(0, "split", split)
    return out


def _blank_interval_metrics(subsets: dict) -> None:
    """In place: NaN for the interval metrics of a one-draw sample (see INTERVAL_METRICS)."""
    def _walk(node):
        if isinstance(node, dict):
            if "CP" in node and "RMSE" in node:
                for key in INTERVAL_METRICS:
                    node[key] = float("nan")
            else:
                for value in node.values():
                    _walk(value)
    _walk(subsets)


def _train_replicas(splits, config, n_cities, device, exp_dir, checkpoint_stem,
                    seed_base, rng, label, log_lines, target_floor):
    """Train the run's n_bootstrap networks on `splits["train"]`; return them and their records.

    Replica b is seeded with seed_base + b and draws its resample from `rng` in order, so the
    first k replicas of a B=16 run are the replicas of a B=k run with the same seed: the
    ensemble-size curves (scripts/14_ensemble_curves.py) read sub-ensembles off one run. Every
    network is kept in memory for scoring (16 networks of at most a few MB each).
    """
    replicas = config.n_bootstrap
    models, records, histories = [], [], []
    prefix = "" if label == "all" else f"{label} "

    for b in range(replicas):
        set_seed(seed_base + b)
        # n_bootstrap=1 never resamples; bootstrap_resample=False is the plain seed ensemble.
        resample = replicas > 1 and config.bootstrap_resample
        replica_train = (
            resample_train_split(splits["train"], config.bootstrap_block_length, rng)
            if resample else splits["train"]
        )
        model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), n_cities, config)
        t0 = time.time()
        model, history = train_model(model, replica_train, splits["val"], config,
                                     target_floor=target_floor, device=device)
        torch.save(model.state_dict(), exp_dir / "checkpoints" / f"{checkpoint_stem}_{b}.pt")
        models.append(model)

        best = min(history, key=lambda h: h["val_loss"])
        at_cap = len(history) >= config.max_epochs
        records.append({
            "city": label, "replica": b, "seed": seed_base + b, "resampled": resample,
            "best_epoch": best["epoch"], "n_epochs": len(history),
            "best_val_loss": best["val_loss"], "last_val_loss": history[-1]["val_loss"],
            "hit_max_epochs": at_cap, "train_time_sec": time.time() - t0,
        })
        histories.extend({"city": label, "replica": b, **h} for h in history)
        # best_val_loss FIRST because it describes the returned model; last_val_loss and
        # best_epoch say how far training ran past its own optimum.
        log_lines.append(
            f"{prefix}replica {b}: best_val_loss={best['val_loss']:.4f} "
            f"best_epoch={best['epoch']} last_val_loss={history[-1]['val_loss']:.4f} "
            f"epochs={len(history)}" + ("  WARNING: hit max_epochs" if at_cap else "")
        )
    return models, records, histories


def _fit_scale_window(base_df, config, train_end, val_end, cities, scaler_path):
    """Fit a scaler on THESE rows' train range only, apply it, and build their windows.

    Both scope arms call this; the only difference is which rows are passed in, which is
    exactly what training_scope means. The train-only boundary is preserved either way.
    """
    scaler = fit_scaler(base_df, train_end)
    scaled = apply_scaler(base_df, scaler)
    save_scaler(scaler, scaler_path)
    return build_experiment_windows(scaled, config, train_end, val_end, cities=cities), scaler


def _zero_city_ids(splits: dict) -> dict:
    """New dicts with city_id zeroed, for a model built with n_cities=1.

    A per-city model sees one city, so its embedding table has a single row; passing the real
    id (3 for Rize) would be an out-of-range index. Zeroing makes the embedding a learned
    constant bias, leaving the architecture otherwise identical to the global arm. Returns
    copies so the original city_id stays available for the alignment check.
    """
    return {
        name: {**d, "city_id": np.zeros_like(d["city_id"])}
        for name, d in splits.items()
    }


def _assert_city_block_aligned(city, city_test, layout_test, slot, split="test") -> None:
    """The per_city arm is only valid if a city's own test windows are the SAME windows, in the
    SAME order, as the pooled layout's slice for that city.

    Asserted at runtime because a misalignment would swap two cities' scores without changing
    a single array shape. The check is on window_start, deliberately not on y: the per-city y
    is scaled by that city's own scaler while the layout y is raw W/m^2, so they are different
    arrays representing the same windows. Timestamps are the arm-independent identity.
    """
    n = city_test["y"].shape[0]
    if n != slot.size:
        raise RuntimeError(f"{city}: {n} {split} windows but {slot.size} layout slots")
    if slot.size and np.any(np.diff(slot) != 1):
        raise RuntimeError(f"{city}: layout slice is not contiguous — the CITIES-order assumption broke")
    if not np.array_equal(city_test["window_start"], layout_test["window_start"][slot]):
        raise RuntimeError(f"{city}: {split} window timestamps differ between the per-city and pooled builds")


def _run_global_scope(base_df, config, train_end, val_end, layout, device, exp_dir, log_lines):
    """Train one network set on every active province; return it as a single EvaluationPart."""
    splits, scaler = _fit_scale_window(
        base_df, config, train_end, val_end, None, exp_dir / "checkpoints" / "scaler.joblib"
    )
    for split in ("val", "test"):
        if not np.array_equal(splits[split]["window_start"], layout[split]["window_start"]):
            raise RuntimeError(f"scaled and unscaled window builds disagree on the {split} windows")
    for name, d in splits.items():
        log_lines.append(f"{name}: {d['y'].shape[0]} windows")

    # n_cities is len(CITIES), NOT len(active_cities): the embedding table keeps a row per
    # province so that city_id values are never renumbered by an exclusion and checkpoints stay
    # comparable across runs. An excluded province's row simply never receives a gradient.
    models, records, histories = _train_replicas(
        splits, config, len(CITIES), device, exp_dir, "bootstrap_model",
        seed_base=config.seed + 1, rng=np.random.default_rng(config.seed),
        label="all", log_lines=log_lines, target_floor=scaled_target_zero(scaler),
    )
    part = EvaluationPart(
        models=models,
        X={s: splits[s]["X"] for s in ("val", "test")},
        city_id={s: splits[s]["city_id"] for s in ("val", "test")},
        slot={s: np.arange(layout[s]["y"].shape[0]) for s in ("val", "test")},
        scaler=scaler,
    )
    return [part], records, histories


def _run_per_city_scope(base_df, config, train_end, val_end, layout, device, exp_dir, log_lines):
    """Train an independent network set per province; one EvaluationPart each."""
    # With per_city_scaler=False the pooled scaler is fitted once and shared, so the arms differ
    # only in what each model was trained on, not in how the target was normalised.
    shared_scaler = None
    if not config.per_city_scaler:
        shared_scaler = fit_scaler(base_df, train_end)
        save_scaler(shared_scaler, exp_dir / "checkpoints" / "scaler.joblib")
        log_lines.append("per_city_scaler=False: all provinces share the pooled scaler")

    parts, records, histories = [], [], []
    for city in config.active_cities:
        city_idx = CITY_TO_ID[city]  # canonical id, never a position in active_cities
        city_rows = base_df[base_df["city"] == city]
        if shared_scaler is None:
            splits, city_scaler = _fit_scale_window(
                city_rows, config, train_end, val_end, [city],
                exp_dir / "checkpoints" / f"scaler_{city}.joblib",
            )
        else:
            city_scaler = shared_scaler
            splits = build_experiment_windows(
                apply_scaler(city_rows, shared_scaler), config, train_end, val_end, cities=[city]
            )
        slots = {}
        for split in ("val", "test"):
            slots[split] = np.flatnonzero(layout[split]["city_id"] == city_idx)
            _assert_city_block_aligned(city, splits[split], layout[split], slots[split], split=split)
        for name, d in splits.items():
            log_lines.append(f"{city}/{name}: {d['y'].shape[0]} windows")

        # Seeds must not collide across cities, or two cities would share weight inits and
        # bootstrap draws.
        zeroed = _zero_city_ids(splits)
        models, city_records, city_histories = _train_replicas(
            zeroed, config, 1, device, exp_dir, f"bootstrap_model_{city}",
            seed_base=config.seed + 1 + city_idx * config.n_bootstrap,
            rng=np.random.default_rng([config.seed, city_idx]),
            label=city, log_lines=log_lines, target_floor=scaled_target_zero(city_scaler),
        )
        parts.append(EvaluationPart(
            models=models,
            X={s: zeroed[s]["X"] for s in ("val", "test")},
            city_id={s: zeroed[s]["city_id"] for s in ("val", "test")},
            slot=slots, scaler=city_scaler,
        ))
        records.extend(city_records)
        histories.extend(city_histories)
    return parts, records, histories


SCOPE_RUNNERS = {"global": _run_global_scope, "per_city": _run_per_city_scope}

# Files every finished LSTM run must leave behind (relative to its experiment directory). The
# remote-run check (scripts/check_outputs.py) and the tests both read this list.
REQUIRED_RUN_OUTPUTS = (
    "config.json",
    "log.txt",
    "metrics/results_summary.csv",
    "metrics/results_by_horizon.csv",
    "metrics/val_results_summary.csv",
    "metrics/daily_scores.csv",
    "metrics/replicas.csv",
    "metrics/training_history.csv",
    "metrics/test_predictions.npz",
)


def missing_run_outputs(config) -> list[str]:
    return [rel for rel in REQUIRED_RUN_OUTPUTS if not (config.experiment_dir / rel).exists()]


def run_experiment(config, base_df: pd.DataFrame | None = None) -> dict:
    start_time = time.time()
    # Both fail in milliseconds rather than after hours of training.
    assert_ledger_schema_ok()
    assert_trainable_model_family(config)
    set_seed(config.seed)

    exp_dir = config.experiment_dir
    (exp_dir / "checkpoints").mkdir(parents=True, exist_ok=True)
    (exp_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (exp_dir / "figures").mkdir(parents=True, exist_ok=True)
    config.to_json(exp_dir / "config.json")

    if base_df is None:
        base_df = load_base_features(BASE_FEATURES_PATH)

    # Boundaries come from the FULL frame once, BEFORE any exclusion is applied, so both arms
    # of every comparison split on identical dates. compute_split_boundaries counts hours off
    # CITIES[0] and raises on a partial frame, so filtering first would either crash (Ankara
    # excluded) or silently produce different split dates for the excluded-city arm.
    train_end, val_end = compute_split_boundaries(base_df, config)

    # Only now drop the excluded provinces. Everything downstream -- the scaler fit, the
    # windows, the models, the metric table -- sees only the active ones, which is what
    # "removed entirely" means.
    if config.excluded_cities:
        base_df = base_df[base_df["city"].isin(config.active_cities)].reset_index(drop=True)

    # Layout pass on the UNSCALED frame: the canonical ground truth in W/m^2, plus the daylight
    # mask and window identities. Taking y_true from here rather than inverse-transforming the
    # scaled targets keeps exact night zeros (a float32 round-trip through StandardScaler
    # returns them as +-1e-5 noise) and gives every arm a byte-identical truth to score against.
    layout = build_experiment_windows(base_df, config, train_end, val_end, include_X=False)
    y_true = layout["test"]["y"]
    daylight = layout["test"]["daylight"]
    city_id_test = layout["test"]["city_id"]

    device = get_device()
    n_draws = config.n_bootstrap * draws_per_network(config)
    log_lines = [
        f"device={device}",
        f"training_scope={config.training_scope} model_family={config.model_family}",
        f"loss_function={config.loss_function}",
        f"inference_mode={config.inference_mode} bootstrap_resample={config.bootstrap_resample} "
        f"pooled draws per element={n_draws}",
        f"active_cities={config.active_cities} excluded={config.excluded_cities}",
        f"train_end={train_end} val_end={val_end}",
        f"test daylight elements: {int(daylight.sum())} of {daylight.size}",
    ]

    parts, records, histories = SCOPE_RUNNERS[config.training_scope](
        base_df, config, train_end, val_end, layout, device, exp_dir, log_lines
    )
    train_seconds = time.time() - start_time
    pd.DataFrame(records).to_csv(exp_dir / "metrics" / "replicas.csv", index=False)
    pd.DataFrame(histories).to_csv(exp_dir / "metrics" / "training_history.csv", index=False)
    run_stats = {
        "hit_max_epochs": int(sum(r["hit_max_epochs"] for r in records)),
        "n_models": len(records),
        # Pooled flat across (city, replica). With per_city_scaler=True each province's loss is
        # in its OWN scaled space, so a per-city mean is not comparable to a global-arm row.
        "best_val_losses": [r["best_val_loss"] for r in records],
        "mean_best_epoch": float(np.mean([r["best_epoch"] for r in records])),
        "device": device,
    }

    # Validation first: it is the tuning criterion, and the conformal calibration split.
    # Clamped like the test split -- the clamp is part of the forecast, not of the scoring.
    val_dist, val_crps = evaluate_split(parts, "val", layout["val"], config, device)
    val_subsets = compute_metric_subsets(
        None, layout["val"]["y"], layout["val"]["city_id"], config.active_cities,
        daylight=layout["val"]["daylight"], dist=val_dist, crps_elements=val_crps,
    )
    if n_draws == 1:
        _blank_interval_metrics(val_subsets)
    results_summary_dataframe(val_subsets).to_csv(
        exp_dir / "metrics" / "val_results_summary.csv", index=False)

    factors = None
    if config.conformal_mode != "none":
        factors = _fit_conformal(val_dist, layout, config, city_id_test, daylight, exp_dir, log_lines)

    # The conformal layer rescales each element's sample about its own mean (an affine,
    # increasing map), so the corrected summary is derived analytically from the uncorrected
    # one; only CRPS needs the rescaled sample, and evaluate_split scores that chunk by chunk.
    before, crps = evaluate_split(parts, "test", layout["test"], config, device, factors=factors)
    dist = before if factors is None else _rescaled_summary(before, factors)
    if factors is not None:
        _conformal_effect_frame(
            y_true, daylight, city_id_test, config.active_cities, before, dist, factors
        ).to_csv(exp_dir / "metrics" / "conformal_effect.csv", index=False)
    if config.clamp_night_to_zero:
        log_lines.append(f"clamped {int((~daylight).sum())} test night elements to zero")

    subsets = compute_metric_subsets(
        None, y_true, city_id_test, config.active_cities, daylight=daylight, dist=dist,
        crps_elements=crps,
    )
    if n_draws == 1:
        _blank_interval_metrics(subsets)

    summary_df = results_summary_dataframe(subsets)
    horizon_df = results_by_horizon_dataframe(subsets)
    summary_df.to_csv(exp_dir / "metrics" / "results_summary.csv", index=False)
    horizon_df.to_csv(exp_dir / "metrics" / "results_by_horizon.csv", index=False)
    pd.concat([
        daily_scores_frame("val", layout["val"], val_dist, val_crps, config.lookback_hours),
        daily_scores_frame("test", layout["test"], dist, crps, config.lookback_hours),
    ]).to_csv(exp_dir / "metrics" / "daily_scores.csv", index=False)
    _save_test_predictions(exp_dir, dist, y_true, city_id_test, daylight,
                           layout["test"]["window_start"], factors)

    _plot_representative_forecasts(dist, y_true, city_id_test, config, exp_dir)
    for subset in horizon_df["subset"].unique():
        block = horizon_df[horizon_df["subset"] == subset]
        suffix = "" if subset == "all_hours" else f"_{subset}"
        for metric in ("RMSE", "CP"):
            plot_metric_vs_horizon(
                block, metric, f"{metric} vs horizon ({subset})",
                exp_dir / "figures" / f"{metric.lower()}_vs_horizon{suffix}.png",
            )

    training_time_sec = time.time() - start_time
    log_lines.append(f"train_time_sec={train_seconds:.1f}")
    log_lines.append(f"total_training_time_sec={training_time_sec:.1f}")
    (exp_dir / "log.txt").write_text("\n".join(log_lines) + "\n")

    missing = missing_run_outputs(config)
    if missing:
        raise RuntimeError(f"{config.experiment_id}: run finished without {missing}")
    _append_ledger_row(
        _ledger_row(config, subsets, run_stats, training_time_sec, val_subsets=val_subsets)
    )
    return subsets
