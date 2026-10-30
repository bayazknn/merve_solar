"""Choose the conformal grid on the VALIDATION split alone, by cross-fitting inside it.

Post-correction coverage on the split k was fitted on is ~0.95 by construction, and scoring on
test would select a hyperparameter on test. So each candidate mode is fitted on some validation
windows and scored on the others, and every window is scored exactly once by factors that never
saw it:

  alternating_months    fit on odd months, score on even, and the reverse. Both folds hold
                        every season the split has, so this measures GEOMETRY: does a finer grid
                        (city_horizon) fix conditional coverage, or only add noise?
  leave_one_season_out  fit on the other seasons, score on the held-out one. This stands in for
                        the transfer the test set really demands (a calibration set with no full
                        summer applied to two summers), so it measures SEASONAL TRANSFER error.
  in_sample             fit and score on all of validation. Reported only to show the optimism
                        a fitted coverage has; never a selection criterion.

Folds are whole windows. Neighbouring windows overlap by up to 47 h, so a fold boundary leaks at
most two days of shared hours into the other fold, out of a month.

Everything is computed from the daylight elements of one pooled sample per run. The rescaling
x -> m + k(x - m) is affine and increasing, so the rescaled interval is [m + k(L - m),
m + k(U - m)] exactly, and the rescaled CRPS is

    CRPS_k = E|m + k(X - m) - y| - k * (1/2) E|X - X'|,

whose second term is computed once per element. No mode or fold needs a second prediction.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from merve_solar.config import CITY_TO_ID
from merve_solar.metrics import TARGET_CI_COVERAGE
from merve_solar.conformal import SEASON_NAMES, SEASON_OF_MONTH, fit_conformal_grid

ALPHA = 1.0 - TARGET_CI_COVERAGE
CHECK_MODES = ("global", "per_city", "per_horizon", "city_horizon")
SCHEMES = ("alternating_months", "leave_one_season_out", "in_sample")
# Elements per chunk when the rescaled CRPS is computed; ~200 MB of float32 at S=600.
_CHUNK = 80_000


def fold_labels(window_start: np.ndarray, scheme: str) -> tuple[np.ndarray, dict[int, str]]:
    """(per-window fold label, {label: name}). in_sample is one fold scored on itself."""
    months = pd.to_datetime(np.asarray(window_start)).month.to_numpy()
    if scheme == "alternating_months":
        return (months % 2).astype(np.int64), {1: "odd months", 0: "even months"}
    if scheme == "leave_one_season_out":
        labels = np.array([SEASON_OF_MONTH[int(m)] for m in months], dtype=np.int64)
        return labels, {int(s): SEASON_NAMES[s] for s in np.unique(labels)}
    if scheme == "in_sample":
        return np.zeros(months.size, dtype=np.int64), {0: "all"}
    raise ValueError(f"scheme must be one of {SCHEMES}, got {scheme!r}")


def cross_fit_factors(y, mean, lower, upper, city_id, daylight, window_start, mode, scheme,
                      alpha=ALPHA) -> tuple[np.ndarray, list[dict]]:
    """(N, horizon) factors, each window's from a grid fitted without its fold, plus a fold log."""
    labels, names = fold_labels(window_start, scheme)
    factors = np.ones(daylight.shape, dtype=np.float64)
    log = []
    for label, name in names.items():
        score_rows = labels == label
        fit_rows = score_rows if scheme == "in_sample" else ~score_rows
        grid = fit_conformal_grid(y[fit_rows], mean[fit_rows], lower[fit_rows], upper[fit_rows],
                                  city_id[fit_rows], daylight[fit_rows], mode, alpha)
        applied = grid.factor_array(city_id[score_rows], daylight[score_rows])
        factors[score_rows] = applied
        day_k = applied[daylight[score_rows]]
        log.append({"mode": mode, "scheme": scheme, "fold": name,
                    "n_fit": int(daylight[fit_rows].sum()),
                    "n_score": int(daylight[score_rows].sum()),
                    "pooled_k": grid.pooled_factor,
                    "k_min": float(day_k.min()) if day_k.size else np.nan,
                    "k_max": float(day_k.max()) if day_k.size else np.nan})
    return factors, log


def half_pairwise(samples: np.ndarray) -> np.ndarray:
    """(1/2) E|X - X'| per column of an (S, n) sample, by the sorted-weights identity."""
    S = samples.shape[0]
    weights = (2 * np.arange(1, S + 1, dtype=np.float64) - S - 1).reshape(-1, 1)
    out = np.empty(samples.shape[1], dtype=np.float64)
    for start in range(0, samples.shape[1], _CHUNK):
        block = np.sort(samples[:, start:start + _CHUNK], axis=0)
        out[start:start + _CHUNK] = (weights * block).sum(axis=0, dtype=np.float64) / S**2
    return out


def rescaled_crps(samples: np.ndarray, mean: np.ndarray, y: np.ndarray, k: np.ndarray,
                  half_pair: np.ndarray) -> np.ndarray:
    """Per-element CRPS of the sample rescaled about its mean by k; all inputs daylight-flat."""
    out = np.empty(y.size, dtype=np.float64)
    for start in range(0, y.size, _CHUNK):
        sl = slice(start, start + _CHUNK)
        m, kk = mean[sl][None, :], k[sl][None, :]
        term1 = np.abs(m + kk * (samples[:, sl] - m) - y[sl][None, :]).mean(axis=0, dtype=np.float64)
        out[sl] = term1 - k[sl] * half_pair[sl]
    return out


