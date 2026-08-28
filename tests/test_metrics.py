import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pytest

from merve_solar.metrics import empirical_crps, summarize_predictive_distribution


@pytest.fixture(scope="module")
def pooled_and_truth():
    rng = np.random.default_rng(0)
    pooled = rng.normal(400, 120, size=(60, 500, 24)).astype(np.float32)
    y_true = rng.normal(400, 120, size=(500, 24)).astype(np.float32)
    return pooled, y_true


@pytest.mark.parametrize("key", ["mean", "std", "lower", "upper"])
def test_summarize_is_chunk_size_invariant(pooled_and_truth, key):
    """The chunked reduction must be exact, not an approximation.

    Every statistic is computed independently per (window, horizon) element, so splitting the
    window axis cannot change a result. A chunk of 1 window is the harshest possible split.
    """
    pooled, _ = pooled_and_truth
    one_block = summarize_predictive_distribution(pooled, chunk_elements=10**12)
    per_window = summarize_predictive_distribution(pooled, chunk_elements=1)
    assert np.array_equal(one_block[key], per_window[key])


def test_summarize_matches_unchunked_numpy(pooled_and_truth):
    pooled, _ = pooled_and_truth
    got = summarize_predictive_distribution(pooled)
    assert np.allclose(got["mean"], pooled.mean(axis=0), atol=1e-3)
    assert np.allclose(got["std"], pooled.std(axis=0), atol=1e-3)
    assert np.allclose(got["lower"], np.percentile(pooled, 2.5, axis=0), atol=1e-3)
    assert np.allclose(got["upper"], np.percentile(pooled, 97.5, axis=0), atol=1e-3)


def test_crps_is_chunk_size_invariant(pooled_and_truth):
    pooled, y_true = pooled_and_truth
    one_block = empirical_crps(pooled, y_true, chunk_elements=10**12)
    per_column = empirical_crps(pooled, y_true, chunk_elements=1)
    assert one_block == pytest.approx(per_column, abs=1e-9)


def test_crps_matches_naive_pairwise_estimator():
    """Pins the O(S log S) rearrangement against the O(S^2) definition it replaces."""
    rng = np.random.default_rng(1)
    pooled = rng.normal(400, 120, size=(40, 120, 4)).astype(np.float32)
    y_true = rng.normal(400, 120, size=(120, 4)).astype(np.float32)

    n_samples = pooled.shape[0]
    flat_preds = pooled.reshape(n_samples, -1).astype(np.float64)
    flat_y = y_true.reshape(-1).astype(np.float64)
    term1 = np.abs(flat_preds - flat_y[None, :]).mean(axis=0)
    term2 = np.abs(flat_preds[:, None, :] - flat_preds[None, :, :]).mean(axis=(0, 1))
    naive = float((term1 - 0.5 * term2).mean())

    assert empirical_crps(pooled, y_true) == pytest.approx(naive, abs=1e-6)


def test_crps_of_a_point_forecast_equals_mae():
    """With a single sample the predictive distribution is degenerate and CRPS reduces to MAE.

    This is why the naive baselines (S=1) can report CRPS as a real value rather than NaN.
    """
    rng = np.random.default_rng(2)
    point = rng.normal(400, 120, size=(1, 200, 24)).astype(np.float32)
    y_true = rng.normal(400, 120, size=(200, 24)).astype(np.float32)
    assert empirical_crps(point, y_true) == pytest.approx(
        float(np.abs(y_true - point[0]).mean()), rel=1e-6
    )


def test_crps_empty_subset_is_nan():
    pooled = np.empty((8, 0, 24), dtype=np.float32)
    y_true = np.empty((0, 24), dtype=np.float32)
    assert np.isnan(empirical_crps(pooled, y_true))
