"""Seeding, checkpoint IO, and plotting helpers."""
import random
from pathlib import Path

import numpy as np
import torch


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def get_device() -> str:
    """Best available torch device: MPS (Apple Silicon) > CUDA (Nvidia) > CPU."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def save_checkpoint(model: torch.nn.Module, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)


def plot_forecast_with_ci(x_values, y_true, mean, lower, upper, title: str, save_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x_values, y_true, label="True", color="black")
    ax.plot(x_values, mean, label="Predicted mean", color="tab:blue")
    ax.fill_between(x_values, lower, upper, color="tab:blue", alpha=0.2, label="95% CI")
    ax.set_title(title)
    ax.set_xlabel("Horizon step (h)")
    ax.set_ylabel("Solar irradiance (W/m^2)")
    ax.legend()
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=120)
    plt.close(fig)


def plot_metric_vs_horizon(df, metric_col: str, title: str, save_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(df["horizon_step"], df[metric_col], marker="o")
    ax.set_title(title)
    ax.set_xlabel("Horizon step (h)")
    ax.set_ylabel(metric_col)
    fig.tight_layout()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path, dpi=120)
    plt.close(fig)
