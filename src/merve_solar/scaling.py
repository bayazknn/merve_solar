"""Leakage-safe scaling: fit on train-range rows only, apply everywhere."""
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from merve_solar.config import NUMERIC_FEATURE_COLUMNS, TARGET_COLUMN


def fit_scaler(df: pd.DataFrame, train_end: pd.Timestamp) -> StandardScaler:
    train_mask = df["datetime"] <= train_end
    scaler = StandardScaler()
    scaler.fit(df.loc[train_mask, NUMERIC_FEATURE_COLUMNS].to_numpy(dtype=np.float64))
    return scaler


def apply_scaler(df: pd.DataFrame, scaler: StandardScaler) -> pd.DataFrame:
    df = df.copy()
    df[NUMERIC_FEATURE_COLUMNS] = scaler.transform(
        df[NUMERIC_FEATURE_COLUMNS].to_numpy(dtype=np.float64)
    )
    return df


def save_scaler(scaler: StandardScaler, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, path)


def load_scaler(path) -> StandardScaler:
    return joblib.load(path)


def inverse_transform_target(scaler: StandardScaler, scaled_values: np.ndarray) -> np.ndarray:
    """Inverse-transform an array of scaled target values back to W/m^2.

    Preserves the input dtype (float32 in -> float32 out). The pooled prediction array is
    ~3.4 GB at the default n_bootstrap=8 x mc_dropout_passes=100; promoting it to float64
    here is what made the full-fidelity run exhaust memory. Precision cost is nil: float32
    represents 1216 W/m^2 to within ~1.5e-4, six orders of magnitude below an RMSE of ~50-80.
    """
    target_idx = NUMERIC_FEATURE_COLUMNS.index(TARGET_COLUMN)
    dtype = np.result_type(scaled_values.dtype, np.float32)
    mean = dtype.type(scaler.mean_[target_idx])
    scale = dtype.type(scaler.scale_[target_idx])
    return scaled_values * scale + mean
