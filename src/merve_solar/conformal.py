"""Split-conformal recalibration of the predictive distribution.

WHY THIS EXISTS. The pooled Bootstrap x MC-Dropout sample contains only EPISTEMIC spread --
where the model's own mean might sit -- while the interval is scored on whether it contains the
OBSERVATION, which additionally carries the residual (aleatoric) term. Nothing in the pipeline
ever reconciles the two, so coverage is whatever that mismatch happens to produce, and it is
measured to break on three independent axes that do not correct one another (ABLATION.md 3.5,
4.6, 6.5): fidelity B, model capacity, and the target formulation. Under `raw` the interval
comes out too WIDE (daylight CP 0.977) and under `clearsky_index` too NARROW (0.928) at an
identical MPIW/RMSE ratio, so the required correction is signed differently per arm and a single
scalar multiplier fitted on one of them is wrong on the other.

THE FORM OF THE CORRECTION. This module rescales the predictive distribution about its own mean,

    x  ->  m + k * (x - m),

with one k per grid cell. That is deliberately a statement about the DISTRIBUTION, not about the
interval: because the map is affine and increasing, the 2.5/97.5 percentiles of the rescaled
sample are exactly the rescaled percentiles, so CP/PINW/MPIW/CWC and CRPS all stay mutually
coherent, and the mean is unchanged so RMSE/MAE/R^2 are untouched by construction. The
alternative (CQR-style additive shifts of the two interval endpoints) recalibrates the interval
while leaving CRPS describing an uncorrected distribution, which would put two incompatible
objects in one ledger row.

k is then directly readable: k < 1 means the epistemic spread was too wide for the residuals,
k > 1 that it was too narrow. It is the number the write-up wants.

CONFORMITY SCORE. For one calibration element, the smallest k that would have covered y is

    s = (y - m) / (U - m)   if y >= m,      (m - y) / (m - L)   otherwise,

so k is the (1-alpha) split-conformal quantile of {s_i} over the cell -- the
ceil((n+1)(1-alpha))-th smallest, the finite-sample correction that makes the coverage guarantee
exact rather than asymptotic. The score is one-sided on purpose: only the half-width the
observation actually fell outside of has to be well defined, which drops fewer elements than the
symmetric max-form and is identical to it wherever both half-widths are positive.

NIGHT IS NEVER CALIBRATED AND NEVER CORRECTED. Below the horizon m = L = U = 0 and y = 0, so the
score is 0/0; those elements carry no information about interval width and are excluded from the
fit and left at k = 1. This holds whether or not clamp_night_to_zero is on.

WHAT THIS DOES NOT FIX -- state both in the paper.

1. The calibration set is the validation split, which the models ALSO early-stopped on. That is
   a genuine exchangeability violation. It is a weak one (early stopping selects a single integer
   -- the epoch -- from the mean loss over 32,315 windows), but it is not nothing, and the clean
   version needs a calibration split that no training decision touched.
2. The validation split spans 2024-06-27 -> 2025-03-24: 269 days covering ten months, MISSING
   APRIL AND MAY, while the test split covers all twelve. Its daylight fraction is 0.489 against
   the test split's 0.515, i.e. the calibration set is winter-weighted relative to what it
   calibrates. k is a RATIO of residual scale to interval scale and both scale together with the
   season, so it is far more stationary than either -- but that is an argument, and
   `month_stability_table` turns it into a measurement.

The identified upgrade path is jackknife+-after-bootstrap: each replica's moving-block resample
leaves out-of-bag windows that replica never saw, which would put the calibration set inside the
five-year training period and remove the seasonal hole entirely. It needs B > 1 and calibrates
single-replica rather than ensemble intervals, so it is a separate piece of work.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from merve_solar.config import CITIES, CITY_TO_ID

# "none" is the default and the behaviour every ledger row before this module was produced under.
# The other four are nested granularities of the same grid, which is what makes the claim "a
# scalar factor cannot work" testable rather than asserted: they are fitted from one identical
# set of calibration predictions and differ only in how that set is partitioned.
CONFORMAL_MODES = ("none", "global", "per_horizon", "per_city",
                   "city_horizon", "per_season", "city_season")

# Meteorological seasons, keyed on the month of the window START. The target hours sit 24-47 h
# later, so at most two days of a season boundary land in the neighbouring cell out of ~90 --
# immaterial next to the effect being captured, and using the window's own identity keeps the
# cell assignment independent of the horizon step.
#
# The season axis is here because it was MEASURED to dominate the two that were originally
# proposed. Refitting k month by month on three finished B=1 runs gives a 1.7x-2.0x swing
# (June-July 0.74-1.10, February-April 1.35-1.68): cloud variability, and with it the residual
# scale, is seasonal while the epistemic spread is not. Against that, the horizon axis is null
# -- `city_horizon` reproduces `per_city` to three decimals in every province of every run --
# and the city axis matters for conditional coverage but not for the level.
SEASON_OF_MONTH = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3}
SEASON_NAMES = ("DJF", "MAM", "JJA", "SON")

_CITY_MODES = ("per_city", "city_horizon", "city_season")
_HORIZON_MODES = ("per_horizon", "city_horizon")
_SEASON_MODES = ("per_season", "city_season")

# Below this many usable calibration elements a cell falls back to its parent (city_horizon ->
# the pooled fit; likewise for the coarser modes). Well above the ~19 the finite-sample quantile
# formally needs, because stride-1 windows overlap by 47 of 48 hours: a cell's ~3,200 elements
# are worth roughly 3,200/24 independent observations, so the quantile estimate is much noisier
# than the raw count suggests.
MIN_CELL_N = 200

# Guards a half-width that has collapsed to zero. At 800 pooled samples a daylight half-width is
# ~2 standard deviations, so this only ever fires on degenerate elements.
_EPS = 1e-6


def conformity_scores(y: np.ndarray, mean: np.ndarray, lower: np.ndarray,
                      upper: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The smallest k that would have covered each element, plus a validity mask.

    Elements whose relevant half-width is ~0 carry no information about how the interval should
    be scaled (any k covers, or none does) and are reported invalid rather than silently
    contributing an inf.
    """
    above = y >= mean
    num = np.where(above, y - mean, mean - y).astype(np.float64)
    den = np.where(above, upper - mean, mean - lower).astype(np.float64)
    valid = den > _EPS
    scores = np.full(np.shape(y), np.nan, dtype=np.float64)
    np.divide(num, den, out=scores, where=valid)
    return scores, valid


