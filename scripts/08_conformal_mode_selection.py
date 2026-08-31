"""Re-choose the conformal grid geometry HONESTLY -- fitted on validation, scored on test.

`scripts/07_conformal_diagnostic.py` chose the geometry by splitting a finished run's TEST
windows in half, which is selecting a hyperparameter on the test set (threat T-8.3). It also
scored the modes on one criterion, worst per-PROVINCE coverage, and that turned out to decide the
answer: the horizon axis buys nothing on that criterion and was dropped, after which the
full-fidelity runs came back with a 4.6-5.6 pp coverage spread ACROSS THE 24 HORIZON STEPS that no
city or season cell can see.

This script fixes both. It reads a finished conformal run's `calibration_predictions.npz` (the
validation split, which is what production actually calibrates on) and its
`test_predictions.npz`, fits every mode on the former, applies it to the latter, and scores three
conditionals rather than one:

  aggregate        |CP - 0.95| over all daylight elements       -- marginal coverage
  worst province   max over the five provinces                  -- what the city axis fixes
  worst step       max over the 24 horizon steps                -- what the horizon axis fixes

Nothing is retrained: both files are summaries of distributions that already exist, and the
correction is an affine rescaling of them. Seconds per run.

It also reports the ORACLE factor -- k refitted on the test split itself. The applied-to-oracle
gap is exactly the calibration transfer error, i.e. how much of the residual miscalibration is
the validation split being a different ten months of a different year rather than the grid being
the wrong shape. That decomposition is what says whether a rerun under a different mode would
help, or whether the layer has reached what this calibration set can deliver.

CRPS is out of scope here as everywhere in postprocess.py: it is the one metric that needs the
S pooled samples rather than their summary.

    uv run python scripts/08_conformal_mode_selection.py            # every run with both files
    uv run python scripts/08_conformal_mode_selection.py --experiment-id abl_conformal_raw_s42_full
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from merve_solar.conformal import CONFORMAL_MODES, MIN_CELL_N, fit_conformal_grid
from merve_solar.config import CITIES, CITY_TO_ID, OUTPUTS_DIR
from merve_solar.metrics import (
    TARGET_CI_COVERAGE,
    coverage_probability,
    mean_prediction_interval_width,
)
from merve_solar.postprocess import calibration_path, load_run_predictions, prediction_path

ALPHA = 1.0 - TARGET_CI_COVERAGE
TABLES_DIR = OUTPUTS_DIR / "tables"
OUT_NAME = "conformal_mode_selection_validation.csv"


def _rescale(run: dict, factors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = run["mean"]
    return mean + factors * (run["lower"] - mean), mean + factors * (run["upper"] - mean)


def _score(run: dict, lower: np.ndarray, upper: np.ndarray) -> dict:
    y, day, city = run["y_true"], run["daylight"], run["city_id"]
    per_city, per_step = {}, []
    for name in CITIES:
        rows = city == CITY_TO_ID[name]
        if not rows.any():
            continue
        mask = day[rows]
        per_city[name] = coverage_probability(y[rows][mask], lower[rows][mask], upper[rows][mask])
    for step in range(y.shape[1]):
        mask = day[:, step]
        per_step.append(coverage_probability(y[mask, step], lower[mask, step], upper[mask, step]))
    cp = coverage_probability(y[day], lower[day], upper[day])
    return {
        "CP": cp,
        "MPIW": mean_prediction_interval_width(lower[day], upper[day]),
        "aggregate_dev": abs(cp - TARGET_CI_COVERAGE),
        "worst_city_dev": max(abs(v - TARGET_CI_COVERAGE) for v in per_city.values()),
        "worst_step_dev": max(abs(v - TARGET_CI_COVERAGE) for v in per_step),
        "CP_step_1": per_step[0],
        "CP_step_last": per_step[-1],
        **{f"CP_{name}": value for name, value in per_city.items()},
    }


def evaluate_run(experiment_id: str) -> pd.DataFrame:
    cal = load_run_predictions(experiment_id, split="calibration")
    test = load_run_predictions(experiment_id, split="test")
    rows = []
    for mode in CONFORMAL_MODES:
        if mode == "none":
            lower, upper = test["lower"], test["upper"]
            extra = {"n_cells": 0, "min_cell_n": np.nan, "n_fallback": 0,
                     "k_min": 1.0, "k_max": 1.0, "oracle_dev": np.nan}
        else:
            grid = fit_conformal_grid(
                cal["y_true"], cal["mean"], cal["lower"], cal["upper"], cal["city_id"],
                cal["daylight"], mode, ALPHA, window_start=cal["window_start"],
            )
            factors = grid.factor_array(test["city_id"], test["daylight"], test["window_start"])
            lower, upper = _rescale(test, factors)
            frame = grid.to_frame()
            day_k = factors[test["daylight"]]
            # The same mode fitted on the test split itself: the best this grid shape could
            # possibly do, so the gap to it is the calibration transfer error alone.
            oracle = fit_conformal_grid(
                test["y_true"], test["mean"], test["lower"], test["upper"], test["city_id"],
                test["daylight"], mode, ALPHA, window_start=test["window_start"],
            )
            o_lower, o_upper = _rescale(
                test, oracle.factor_array(test["city_id"], test["daylight"], test["window_start"]))
            day = test["daylight"]
            extra = {
                "n_cells": len(frame),
                "min_cell_n": int(frame["n_calibration"].min()),
                "n_fallback": int(frame["fell_back"].sum()),
                "k_min": float(day_k.min()), "k_max": float(day_k.max()),
                "oracle_dev": abs(coverage_probability(
                    test["y_true"][day], o_lower[day], o_upper[day]) - TARGET_CI_COVERAGE),
            }
        rows.append({"experiment_id": experiment_id, "mode": mode,
                     **extra, **_score(test, lower, upper)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--experiment-id", action="append", default=None,
                        help="repeatable; default is every run that has BOTH npz files")
    args = parser.parse_args()

    ids = args.experiment_id or sorted(
        p.parts[-3] for p in (OUTPUTS_DIR / "experiments").glob("*/metrics/" + calibration_path("x").name)
    )
    ids = [i for i in ids if calibration_path(i).exists() and prediction_path(i).exists()]
    if not ids:
        raise SystemExit(
            "No run has both calibration_predictions.npz and test_predictions.npz. They are "
            "gitignored, so this runs on the machine that ran the experiments, and only runs "
            "with conformal_mode != 'none' write the calibration file."
        )

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for experiment_id in ids:
        print(f"{experiment_id} ...", flush=True)
        frames.append(evaluate_run(experiment_id))
    table = pd.concat(frames, ignore_index=True)
    table.to_csv(TABLES_DIR / OUT_NAME, index=False)
    print(f"\nwrote {TABLES_DIR / OUT_NAME} ({len(table)} rows)")

    order = [m for m in CONFORMAL_MODES]
    summary = (table.groupby("mode", as_index=False)
               [["aggregate_dev", "worst_city_dev", "worst_step_dev", "oracle_dev",
                 "n_cells", "min_cell_n", "n_fallback"]].mean()
               .set_index("mode").loc[order])
    print(f"\nmean over {len(ids)} run(s), calibrated on VALIDATION, scored on test; "
          "lower is better:")
    print(summary.to_string(float_format=lambda v: f"{v:.4f}"))
    print(f"\nMIN_CELL_N = {MIN_CELL_N}; a mode whose min_cell_n falls below it is thinning "
          "cells into the pooled fallback.")
    print("`oracle_dev` is the same grid shape fitted on the test split itself: the gap between "
          "it and aggregate_dev is the calibration transfer error, not a defect of the geometry.")


if __name__ == "__main__":
    main()
