"""Moving block bootstrap: resample contiguous window-blocks with replacement, per city.

Naive i.i.d. resampling (sklearn.utils.resample) would break the temporal
autocorrelation structure the methodology doc explicitly warns against — MBB
preserves local structure within each block while still injecting resampling
diversity across blocks.
"""
import numpy as np


def _moving_block_bootstrap_indices(n: int, block_length: int, rng: np.random.Generator) -> np.ndarray:
    if n <= 0:
        return np.empty((0,), dtype=np.int64)
    block_length = min(block_length, n)
    n_blocks = int(np.ceil(n / block_length))
    max_start = n - block_length
    block_starts = rng.integers(0, max_start + 1, size=n_blocks)
    indices = np.concatenate([np.arange(s, s + block_length) for s in block_starts])
    return indices[:n]


def resample_train_split(train_data: dict, block_length: int, rng: np.random.Generator) -> dict:
    """Resample each city's windows independently (temporal order preserved within
    blocks), then pool — mirrors how the base train set itself is built per-city."""
    city_ids = train_data["city_id"]
    resampled_positions = []
    for city in np.unique(city_ids):
        city_positions = np.where(city_ids == city)[0]
        block_idx = _moving_block_bootstrap_indices(len(city_positions), block_length, rng)
        resampled_positions.append(city_positions[block_idx])
    idx = np.concatenate(resampled_positions)
    return {
        "X": train_data["X"][idx],
        "y": train_data["y"][idx],
        "city_id": train_data["city_id"][idx],
    }