def conformal_factor(scores: np.ndarray, alpha: float) -> tuple[float, int]:
    """(k, n): the ceil((n+1)(1-alpha))-th smallest score, and how many were used.

    When (n+1)(1-alpha) exceeds n the requested coverage is not certifiable from this many
    points and the widest observed score is returned -- the most conservative value available.
    MIN_CELL_N keeps that from happening in practice; it is handled rather than raised because a
    run over a short test period should still produce a table.
    """
    s = np.asarray(scores, dtype=np.float64)
    s = s[np.isfinite(s)]
    n = int(s.size)
    if n == 0:
        return float("nan"), 0
    rank = int(np.ceil((n + 1) * (1.0 - alpha)))
    if rank > n:
        return float(s.max()), n
    return float(np.partition(s, rank - 1)[rank - 1]), n


def _cell_keys(mode: str, city_id: np.ndarray, horizon: int,
               window_start: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(N, horizon) integer planes for the two grid axes.

    The first is the province (or a constant), the second is whichever of horizon step / season
    the mode uses (or a constant). Two axes are enough because no mode crosses horizon with
    season: the horizon axis was measured to carry nothing once the city axis is in, so a
    three-way grid would only thin the cells.
    """
    if mode not in CONFORMAL_MODES or mode == "none":
        raise ValueError(f"mode must be one of {CONFORMAL_MODES[1:]}, got {mode!r}")
    zeros = np.zeros((city_id.size, horizon), dtype=np.int64)
    city_plane = np.repeat(city_id[:, None], horizon, axis=1) if mode in _CITY_MODES else zeros

    if mode in _HORIZON_MODES:
        time_plane = np.repeat(np.arange(1, horizon + 1)[None, :], city_id.size, axis=0)
    elif mode in _SEASON_MODES:
        if window_start is None:
            raise ValueError(f"mode {mode!r} needs window_start to assign each window a season")
        months = pd.to_datetime(np.asarray(window_start)).month.to_numpy()
        codes = np.array([SEASON_OF_MONTH[int(m)] for m in months], dtype=np.int64)
        time_plane = np.repeat(codes[:, None], horizon, axis=1)
    else:
        time_plane = zeros
    return city_plane, time_plane


@dataclass
class ConformalGrid:
    """The fitted correction: one k per cell, plus the pooled fallback and the audit counts."""
    mode: str
    alpha: float
    factors: dict[tuple[int, int], float] = field(default_factory=dict)
    counts: dict[tuple[int, int], int] = field(default_factory=dict)
    pooled_factor: float = 1.0
    pooled_n: int = 0
    n_invalid: int = 0

    def factor_for(self, city: int, time_key: int) -> float:
        """The cell's k, or the pooled one when the cell is absent or too small to trust."""
        key = (int(city), int(time_key))
        if self.counts.get(key, 0) >= MIN_CELL_N:
            return self.factors[key]
        return self.pooled_factor

    def factor_array(self, city_id: np.ndarray, daylight: np.ndarray,
                     window_start: np.ndarray | None = None) -> np.ndarray:
        """(N, horizon) multiplier: the cell's k on daylight elements, exactly 1.0 at night."""
        horizon = daylight.shape[1]
        city_plane, time_plane = _cell_keys(self.mode, city_id, horizon, window_start)
        out = np.ones(daylight.shape, dtype=np.float32)
        for city in np.unique(city_plane):
            for time_key in np.unique(time_plane):
                cell = (city_plane == city) & (time_plane == time_key) & daylight
                if cell.any():
                    out[cell] = self.factor_for(city, time_key)
        return out

    def to_frame(self) -> pd.DataFrame:
        """Paper-facing table: a few hundred bytes, so unlike the npz dumps it is committed."""
        id_to_city = {i: c for c, i in CITY_TO_ID.items()}
        rows = []
        for key in sorted(set(self.factors) | set(self.counts)):
            city, time_key = key
            n = self.counts.get(key, 0)
            k = self.factors.get(key, float("nan"))
            used = k if n >= MIN_CELL_N else self.pooled_factor
            rows.append({
                "mode": self.mode,
                "city": id_to_city.get(city, "all") if self.mode in _CITY_MODES else "all",
                "horizon_step": time_key if self.mode in _HORIZON_MODES else "all",
                "season": SEASON_NAMES[time_key] if self.mode in _SEASON_MODES else "all",
                "n_calibration": n,
                "k_cell": k,
                "k_applied": used,
                "fell_back": bool(n < MIN_CELL_N),
                # What the interval width is multiplied by is k itself (both half-widths scale),
                # so this column exists only to state the direction without arithmetic.
                "direction": "narrower" if used < 1 else ("wider" if used > 1 else "unchanged"),
            })
        frame = pd.DataFrame(rows)
        frame.attrs["pooled_factor"] = self.pooled_factor
        return frame


def fit_conformal_grid(y: np.ndarray, mean: np.ndarray, lower: np.ndarray, upper: np.ndarray,
                       city_id: np.ndarray, daylight: np.ndarray, mode: str,
                       alpha: float, window_start: np.ndarray | None = None) -> ConformalGrid:
    """Fit k per cell on the CALIBRATION split. Daylight elements only -- see the module docstring."""
    if mode not in CONFORMAL_MODES or mode == "none":
        raise ValueError(f"fit_conformal_grid needs a real mode, got {mode!r}")
    scores, valid = conformity_scores(y, mean, lower, upper)
    usable = valid & daylight
    grid = ConformalGrid(mode=mode, alpha=alpha,
                         n_invalid=int((daylight & ~valid).sum()))
    grid.pooled_factor, grid.pooled_n = conformal_factor(scores[usable], alpha)

    city_plane, time_plane = _cell_keys(mode, city_id, daylight.shape[1], window_start)
    for city in np.unique(city_plane):
        for time_key in np.unique(time_plane):
            cell = usable & (city_plane == city) & (time_plane == time_key)
            k, n = conformal_factor(scores[cell], alpha)
            grid.factors[(int(city), int(time_key))] = k
            grid.counts[(int(city), int(time_key))] = n
    return grid


def apply_conformal(pooled_preds: np.ndarray, mean: np.ndarray, factors: np.ndarray,
                    chunk_elements: int = 16_000_000) -> np.ndarray:
    """x -> m + k(x - m), in place, chunked over the window axis.

    In place because the pooled array is ~3.4 GB at full fidelity. The mean is preserved exactly
    (the map is affine and centred on it), which is what keeps RMSE/MAE/R^2 identical to the
    uncorrected run -- asserted in the tests, because a conformal layer that moved the point
    forecast would silently change the headline accuracy numbers too.
    """
    if mean.shape != pooled_preds.shape[1:] or factors.shape != pooled_preds.shape[1:]:
        raise ValueError(
            f"mean {mean.shape} and factors {factors.shape} must both be {pooled_preds.shape[1:]}"
        )
    n_samples, n_windows, horizon = pooled_preds.shape
    m32 = mean.astype(pooled_preds.dtype, copy=False)
    k32 = factors.astype(pooled_preds.dtype, copy=False)
    step = max(1, chunk_elements // max(1, n_samples * horizon))
    for start in range(0, n_windows, step):
        stop = min(start + step, n_windows)
        block = pooled_preds[:, start:stop, :]
        block -= m32[start:stop]
        block *= k32[start:stop]
        block += m32[start:stop]
    return pooled_preds


def month_stability_table(y: np.ndarray, mean: np.ndarray, lower: np.ndarray, upper: np.ndarray,
                          daylight: np.ndarray, window_start: np.ndarray,
                          alpha: float) -> pd.DataFrame:
    """k refitted month by month on the calibration split.

    The threat this measures: the validation split misses April and May and is winter-weighted,
    so a k fitted on it is applied to two months it never saw. If k is flat across the ten months
    that ARE present, the hole is benign and the paper can say so with a number instead of an
    argument. If it is not flat, the conformal layer needs a season-aware grid -- which this
    calibration set cannot supply, and which is then a finding rather than a silent error.
    """
    scores, valid = conformity_scores(y, mean, lower, upper)
    usable = valid & daylight
    months = pd.to_datetime(window_start).month
    month_plane = np.repeat(np.asarray(months)[:, None], daylight.shape[1], axis=1)
    rows = []
    for month in range(1, 13):
        cell = usable & (month_plane == month)
        if not cell.any():
            continue
        k, n = conformal_factor(scores[cell], alpha)
        rows.append({"month": month, "n_calibration": int(n), "k": k})
    return pd.DataFrame(rows)
