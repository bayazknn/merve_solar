"""Re-scoring a finished run from its saved summary must equal what the pipeline reported.

postprocess.py exists to produce the per-(city x horizon) table the pipeline never emits, and
later to carry the conformal rescaling and the paired tests. All three read mean/lower/upper
instead of the (S, N, horizon) sample, so the load-bearing claim is that doing so changes
nothing for the metrics that do not need the sample -- and that a cell lands in the right
(city, step) slot, which no shape or total would reveal.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

import merve_solar.postprocess as pp
from merve_solar.config import CITIES, CITY_TO_ID
from merve_solar.metrics import (
    compute_metrics_for_subset,
    results_by_horizon_dataframe,
    results_summary_dataframe,
    compute_metric_subsets,
    summarize_predictive_distribution,
)

N_PER_CITY, HORIZON, S = 7, 4, 40


def _fake_run(seed=0, cities=CITIES):
    """A pooled sample plus the summary saved from it, so both scoring paths are available."""
    rng = np.random.default_rng(seed)
    n = N_PER_CITY * len(cities)
    city_id = np.repeat([CITY_TO_ID[c] for c in cities], N_PER_CITY)
    y = rng.uniform(0, 900, size=(n, HORIZON)).astype(np.float32)
    # Each province gets its own bias and spread, so a transposition changes the numbers.
    bias = np.repeat(np.arange(len(cities)) * 40.0, N_PER_CITY)[:, None]
    pooled = (y + bias + rng.normal(0, 30, size=(S, n, HORIZON))).astype(np.float32)
    daylight = rng.random((n, HORIZON)) > 0.4
    return pooled, {
        **summarize_predictive_distribution(pooled),
        "y_true": y, "city_id": city_id, "daylight": daylight,
        "window_start": np.arange(n).astype("datetime64[h]"),
    }


def test_scoring_from_the_summary_equals_scoring_from_the_sample():
    """The claim the whole module rests on. CRPS is the one exception and is NaN, not wrong."""
    pooled, run = _fake_run()
    dist = {k: run[k] for k in ("mean", "lower", "upper")}
    full = compute_metrics_for_subset(pooled, run["y_true"], run["daylight"], dist)
    summary = compute_metrics_for_subset(None, run["y_true"], run["daylight"], dist)
    for key in pp.SUMMARY_ONLY_METRICS:
        assert summary[key] == pytest.approx(full[key], rel=1e-12), key
    assert np.isnan(summary["CRPS"]) and not np.isnan(full["CRPS"])


def test_a_summary_only_call_without_a_dist_is_refused():
    """Passing neither would silently score against a summary of nothing."""
    with pytest.raises(ValueError, match="pooled_preds or dist"):
        compute_metrics_for_subset(None, np.zeros((2, 2)))


def test_the_table_covers_every_city_and_step_once_in_each_subset():
    _, run = _fake_run()
    t = pp.city_horizon_table(run)
    assert len(t) == len(CITIES) * HORIZON * 2
    assert set(t["subset"]) == {"all_hours", "daylight"}
    assert t.groupby(["subset", "group", "horizon_step"]).size().max() == 1


def test_cells_carry_their_own_provinces_numbers():
    """The reason the cross-check exists: a transposition preserves every shape and total."""
    _, run = _fake_run()
    t = pp.city_horizon_table(run).set_index(["subset", "group", "horizon_step"])
    ankara = t.loc[("all_hours", "Ankara")]["MAE"].mean()
    van = t.loc[("all_hours", "Van")]["MAE"].mean()
    # _fake_run gives later provinces a larger bias, so the ordering is known a priori.
    assert ankara < van


def test_the_cross_check_reports_a_transposed_table(tmp_path, monkeypatch):
    pooled, run = _fake_run()
    subsets = compute_metric_subsets(pooled, run["y_true"], run["city_id"], list(CITIES),
                                     run["daylight"])
    metrics_dir = tmp_path / "outputs" / "experiments" / "x" / "metrics"
    metrics_dir.mkdir(parents=True)
    results_summary_dataframe(subsets).to_csv(metrics_dir / "results_summary.csv", index=False)
    results_by_horizon_dataframe(subsets).to_csv(metrics_dir / "results_by_horizon.csv", index=False)
    monkeypatch.setattr(pp, "PROJECT_ROOT", tmp_path)

    honest = pp.city_horizon_table(run)
    assert pp.check_against_pipeline_csvs("x", honest) == []

    swapped = honest.copy()
    swapped["group"] = swapped["group"].map({"Ankara": "Van", "Van": "Ankara"}).fillna(swapped["group"])
    problems = pp.check_against_pipeline_csvs("x", swapped)
    assert any("pooled RMSE" in p for p in problems), problems


def test_an_interval_that_does_not_contain_its_centre_is_rejected(tmp_path, monkeypatch):
    _, run = _fake_run()
    run["lower"], run["upper"] = run["upper"], run["lower"]
    metrics_dir = tmp_path / "outputs" / "experiments" / "x" / "metrics"
    metrics_dir.mkdir(parents=True)
    np.savez_compressed(metrics_dir / pp.PREDICTION_FILENAME,
                        **{k: (v.astype("datetime64[h]").astype(np.int64) if k == "window_start" else v)
                           for k, v in run.items()})
    monkeypatch.setattr(pp, "PROJECT_ROOT", tmp_path)
    with pytest.raises(ValueError, match="lower exceeds upper"):
        pp.load_run_predictions("x")


def test_a_missing_prediction_file_says_why_it_is_missing(tmp_path, monkeypatch):
    """It is gitignored, so 'file not found' on a synced-but-not-run machine is expected."""
    monkeypatch.setattr(pp, "PROJECT_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="gitignored"):
        pp.load_run_predictions("never_ran")


def test_a_run_that_excluded_provinces_reports_only_the_ones_it_has():
    _, run = _fake_run(cities=["Rize"])
    assert pp.run_cities(run) == ["Rize"]
    assert set(pp.city_horizon_table(run)["group"]) == {"Rize"}