def _deviation(cp: float) -> float:
    return abs(cp - TARGET_CI_COVERAGE)


def score(y, mean, lower, upper, k, crps, city, step, season, y_range) -> tuple[dict, list[dict]]:
    """Summary row and per-group rows for one factor set; every input is daylight-flat."""
    lo, hi = mean + k * (lower - mean), mean + k * (upper - mean)
    inside = (y >= lo) & (y <= hi)
    width = hi - lo
    groups = []
    for axis, values in (("city", city), ("horizon_step", step), ("season", season)):
        for value in np.unique(values):
            sel = values == value
            groups.append({"axis": axis, "group": value, "n": int(sel.sum()),
                           "CP": float(inside[sel].mean()), "MPIW": float(width[sel].mean()),
                           "CRPS": float(crps[sel].mean())})
    frame = pd.DataFrame(groups)
    by_city = frame[frame.axis == "city"].set_index("group")["CP"]
    by_step = frame[frame.axis == "horizon_step"].set_index("group")["CP"]
    worst_city = (by_city - TARGET_CI_COVERAGE).abs().idxmax()
    worst_step = (by_step - TARGET_CI_COVERAGE).abs().idxmax()
    cp = float(inside.mean())
    summary = {"n": int(y.size), "CP": cp, "dev_aggregate": _deviation(cp),
               "dev_worst_province": _deviation(by_city[worst_city]), "worst_province": worst_city,
               "dev_worst_step": _deviation(by_step[worst_step]), "worst_step": int(worst_step),
               "step_CP_spread": float(by_step.max() - by_step.min()),
               "MPIW": float(width.mean()), "PINW": float(width.mean() / y_range),
               "CRPS": float(crps.mean())}
    return summary, groups


def check_run(samples: np.ndarray, y: np.ndarray, daylight: np.ndarray, city_id: np.ndarray,
              window_start: np.ndarray, alpha: float = ALPHA,
              modes=CHECK_MODES, schemes=SCHEMES) -> dict[str, pd.DataFrame]:
    """All tables for one run.

    samples: (S, n_daylight) pooled daylight sample in W/m^2, in row-major order of `daylight`
    (window, then step). y, daylight: (N, horizon). city_id, window_start: (N,).
    """
    from merve_solar.metrics import summarize_predictive_distribution

    n, horizon = daylight.shape
    summ = summarize_predictive_distribution(samples[:, :, None])
    full = {key: np.zeros((n, horizon), dtype=np.float64) for key in ("mean", "lower", "upper")}
    for key in full:
        full[key][daylight] = summ[key][:, 0]
    mean_d, lower_d, upper_d = (full[k][daylight] for k in ("mean", "lower", "upper"))
    y_d = y[daylight].astype(np.float64)

    id_to_city = {i: c for c, i in CITY_TO_ID.items()}
    city_d = np.array([id_to_city[int(c)] for c in np.repeat(city_id[:, None], horizon, 1)[daylight]])
    step_d = np.repeat(np.arange(1, horizon + 1)[None, :], n, 0)[daylight]
    seasons = np.array([SEASON_NAMES[SEASON_OF_MONTH[int(m)]]
                        for m in pd.to_datetime(np.asarray(window_start)).month])
    season_d = np.repeat(seasons[:, None], horizon, 1)[daylight]
    y_range = float(y_d.max() - y_d.min())
    hp = half_pairwise(samples)

    rows, group_rows, fold_rows = [], [], []

    def _add(mode, scheme, k_d):
        crps = rescaled_crps(samples, mean_d, y_d, k_d, hp)
        summary, groups = score(y_d, mean_d, lower_d, upper_d, k_d, crps, city_d, step_d,
                                season_d, y_range)
        rows.append({"mode": mode, "scheme": scheme, **summary})
        group_rows.extend({"mode": mode, "scheme": scheme, **g} for g in groups)

    _add("none", "none", np.ones(y_d.size))
    for mode in modes:
        for scheme in schemes:
            factors, log = cross_fit_factors(y, full["mean"], full["lower"], full["upper"],
                                             city_id, daylight, window_start, mode, scheme, alpha)
            fold_rows.extend(log)
            _add(mode, scheme, factors[daylight])

    month = pd.to_datetime(np.asarray(window_start)).month.to_numpy()
    month_d = np.repeat(month[:, None], horizon, 1)[daylight]
    k_rows = []
    for c in ["all"] + sorted(set(city_d)):
        for m in np.unique(month_d):
            sel = (month_d == m) & ((city_d == c) if c != "all" else True)
            grid = fit_conformal_grid(y_d[sel][:, None], mean_d[sel][:, None],
                                      lower_d[sel][:, None], upper_d[sel][:, None],
                                      np.zeros(int(sel.sum()), dtype=np.int64),
                                      np.ones((int(sel.sum()), 1), dtype=bool), "global", alpha)
            k_rows.append({"city": c, "month": int(m), "n": grid.pooled_n, "k": grid.pooled_factor})

    return {"scores": pd.DataFrame(rows), "groups": pd.DataFrame(group_rows),
            "folds": pd.DataFrame(fold_rows), "month_k": pd.DataFrame(k_rows)}
