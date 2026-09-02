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

THE FILE IT READS IS ALREADY CORRECTED, AND THAT HAS TO BE UNDONE FIRST. `test_predictions.npz`
stores what was scored, which for a conformal run is the post-correction interval. The first
version of this script did not undo it and evaluated every mode on top of the run's own
correction -- a double rescaling, which showed as every mode moving the raw arm from 0.0096 to
0.056-0.064 and every MPIW landing at exactly 0.843x the stored one. Runs written since carry a
`conformal_k` array for the exact inverse; older ones are undone by refitting their own
configured mode from their calibration file, which is deterministic and reproduces the same
factors. Either way the recovered baseline is checked against the stored intervals before
anything else runs.

Nothing is retrained: both files are summaries of distributions that already exist, and the
correction is an affine rescaling of them. Seconds per run.

It also reports the ORACLE factor -- the same grid shape refitted on the test split itself -- and
scores it on ALL THREE conditionals, because the aggregate one alone cannot answer the question.
Any grid containing a cell fitted on the target split hits marginal coverage almost exactly by
construction, so an aggregate-only oracle reads ~0 for every mode and says nothing. The
conditional oracles are the ones that discriminate: a shape with no horizon axis applies a single
k to all 24 steps, so it CANNOT flatten a horizon-shaped miscalibration however well calibrated
it is, and that residual survives into its oracle row. So, per conditional: what survives in the
oracle is geometry (a rerun under a richer mode fixes it), and the gap from the oracle up to the
applied score is calibration transfer error -- the validation split being a different ten months
of a different year (no mode fixes that).

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
from merve_solar.config import CITIES, CITY_TO_ID, OUTPUTS_DIR, ExperimentConfig
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


def uncorrect(test: dict, cal: dict, experiment_id: str) -> np.ndarray:
    """The factors this run already applied, so they can be divided back out.

    Preferred source is the `conformal_k` array the run saved. For a run written before that
    array existed, the same grid is refitted from its calibration file under the mode recorded in
    its config.json -- deterministic, since fit_conformal_grid is a pure function of those inputs.
    Returns an all-ones array for a run that applied no correction.
    """
    if "conformal_k" in test:
        return test["conformal_k"]
    config_path = (OUTPUTS_DIR / "experiments" / experiment_id / "config.json")
    mode = ExperimentConfig.from_json(config_path).conformal_mode
    if mode == "none":
        return np.ones(test["y_true"].shape, dtype=np.float32)
    grid = fit_conformal_grid(
        cal["y_true"], cal["mean"], cal["lower"], cal["upper"], cal["city_id"],
        cal["daylight"], mode, ALPHA, window_start=cal["window_start"],
    )
    return grid.factor_array(test["city_id"], test["daylight"], test["window_start"])


def strip_correction(test: dict, cal: dict, experiment_id: str) -> tuple[dict, np.ndarray]:
    """(uncorrected run, applied factors), verified by re-applying them.

    The check is the point: if the recovered factors do not reproduce the stored intervals, the
    baseline is wrong and every mode below would be scored against the wrong thing. Better to
    stop than to publish a ranking built on it.
    """
    factors = np.asarray(test["conformal_k"] if "conformal_k" in test
                         else uncorrect(test, cal, experiment_id), dtype=np.float32)
    mean = test["mean"]
    base = dict(test)
    base["lower"] = mean + (test["lower"] - mean) / factors
    base["upper"] = mean + (test["upper"] - mean) / factors
    back_lower, back_upper = _rescale(base, factors)
    worst = max(np.abs(back_lower - test["lower"]).max(), np.abs(back_upper - test["upper"]).max())
    if worst > 1e-2:
        raise RuntimeError(
            f"{experiment_id}: could not invert the applied conformal correction "
            f"(worst residual {worst:.4g} W/m^2). Refusing to rank modes against a wrong baseline."
        )
    return base, factors


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
        # Spread, not deviation. A grid fitted on its own split has the LEVEL right by
        # construction, so its max|CP-0.95| collapses toward half the spread and understates what
        # the shape cannot express; the spread is the part that survives recentring, and it is the
        # quantity ABLATION.md 8 already quotes ("5.6 pp across the 24 steps").
        "city_spread": max(per_city.values()) - min(per_city.values()),
        "step_spread": max(per_step) - min(per_step),
        "CP_step_1": per_step[0],
        "CP_step_last": per_step[-1],
        **{f"CP_{name}": value for name, value in per_city.items()},
    }


