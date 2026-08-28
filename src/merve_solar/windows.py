"""Per-city sliding windows (lookback-in/horizon-out) with split-boundary-safe assignment.

Windows are built strictly per city (never crossing a city boundary) and pooled
after. A window is assigned to a split only if its full lookback+horizon span
falls entirely inside that split's date range; boundary-straddling windows are
dropped.
"""
import numpy as np
import pandas as pd

from merve_solar.config import (
    CITIES,
    DAYLIGHT_REFERENCE_COLUMN,
    NUMERIC_FEATURE_COLUMNS,
    TARGET_COLUMN,
)


def compute_split_boundaries(df: pd.DataFrame, config) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Chronological split boundaries, derived from the FULL multi-city frame.

    Hours are counted off CITIES[0], so a partial frame would silently produce nonsense
    (a Konya-only frame returns start-1h for both boundaries rather than raising). Both
    arms of the training-scope ablation must share byte-identical boundaries, so compute
    these once here and pass them down to build_experiment_windows.
    """
    missing = [city for city in CITIES if city not in set(df["city"].unique())]
    if missing:
        raise ValueError(
            f"compute_split_boundaries needs the full multi-city frame (it counts hours via "
            f"CITIES[0]={CITIES[0]!r}); missing: {missing}. Compute boundaries once on base_df "
            "and pass them to build_experiment_windows."
        )
    if df.groupby("city").size().nunique() != 1:
        raise ValueError(
            "Cities have differing row counts; the split boundaries derived from CITIES[0] "
            "would not apply to the others."
        )

    start_ts = df["datetime"].min()
    total_hours = int((df["city"] == CITIES[0]).sum())
    train_hours = int(round(total_hours * config.train_ratio))
    val_hours = int(round(total_hours * config.val_ratio))
    train_end = start_ts + pd.Timedelta(hours=train_hours - 1)
    val_end = start_ts + pd.Timedelta(hours=train_hours + val_hours - 1)
    return train_end, val_end


def _build_city_windows(city_df: pd.DataFrame, lookback: int, horizon: int, stride: int, include_X: bool = True):
    if len(city_df) == 0:
        raise ValueError("no rows for this city — check the city name and the frame passed in")

    city_df = city_df.sort_values("datetime").reset_index(drop=True)
    dt = city_df["datetime"].to_numpy()

    diffs = np.diff(dt).astype("timedelta64[h]").astype(int)
    if len(diffs) and not np.all(diffs == 1):
        raise ValueError("Non-contiguous hourly series detected within a city's data.")

    target = city_df[TARGET_COLUMN].to_numpy(dtype=np.float32)
    # Daylight is decided by clear-sky irradiance (pure solar geometry), never by the realised
    # target — so the mask never conditions on the outcome. See config.py MASK_COLUMNS.
    daylight_hour = (city_df[DAYLIGHT_REFERENCE_COLUMN].to_numpy() > 0)
    city_id = int(city_df["city_id"].iloc[0])

    span = lookback + horizon
    total_rows = len(city_df)
    n_windows = (total_rows - span) // stride + 1
    n_features = len(NUMERIC_FEATURE_COLUMNS)

    if n_windows <= 0:
        empty_dt = np.empty((0,), dtype=dt.dtype)
        return (
            np.empty((0, lookback, n_features), dtype=np.float32) if include_X else None,
            np.empty((0, horizon), dtype=np.float32),
            np.empty((0, horizon), dtype=bool),
            np.empty((0,), dtype=np.int64),
            empty_dt,
            empty_dt,
        )

    starts = np.arange(n_windows) * stride
    if include_X:
        values = city_df[NUMERIC_FEATURE_COLUMNS].to_numpy(dtype=np.float32)
        X = np.stack([values[starts + o] for o in range(lookback)], axis=1)
    else:
        X = None
    y = np.stack([target[starts + lookback + o] for o in range(horizon)], axis=1)
    daylight = np.stack([daylight_hour[starts + lookback + o] for o in range(horizon)], axis=1)
    city_ids = np.full(n_windows, city_id, dtype=np.int64)
    window_start = dt[starts]
    window_end = dt[starts + span - 1]
    return X, y, daylight, city_ids, window_start, window_end


def build_experiment_windows(
    df: pd.DataFrame,
    config,
    train_end: pd.Timestamp,
    val_end: pd.Timestamp,
    cities: list | None = None,
    include_X: bool = True,
) -> dict:
    """Returns {'train'/'val'/'test': {'X', 'y', 'daylight', 'city_id', 'window_start'}}.

    cities=None means all CITIES (the global arm). Passing a single-element list builds that
    city's block alone, with output row-identical and order-identical to that city's slice of
    the pooled global build — which is what lets the per_city ablation arm assemble its
    predictions back into the global layout by mask.

    include_X=False skips the (N, lookback, F) allocation. Used for a cheap "layout" pass that
    yields the canonical raw-W/m^2 ground truth, city ids, daylight mask and window timestamps
    without training anything.
    """
    cities = list(CITIES) if cities is None else list(cities)
    train_end_np = np.datetime64(train_end)
    val_end_np = np.datetime64(val_end)

    per_split_parts = {"train": [], "val": [], "test": []}
    for city in cities:
        X, y, daylight, city_ids, w_start, w_end = _build_city_windows(
            df[df["city"] == city],
            config.lookback_hours,
            config.horizon_hours,
            config.window_stride,
            include_X=include_X,
        )

        masks = {
            "train": w_end <= train_end_np,
            "val": (w_start > train_end_np) & (w_end <= val_end_np),
            "test": w_start > val_end_np,
        }
        for split_name, m in masks.items():
            per_split_parts[split_name].append(
                (None if X is None else X[m], y[m], daylight[m], city_ids[m], w_start[m])
            )

    result = {}
    for split_name, parts in per_split_parts.items():
        Xs, ys, days, cids, starts = zip(*parts)
        result[split_name] = {
            "X": None if Xs[0] is None else np.concatenate(Xs, axis=0),
            "y": np.concatenate(ys, axis=0),
            "daylight": np.concatenate(days, axis=0),
            "city_id": np.concatenate(cids, axis=0),
            "window_start": np.concatenate(starts, axis=0),
        }
    return result
