"""Per-city sliding windows (lookback-in/horizon-out) with split-boundary-safe assignment.

Windows are built strictly per city (never crossing a city boundary) and pooled
after. A window is assigned to a split only if its full lookback+horizon span
falls entirely inside that split's date range; boundary-straddling windows are
dropped.
"""
import numpy as np
import pandas as pd

from merve_solar.config import CITIES, NUMERIC_FEATURE_COLUMNS, TARGET_COLUMN


def compute_split_boundaries(df: pd.DataFrame, config) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_ts = df["datetime"].min()
    total_hours = int((df["city"] == CITIES[0]).sum())
    train_hours = int(round(total_hours * config.train_ratio))
    val_hours = int(round(total_hours * config.val_ratio))
    train_end = start_ts + pd.Timedelta(hours=train_hours - 1)
    val_end = start_ts + pd.Timedelta(hours=train_hours + val_hours - 1)
    return train_end, val_end


def _build_city_windows(city_df: pd.DataFrame, lookback: int, horizon: int, stride: int):
    city_df = city_df.sort_values("datetime").reset_index(drop=True)
    dt = city_df["datetime"].to_numpy()

    diffs = np.diff(dt).astype("timedelta64[h]").astype(int)
    if len(diffs) and not np.all(diffs == 1):
        raise ValueError("Non-contiguous hourly series detected within a city's data.")

    values = city_df[NUMERIC_FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    target = city_df[TARGET_COLUMN].to_numpy(dtype=np.float32)
    city_id = int(city_df["city_id"].iloc[0])

    span = lookback + horizon
    total_rows = len(city_df)
    n_windows = (total_rows - span) // stride + 1
    n_features = values.shape[1]

    if n_windows <= 0:
        empty_dt = np.empty((0,), dtype=dt.dtype)
        return (
            np.empty((0, lookback, n_features), dtype=np.float32),
            np.empty((0, horizon), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
            empty_dt,
            empty_dt,
        )

    starts = np.arange(n_windows) * stride
    X = np.stack([values[starts + o] for o in range(lookback)], axis=1)
    y = np.stack([target[starts + lookback + o] for o in range(horizon)], axis=1)
    city_ids = np.full(n_windows, city_id, dtype=np.int64)
    window_start = dt[starts]
    window_end = dt[starts + span - 1]
    return X, y, city_ids, window_start, window_end


def build_experiment_windows(
    df: pd.DataFrame,
    config,
    train_end: pd.Timestamp,
    val_end: pd.Timestamp,
) -> dict:
    """Returns {'train'/'val'/'test': {'X', 'y', 'city_id'}}."""
    train_end_np = np.datetime64(train_end)
    val_end_np = np.datetime64(val_end)

    per_split_parts = {"train": [], "val": [], "test": []}
    for city in CITIES:
        city_df = df[df["city"] == city]
        X, y, city_ids, w_start, w_end = _build_city_windows(
            city_df, config.lookback_hours, config.horizon_hours, config.window_stride
        )

        train_mask = w_end <= train_end_np
        val_mask = (w_start > train_end_np) & (w_end <= val_end_np)
        test_mask = w_start > val_end_np

        per_split_parts["train"].append((X[train_mask], y[train_mask], city_ids[train_mask]))
        per_split_parts["val"].append((X[val_mask], y[val_mask], city_ids[val_mask]))
        per_split_parts["test"].append((X[test_mask], y[test_mask], city_ids[test_mask]))

    result = {}
    for split_name, parts in per_split_parts.items():
        Xs, ys, cids = zip(*parts)
        result[split_name] = {
            "X": np.concatenate(Xs, axis=0),
            "y": np.concatenate(ys, axis=0),
            "city_id": np.concatenate(cids, axis=0),
        }
    return result
