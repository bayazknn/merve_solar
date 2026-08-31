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
from merve_solar.config import (
    BASE_FEATURES_PATH,
    CITIES,
    CITY_TO_ID,
    DAYLIGHT_REFERENCE_COLUMN,
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
from merve_solar.mc_dropout import mc_dropout_predict, pooled_summary
from merve_solar.metrics import (
    TARGET_CI_COVERAGE,
    compute_metric_subsets,
    compute_metrics_for_subset,
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
    "experiment_id", "model_family", "training_scope", "excluded_cities",
    "lookback_hours", "horizon_hours", "window_stride", "n_features",
    "hidden_sizes", "dropout_rate", "city_embedding_dim",
    "train_ratio", "val_ratio",
    "n_bootstrap", "bootstrap_block_length", "mc_dropout_passes",
    "batch_size", "learning_rate", "lr_reduce_factor", "lr_reduce_patience",
    "max_epochs", "early_stop_patience",
    "loss_function", "huber_delta", "nonneg_penalty_weight",
    "target_transform", "loss_daylight_only", "per_city_scaler",
    "clamp_night_to_zero", "conformal_mode", "seed", "device",
    "RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS",
    "n_samples", "n_elements",
    "RMSE_daylight", "MAE_daylight", "R2_daylight", "CP_daylight", "n_elements_daylight",
    "best_val_loss", "hit_max_epochs", "n_models_trained", "training_time_sec",
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
            "The non-LSTM families (climatology, persistence, smart_persistence) are not trained "
            "at all -- they are scored through the same windows and metrics by "
            "scripts/03_run_naive_baselines.py, which writes their ledger rows directly. "
            "Running this config would train an LSTM and label the row "
            f"{config.model_family!r}."
        )


def _append_ledger_row(row: dict) -> None:
    if tuple(row) != LEDGER_COLUMNS:
        raise ValueError(f"ledger row keys do not match LEDGER_COLUMNS: {set(row) ^ set(LEDGER_COLUMNS)}")
    assert_ledger_schema_ok()
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_row = pd.DataFrame([row], columns=list(LEDGER_COLUMNS))
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


def _ledger_row(config, subsets: dict, run_stats: dict, training_time_sec: float) -> dict:
    """Pure function over a finished run -- unit-testable without training anything."""
    agg = subsets["all_hours"]["aggregate"]
    day = subsets.get("daylight", {}).get("aggregate", {})
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
        "dropout_rate": config.dropout_rate,
        "city_embedding_dim": config.city_embedding_dim,
        "train_ratio": config.train_ratio,
        "val_ratio": config.val_ratio,
        "n_bootstrap": config.n_bootstrap,
        "bootstrap_block_length": config.bootstrap_block_length,
        "mc_dropout_passes": config.mc_dropout_passes,
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
        "target_transform": config.target_transform,
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
        # The model-selection criterion, in SCALED target space. Comparable ONLY between runs
        # that share loss_function/huber_delta, loss_daylight_only, target_transform, and the
        # same pooled provinces (which fix the scaler): it is the right instrument for "same
        # data, same criterion, different architecture" and meaningless across anything else.
        # target_transform matters most of all -- a clearsky_index run's loss is in units of the
        # clearness index, so its 0.28 and a raw run's 0.14 are not on the same axis at all. Never a substitute for
        # the test metrics next to it -- it exists so architecture can be chosen without them.
        "best_val_loss": _mean_best_val_loss(run_stats),
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


def _conformalize(pooled_preds, dist, calibration, layout, config, city_id_test, daylight,
                  exp_dir, log_lines) -> dict:
    """Fit the conformal grid on the validation split and apply it to the test distribution.

    Returns the rescaled summary; `pooled_preds` is rescaled in place so CRPS describes the same
    distribution the interval metrics do. Everything written here is a small CSV, so unlike the
    npz dumps it syncs through git and the grid itself is a publishable table.
    """
    val = layout["val"]
    # Saved before anything is fitted, so the choice of grid geometry can later be redone on the
    # CALIBRATION split alone. Selecting a mode from test-split behaviour would be test-set
    # selection; with this file the same comparison runs on validation, where it is honest.
    # Gitignored with the other npz dumps, so it lives only where the run ran.
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
    after = _rescaled_summary(dist, factors)
    _conformal_effect_frame(
        layout["test"]["y"], daylight, city_id_test, config.active_cities, dist, after, factors
    ).to_csv(exp_dir / "metrics" / "conformal_effect.csv", index=False)

    apply_conformal(pooled_preds, dist["mean"], factors)
    after["conformal_k"] = factors
    day_k = factors[daylight]
    log_lines.append(
        f"conformal_mode={config.conformal_mode} alpha={CONFORMAL_ALPHA} "
        f"pooled_k={grid.pooled_factor:.4f} (n={grid.pooled_n}) "
        f"daylight k in [{day_k.min():.4f}, {day_k.max():.4f}] mean {day_k.mean():.4f}; "
        f"{grid.n_invalid} calibration elements dropped for a degenerate half-width"
    )
    return after


def _plot_representative_forecasts(pooled_preds, y_true, city_id_test, config, exp_dir) -> None:
    horizon_axis = np.arange(1, config.horizon_hours + 1)
    for city in config.active_cities:
        mask = city_id_test == CITY_TO_ID[city]
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


def _save_test_predictions(exp_dir, dist, y_true, city_id, daylight, window_start,
                           conformal_factors=None) -> None:
    """Summary of the predictive distribution, for the paired significance tests.

    Stores mean/lower/upper rather than the full (S, N, horizon) sample, which is ~3.4 GB at
    full fidelity; this is ~12 MB compressed. Gitignored alongside the .pt checkpoints.

    Takes the already-computed summary rather than re-deriving it, so what is saved is
    bit-identical to what was scored -- including any conformal rescaling, which is applied to
    the summary and to the sample but would be lost by a second summarise of a sample this
    function does not receive.

    `conformal_factors` is that rescaling, saved alongside so the file stays INVERTIBLE. Without
    it a reader cannot tell a corrected interval from an uncorrected one and will silently apply
    a second correction on top of the first -- which is exactly what happened to the first run of
    scripts/08_conformal_mode_selection.py. (N, horizon) float32, ~4 MB, 1.0 wherever nothing was
    corrected.
    """
    payload = dict(
        mean=dist["mean"], lower=dist["lower"], upper=dist["upper"],
        y_true=y_true, city_id=city_id, daylight=daylight,
        window_start=window_start.astype("datetime64[h]").astype(np.int64),
    )
    if conformal_factors is not None:
        payload["conformal_k"] = conformal_factors
    np.savez_compressed(exp_dir / "metrics" / "test_predictions.npz", **payload)


def apply_target_transform(base_df: pd.DataFrame, config) -> pd.DataFrame:
    """The frame the MODEL is fitted on. The layout frame is never transformed.

    Under target_transform="clearsky_index" the target column becomes the clearness index
    kt = ALLSKY / CLRSKY, so the scaler, the windows, the loss and every early-stopping decision
    downstream all happen in kt space with no further changes. Night (CLRSKY = 0) is defined to
    0 rather than left undefined; it is multiplied back by CLRSKY = 0 anyway, which makes the
    night output exactly zero by construction -- a stronger statement than clamp_night_to_zero,
    which is then a no-op rather than a correction.

    Returns base_df itself under "raw", so the default path allocates nothing.
    """
    if config.target_transform == "raw":
        return base_df
    clear = base_df[DAYLIGHT_REFERENCE_COLUMN].to_numpy()
    day = clear > 0
    out = base_df.copy()
    out[TARGET_COLUMN] = np.where(day, base_df[TARGET_COLUMN].to_numpy() / np.where(day, clear, 1.0), 0.0)
    return out


def invert_target_transform(pooled_preds: np.ndarray, config, clearsky_test: np.ndarray) -> np.ndarray:
    """Bring predictions back to W/m^2, in place.

    The scope runners already undid the StandardScaler, so under "clearsky_index" what arrives
    here is kt and the remaining step is the multiplication by the target hour's clear-sky
    value. clearsky_test is (N, horizon), broadcast over the S pooled samples.
    """
    if config.target_transform == "raw":
        return pooled_preds
    if clearsky_test.shape != pooled_preds.shape[1:]:
        raise ValueError(
            f"clear-sky array is {clearsky_test.shape}, expected {pooled_preds.shape[1:]}"
        )
    pooled_preds *= clearsky_test[None, :, :]
    return pooled_preds


def invert_summary_transform(summary: dict, config, clearsky: np.ndarray) -> dict:
    """invert_target_transform for a (N, horizon) distribution SUMMARY rather than the sample.

    Valid for every key because the clear-sky multiplication is affine with a non-negative
    factor: it maps the mean to the transformed mean and each percentile to the transformed
    percentile. `std` scales by the same factor and is kept only for diagnostics.
    """
    if config.target_transform == "raw":
        return summary
    return {k: v * clearsky for k, v in summary.items()}


def _predict_replicas(splits, config, n_cities, device, exp_dir, checkpoint_stem,
                      seed_base, rng, log_prefix, log_lines, calibrate=False):
    """Train n_bootstrap replicas on `splits` and MC-Dropout predict the test split.

    Returns ((n_bootstrap * mc_dropout_passes, N_test, horizon) float32, SCALED units), an
    optional calibration-split summary, and run statistics. The destination array is
    preallocated rather than built by appending and concatenating, which would double a 3.4 GB
    allocation at full fidelity.

    `calibrate=True` additionally predicts the VALIDATION split, pooled over the same B*T passes,
    for the conformal layer. The replicas are held in memory for that second pass (8 models of
    at most ~848k parameters is ~27 MB, against a ~2.5 GB pooled validation sample it avoids)
    and the summary is taken chunk by chunk, so peak memory is unchanged in practice. Summarising
    in SCALED units is exact: the inverse scaler and the clear-sky multiplication are both affine
    and non-decreasing, so a percentile of the transformed sample equals the transform of the
    percentile.
    """
    passes, replicas = config.mc_dropout_passes, config.n_bootstrap
    n_test = splits["test"]["y"].shape[0]
    out = np.empty((replicas * passes, n_test, config.horizon_hours), dtype=np.float32)
    hit_cap = 0
    best_val_losses = []
    models = []

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
        if calibrate:
            models.append(model)
        at_cap = len(history) >= config.max_epochs
        hit_cap += int(at_cap)
        best = _best_val_loss(history)
        best_val_losses.append(best)
        # best_val_loss FIRST because it is the one that describes the returned model; last_val_loss
        # is kept beside it because the gap between the two, together with best_epoch, is how far
        # training ran past its own optimum -- and because every log written before this change
        # reported the last one, so old and new logs stay readable against each other.
        log_lines.append(
            f"{log_prefix}replica {b}: best_val_loss={best:.4f} "
            f"best_epoch={min(history, key=lambda h: h['val_loss'])['epoch']} "
            f"last_val_loss={history[-1]['val_loss']:.4f} epochs={len(history)}"
            + ("  WARNING: hit max_epochs" if at_cap else "")
        )
        if not calibrate:
            del model

    calibration = None
    if calibrate:
        calibration = pooled_summary(
            models, splits["val"]["X"], splits["val"]["city_id"], passes,
            config.horizon_hours, device=device,
        )
        log_lines.append(
            f"{log_prefix}calibration pass: {splits['val']['y'].shape[0]} validation windows "
            f"x {replicas * passes} pooled predictions"
        )
        models.clear()

    return out, calibration, {"hit_max_epochs": hit_cap, "n_models": replicas,
                              "best_val_losses": best_val_losses}


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
    splits, scaler = _fit_scale_window(
        base_df, config, train_end, val_end, None, exp_dir / "checkpoints" / "scaler.joblib"
    )
    if not np.array_equal(splits["test"]["window_start"], layout["test"]["window_start"]):
        raise RuntimeError("scaled and unscaled window builds disagree on the test-set windows")
    for name, d in splits.items():
        log_lines.append(f"{name}: {d['y'].shape[0]} windows")

    # n_cities is len(CITIES), NOT len(active_cities): the embedding table keeps a row per
    # province so that city_id values are never renumbered by an exclusion and checkpoints stay
    # comparable across runs. An excluded province's row simply never receives a gradient.
    calibrate = config.conformal_mode != "none"
    if calibrate and not np.array_equal(splits["val"]["window_start"], layout["val"]["window_start"]):
        raise RuntimeError("scaled and unscaled window builds disagree on the validation windows")
    pooled_scaled, calibration, stats = _predict_replicas(
        splits, config, len(CITIES), device, exp_dir, "bootstrap_model",
        seed_base=config.seed + 1, rng=np.random.default_rng(config.seed),
        log_prefix="", log_lines=log_lines, calibrate=calibrate,
    )
    out = inverse_transform_target(scaler, pooled_scaled)
    del pooled_scaled
    if calibration is not None:
        calibration = {k: inverse_transform_target(scaler, v) for k, v in calibration.items()}
    return out, calibration, stats


def _run_per_city_scope(base_df, config, train_end, val_end, layout, device, exp_dir, log_lines):
    """Train an independent model set per city, then assemble into the pooled test layout."""
    n_pooled = config.n_bootstrap * config.mc_dropout_passes
    layout_test, layout_val = layout["test"], layout["val"]
    pooled = np.full((n_pooled, layout_test["y"].shape[0], config.horizon_hours), np.nan, dtype=np.float32)
    filled = np.zeros(layout_test["y"].shape[0], dtype=bool)
    hit_cap = 0
    best_val_losses = []
    calibrate = config.conformal_mode != "none"
    # Assembled into the pooled VALIDATION layout exactly as the test predictions are, so the
    # conformal grid is fitted on the same province ordering it will be applied in.
    calibration = None if not calibrate else {
        k: np.full((layout_val["y"].shape[0], config.horizon_hours), np.nan, dtype=np.float32)
        for k in ("mean", "std", "lower", "upper")
    }

    # With per_city_scaler=False the pooled scaler is fitted once and shared, so the arms differ
    # only in what each model was trained on, not in how the target was normalised.
    shared_scaler = None
    if not config.per_city_scaler:
        shared_scaler = fit_scaler(base_df, train_end)
        save_scaler(shared_scaler, exp_dir / "checkpoints" / "scaler.joblib")
        log_lines.append("per_city_scaler=False: all provinces share the pooled scaler")

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
        slot = np.flatnonzero(layout_test["city_id"] == city_idx)
        _assert_city_block_aligned(city, splits["test"], layout_test, slot)
        val_slot = np.flatnonzero(layout_val["city_id"] == city_idx)
        if calibrate:
            _assert_city_block_aligned(city, splits["val"], layout_val, val_slot, split="val")
        for name, d in splits.items():
            log_lines.append(f"{city}/{name}: {d['y'].shape[0]} windows")

        # Seeds must not collide across cities, or two cities would share weight inits and
        # bootstrap draws. Documented alongside the global seed+b+1 scheme in methodology 13.3.
        scaled_preds, city_calibration, stats = _predict_replicas(
            _zero_city_ids(splits), config, 1, device, exp_dir, f"bootstrap_model_{city}",
            seed_base=config.seed + 1 + city_idx * config.n_bootstrap,
            rng=np.random.default_rng([config.seed, city_idx]),
            log_prefix=f"{city} ", log_lines=log_lines, calibrate=calibrate,
        )
        pooled[:, slot, :] = inverse_transform_target(city_scaler, scaled_preds)
        if city_calibration is not None:
            for key, value in city_calibration.items():
                calibration[key][val_slot] = inverse_transform_target(city_scaler, value)
        filled[slot] = True
        hit_cap += stats["hit_max_epochs"]
        # Pooled flat across (city, replica): the ledger's best_val_loss is then the mean over all
        # 5B models. With per_city_scaler=True each city's loss is in its OWN scaled space, so the
        # mean is a summary of this arm's fit, not a quantity comparable to a global-arm row.
        best_val_losses.extend(stats["best_val_losses"])
        del scaled_preds

    if not filled.all():
        raise RuntimeError(f"per_city assembly left {int((~filled).sum())} test windows unfilled")
    if np.isnan(pooled).any():
        raise RuntimeError("per_city assembly produced NaN predictions")
    if calibration is not None and any(np.isnan(v).any() for v in calibration.values()):
        raise RuntimeError("per_city assembly left validation windows unfilled")
    return pooled, calibration, {"hit_max_epochs": hit_cap,
                                 "n_models": config.n_bootstrap * len(config.active_cities),
                                 "best_val_losses": best_val_losses}


SCOPE_RUNNERS = {"global": _run_global_scope, "per_city": _run_per_city_scope}


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
    # CLRSKY at the target hours is gathered on every run, not only the clearsky_index ones:
    # it is an additive (N, horizon) output that changes no other array, ~4 MB, and gathering it
    # unconditionally means the layout is provably identical across target_transform arms.
    layout = build_experiment_windows(base_df, config, train_end, val_end, include_X=False,
                                      extra_target_columns=(DAYLIGHT_REFERENCE_COLUMN,))
    y_true = layout["test"]["y"]
    daylight = layout["test"]["daylight"]
    city_id_test = layout["test"]["city_id"]

    device = get_device()
    log_lines = [
        f"device={device}",
        f"training_scope={config.training_scope} model_family={config.model_family}",
        f"loss_function={config.loss_function}",
        f"active_cities={config.active_cities} excluded={config.excluded_cities}",
        f"train_end={train_end} val_end={val_end}",
        f"test daylight elements: {int(daylight.sum())} of {daylight.size}",
    ]

    pooled_preds, calibration, run_stats = SCOPE_RUNNERS[config.training_scope](
        apply_target_transform(base_df, config), config, train_end, val_end, layout,
        device, exp_dir, log_lines
    )
    pooled_preds = invert_target_transform(
        pooled_preds, config, layout["test"]["extras"][DAYLIGHT_REFERENCE_COLUMN]
    )
    if calibration is not None:
        calibration = invert_summary_transform(
            calibration, config, layout["val"]["extras"][DAYLIGHT_REFERENCE_COLUMN]
        )
    log_lines.append(f"target_transform={config.target_transform}")

    if config.clamp_night_to_zero:
        # Applied once here rather than inside each scope runner, so every arm gets it
        # identically. `daylight` is CLRSKY > 0, i.e. pure solar geometry, so this asserts a
        # known physical fact rather than fitting anything: below the horizon the target is
        # exactly 0. Done in place to avoid duplicating a multi-GB array.
        night = ~daylight
        pooled_preds[:, night] = 0.0
        log_lines.append(f"clamped {int(night.sum())} night elements to zero")

    # The conformal layer rescales the predictive distribution about its own mean, so the
    # summary has to exist BEFORE the rescaling (it supplies the centre) and the rescaled summary
    # is then derived analytically rather than re-sorted -- the map is affine and increasing, so
    # the percentiles of the rescaled sample ARE the rescaled percentiles, and deriving them
    # keeps the whole run to a single sort of the multi-GB array. The sample itself is still
    # rescaled in place, because CRPS is the one metric that reads it rather than the summary.
    dist = summarize_predictive_distribution(pooled_preds)
    conformal_factors = None
    if calibration is not None:
        dist = _conformalize(pooled_preds, dist, calibration, layout, config,
                             city_id_test, daylight, exp_dir, log_lines)
        conformal_factors = dist.pop("conformal_k")

    subsets = compute_metric_subsets(
        pooled_preds, y_true, city_id_test, config.active_cities, daylight=daylight, dist=dist
    )

    summary_df = results_summary_dataframe(subsets)
    horizon_df = results_by_horizon_dataframe(subsets)
    summary_df.to_csv(exp_dir / "metrics" / "results_summary.csv", index=False)
    horizon_df.to_csv(exp_dir / "metrics" / "results_by_horizon.csv", index=False)
    _save_test_predictions(exp_dir, dist, y_true, city_id_test, daylight,
                           layout["test"]["window_start"], conformal_factors)

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

    _append_ledger_row(
        _ledger_row(config, subsets, {**run_stats, "device": device}, training_time_sec)
    )
    return subsets
