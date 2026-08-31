"""Choose the geometry of the conformal grid, and measure what threatens it.

This is a METHOD-SELECTION measurement, not a result. It answers three questions that had to be
settled before spending Mac time on full-fidelity conformal runs, and it answers them from
prediction dumps that already exist -- no training, seconds of compute:

1. Does the correction have to be a grid at all, or does one scalar suffice?
2. Which axes does it need? The design in ABLATION.md 6.5 proposed (city x horizon).
3. How much damage does the calibration split's seasonal hole do? The validation split runs
   2024-06-27 -> 2025-03-24 and contains no April and no May, while the test split covers all
   twelve months.

Four calibration geometries are compared, each fitted on half the finished run's TEST windows
and evaluated on the other half:

  exchangeable     a random half. What split-conformal theory actually covers -- the ceiling.
  temporal         the chronologically first half. The harshest possible seasonal mismatch:
                   calibration is spring-summer, evaluation autumn-winter.
  season_balanced  alternating months. Temporally interleaved but seasonally balanced, so it
                   separates "the seasons differ" from "the model drifts through time".
  production_like  a random half with April and May removed, mimicking the real validation
                   split's hole while leaving everything else exchangeable.

CAVEAT, and it is the reason `calibration_predictions.npz` now exists: fitting and scoring both
happen inside the test period here, so this cannot be the final word on which mode to run --
that would be selecting a hyperparameter on the test set. The design conclusions it supports are
structural (which axis carries signal, how far k moves with the season) and would show up on any
split; the confirmation belongs on the validation split, and can be run there as soon as one
conformal experiment has produced that file.

Every run available is B=1. Fidelity changes what the interval IS (see the comparability rules),
so the k values here are not the k values a B=8 run will fit -- only their structure carries over.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from merve_solar.conformal import CONFORMAL_MODES, fit_conformal_grid, month_stability_table
from merve_solar.config import CITIES, CITY_TO_ID, OUTPUTS_DIR
from merve_solar.metrics import (
    TARGET_CI_COVERAGE,
    coverage_probability,
    mean_prediction_interval_width,
)
from merve_solar.postprocess import load_run_predictions, prediction_path

ALPHA = 1.0 - TARGET_CI_COVERAGE
TABLES_DIR = OUTPUTS_DIR / "tables"
MODE_TABLE = "conformal_mode_selection.csv"
MONTH_TABLE = "conformal_month_stability_test.csv"


def calibration_masks(window_start: np.ndarray, seed: int = 0) -> dict:
    """The four geometries, as boolean masks over windows."""
    month = pd.to_datetime(window_start).month.to_numpy()
    order = window_start.astype("int64")
    rng = np.random.default_rng(seed)
    random_half = rng.random(order.size) < 0.5
    return {
        "exchangeable": random_half,
        "temporal": order <= np.median(order),
        "season_balanced": np.isin(month, [1, 3, 5, 7, 9, 11]),
        "production_like": random_half & ~np.isin(month, [4, 5]),
    }


def _coverage_row(run, rows, lower, upper) -> dict:
    y, day, city = run["y_true"][rows], run["daylight"][rows], run["city_id"][rows]
    out = {"CP": coverage_probability(y[day], lower[day], upper[day]),
           "MPIW": mean_prediction_interval_width(lower[day], upper[day])}
    for name in CITIES:
        sel = city == CITY_TO_ID[name]
        if sel.any():
            mask = day[sel]
            out[f"CP_{name}"] = coverage_probability(
                y[sel][mask], lower[sel][mask], upper[sel][mask])
    # The two months no calibration point ever saw under `production_like`; under the other
    # geometries this is just an ordinary slice and the column is still comparable.
    unseen = np.isin(pd.to_datetime(run["window_start"][rows]).month.to_numpy(), [4, 5])
    if unseen.any():
        mask = day[unseen]
        out["CP_AprMay"] = coverage_probability(
            y[unseen][mask], lower[unseen][mask], upper[unseen][mask])
    return out


def evaluate_run(experiment_id: str, seed: int = 0) -> pd.DataFrame:
    run = load_run_predictions(experiment_id)
    rows = []
    for geometry, cal_rows in calibration_masks(run["window_start"], seed).items():
        eval_rows = ~cal_rows
        for mode in CONFORMAL_MODES:
            if mode == "none":
                lower, upper = run["lower"][eval_rows], run["upper"][eval_rows]
                spread = {"k_min": 1.0, "k_max": 1.0, "n_cells": 0}
            else:
                grid = fit_conformal_grid(
                    run["y_true"][cal_rows], run["mean"][cal_rows], run["lower"][cal_rows],
                    run["upper"][cal_rows], run["city_id"][cal_rows], run["daylight"][cal_rows],
                    mode, ALPHA, window_start=run["window_start"][cal_rows],
                )
                k = grid.factor_array(run["city_id"][eval_rows], run["daylight"][eval_rows],
                                      run["window_start"][eval_rows])
                mean = run["mean"][eval_rows]
                lower = mean + k * (run["lower"][eval_rows] - mean)
                upper = mean + k * (run["upper"][eval_rows] - mean)
                day_k = k[run["daylight"][eval_rows]]
                spread = {"k_min": float(day_k.min()), "k_max": float(day_k.max()),
                          "n_cells": int(len(grid.to_frame()))}
            rows.append({"experiment_id": experiment_id, "geometry": geometry, "mode": mode,
                         **spread, **_coverage_row(run, eval_rows, lower, upper)})
    frame = pd.DataFrame(rows)
    city_columns = [c for c in frame.columns if c.startswith("CP_") and c != "CP_AprMay"]
    # The headline of the whole table. Marginal coverage is easy -- a scalar reaches it by
    # over-covering four provinces and under-covering the fifth, which is the aggregate trap in
    # its coverage form. This column is what separates the modes.
    frame["max_city_deviation"] = (frame[city_columns] - TARGET_CI_COVERAGE).abs().max(axis=1)
    frame["reliability"] = (frame["CP"] - TARGET_CI_COVERAGE).abs()
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--experiment-id", action="append", default=None,
                        help="repeatable; default is every run with a prediction dump on disk")
    parser.add_argument("--seed", type=int, default=0, help="seed for the random half")
    args = parser.parse_args()

    ids = args.experiment_id
    if not ids:
        ids = sorted(p.parts[-3] for p in
                     (OUTPUTS_DIR / "experiments").glob("*/metrics/test_predictions.npz"))
    if not ids:
        raise SystemExit(
            "No prediction dumps found. They are gitignored, so this runs on the machine that "
            "ran the experiments."
        )

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    modes, months = [], []
    for experiment_id in ids:
        if not prediction_path(experiment_id).exists():
            print(f"skip {experiment_id}: no prediction dump")
            continue
        print(f"{experiment_id} ...", flush=True)
        modes.append(evaluate_run(experiment_id, args.seed))
        run = load_run_predictions(experiment_id)
        table = month_stability_table(run["y_true"], run["mean"], run["lower"], run["upper"],
                                      run["daylight"], run["window_start"], ALPHA)
        months.append(table.assign(experiment_id=experiment_id))

    mode_frame = pd.concat(modes, ignore_index=True)
    month_frame = pd.concat(months, ignore_index=True)
    mode_frame.to_csv(TABLES_DIR / MODE_TABLE, index=False)
    month_frame.to_csv(TABLES_DIR / MONTH_TABLE, index=False)

    print(f"\nwrote {TABLES_DIR / MODE_TABLE} ({len(mode_frame)} rows)")
    print(f"wrote {TABLES_DIR / MONTH_TABLE} ({len(month_frame)} rows)")
    summary = (mode_frame.groupby(["geometry", "mode"], as_index=False)
               [["reliability", "max_city_deviation"]].mean()
               .sort_values(["geometry", "max_city_deviation"]))
    print("\nmean over runs, lower is better:")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    swing = month_frame.groupby("experiment_id")["k"].agg(["min", "max"])
    swing["swing"] = swing["max"] / swing["min"]
    print("\nhow far k moves across the year, per run:")
    print(swing.to_string(float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
