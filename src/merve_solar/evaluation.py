"""Trained networks -> scored predictive distribution, streamed chunk by chunk over windows.

The pooled sample is (B*T, N, horizon): 3.4 GB at B=8, T=100 and 7 GB at B=16, so it is never
materialised. Each chunk of windows is predicted by every network, mapped to W/m^2, night-clamped,
optionally conformally rescaled, and reduced to its summary (mean/std/2.5/97.5 percentiles) and
per-element CRPS before the next chunk starts. Every statistic is per element, so chunking is
exact, not an approximation. Validation and test go through the same function, which is what
makes the validation numbers used for tuning the same objects as the test numbers reported.
"""
from dataclasses import dataclass

import numpy as np

from merve_solar.conformal import apply_conformal
from merve_solar.mc_dropout import deterministic_predict, mc_dropout_predict
from merve_solar.metrics import crps_per_element, summarize_predictive_distribution
from merve_solar.scaling import inverse_transform_target

# Elements (S * windows * horizon) per chunk: ~128 MB of float32 plus a sort copy.
EVAL_CHUNK_ELEMENTS = 32_000_000

SUMMARY_KEYS = ("mean", "std", "lower", "upper")


@dataclass
class EvaluationPart:
    """One set of networks and the windows it predicts.

    The global scope is one part covering every window; the per-city scope is one part per
    province. `X`/`city_id` are what the networks expect (zeroed ids for a one-province model);
    `slot` says where row i of X lands in the pooled layout.
    """
    models: list
    X: dict          # split name -> (n, lookback, features), scaled
    city_id: dict    # split name -> (n,)
    slot: dict       # split name -> (n,) positions in the pooled layout
    scaler: object


def draws_per_network(config) -> int:
    return 1 if config.inference_mode == "deterministic" else config.mc_dropout_passes


def predict_samples(models, X, city_id, config, device) -> np.ndarray:
    """(len(models) * draws_per_network, n, horizon), scaled units, network-major order.

    Network-major order is what lets the first k networks' samples be read off as a B=k run.
    """
    if config.inference_mode == "deterministic":
        return np.concatenate([deterministic_predict(m, X, city_id, device=device) for m in models])
    return np.concatenate([mc_dropout_predict(m, X, city_id, config.mc_dropout_passes, device=device)
                           for m in models])


