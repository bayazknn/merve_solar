"""torch Dataset/DataLoader wrappers over windowed arrays."""
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset


class WindowDataset(Dataset):
    """X/y/city_id, plus the per-element daylight mask when the loss needs it.

    `daylight` is (N, horizon) bool from windows.py. When omitted it is all-True, so the
    masked and unmasked training paths are one code path rather than two.
    """

    def __init__(self, X: np.ndarray, y: np.ndarray, city_id: np.ndarray, daylight: np.ndarray | None = None):
        self.X = torch.as_tensor(X, dtype=torch.float32)
        self.y = torch.as_tensor(y, dtype=torch.float32)
        self.city_id = torch.as_tensor(city_id, dtype=torch.long)
        self.daylight = (
            torch.ones_like(self.y, dtype=torch.bool)
            if daylight is None
            else torch.as_tensor(daylight, dtype=torch.bool)
        )

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.city_id[idx], self.y[idx], self.daylight[idx]


def make_dataloader(
    X: np.ndarray,
    y: np.ndarray,
    city_id: np.ndarray,
    batch_size: int,
    shuffle: bool,
    daylight: np.ndarray | None = None,
) -> DataLoader:
    return DataLoader(WindowDataset(X, y, city_id, daylight), batch_size=batch_size, shuffle=shuffle)