def evaluate_run(experiment_id: str) -> pd.DataFrame:
    cal = load_run_predictions(experiment_id, split="calibration")
    stored = load_run_predictions(experiment_id, split="test")
    test, applied = strip_correction(stored, cal, experiment_id)
    day = test["daylight"]
    print(f"    undid a correction with k in [{applied[day].min():.4f}, {applied[day].max():.4f}]"
          if not np.allclose(applied[day], 1.0) else "    run applied no correction")
    rows = []
    for mode in CONFORMAL_MODES:
        if mode == "none":
            lower, upper = test["lower"], test["upper"]
            extra = {"n_cells": 0, "min_cell_n": np.nan, "n_fallback": 0,
                     "k_min": 1.0, "k_max": 1.0, "oracle_dev": np.nan,
                     "oracle_city_dev": np.nan, "oracle_step_dev": np.nan,
                     "oracle_step_spread": np.nan}
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
            o = _score(test, o_lower, o_upper)
            extra = {
                "n_cells": len(frame),
                "min_cell_n": int(frame["n_calibration"].min()),
                "n_fallback": int(frame["fell_back"].sum()),
                "k_min": float(day_k.min()), "k_max": float(day_k.max()),
                "oracle_dev": o["aggregate_dev"],
                "oracle_city_dev": o["worst_city_dev"],
                "oracle_step_dev": o["worst_step_dev"],
                "oracle_step_spread": o["step_spread"],
            }
        rows.append({"experiment_id": experiment_id, "mode": mode,
                     **extra, **_score(test, lower, upper)})
    frame = pd.DataFrame(rows)
    _assert_reproduces_the_run(frame, stored, experiment_id)
    return frame


def _assert_reproduces_the_run(frame: pd.DataFrame, stored: dict, experiment_id: str) -> None:
    """The end-to-end check on the un-correction: re-deriving the run's OWN configured mode here
    must land on the score the pipeline actually wrote.

    It closes the loop on both halves at once -- the factors were recovered correctly, and this
    script's fit/apply path is the same one experiment.py used. Without it, a silent error in
    either half would produce a plausible-looking ranking of the wrong thing, which is precisely
    the failure this script was rewritten to remove.
    """
    mode = ExperimentConfig.from_json(
        OUTPUTS_DIR / "experiments" / experiment_id / "config.json").conformal_mode
    if mode == "none":
        return
    day = stored["daylight"]
    actual = abs(coverage_probability(
        stored["y_true"][day], stored["lower"][day], stored["upper"][day]) - TARGET_CI_COVERAGE)
    derived = float(frame.loc[frame["mode"] == mode, "aggregate_dev"].iloc[0])
    if abs(derived - actual) > 5e-4:
        raise RuntimeError(
            f"{experiment_id}: re-deriving its own mode {mode!r} gives |CP-0.95| = {derived:.5f} "
            f"but the run scored {actual:.5f}. The un-correction or the refit is wrong."
        )
    print(f"    check ok: refitting its own {mode!r} reproduces the run ({derived:.5f})")


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
    applied = ["aggregate_dev", "worst_city_dev", "worst_step_dev", "step_spread"]
    oracle = ["oracle_dev", "oracle_city_dev", "oracle_step_dev", "oracle_step_spread"]
    summary = (table.groupby("mode", as_index=False)
               [applied + oracle + ["n_cells", "min_cell_n", "n_fallback"]].mean()
               .set_index("mode").loc[order])
    print(f"\nmean over {len(ids)} run(s), calibrated on VALIDATION, scored on test; "
          "lower is better:")
    print(summary[applied + ["n_cells", "min_cell_n", "n_fallback"]]
          .to_string(float_format=lambda v: f"{v:.4f}"))
    print("\nsame grid shapes fitted on the TEST split itself (oracle) -- what each shape could "
          "achieve with zero transfer error:")
    print(summary[oracle].to_string(float_format=lambda v: f"{v:.4f}"))
    print(f"\nMIN_CELL_N = {MIN_CELL_N}; a mode whose min_cell_n falls below it is thinning "
          "cells into the pooled fallback.")
    print("Read the two blocks as a decomposition, one conditional at a time: the oracle column "
          "is what the SHAPE can express, and the gap up to the applied column is calibration "
          "transfer error. A residual that survives in the oracle is geometry and a rerun under a "
          "richer mode fixes it; one that appears only in the applied column is the validation "
          "split being a different ten months of a different year, and no mode fixes that.")
    print("`step_spread` (max-min coverage over the 24 steps) is the honest horizon number: a "
          "grid fitted on its own split gets the LEVEL right for free, so max|CP-0.95| flatters "
          "every oracle row while the spread does not.")


if __name__ == "__main__":
    main()
