"""Re-analysis of a finished run from its saved prediction summary.

The (S, N, horizon) pooled sample is ~3.4 GB at full fidelity and is deliberately never
persisted; `experiment.py::_save_test_predictions` keeps mean/lower/upper alongside the truth,
the city ids, the daylight mask and the window timestamps (~12 MB compressed). That file is
enough to re-slice a completed run along any axis without retraining or even reloading a
checkpoint, which is what this module is for:

* **per (city x horizon-step) metrics**, which `metrics.py` does not emit -- `results_summary.csv`
  is per city pooled over the horizon, `results_by_horizon.csv` is per step pooled over the
  cities, and the paper needs the cross of the two (how each province's error and coverage grow
  with lead time, the grid a conformal factor is fitted on, the cells a paired test runs in).
* later, conformal interval rescaling and the paired significance tests, which are post-hoc by
  nature and share exactly this input.

CRPS is out of scope here and is emitted as NaN: it is the one reported metric that genuinely
needs the S samples rather than their summary. It is already reported aggregate, per city and
per horizon by the pipeline itself.

The npz files are gitignored (`outputs/**/metrics/*.npz`), so this runs where the experiment
ran, not on a machine that only synced the CSVs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CITIES, CITY_TO_ID, PROJECT_ROOT
from .metrics import compute_metrics_for_subset

PREDICTION_FILENAME = "test_predictions.npz"
CITY_HORIZON_FILENAME = "results_by_city_horizon.csv"

# Everything compute_metrics_for_subset returns that does NOT need the pooled sample. CRPS is
# excluded by name rather than by dropping NaNs, so a future metric that also needs the sample
# fails loudly here instead of silently arriving as a NaN column.
SUMMARY_ONLY_METRICS = (
    "RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC", "n_samples", "n_elements",
)


def prediction_path(experiment_id: str):
    return PROJECT_ROOT / "outputs" / "experiments" / experiment_id / "metrics" / PREDICTION_FILENAME


def load_run_predictions(experiment_id: str) -> dict:
    """mean/lower/upper/y_true (N, H), city_id (N,), daylight (N, H), window_start (N,)."""
    path = prediction_path(experiment_id)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. It is gitignored, so it exists only on the machine that ran "
            f"{experiment_id}; run this there, or rerun the experiment to regenerate it."
        )
    with np.load(path) as z:
        run = {k: z[k] for k in z.files}
    run["window_start"] = run["window_start"].astype("datetime64[h]")
    _assert_shapes(run, experiment_id)
    return run


def _assert_shapes(run: dict, experiment_id: str) -> None:
    n, h = run["y_true"].shape
    for key in ("mean", "lower", "upper", "daylight"):
        if run[key].shape != (n, h):
            raise ValueError(f"{experiment_id}: {key} is {run[key].shape}, expected {(n, h)}")
    for key in ("city_id", "window_start"):
        if run[key].shape != (n,):
            raise ValueError(f"{experiment_id}: {key} is {run[key].shape}, expected {(n,)}")
    # An interval that does not contain its own centre would make every coverage number below
    # meaningless, and is the shape a mis-ordered percentile slice takes.
    if not (run["lower"] <= run["upper"]).all():
        raise ValueError(f"{experiment_id}: lower exceeds upper in {(run['lower'] > run['upper']).sum()} elements")


def run_cities(run: dict) -> list[str]:
    """Provinces present in this run, in CITIES order -- ids are never renumbered."""
    present = set(np.unique(run["city_id"]).tolist())
    return [c for c in CITIES if CITY_TO_ID[c] in present]


def _dist(run: dict, rows, step) -> tuple[dict, np.ndarray, np.ndarray]:
    sl = slice(step, step + 1)
    dist = {k: run[k][rows, sl] for k in ("mean", "lower", "upper")}
    return dist, run["y_true"][rows, sl], run["daylight"][rows, sl]


def city_horizon_table(run: dict, cities: list[str] | None = None) -> pd.DataFrame:
    """One row per (city, horizon_step, subset). CRPS is NaN by design -- see the module docstring."""
    cities = run_cities(run) if cities is None else cities
    horizon = run["y_true"].shape[1]
    rows = []
    for city in cities:
        sel = run["city_id"] == CITY_TO_ID[city]
        if not sel.any():
            continue
        for step in range(horizon):
            dist, y, day = _dist(run, sel, step)
            for subset, mask in (("all_hours", None), ("daylight", day)):
                m = compute_metrics_for_subset(None, y, mask, dist)
                rows.append({"group": city, "horizon_step": step + 1, "subset": subset,
                             **{k: m[k] for k in SUMMARY_ONLY_METRICS}, "CRPS": m["CRPS"]})
    return pd.DataFrame(rows).sort_values(["subset", "group", "horizon_step"]).reset_index(drop=True)


def check_against_pipeline_csvs(experiment_id: str, table: pd.DataFrame, tol: float = 1e-4) -> list[str]:
    """Cross-check the new table against what the pipeline already wrote.

    n_elements must partition exactly two ways: summed over horizon steps it is the per-city row
    of results_summary.csv, summed over cities it is the row of results_by_horizon.csv. This is
    the guard that a (city, step) slice went to the right cell -- a transposition changes no
    shape and no total, only which province gets which numbers, and would otherwise be invisible.

    Returns a list of human-readable mismatches; empty means agreement.
    """
    base = prediction_path(experiment_id).parent
    problems = []
    for name, keys, group_col in (("results_summary.csv", ["group", "subset"], "group"),
                                  ("results_by_horizon.csv", ["horizon_step", "subset"], "horizon_step")):
        path = base / name
        if not path.exists():
            problems.append(f"{name} missing, cannot cross-check")
            continue
        ref = pd.read_csv(path)
        got = table.groupby(keys, as_index=False)["n_elements"].sum()
        merged = got.merge(ref[keys + ["n_elements"]], on=keys, suffixes=("_new", "_ref"))
        if merged.empty:
            problems.append(f"{name}: no overlapping {group_col} rows to compare")
        bad = merged[merged["n_elements_new"] != merged["n_elements_ref"]]
        for _, r in bad.iterrows():
            problems.append(
                f"{name}: {group_col}={r[group_col]} subset={r['subset']} "
                f"n_elements {int(r['n_elements_new'])} != {int(r['n_elements_ref'])}"
            )
        # RMSE cannot be summed, but the per-city (pooled over steps) value must reproduce from
        # the cells: sqrt of the n_elements-weighted mean of the squared cell RMSEs.
        if name == "results_summary.csv":
            w = table.assign(sse=table["RMSE"] ** 2 * table["n_elements"])
            pooled = w.groupby(keys, as_index=False)[["sse", "n_elements"]].sum()
            pooled["RMSE"] = np.sqrt(pooled["sse"] / pooled["n_elements"])
            m = pooled.merge(ref[keys + ["RMSE"]], on=keys, suffixes=("_new", "_ref"))
            for _, r in m[np.abs(m["RMSE_new"] - m["RMSE_ref"]) > tol].iterrows():
                problems.append(
                    f"{name}: {r['group']} subset={r['subset']} pooled RMSE "
                    f"{r['RMSE_new']:.6f} != {r['RMSE_ref']:.6f}"
                )
    return problems


def write_city_horizon_table(experiment_id: str, check: bool = True) -> tuple[pd.DataFrame, list[str]]:
    run = load_run_predictions(experiment_id)
    table = city_horizon_table(run)
    problems = check_against_pipeline_csvs(experiment_id, table) if check else []
    out = prediction_path(experiment_id).parent / CITY_HORIZON_FILENAME
    table.to_csv(out, index=False)
    return table, problems
