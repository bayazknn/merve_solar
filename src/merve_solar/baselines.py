"""Naive reference forecasts, scored through the same pipeline as the models.

These exist because a metric is only interpretable against a floor. Measured on this dataset,
a climatological lookup table scores R^2 = 0.92 over all 24 hours -- so an impressive-looking
all-hours R^2 in a results table can be worse than a monthly average, and a model that does not
beat these is not a result. They cost seconds: no training, no scaler, no sweep.

Each returns predictions shaped (1, N, horizon) so they flow through metrics.py unchanged.
With a single sample the predictive distribution is degenerate: the interval metrics
(CP/PINW/MPIW/CWC/Reliability) are meaningless and are reported as NaN, but CRPS is not --
for a point forecast it reduces exactly to MAE, which is a legitimate proper-score value.
"""
import numpy as np
import pandas as pd

from merve_solar.config import TARGET_COLUMN
from merve_solar.windows import build_experiment_windows

HOURS_PER_DAY = 24

# Smart persistence (yhat(T) = kt(T-24h) * CLRSKY(T)) used to sit here as a third rule. It
# needs a clear-sky MAGNITUDE, which the 14-Sep-2026 export no longer supplies, and no
# substitute model reproduces it closely enough to serve as a reference floor -- see
# MODEL_FAMILIES in config.py for the measurement. It is removed rather than approximated:
# a floor the model is judged against has to be a fact about the data, not about a model we
# swapped in.
BASELINE_COLUMNS = {
    "climatology": "_pred_climatology",
    "persistence": "_pred_persistence",
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

    # Where the lag is missing the window genuinely has no yesterday; it stays missing rather
    # than becoming a confident zero, and build_baseline_predictions drops those windows from
    # every arm together.
    return df


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

    # Same clamp experiment.py applies to the LSTM arms, for the same reason: below the horizon
    # the target is exactly zero by geometry. Applying it here is what makes these rows honest
    # reference floors -- the ledger records clamp_night_to_zero for them either way, so leaving
    # it out would make the column describe something the run did not do. The effect is small
    # (climatology's all-hours MAE moves 37.86 -> 37.82; only the (city, month, hour) mean is
    # nonzero at night at all, at edge hours of a monthly cell) but "small" is not "absent".
    if config.clamp_night_to_zero:
        night = ~layout["daylight"]
        for preds in predictions.values():
            preds[:, night] = 0.0

    return {"predictions": predictions, "layout": layout}