def evaluate_split(parts, split: str, layout_split: dict, config, device, factors=None,
                   chunk_elements: int = EVAL_CHUNK_ELEMENTS):
    """Summary and per-element CRPS of the pooled predictive sample for one split, in W/m^2.

    Returns (before, crps): `before` is the summary BEFORE any conformal rescaling (the layer
    needs it as its centre and for the before/after table); `crps` describes the sample that is
    actually scored, i.e. after the rescaling when `factors` is given.
    """
    y, daylight = layout_split["y"], layout_split["daylight"]
    n, horizon = y.shape
    before = {k: np.full((n, horizon), np.nan, dtype=np.float32) for k in SUMMARY_KEYS}
    crps = np.full((n, horizon), np.nan, dtype=np.float64)
    filled = np.zeros(n, dtype=bool)

    for part in parts:
        slot = part.slot[split]
        s = len(part.models) * draws_per_network(config)
        step = max(1, chunk_elements // max(1, s * horizon))
        for start in range(0, len(slot), step):
            stop = min(start + step, len(slot))
            sel = slot[start:stop]
            scaled = predict_samples(part.models, part.X[split][start:stop],
                                     part.city_id[split][start:stop], config, device)
            samples = inverse_transform_target(part.scaler, scaled)
            del scaled
            if config.clamp_night_to_zero:
                # Geometry, not fitting: below the horizon the target is exactly 0.
                samples[:, ~daylight[sel]] = 0.0
            summary = summarize_predictive_distribution(samples)
            if factors is not None:
                apply_conformal(samples, summary["mean"], factors[sel])
            crps[sel] = crps_per_element(samples, y[sel])
            for key in SUMMARY_KEYS:
                before[key][sel] = summary[key]
            filled[sel] = True

    if not filled.all():
        raise RuntimeError(f"{split}: {int((~filled).sum())} windows were not predicted by any part")
    if np.isnan(crps).any() or any(np.isnan(v).any() for v in before.values()):
        raise RuntimeError(f"{split}: NaN in the predictive summary")
    return before, crps


# --- ensemble-size curves -----------------------------------------------------------------------

CURVE_COLUMNS = ("split", "inference_mode", "B", "T", "n_elements", "RMSE", "MAE", "bias", "CP",
                 "PINW", "MPIW", "CRPS")


def _linear_percentile(sorted_samples: np.ndarray, q: float) -> np.ndarray:
    """np.percentile(method='linear') along axis 0 of an already-sorted array."""
    pos = q / 100.0 * (sorted_samples.shape[0] - 1)
    lo = int(np.floor(pos))
    hi = min(lo + 1, sorted_samples.shape[0] - 1)
    frac = pos - lo
    return sorted_samples[lo] * (1.0 - frac) + sorted_samples[hi] * frac


def _accumulate(acc: dict, samples: np.ndarray, y: np.ndarray) -> None:
    """Add one chunk's daylight sums for a (S, m) sample against (m,) truth. One sort serves the
    interval and CRPS."""
    s = samples.shape[0]
    mean = samples.mean(axis=0, dtype=np.float64)
    err = mean - y
    srt = np.sort(samples, axis=0)
    lower, upper = _linear_percentile(srt, 2.5), _linear_percentile(srt, 97.5)
    weights = (2 * np.arange(1, s + 1, dtype=np.float64) - s - 1)[:, None]
    crps = (np.abs(samples - y[None]).mean(axis=0, dtype=np.float64)
            - (weights * srt).sum(axis=0, dtype=np.float64) / s**2)
    acc["n"] += y.size
    acc["sum_error"] += float(err.sum())
    acc["sum_abs_error"] += float(np.abs(err).sum())
    acc["sum_sq_error"] += float((err**2).sum())
    acc["n_covered"] += int(((y >= lower) & (y <= upper)).sum())
    acc["sum_width"] += float((upper - lower).sum(dtype=np.float64))
    acc["sum_crps"] += float(crps.sum())


def ensemble_curves(models, X, city_id, y, daylight, scaler, b_grid, t_grid, device, split,
                    chunk_windows: int = 1000) -> list[dict]:
    """Daylight metrics of every sub-ensemble (first B networks x first T passes) of one run.

    Each network predicts max(T) MC-Dropout passes and one deterministic pass per chunk; every
    (B, T) cell is a slice of those, so the whole grid costs one prediction of the largest cell.
    The first B networks of a run ARE a B-network run with the same seed (experiment
    ._train_replicas), so a cell is the run that config would have produced, up to the
    MC-Dropout draws. Daylight only: night elements are clamped to an exact zero and carry no
    information about ensemble size. No conformal correction is applied.
    """
    b_grid, t_grid = sorted(b_grid), sorted(t_grid)
    if b_grid[-1] > len(models):
        raise ValueError(f"B grid goes to {b_grid[-1]} but the run has {len(models)} networks")
    t_max = t_grid[-1]
    keys = ([("mc_dropout", b, t) for b in b_grid for t in t_grid]
            + [("deterministic", b, 1) for b in b_grid])
    acc = {k: dict(n=0, sum_error=0.0, sum_abs_error=0.0, sum_sq_error=0.0, n_covered=0,
                   sum_width=0.0, sum_crps=0.0) for k in keys}
    models = models[: b_grid[-1]]

    for start in range(0, len(X), chunk_windows):
        stop = min(start + chunk_windows, len(X))
        mask = daylight[start:stop]
        if not mask.any():
            continue
        yd = y[start:stop][mask].astype(np.float64)
        mc = np.stack([
            inverse_transform_target(scaler, mc_dropout_predict(m, X[start:stop], city_id[start:stop],
                                                                t_max, device=device))[:, mask]
            for m in models
        ])  # (B, T, m)
        det = np.stack([
            inverse_transform_target(scaler, deterministic_predict(m, X[start:stop],
                                                                   city_id[start:stop], device=device))[0][mask]
            for m in models
        ])  # (B, m)
        for b in b_grid:
            for t in t_grid:
                _accumulate(acc[("mc_dropout", b, t)], mc[:b, :t].reshape(b * t, -1), yd)
            _accumulate(acc[("deterministic", b, 1)], det[:b], yd)

    y_day = y[daylight]
    y_range = float(y_day.max() - y_day.min())
    rows = []
    for (mode, b, t), a in acc.items():
        n = a["n"]
        rows.append({
            "split": split, "inference_mode": mode, "B": b, "T": t, "n_elements": n,
            "RMSE": np.sqrt(a["sum_sq_error"] / n), "MAE": a["sum_abs_error"] / n,
            "bias": a["sum_error"] / n, "CP": a["n_covered"] / n,
            "PINW": a["sum_width"] / n / y_range, "MPIW": a["sum_width"] / n,
            "CRPS": a["sum_crps"] / n,
        })
    return rows
