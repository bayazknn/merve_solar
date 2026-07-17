"""Monte Carlo Dropout inference: T stochastic forward passes with dropout kept active.

Per the methodology doc: model.train() (NOT .eval()) so dropout stays active,
predictions collected under torch.no_grad().
"""
import numpy as np
import torch
import torch.nn as nn


def mc_dropout_predict(
    model: nn.Module,
    X: np.ndarray,
    city_id: np.ndarray,
    T: int,
    batch_size: int = 512,
    device: str = "cpu",
) -> np.ndarray:
    """Returns predictions of shape (T, N, horizon)."""
    model.to(device)
    model.train()  # dropout active — deliberately not .eval()

    n = len(X)
    X_t = torch.as_tensor(X, dtype=torch.float32)
    city_id_t = torch.as_tensor(city_id, dtype=torch.long)

    passes = []
    with torch.no_grad():
        for _ in range(T):
            outputs = []
            for start in range(0, n, batch_size):
                end = min(start + batch_size, n)
                xb = X_t[start:end].to(device)
                cb = city_id_t[start:end].to(device)
                outputs.append(model(xb, cb).cpu().numpy())
            passes.append(np.concatenate(outputs, axis=0))
    return np.stack(passes, axis=0)
