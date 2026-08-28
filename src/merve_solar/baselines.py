"""Naive reference forecasts, scored through the same pipeline as the models.

These exist because a metric is only interpretable against a floor. Measured on this dataset,
a climatological lookup table scores R^2 = 0.923 over all 24 hours -- so an impressive-looking
all-hours R^2 in a results table can be worse than a monthly average, and a model that does not
beat these is not a result. They cost seconds: no training, no scaler, no sweep.

Each returns predictions shaped (1, N, horizon) so they flow through metrics.py unchanged.
With a single sample the predictive distribution is degenerate: the interval metrics
(CP/PINW/MPIW/CWC/Reliability) are meaningless and are reported as NaN, but CRPS is not --
for a point forecast it reduces exactly to MAE, which is a legitimate proper-score value.
"""
import numpy as np
import pandas as pd

from merve_solar.config import DAYLIGHT_REFERENCE_COLUMN, TARGET_COLUMN
from merve_solar.windows import build_experiment_windows

HOURS_PER_DAY = 24

# Physical ceiling on the carried-forward clear-sky index. Occasional hours measure slightly
# above the clear-sky reference (cloud-edge reflection), and letting those propagate a day
# forward would produce predictions above the clear-sky curve.
MAX_CLEARNESS_INDEX = 1.1

BASELINE_COLUMNS = {
    "climatology": "_pred_climatology",
    "persistence": "_pred_persistence",
    "smart_persistence": "_pred_smart_persistence",
}


def add_baseline_columns(base_df: pd.DataFrame, train_end: pd.Timestamp) -> pd.DataFrame:
    """Attach one per-hour prediction column per baseline rule.

    Everything is fitted on training rows only (`datetime <= train_end`), exactly like the
    scaler. Predictions are computed per hour here and gathered into windows afterwards by
    build_experiment_windows, so they are aligned by the same indexing the model's targets are
    rather than by a parallel implementation that could drift.
    """
    df = base_df.sort_values(["city", "datetime"]).reset_index(drop=True).copy()

    # Climatology: the (city, month, hour) mean over training rows.
    train_rows = df[df["datetime"] <= train_end]
    climatology = train_rows.groupby(["city", "MO", "HR"])[TARGET_COLUMN].mean().rename("_clim")
    df = df.join(climatology, on=["city", "MO", "HR"])
    df[BASELINE_COLUMNS["climatology"]] = df["_clim"].astype(np.float32)
    df = df.drop(columns="_clim")

    # Persistence: the same hour one day earlier.
    by_city = df.groupby("city", sort=False)[TARGET_COLUMN]
    df[BASELINE_COLUMNS["persistence"]] = by_city.shift(HOURS_PER_DAY).astype(np.float32)

    # Smart persistence: carry yesterday's clear-sky index forward and re-apply it to today's
    # clear-sky irradiance. kt is undefined at night (CLRSKY = 0); filling those with 0 rather
    # than leaving NaN matters, because a NaN carried forward would silently drop every night
    # row from this reference alone and make its scope incomparable with the others. Yesterday's
    # night has clearness 0 and tonight's clear-sky is 0, so the prediction is 0 either way.
    clearsky = df[DAYLIGHT_REFERENCE_COLUMN].to_numpy(dtype=np.float64)
    kt = np.divide(
        df[TARGET_COLUMN].to_numpy(dtype=np.float64), clearsky,
        out=np.zeros(len(df)), where=clearsky > 0,
    )
    df["_kt"] = kt
    kt_lag = df.groupby("city", sort=False)["_kt"].shift(HOURS_PER_DAY).clip(upper=MAX_CLEARNESS_INDEX)
    df[BASELINE_COLUMNS["smart_persistence"]] = (
        (kt_lag.fillna(0.0).to_numpy() * clearsky).clip(min=0).astype(np.float32)
    )
    # Where the plain lag is missing the window genuinely has no yesterday, so keep it missing
    # rather than letting it become a confident zero.
    df.loc[df[BASELINE_COLUMNS["persistence"]].isna(), BASELINE_COLUMNS["smart_persistence"]] = np.nan
    return df.drop(columns="_kt")


def build_baseline_predictions(base_df: pd.DataFrame, config, train_end, val_end) -> dict:
    """{'baseline name': (1, N_test, horizon)} plus the shared test layout.

    Windows whose prediction is undefined for ANY baseline (the first day of each city's
    series has no previous day) are dropped from every arm together, so all references and the
    layout they are scored against cover exactly the same windows.
    """
    with_preds = add_baseline_columns(base_df, train_end)
    columns = tuple(BASELINE_COLUMNS.values())
    windows = build_experiment_windows(
        with_preds, config, train_end, val_end, include_X=False, extra_target_columns=columns
    )
    test = windows["test"]

    usable = np.ones(test["y"].shape[0], dtype=bool)
    for column in columns:
        usable &= ~np.isnan(test["extras"][column]).any(axis=1)

    layout = {
        "y": test["y"][usable],
        "daylight": test["daylight"][usable],
        "city_id": test["city_id"][usable],
        "window_start": test["window_start"][usable],
        "n_dropped": int((~usable).sum()),
    }
    predictions = {
        name: test["extras"][column][usable][None, :, :].astype(np.float32)
        for name, column in BASELINE_COLUMNS.items()
    }
    return {"predictions": predictions, "layout": layout}
