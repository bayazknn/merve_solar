"""torch Dataset/DataLoader wrappers over windowed arrays."""
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset


class WindowDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray, city_id: np.ndarray):
        self.X = torch.as_tensor(X, dtype=torch.float32)
        self.y = torch.as_tensor(y, dtype=torch.float32)
        self.city_id = torch.as_tensor(city_id, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.city_id[idx], self.y[idx]


def make_dataloader(X: np.ndarray, y: np.ndarray, city_id: np.ndarray, batch_size: int, shuffle: bool) -> DataLoader:
    dataset = WindowDataset(X, y, city_id)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)
