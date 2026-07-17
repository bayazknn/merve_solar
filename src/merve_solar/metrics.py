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


def summarize_predictive_distribution(pooled_preds: np.ndarray) -> dict:
    """pooled_preds: (n_samples, N, horizon) -> mean/std/lower/upper, each (N, horizon)."""
    return {
        "mean": pooled_preds.mean(axis=0),
        "std": pooled_preds.std(axis=0),
        "lower": np.percentile(pooled_preds, 2.5, axis=0),
        "upper": np.percentile(pooled_preds, 97.5, axis=0),
    }


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


def empirical_crps(pooled_preds: np.ndarray, y_true: np.ndarray) -> float:
    """CRPS(F, y) = E|X-y| - 0.5*E|X-X'|, X,X' ~ F, estimated from a finite sample.

    Uses the O(S log S) rearrangement E|X-X'| = (2/S^2) * sum_i (2i-S-1)*x_(i)
    (sorted ascending) instead of the naive O(S^2) pairwise sum.
    """
    S = pooled_preds.shape[0]
    flat_preds = pooled_preds.reshape(S, -1)
    flat_y = y_true.reshape(-1)

    term1 = np.mean(np.abs(flat_preds - flat_y[None, :]), axis=0)

    sorted_preds = np.sort(flat_preds, axis=0)
    i = np.arange(1, S + 1).reshape(-1, 1)
    weights = 2 * i - S - 1
    half_pairwise = (weights * sorted_preds).sum(axis=0) / (S**2)  # already the 0.5-scaled term

    return float(np.mean(term1 - half_pairwise))


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
