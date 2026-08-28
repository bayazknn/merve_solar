"""Point-forecast and UQ metrics — aggregate, per-city, per-horizon.

CP/PINW match the methodology doc's exact formulas (percentile-based CI, not
mean+-1.96*std). MPIW/CWC/Reliability/CRPS extend to match the source paper's
Table 11 reporting format; the paper gives no explicit formulas for these four,
so standard literature definitions are used (Reliability = |CP-target|, which
matches the paper's own reported PCNN value of 0.0028 = |0.9472-0.95| exactly;
CWC is the standard Khosravi coverage-width criterion; CRPS uses the standard
O(S log S) sorted-sample estimator for a finite predictive sample).
"""
import numpy as np
import pandas as pd

TARGET_CI_COVERAGE = 0.95


# Block sizes for the chunked reductions below, in array elements (S * columns). The pooled
# prediction array is ~3.4 GB at the default B=8 x T=100; np.percentile and the CRPS estimator
# both allocate a full-size copy, which is what exhausted memory on the first full run. Chunking
# over the window axis bounds that copy without changing any result.
CHUNK_ELEMENTS = 16_000_000


def summarize_predictive_distribution(pooled_preds: np.ndarray, chunk_elements: int = CHUNK_ELEMENTS) -> dict:
    """pooled_preds: (n_samples, N, horizon) -> mean/std/lower/upper, each (N, horizon).

    Reductions run independently per (window, horizon) element, so chunking over the window
    axis is exact, not an approximation. Percentiles are taken in one call rather than two so
    the block is sorted once.
    """
    n_samples, n_windows, horizon = pooled_preds.shape
    out = {k: np.empty((n_windows, horizon), dtype=np.float32) for k in ("mean", "std", "lower", "upper")}
    step = max(1, chunk_elements // max(1, n_samples * horizon))

    for start in range(0, n_windows, step):
        stop = min(start + step, n_windows)
        block = pooled_preds[:, start:stop, :]
        out["mean"][start:stop] = block.mean(axis=0, dtype=np.float64)
        out["std"][start:stop] = block.std(axis=0, dtype=np.float64)
        lower, upper = np.percentile(block, [2.5, 97.5], axis=0)
        out["lower"][start:stop] = lower
        out["upper"][start:stop] = upper
    return out


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def coverage_probability(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    inside = (y_true >= lower) & (y_true <= upper)
    return float(inside.mean())


def mean_prediction_interval_width(lower: np.ndarray, upper: np.ndarray) -> float:
    return float((upper - lower).mean())


def prediction_interval_normalized_width(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    y_range = y_true.max() - y_true.min()
    if y_range <= 0:
        return float("nan")
    return float((upper - lower).mean() / y_range)


def reliability(cp: float, target: float = TARGET_CI_COVERAGE) -> float:
    return float(abs(cp - target))


def coverage_width_criterion(pinw: float, cp: float, target: float = TARGET_CI_COVERAGE, eta: float = 50.0) -> float:
    penalty = 1.0 if cp < target else 0.0
    return float(pinw * (1 + penalty * np.exp(-eta * (cp - target))))


def empirical_crps(pooled_preds: np.ndarray, y_true: np.ndarray, chunk_elements: int = CHUNK_ELEMENTS) -> float:
    """CRPS(F, y) = E|X-y| - 0.5*E|X-X'|, X,X' ~ F, estimated from a finite sample.

    Uses the O(S log S) rearrangement E|X-X'| = (2/S^2) * sum_i (2i-S-1)*x_(i)
    (sorted ascending) instead of the naive O(S^2) pairwise sum.
    """
    S = pooled_preds.shape[0]
    flat_preds = pooled_preds.reshape(S, -1)
    flat_y = y_true.reshape(-1)
    n_cols = flat_y.size
    if n_cols == 0:
        return float("nan")

    weights = (2 * np.arange(1, S + 1, dtype=np.float64) - S - 1).reshape(-1, 1)
    step = max(1, chunk_elements // max(1, S))
    total = 0.0  # float64 accumulator: a float32 running sum over ~1e6 columns loses 3-4 digits

    for start in range(0, n_cols, step):
        stop = min(start + step, n_cols)
        preds_block = flat_preds[:, start:stop]
        term1 = np.abs(preds_block - flat_y[None, start:stop]).mean(axis=0, dtype=np.float64)
        sorted_block = np.sort(preds_block, axis=0)
        half_pairwise = (weights * sorted_block).sum(axis=0, dtype=np.float64) / (S**2)
        total += float((term1 - half_pairwise).sum())

    return float(total / n_cols)


def compute_metrics_for_subset(pooled_preds: np.ndarray, y_true: np.ndarray) -> dict:
    dist = summarize_predictive_distribution(pooled_preds)
    cp = coverage_probability(y_true, dist["lower"], dist["upper"])
    pinw = prediction_interval_normalized_width(y_true, dist["lower"], dist["upper"])
    return {
        "RMSE": rmse(y_true, dist["mean"]),
        "MAE": mae(y_true, dist["mean"]),
        "CP": cp,
        "PINW": pinw,
        "MPIW": mean_prediction_interval_width(dist["lower"], dist["upper"]),
        "Reliability": reliability(cp),
        "CWC": coverage_width_criterion(pinw, cp),
        "CRPS": empirical_crps(pooled_preds, y_true),
        "n_samples": int(y_true.shape[0]),
    }


def compute_all_metrics(pooled_preds: np.ndarray, y_true: np.ndarray, city_id: np.ndarray, cities: list) -> dict:
    """pooled_preds: (S, N, horizon); y_true/city_id: (N, horizon)/(N,)."""
    result = {"aggregate": compute_metrics_for_subset(pooled_preds, y_true)}

    per_city = {}
    for idx, city in enumerate(cities):
        mask = city_id == idx
        if mask.sum() == 0:
            continue
        per_city[city] = compute_metrics_for_subset(pooled_preds[:, mask, :], y_true[mask])
    result["per_city"] = per_city

    per_horizon = {}
    for h in range(y_true.shape[1]):
        per_horizon[h + 1] = compute_metrics_for_subset(pooled_preds[:, :, h : h + 1], y_true[:, h : h + 1])
    result["per_horizon"] = per_horizon

    return result


def results_summary_dataframe(all_metrics: dict) -> pd.DataFrame:
    rows = [{"group": "Aggregate", **all_metrics["aggregate"]}]
    for city, m in all_metrics["per_city"].items():
        rows.append({"group": city, **m})
    return pd.DataFrame(rows)


def results_by_horizon_dataframe(all_metrics: dict) -> pd.DataFrame:
    rows = [{"horizon_step": h, **m} for h, m in all_metrics["per_horizon"].items()]
    return pd.DataFrame(rows).sort_values("horizon_step").reset_index(drop=True)
