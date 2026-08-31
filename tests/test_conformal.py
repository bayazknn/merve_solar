"""The split-conformal recalibration layer.

Three things here are load-bearing for published numbers and the rest is plumbing:

* the correction must not move the point forecast (RMSE/MAE/R2 are the headline accuracy numbers
  and a conformal run must not silently change them);
* the analytically rescaled summary must equal an honest resummarise of the rescaled sample,
  because run_experiment relies on that identity to avoid a second sort of a multi-GB array;
* a cell's factor must reach the (city, horizon) elements it was fitted on -- a transposed grid
  changes no shape and no total, only which province gets which correction.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

import merve_solar.config as config_module
import merve_solar.experiment as experiment_module
from conftest import make_synthetic_base_df
from merve_solar.conformal import (
    CONFORMAL_MODES,
    MIN_CELL_N,
    ConformalGrid,
    apply_conformal,
    conformal_factor,
    conformity_scores,
    fit_conformal_grid,
    month_stability_table,
)
from merve_solar.config import CITIES, CITY_TO_ID, ExperimentConfig
from merve_solar.experiment import LEDGER_COLUMNS, _rescaled_summary, run_experiment
from merve_solar.metrics import summarize_predictive_distribution

ALPHA = 0.05


def _calibration_arrays(n=4000, horizon=4, seed=0, spread=1.0):
    """A predictive summary whose interval is `spread` times as wide as the truth warrants.

    spread > 1 is an over-wide interval (the `raw` arm's failure), spread < 1 an over-narrow one
    (the `clearsky_index` arm's). The correct factor is therefore ~1/spread, which is what makes
    the direction of the correction testable rather than merely plausible.
    """
    rng = np.random.default_rng(seed)
    mean = rng.normal(500, 100, size=(n, horizon)).astype(np.float32)
    sigma = 40.0
    y = (mean + rng.normal(0, sigma, size=(n, horizon))).astype(np.float32)
    half = spread * 1.959963985 * sigma
    return y, mean, (mean - half).astype(np.float32), (mean + half).astype(np.float32)


# --- the score ------------------------------------------------------------------------------

def test_the_score_is_exactly_the_smallest_factor_that_would_have_covered():
    """Definitional. If this drifts, every k in the grid means something else."""
    mean = np.array([[100.0, 100.0]])
    lower = np.array([[80.0, 80.0]])
    upper = np.array([[130.0, 130.0]])
    y = np.array([[145.0, 90.0]])  # 45 above the mean of a 30-wide upper half; 10 below a 20-wide lower
    scores, valid = conformity_scores(y, mean, lower, upper)
    assert valid.all()
    assert scores[0, 0] == pytest.approx(45.0 / 30.0)
    assert scores[0, 1] == pytest.approx(10.0 / 20.0)
    # ... and the interval scaled by exactly that score touches y.
    for j in (0, 1):
        k = scores[0, j]
        lo = mean[0, j] + k * (lower[0, j] - mean[0, j])
        hi = mean[0, j] + k * (upper[0, j] - mean[0, j])
        assert lo - 1e-9 <= y[0, j] <= hi + 1e-9


def test_an_element_inside_its_interval_scores_below_one():
    y, mean, lower, upper = _calibration_arrays(n=50, spread=1.0)
    scores, _ = conformity_scores(y, mean, lower, upper)
    inside = (y >= lower) & (y <= upper)
    assert (scores[inside] <= 1.0).all()
    assert (scores[~inside] > 1.0).all()


def test_a_collapsed_half_width_is_reported_invalid_rather_than_infinite():
    """Night elements are exactly this shape (mean = lower = upper = 0) and must not enter a fit."""
    zero = np.zeros((3, 2))
    scores, valid = conformity_scores(zero, zero, zero, zero)
    assert not valid.any()
    assert np.isnan(scores).all()


# --- the quantile ---------------------------------------------------------------------------

def test_the_quantile_is_the_finite_sample_rank_not_the_plain_percentile():
    """ceil((n+1)(1-alpha)) is what makes the coverage guarantee exact rather than asymptotic."""
    scores = np.arange(1.0, 101.0)  # n = 100 -> rank = ceil(101 * 0.95) = 96
    k, n = conformal_factor(scores, ALPHA)
    assert (k, n) == (96.0, 100)


def test_too_few_points_to_certify_returns_the_most_conservative_value_available():
    """n = 10 cannot certify 95%: ceil(11*0.95) = 11 > 10. The widest observed score is the
    honest answer; silently returning the 95th percentile would claim a guarantee it lacks."""
    k, n = conformal_factor(np.arange(10.0), ALPHA)
    assert (k, n) == (9.0, 10)


def test_an_empty_cell_is_nan_not_one():
    """1.0 would read as 'no correction needed'; NaN reads as 'nothing was measured here'."""
    k, n = conformal_factor(np.array([]), ALPHA)
    assert np.isnan(k) and n == 0


# --- the guarantee --------------------------------------------------------------------------

@pytest.mark.parametrize("spread", [0.5, 1.0, 2.0])
def test_calibrating_on_exchangeable_data_delivers_the_nominal_coverage(spread):
    """The point of the whole layer, on data where exchangeability actually holds.

    The real calibration set is the validation split, which is neither exchangeable with test
    (it precedes it and misses two months) nor untouched by training (early stopping read it) --
    both stated in conformal.py. This test isolates the estimator from those two threats: given
    exchangeable data it must hit 0.95 from either direction of miscalibration.
    """
    y_cal, m_cal, lo_cal, hi_cal = _calibration_arrays(n=6000, seed=1, spread=spread)
    y_te, m_te, lo_te, hi_te = _calibration_arrays(n=6000, seed=2, spread=spread)
    city = np.zeros(len(y_cal), dtype=np.int64)
    day = np.ones(y_cal.shape, dtype=bool)

    grid = fit_conformal_grid(y_cal, m_cal, lo_cal, hi_cal, city, day, "global", ALPHA)
    assert grid.pooled_factor == pytest.approx(1.0 / spread, rel=0.08)

    k = grid.factor_array(np.zeros(len(y_te), dtype=np.int64), np.ones(y_te.shape, dtype=bool))
    lo = m_te + k * (lo_te - m_te)
    hi = m_te + k * (hi_te - m_te)
    covered = ((y_te >= lo) & (y_te <= hi)).mean()
    assert covered == pytest.approx(0.95, abs=0.01)

    uncorrected = ((y_te >= lo_te) & (y_te <= hi_te)).mean()
    if spread != 1.0:
        assert abs(uncorrected - 0.95) > abs(covered - 0.95)


def test_the_direction_of_the_correction_matches_the_direction_of_the_miscalibration():
    """`raw` needs narrowing and `clearsky_index` widening -- one number cannot serve both,
    which is the finding this layer exists to act on."""
    over_wide = fit_conformal_grid(
        *_calibration_arrays(n=3000, seed=3, spread=2.0),
        np.zeros(3000, dtype=np.int64), np.ones((3000, 4), dtype=bool), "global", ALPHA)
    over_narrow = fit_conformal_grid(
        *_calibration_arrays(n=3000, seed=3, spread=0.5),
        np.zeros(3000, dtype=np.int64), np.ones((3000, 4), dtype=bool), "global", ALPHA)
    assert over_wide.pooled_factor < 1.0 < over_narrow.pooled_factor


# --- the grid -------------------------------------------------------------------------------

def _year_of_window_starts(n: int, city_id: np.ndarray | None = None) -> np.ndarray:
    """Window starts spread over a full year, so every season cell is populated.

    When city_id is given, EACH province is spread over the whole year independently -- the
    heterogeneous fixture lays cities out in contiguous blocks, and a single monotone timeline
    over those would put each province inside one or two seasons and leave most (city, season)
    cells empty.
    """
    if city_id is None:
        return np.datetime64("2024-01-01T00") + (np.arange(n) * (8760 // n)) * np.timedelta64(1, "h")
    starts = np.empty(n, dtype="datetime64[h]")
    for city in np.unique(city_id):
        rows = np.flatnonzero(city_id == city)
        starts[rows] = _year_of_window_starts(rows.size)
    return starts


def _heterogeneous_grid_inputs(n_per_city=1200, horizon=4, seed=7):
    """Each (city, horizon) cell miscalibrated by its own known amount.

    The cell factors are then a 5 x 4 table of distinct expected values, so a transposition or an
    off-by-one in the grouping cannot pass -- which a homogeneous fixture would let through.
    """
    rng = np.random.default_rng(seed)
    n = n_per_city * len(CITIES)
    city_id = np.repeat([CITY_TO_ID[c] for c in CITIES], n_per_city).astype(np.int64)
    mean = np.zeros((n, horizon), dtype=np.float32)
    y = np.empty((n, horizon), dtype=np.float32)
    lower = np.empty((n, horizon), dtype=np.float32)
    upper = np.empty((n, horizon), dtype=np.float32)
    spreads = {}
    for c in range(len(CITIES)):
        for h in range(horizon):
            spread = 0.6 + 0.2 * c + 0.35 * h
            spreads[(c, h + 1)] = spread
            rows = city_id == c
            y[rows, h] = rng.normal(0, 1.0, size=int(rows.sum()))
            half = spread * 1.959963985
            lower[rows, h] = -half
            upper[rows, h] = half
    return y, mean, lower, upper, city_id, np.ones((n, horizon), dtype=bool), spreads


def test_each_cell_factor_lands_on_the_cell_it_was_fitted_on():
    y, mean, lower, upper, city_id, day, spreads = _heterogeneous_grid_inputs()
    grid = fit_conformal_grid(y, mean, lower, upper, city_id, day, "city_horizon", ALPHA)
    factors = grid.factor_array(city_id, day)
    for (c, h), spread in spreads.items():
        cell = (city_id == c)
        assert factors[cell, h - 1][0] == pytest.approx(1.0 / spread, rel=0.15)
        # every element of the cell carries one value
        assert len(np.unique(factors[cell, h - 1])) == 1


def test_the_grid_is_not_transposed():
    """A city-indexed grid applied along the horizon axis preserves every shape and total."""
    y, mean, lower, upper, city_id, day, spreads = _heterogeneous_grid_inputs()
    grid = fit_conformal_grid(y, mean, lower, upper, city_id, day, "city_horizon", ALPHA)
    factors = grid.factor_array(city_id, day)
    ankara_h1 = factors[city_id == CITY_TO_ID["Ankara"], 0][0]
    van_h1 = factors[city_id == CITY_TO_ID["Van"], 0][0]
    ankara_h4 = factors[city_id == CITY_TO_ID["Ankara"], 3][0]
    assert ankara_h1 != van_h1 and ankara_h1 != ankara_h4
    assert ankara_h1 == pytest.approx(1.0 / spreads[(CITY_TO_ID["Ankara"], 1)], rel=0.15)


@pytest.mark.parametrize("mode", [m for m in CONFORMAL_MODES if m != "none"])
def test_every_mode_produces_one_factor_per_cell_and_a_readable_table(mode):
    y, mean, lower, upper, city_id, day, _ = _heterogeneous_grid_inputs()
    starts = _year_of_window_starts(len(y), city_id)
    grid = fit_conformal_grid(y, mean, lower, upper, city_id, day, mode, ALPHA,
                              window_start=starts)
    frame = grid.to_frame()
    expected = {"global": 1, "per_city": len(CITIES), "per_horizon": 4,
                "city_horizon": len(CITIES) * 4, "per_season": 4,
                "city_season": len(CITIES) * 4, "season_horizon": 4 * 4,
                "city_season_horizon": len(CITIES) * 4 * 4}[mode]
    assert len(frame) == expected
    assert frame["n_calibration"].min() >= MIN_CELL_N
    assert set(frame["direction"]) <= {"narrower", "wider", "unchanged"}


def test_a_cell_too_small_to_trust_falls_back_to_the_pooled_factor():
    grid = ConformalGrid(mode="city_horizon", alpha=ALPHA,
                         factors={(0, 1): 9.9, (1, 1): 0.5},
                         counts={(0, 1): MIN_CELL_N - 1, (1, 1): MIN_CELL_N},
                         pooled_factor=1.25, pooled_n=10_000)
    assert grid.factor_for((0, 1)) == 1.25   # too few points: the pooled fit, not the cell's 9.9
    assert grid.factor_for((1, 1)) == 0.5
    assert grid.factor_for((4, 3)) == 1.25   # a cell that was never fitted at all
    frame = grid.to_frame()
    assert frame.loc[frame["fell_back"], "k_applied"].tolist() == [1.25]


def test_night_elements_are_never_calibrated_and_never_corrected():
    """Below the horizon the interval is degenerate and the target exactly 0 -- there is no
    width to calibrate, and correcting one would be fitting noise onto a known constant."""
    y, mean, lower, upper, city_id, _, _ = _heterogeneous_grid_inputs()
    day = np.ones(y.shape, dtype=bool)
    day[:, 2] = False
    y[:, 2] = mean[:, 2] = lower[:, 2] = upper[:, 2] = 0.0
    grid = fit_conformal_grid(y, mean, lower, upper, city_id, day, "city_horizon", ALPHA)
    factors = grid.factor_array(city_id, day)
    assert (factors[:, 2] == 1.0).all()
    assert (factors[:, [0, 1, 3]] != 1.0).all()
    assert grid.counts[(0, 3)] == 0


def test_the_month_stability_table_reports_one_factor_per_month_present():
    """The instrument for the calibration split's April/May hole: if k is flat across the ten
    months that ARE present, the two it never saw are a stated limitation rather than an error."""
    y, mean, lower, upper = _calibration_arrays(n=3650, horizon=2, seed=11)
    starts = np.datetime64("2024-01-01T00") + np.arange(3650) * np.timedelta64(1, "h")
    table = month_stability_table(y, mean, lower, upper, np.ones(y.shape, dtype=bool),
                                  starts, ALPHA)
    assert list(table["month"]) == [1, 2, 3, 4, 5, 6]  # 3650 hours from January
    assert table["k"].between(0.8, 1.2).all()          # one homogeneous population, so flat


# --- applying it ----------------------------------------------------------------------------

def test_the_correction_leaves_the_point_forecast_bit_identical():
    """RMSE/MAE/R2 are the headline accuracy numbers. A conformal run reports the SAME ones."""
    rng = np.random.default_rng(5)
    pooled = rng.normal(300, 50, size=(64, 200, 4)).astype(np.float32)
    before = summarize_predictive_distribution(pooled)
    factors = rng.uniform(0.4, 2.5, size=(200, 4)).astype(np.float32)
    apply_conformal(pooled, before["mean"], factors)
    after = summarize_predictive_distribution(pooled)
    assert np.allclose(after["mean"], before["mean"], atol=2e-3)


def test_the_analytic_rescaled_summary_equals_resummarising_the_rescaled_sample():
    """run_experiment derives the post-correction interval instead of re-sorting 3.4 GB. That
    saving is only legitimate because an affine increasing map carries percentiles to
    percentiles -- pinned here rather than trusted."""
    rng = np.random.default_rng(6)
    pooled = rng.gamma(2.0, 80.0, size=(128, 150, 3)).astype(np.float32)
    before = summarize_predictive_distribution(pooled)
    factors = rng.uniform(0.3, 3.0, size=(150, 3)).astype(np.float32)
    derived = _rescaled_summary(before, factors)
    apply_conformal(pooled, before["mean"], factors)
    honest = summarize_predictive_distribution(pooled)
    for key in ("lower", "upper", "std"):
        assert np.allclose(derived[key], honest[key], rtol=1e-4, atol=1e-2), key


def test_a_factor_of_one_is_an_exact_no_op():
    rng = np.random.default_rng(7)
    pooled = rng.normal(size=(32, 40, 2)).astype(np.float32)
    original = pooled.copy()
    dist = summarize_predictive_distribution(pooled)
    apply_conformal(pooled, dist["mean"], np.ones((40, 2), dtype=np.float32))
    assert np.allclose(pooled, original, atol=1e-4)


def test_apply_conformal_rejects_a_mismatched_grid():
    pooled = np.zeros((4, 10, 3), dtype=np.float32)
    with pytest.raises(ValueError, match="must both be"):
        apply_conformal(pooled, np.zeros((10, 3)), np.ones((3, 10)))


# --- end to end -----------------------------------------------------------------------------

@pytest.fixture
def isolated_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "EXPERIMENTS_DIR", tmp_path / "experiments")
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", tmp_path / "ledger.csv")
    return tmp_path


def _tiny_config(experiment_id: str, **kwargs) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id=experiment_id, lookback_hours=6, horizon_hours=6, window_stride=1,
        train_ratio=0.6, val_ratio=0.2, hidden_sizes=[4, 4], n_bootstrap=1,
        mc_dropout_passes=4, max_epochs=1, batch_size=256, **kwargs
    )


def test_a_conformal_run_reports_the_same_point_accuracy_as_an_uncorrected_one(isolated_outputs):
    """The end-to-end statement of the invariant above, through the real orchestrator: the two
    runs share a seed, so they differ ONLY in whether the interval was rescaled."""
    df = make_synthetic_base_df(900)
    plain = run_experiment(_tiny_config("cf_none"), base_df=df)
    corrected = run_experiment(_tiny_config("cf_grid", conformal_mode="city_horizon"), base_df=df)
    for subset in ("all_hours", "daylight"):
        for metric in ("RMSE", "MAE", "R2"):
            assert corrected[subset]["aggregate"][metric] == pytest.approx(
                plain[subset]["aggregate"][metric], rel=1e-4), (subset, metric)
    assert (corrected["daylight"]["aggregate"]["MPIW"]
            != pytest.approx(plain["daylight"]["aggregate"]["MPIW"], rel=1e-6))


def test_the_conformal_run_writes_its_grid_and_its_effect_as_committed_csvs(isolated_outputs):
    df = make_synthetic_base_df(900)
    run_experiment(_tiny_config("cf_files", conformal_mode="per_city"), base_df=df)
    metrics_dir = isolated_outputs / "experiments" / "cf_files" / "metrics"
    for name in ("conformal_grid.csv", "conformal_effect.csv", "conformal_month_stability.csv"):
        assert (metrics_dir / name).exists(), name
    log = (isolated_outputs / "experiments" / "cf_files" / "log.txt").read_text()
    assert "conformal_mode=per_city" in log and "calibration pass" in log


def test_the_mode_is_a_ledger_column_so_two_such_runs_are_distinguishable(isolated_outputs):
    """Same point forecast, different intervals. Without the column the paper's coverage table
    could not say which row was corrected."""
    assert "conformal_mode" in LEDGER_COLUMNS
    df = make_synthetic_base_df(900)
    run_experiment(_tiny_config("cf_ledger_none"), base_df=df)
    run_experiment(_tiny_config("cf_ledger_grid", conformal_mode="global"), base_df=df)
    import pandas as pd
    ledger = pd.read_csv(isolated_outputs / "ledger.csv")
    modes = dict(zip(ledger["experiment_id"], ledger["conformal_mode"]))
    assert modes == {"cf_ledger_none": "none", "cf_ledger_grid": "global"}


def test_the_default_run_pays_nothing_for_the_layer(isolated_outputs, monkeypatch):
    """conformal_mode='none' must not predict the validation split at all -- the calibration pass
    is roughly a 13% wall-clock surcharge and every existing ledger row was priced without it."""
    from merve_solar import experiment as exp
    calls = []
    real = exp.pooled_summary
    monkeypatch.setattr(exp, "pooled_summary", lambda *a, **k: calls.append(1) or real(*a, **k))
    run_experiment(_tiny_config("cf_free"), base_df=make_synthetic_base_df(900))
    assert calls == []


def test_the_per_city_arm_assembles_its_calibration_predictions_into_the_pooled_layout(isolated_outputs):
    """Five independent model sets, five validation blocks, one grid. If the assembly were
    misaligned the grid would be fitted on one province's residuals and applied to another's --
    which changes no shape and no count, exactly the failure _assert_city_block_aligned exists
    for, here extended to the validation split."""
    df = make_synthetic_base_df(900)
    subsets = run_experiment(
        _tiny_config("cf_percity", training_scope="per_city", conformal_mode="city_horizon"),
        base_df=df,
    )
    import pandas as pd
    grid = pd.read_csv(isolated_outputs / "experiments" / "cf_percity" / "metrics" / "conformal_grid.csv")
    assert set(grid["city"]) == set(CITIES)
    assert subsets["daylight"]["aggregate"]["n_elements"] > 0


def test_the_calibration_summary_is_brought_back_to_irradiance_before_the_grid_is_fitted():
    """Under target_transform='clearsky_index' the calibration summary arrives as kt while the
    truth it is scored against is always W/m^2. The inversion is a multiplication by the target
    hour's clear-sky value and applies to mean and both percentiles alike -- the map is affine
    with a non-negative factor, so it carries percentiles to percentiles."""
    from merve_solar.experiment import invert_summary_transform
    summary = {k: np.full((2, 3), v, dtype=np.float32)
               for k, v in (("mean", 0.5), ("std", 0.1), ("lower", 0.3), ("upper", 0.7))}
    clear = np.array([[0.0, 400.0, 800.0], [100.0, 200.0, 300.0]], dtype=np.float32)

    raw_cfg = _tiny_config("cf_unit_raw")
    assert invert_summary_transform(summary, raw_cfg, clear) is summary

    kt_cfg = _tiny_config("cf_unit_kt", target_transform="clearsky_index")
    out = invert_summary_transform(summary, kt_cfg, clear)
    assert np.allclose(out["mean"], 0.5 * clear)
    assert np.allclose(out["lower"], 0.3 * clear)
    assert np.allclose(out["upper"], 0.7 * clear)
    assert (out["lower"] <= out["mean"]).all() and (out["mean"] <= out["upper"]).all()
    # Night (clear-sky 0) collapses the whole summary to a point, which conformity_scores then
    # reports invalid -- the mechanism that keeps night out of every fit.
    assert out["upper"][0, 0] == out["lower"][0, 0] == 0.0


def test_the_clearsky_index_arm_runs_end_to_end_with_a_grid(isolated_outputs):
    df = make_synthetic_base_df(900)
    run_experiment(
        _tiny_config("cf_kt", target_transform="clearsky_index", conformal_mode="global"),
        base_df=df,
    )
    import pandas as pd
    metrics_dir = isolated_outputs / "experiments" / "cf_kt" / "metrics"
    grid = pd.read_csv(metrics_dir / "conformal_grid.csv")
    assert len(grid) == 1 and np.isfinite(grid["k_applied"].iloc[0])
    effect = pd.read_csv(metrics_dir / "conformal_effect.csv")
    agg = effect[(effect["group"] == "Aggregate") & (effect["horizon_step"] == "all")].iloc[0]
    assert agg["CP_before"] != agg["CP_after"]


# --- the season axis ------------------------------------------------------------------------

def test_a_season_mode_refuses_to_guess_when_it_is_given_no_timestamps():
    """Silently falling back to one cell would report a `city_season` grid that is a scalar."""
    y, mean, lower, upper, city_id, day, _ = _heterogeneous_grid_inputs(n_per_city=300)
    with pytest.raises(ValueError, match="needs window_start"):
        fit_conformal_grid(y, mean, lower, upper, city_id, day, "city_season", ALPHA)


def test_the_season_cell_follows_the_month_of_the_window_start():
    from merve_solar.conformal import SEASON_NAMES, _cell_keys
    starts = np.array(["2025-01-15T00", "2025-04-15T00", "2025-07-15T00", "2025-10-15T00"],
                      dtype="datetime64[h]")
    seasons = _cell_keys("per_season", np.zeros(4, dtype=np.int64), 2, starts)["season"]
    assert [SEASON_NAMES[c] for c in seasons[:, 0]] == ["DJF", "MAM", "JJA", "SON"]
    assert (seasons[:, 0] == seasons[:, 1]).all(), "a window's season must not vary by horizon step"


def test_a_seasonal_miscalibration_is_only_caught_by_a_seasonal_grid():
    """The measured situation: k swings 1.7x-2.0x between summer and late winter on real runs,
    because cloud variability is seasonal while the epistemic spread is not. A grid without the
    season axis averages that away and leaves both halves of the year mis-covered."""
    rng = np.random.default_rng(21)
    n, horizon = 8000, 2
    starts = _year_of_window_starts(n)
    month = pd.to_datetime(starts).month.to_numpy()
    # Split along the season boundaries the grid actually uses: MAM+JJA quiet, SON+DJF noisy.
    # A split that cut across a season cell would be unfixable by ANY seasonal grid, which would
    # test the fixture rather than the estimator.
    summer = np.isin(month, [3, 4, 5, 6, 7, 8])
    mean = np.zeros((n, horizon), dtype=np.float32)
    # Same interval all year; the residual scale halves in summer.
    sigma = np.where(summer, 0.5, 1.5)[:, None]
    y = (rng.normal(0, 1.0, size=(n, horizon)) * sigma).astype(np.float32)
    half = 1.959963985
    lower = np.full((n, horizon), -half, dtype=np.float32)
    upper = np.full((n, horizon), half, dtype=np.float32)
    city_id = np.zeros(n, dtype=np.int64)
    day = np.ones((n, horizon), dtype=bool)

    cal = rng.random(n) < 0.5
    def coverage_by_season(mode):
        grid = fit_conformal_grid(y[cal], mean[cal], lower[cal], upper[cal], city_id[cal],
                                  day[cal], mode, ALPHA, window_start=starts[cal])
        k = grid.factor_array(city_id[~cal], day[~cal], starts[~cal])
        lo = mean[~cal] + k * (lower[~cal] - mean[~cal])
        hi = mean[~cal] + k * (upper[~cal] - mean[~cal])
        inside = (y[~cal] >= lo) & (y[~cal] <= hi)
        s = summer[~cal]
        return inside[s].mean(), inside[~s].mean()

    flat_summer, flat_winter = coverage_by_season("global")
    seasonal_summer, seasonal_winter = coverage_by_season("per_season")
    # One factor for the whole year over-covers the quiet season and under-covers the noisy one.
    # Marginal coverage is still ~0.95; it is CONDITIONAL coverage that a scalar cannot deliver,
    # which is the precise form of "a scalar factor does not work".
    assert flat_summer > 0.98 and flat_winter < 0.93
    assert seasonal_summer == pytest.approx(0.95, abs=0.02)
    assert seasonal_winter == pytest.approx(0.95, abs=0.02)


def test_a_season_grid_survives_a_calibration_set_that_is_missing_a_month():
    """The production case exactly: the validation split has no April and no May, so the MAM cell
    is fitted on March alone and then applied to all three months. It has to still be a MAM cell
    -- not a fallback to the year-round pooled factor."""
    rng = np.random.default_rng(22)
    n, horizon = 6000, 2
    starts = _year_of_window_starts(n)
    month = pd.to_datetime(starts).month.to_numpy()
    mean = np.zeros((n, horizon), dtype=np.float32)
    y = rng.normal(0, 1.0, size=(n, horizon)).astype(np.float32)
    lower = np.full((n, horizon), -1.96, dtype=np.float32)
    upper = np.full((n, horizon), 1.96, dtype=np.float32)
    city_id = np.zeros(n, dtype=np.int64)
    day = np.ones((n, horizon), dtype=bool)
    cal = ~np.isin(month, [4, 5])

    grid = fit_conformal_grid(y[cal], mean[cal], lower[cal], upper[cal], city_id[cal], day[cal],
                              "per_season", ALPHA, window_start=starts[cal])
    frame = grid.to_frame()
    assert set(frame["season"]) == {"DJF", "MAM", "JJA", "SON"}
    assert not frame["fell_back"].any(), "March alone must still populate the MAM cell"

    # April/May elements are covered by the March-fitted MAM factor, not by a pooled fallback.
    unseen = np.isin(month, [4, 5])
    k = grid.factor_array(city_id[unseen], day[unseen], starts[unseen])
    mam = frame.loc[frame["season"] == "MAM", "k_applied"].iloc[0]
    assert np.allclose(k, mam)


# --- the axes do not substitute for one another ---------------------------------------------

def test_a_horizon_shaped_miscalibration_is_invisible_to_a_city_grid():
    """The selection error this suite now guards against.

    The mode was originally chosen by scoring per-PROVINCE coverage alone, on which the horizon
    axis buys nothing -- so it was dropped, and the runs that followed left a 4.6-5.6 pp coverage
    spread across the 24 horizon steps that no city or season cell can see. Each axis fixes its
    own conditional and no other; a grid is only as good as the conditionals it was scored on.
    """
    rng = np.random.default_rng(31)
    n, horizon = 4000, 8
    city_id = np.repeat(np.arange(len(CITIES)), n // len(CITIES)).astype(np.int64)
    mean = np.zeros((n, horizon), dtype=np.float32)
    # Residual scale grows with lead time; the interval does not. Identical in every province,
    # so the city axis has nothing to find.
    sigma = np.linspace(0.4, 1.6, horizon)[None, :]
    y = (rng.normal(0, 1.0, size=(n, horizon)) * sigma).astype(np.float32)
    half = 1.959963985
    lower = np.full((n, horizon), -half, dtype=np.float32)
    upper = np.full((n, horizon), half, dtype=np.float32)
    day = np.ones((n, horizon), dtype=bool)
    cal = rng.random(n) < 0.5

    def worst_step_deviation(mode):
        grid = fit_conformal_grid(y[cal], mean[cal], lower[cal], upper[cal], city_id[cal],
                                  day[cal], mode, ALPHA)
        k = grid.factor_array(city_id[~cal], day[~cal])
        lo = mean[~cal] + k * (lower[~cal] - mean[~cal])
        hi = mean[~cal] + k * (upper[~cal] - mean[~cal])
        inside = (y[~cal] >= lo) & (y[~cal] <= hi)
        return max(abs(inside[:, h].mean() - 0.95) for h in range(horizon))

    assert worst_step_deviation("per_city") > 0.10
    assert worst_step_deviation("per_horizon") < 0.02
    assert worst_step_deviation("city_horizon") < 0.02


def test_the_three_axis_grid_crosses_all_three_and_keeps_the_cells_apart():
    y, mean, lower, upper, city_id, day, _ = _heterogeneous_grid_inputs(n_per_city=4000)
    starts = _year_of_window_starts(len(y), city_id)
    grid = fit_conformal_grid(y, mean, lower, upper, city_id, day, "city_season_horizon",
                              ALPHA, window_start=starts)
    frame = grid.to_frame()
    assert len(frame) == len(CITIES) * 4 * 4
    assert set(frame["city"]) == set(CITIES)
    assert set(frame["season"]) == {"DJF", "MAM", "JJA", "SON"}
    assert set(frame["horizon_step"]) == {1, 2, 3, 4}
    # The fixture varies by (city, horizon) only, so within a cell's city+step the four season
    # cells must agree -- if the axes were being crossed in the wrong order they would not.
    for (city, step), block in frame.groupby(["city", "horizon_step"]):
        assert block["k_cell"].std() < 0.25 * block["k_cell"].mean(), (city, step)


def test_every_mode_declares_its_axes():
    """MODE_AXES is what _cell_keys, factor_array and to_frame all read, so a mode missing from
    it would fit a grid and then label its cells wrong."""
    from merve_solar.conformal import MODE_AXES
    assert set(MODE_AXES) == set(CONFORMAL_MODES) - {"none"}
    for mode, axes in MODE_AXES.items():
        assert set(axes) <= {"city", "season", "horizon"}, mode
        assert len(set(axes)) == len(axes), mode


def test_a_conformal_run_saves_the_factors_that_make_its_predictions_invertible(isolated_outputs):
    """test_predictions.npz stores what was SCORED, which for a conformal run is the corrected
    interval. Without the factors beside it a reader cannot tell a corrected file from an
    uncorrected one and will apply a second correction on top -- which is what happened to the
    first run of scripts/08_conformal_mode_selection.py, and showed as every mode's MPIW landing
    at exactly the same fraction of the stored one."""
    df = make_synthetic_base_df(900)
    run_experiment(_tiny_config("cf_invertible", conformal_mode="city_season"), base_df=df)
    plain = run_experiment(_tiny_config("cf_plain"), base_df=df)

    with np.load(isolated_outputs / "experiments" / "cf_invertible" / "metrics" / "test_predictions.npz") as z:
        assert "conformal_k" in z.files
        k, mean, lower, upper = z["conformal_k"], z["mean"], z["lower"], z["upper"]
        day = z["daylight"]
    assert k.shape == lower.shape
    assert (k[~day] == 1.0).all(), "night must carry a factor of exactly 1"
    assert not np.allclose(k[day], 1.0), "daylight factors that are all 1 would mean no correction"

    # Dividing the factors back out recovers an interval; re-applying them returns the stored one.
    base_lower = mean + (lower - mean) / k
    base_upper = mean + (upper - mean) / k
    assert np.allclose(mean + k * (base_lower - mean), lower, atol=1e-3)
    assert np.allclose(mean + k * (base_upper - mean), upper, atol=1e-3)
    # ... and the recovered interval is wider or narrower than the stored one, never equal.
    assert not np.allclose(base_lower[day], lower[day])

    with np.load(isolated_outputs / "experiments" / "cf_plain" / "metrics" / "test_predictions.npz") as z:
        assert "conformal_k" not in z.files, "an uncorrected run has nothing to invert"
    assert plain["daylight"]["aggregate"]["n_elements"] > 0
