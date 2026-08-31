"""Monte Carlo Dropout inference: T stochastic forward passes with dropout kept active.

Per the methodology doc: model.train() (NOT .eval()) so dropout stays active,
predictions collected under torch.no_grad().
"""
import numpy as np
import torch
import torch.nn as nn

from merve_solar.utils import get_device


def mc_dropout_predict(
    model: nn.Module,
    X: np.ndarray,
    city_id: np.ndarray,
    T: int,
    batch_size: int = 512,
    device: str | None = None,
) -> np.ndarray:
    """Returns predictions of shape (T, N, horizon)."""
    device = device or get_device()
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


# One pooled calibration block, in array elements (S * columns). The conformal layer needs the
# 2.5/97.5 percentiles over all B*T passes on the CALIBRATION split, which at full fidelity is a
# second ~2.5 GB array alongside the test one. Chunking over the window axis is exact (every
# statistic is per-element) and bounds it to ~250 MB instead.
CALIBRATION_CHUNK_ELEMENTS = 64_000_000


def pooled_summary(
    models: list,
    X: np.ndarray,
    city_id: np.ndarray,
    T: int,
    horizon: int,
    device: str | None = None,
    chunk_elements: int = CALIBRATION_CHUNK_ELEMENTS,
) -> dict:
    """mean/std/lower/upper over len(models) * T MC-Dropout passes, without ever materialising
    the full (S, N, horizon) sample.

    Same pooling as the test path -- every model contributes T passes and the percentiles are
    taken over the pooled S = B*T -- so the intervals this summarises are the same object the
    test intervals are, which is what the conformal transfer requires. Splitting the work by
    window rather than by pass is what makes that possible: each element's statistics depend only
    on that element's S values.
    """
    from merve_solar.metrics import summarize_predictive_distribution

    n = len(X)
    S = len(models) * T
    out = {k: np.empty((n, horizon), dtype=np.float32) for k in ("mean", "std", "lower", "upper")}
    step = max(1, chunk_elements // max(1, S * horizon))
    block = np.empty((S, min(step, max(n, 1)), horizon), dtype=np.float32)

    for start in range(0, n, step):
        stop = min(start + step, n)
        view = block[:, : stop - start, :]
        for b, model in enumerate(models):
            view[b * T:(b + 1) * T] = mc_dropout_predict(
                model, X[start:stop], city_id[start:stop], T, device=device
            )
        chunk_summary = summarize_predictive_distribution(view)
        for key, value in chunk_summary.items():
            out[key][start:stop] = value
    return out
