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

from merve_solar.config import CITY_TO_ID, SECONDARY_AGGREGATE_EXCLUDES

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


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Coefficient of determination against the subset's own mean.

    NaN when the subset's target is constant (SS_tot = 0), which is the honest answer rather
    than an infinity. Caveat for the write-up: over all 24 hours R^2 looks excellent purely
    because the day/night swing dominates total variance -- a climatological lookup table
    scores 0.923 there against 0.856 on daylight hours alone. Report the daylight value.
    """
    ss_res = float(np.sum((y_true - y_pred) ** 2, dtype=np.float64))
    ss_tot = float(np.sum((y_true - y_true.mean(dtype=np.float64)) ** 2, dtype=np.float64))
    if ss_tot <= 0:
        return float("nan")
    return 1.0 - ss_res / ss_tot


def _slice_dist(dist: dict, key) -> dict:
    return {name: value[key] for name, value in dist.items()}


def compute_metrics_for_subset(
    pooled_preds: np.ndarray,
    y_true: np.ndarray,
    element_mask: np.ndarray | None = None,
    dist: dict | None = None,
) -> dict:
    """Metrics for one group of windows, optionally restricted to selected elements.

    `dist` may be passed in already computed (and already row-sliced to this group). Every
    statistic in it is computed independently per (window, horizon) element, so slicing a
    hoisted summary is exactly equal to recomputing it on the slice -- which also guarantees
    that the all-hours and daylight rows differ only by the mask, not by a re-sort.

    `element_mask` is (N, horizon) and selects individual (window, horizon-step) pairs. Under
    a mask everything flattens: all the scalar metrics reduce over every axis anyway, and
    empirical_crps reshapes to (S, -1).
    """
    dist = summarize_predictive_distribution(pooled_preds) if dist is None else dist

    if element_mask is None:
        y, mean = y_true, dist["mean"]
        lower, upper, preds = dist["lower"], dist["upper"], pooled_preds
        n_samples = int(y_true.shape[0])
    else:
        y, mean = y_true[element_mask], dist["mean"][element_mask]
        lower, upper = dist["lower"][element_mask], dist["upper"][element_mask]
        preds = pooled_preds[:, element_mask]
        n_samples = int(element_mask.any(axis=1).sum())

    if y.size == 0:
        return {k: float("nan") for k in
                ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "CRPS")} | {
                "n_samples": 0, "n_elements": 0}

    cp = coverage_probability(y, lower, upper)
    pinw = prediction_interval_normalized_width(y, lower, upper)
    return {
        "RMSE": rmse(y, mean),
        "MAE": mae(y, mean),
        "R2": r2(y, mean),
        "CP": cp,
        "PINW": pinw,
        "MPIW": mean_prediction_interval_width(lower, upper),
        "Reliability": reliability(cp),
        "CWC": coverage_width_criterion(pinw, cp),
        "CRPS": empirical_crps(preds, y),
        "n_samples": n_samples,
        "n_elements": int(y.size),
    }


def compute_all_metrics(
    pooled_preds: np.ndarray,
    y_true: np.ndarray,
    city_id: np.ndarray,
    cities: list,
    element_mask: np.ndarray | None = None,
    dist: dict | None = None,
) -> dict:
    """pooled_preds: (S, N, horizon); y_true/city_id: (N, horizon)/(N,).

    Returns {'aggregate', 'aggregate_excl', 'per_city', 'per_horizon'}.
    """
    dist = summarize_predictive_distribution(pooled_preds) if dist is None else dist

    def _subset(rows=None, step=None):
        if rows is not None:
            return compute_metrics_for_subset(
                pooled_preds[:, rows, :], y_true[rows],
                None if element_mask is None else element_mask[rows], _slice_dist(dist, rows))
        sl = slice(step, step + 1)
        return compute_metrics_for_subset(
            pooled_preds[:, :, sl], y_true[:, sl],
            None if element_mask is None else element_mask[:, sl],
            {k: v[:, sl] for k, v in dist.items()})

    result = {"aggregate": compute_metrics_for_subset(pooled_preds, y_true, element_mask, dist)}

    # City ids come from the frame via CITY_TO_ID and are NEVER renumbered, so `cities` here is
    # a list of provinces to REPORT, not an index mapping. Using enumerate() instead would
    # mis-assign every city after a gap whenever `cities` is a subset (a run excluding Rize
    # would score Van's windows under the label "Rize" and drop Van from the table entirely).
    keep = np.ones(len(city_id), dtype=bool)
    for city in cities:
        if city in SECONDARY_AGGREGATE_EXCLUDES:
            keep &= city_id != CITY_TO_ID[city]
    # If the secondary-aggregate province is not in `cities` at all (a run that already excluded
    # it), the row would be a byte-for-byte duplicate of Aggregate -- omit it rather than emit a
    # second copy of the same numbers under a name that implies a contrast.
    excluded = [c for c in cities if c in SECONDARY_AGGREGATE_EXCLUDES]
    result["aggregate_excl"] = _subset(rows=keep) if (excluded and keep.any()) else None
    result["aggregate_excl_label"] = "Aggregate_excl_" + "_".join(excluded) if excluded else None

    result["per_city"] = {
        city: _subset(rows=(city_id == CITY_TO_ID[city]))
        for city in cities
        if (city_id == CITY_TO_ID[city]).any()
    }
    result["per_horizon"] = {h + 1: _subset(step=h) for h in range(y_true.shape[1])}
    return result


def compute_metric_subsets(
    pooled_preds: np.ndarray,
    y_true: np.ndarray,
    city_id: np.ndarray,
    cities: list,
    daylight: np.ndarray | None = None,
) -> dict:
    """Both reporting subsets: {'all_hours': ..., 'daylight': ...}.

    The predictive distribution is summarised ONCE and shared, so the two subsets are
    guaranteed to come from bit-identical mean/lower/upper and to differ only by the mask.
    `daylight` is the (N, horizon) bool array built from clear-sky irradiance in windows.py.
    """
    dist = summarize_predictive_distribution(pooled_preds)
    subsets = {"all_hours": compute_all_metrics(pooled_preds, y_true, city_id, cities, None, dist)}
    if daylight is not None:
        subsets["daylight"] = compute_all_metrics(pooled_preds, y_true, city_id, cities, daylight, dist)
    return subsets


def results_summary_dataframe(metric_subsets: dict) -> pd.DataFrame:
    """One row per (subset, group): Aggregate, the Rize-excluded aggregate, then each city."""
    rows = []
    for subset, m in metric_subsets.items():
        rows.append({"group": "Aggregate", "subset": subset, **m["aggregate"]})
        if m.get("aggregate_excl") is not None:
            rows.append({"group": m["aggregate_excl_label"], "subset": subset, **m["aggregate_excl"]})
        for city, cm in m["per_city"].items():
            rows.append({"group": city, "subset": subset, **cm})
    return pd.DataFrame(rows)


def results_by_horizon_dataframe(metric_subsets: dict) -> pd.DataFrame:
    rows = [
        {"horizon_step": h, "subset": subset, **hm}
        for subset, m in metric_subsets.items()
        for h, hm in m["per_horizon"].items()
    ]
    return pd.DataFrame(rows).sort_values(["subset", "horizon_step"]).reset_index(drop=True)
