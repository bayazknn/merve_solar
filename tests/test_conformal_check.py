import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar.conformal import apply_conformal
from merve_solar.conformal_check import (check_run, cross_fit_factors, fold_labels, half_pairwise,
                                         rescaled_crps)
from merve_solar.metrics import crps_per_element, summarize_predictive_distribution


def _windows(n, start="2024-09-03"):
    return pd.date_range(start, periods=n, freq="h").to_numpy()


def test_rescaled_crps_matches_crps_of_the_rescaled_sample():
    rng = np.random.default_rng(0)
    samples = rng.normal(300, 40, size=(200, 500)).astype(np.float32)
    y = rng.normal(300, 80, size=500)
    k = rng.uniform(0.5, 2.5, size=500)
    mean = samples.mean(axis=0, dtype=np.float64)
    expected = crps_per_element(apply_conformal(samples[:, :, None].copy(), mean[:, None].astype(np.float32),
                                                k[:, None].astype(np.float32)), y[:, None])[:, 0]
    got = rescaled_crps(samples, mean, y, k, half_pairwise(samples))
    np.testing.assert_allclose(got, expected, rtol=1e-4, atol=1e-3)


def test_k_of_one_reproduces_the_raw_crps():
    rng = np.random.default_rng(1)
    samples = rng.gamma(4, 50, size=(100, 300)).astype(np.float32)
    y = rng.gamma(4, 50, size=300)
    got = rescaled_crps(samples, samples.mean(0, dtype=np.float64), y, np.ones(300), half_pairwise(samples))
    np.testing.assert_allclose(got, crps_per_element(samples, y), rtol=1e-5, atol=1e-4)


@pytest.mark.parametrize("scheme", ["alternating_months", "leave_one_season_out"])
def test_no_window_is_scored_by_factors_fitted_on_its_own_fold(scheme):
    # Residuals are 1x the half-width in odd months and 3x in even months (and so across
    # seasons), so a fold that saw itself would get its own k; a cross-fitted one gets the other.
    n, horizon = 24 * 300, 2
    starts = _windows(n)
    months = pd.to_datetime(starts).month.to_numpy()
    scale = np.where(months % 2 == 1, 1.0, 3.0)[:, None] * np.ones((1, horizon))
    mean = np.full((n, horizon), 500.0)
    lower, upper = mean - 10, mean + 10
    rng = np.random.default_rng(2)
    y = mean + rng.choice([-1, 1], size=(n, horizon)) * scale * 10 * rng.uniform(0, 1, (n, horizon))
    daylight = np.ones((n, horizon), dtype=bool)
    city_id = np.zeros(n, dtype=np.int64)
    factors, log = cross_fit_factors(y, mean, lower, upper, city_id, daylight, starts, "global", scheme)
    labels, names = fold_labels(starts, scheme)
    assert {r["fold"] for r in log} == set(names.values())
    for label in names:
        rows = labels == label
        own = cross_fit_factors(y[rows], mean[rows], lower[rows], upper[rows], city_id[rows],
                                daylight[rows], starts[rows], "global", "in_sample")[0]
        if scheme == "alternating_months":
            # The two folds have different residual scales, so cross-fitting must differ.
            assert not np.allclose(factors[rows], own)


def test_in_sample_coverage_is_nominal_and_cross_fit_is_not_better():
    rng = np.random.default_rng(3)
    n, horizon, S = 24 * 250, 3, 60
    starts = _windows(n)
    city_id = rng.integers(0, 5, size=n)
    centre = rng.uniform(100, 800, size=(n, horizon))
    samples3 = centre[None] + rng.normal(0, 20, size=(S, n, horizon))
    y = centre + rng.normal(0, 60, size=(n, horizon))
    daylight = np.ones((n, horizon), dtype=bool)
    tables = check_run(samples3.reshape(S, -1).astype(np.float32), y, daylight, city_id, starts,
                       modes=("global",), schemes=("alternating_months", "in_sample"))
    scores = tables["scores"].set_index(["mode", "scheme"])
    assert scores.loc[("none", "none"), "CP"] < 0.8          # raw intervals under-cover
    assert abs(scores.loc[("global", "in_sample"), "CP"] - 0.95) < 0.005
    assert abs(scores.loc[("global", "alternating_months"), "CP"] - 0.95) < 0.02
    # The summary the check uses is the pipeline's own.
    summ = summarize_predictive_distribution(samples3.astype(np.float32))
    assert np.isclose(tables["groups"].query("mode == 'none' and axis == 'city'")["n"].sum(), n * horizon)
    assert summ["lower"].shape == (n, horizon)
    assert set(tables["month_k"]["city"]) >= {"all"}
