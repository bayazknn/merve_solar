"""Training loop: MSE + a soft non-negativity penalty, early stopping, LR scheduling.

The non-negativity penalty is the one piece of the source paper's physics-constraint
machinery that transfers directly to irradiance (irradiance can't be negative either);
the paper's capacity-ceiling term has no analog for irradiance and is not included.
"""
import copy

import torch
import torch.nn as nn

from merve_solar.datasets import make_dataloader
from merve_solar.utils import get_device


def nonneg_penalty(pred: torch.Tensor) -> torch.Tensor:
    return torch.relu(-pred).pow(2).mean()


def train_model(model: nn.Module, train_data: dict, val_data: dict, config, device: str | None = None):
    device = device or get_device()
    train_loader = make_dataloader(
        train_data["X"], train_data["y"], train_data["city_id"], config.batch_size, shuffle=True
    )
    val_loader = make_dataloader(
        val_data["X"], val_data["y"], val_data["city_id"], config.batch_size, shuffle=False
    )

    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=config.lr_reduce_factor, patience=config.lr_reduce_patience
    )
    mse_loss = nn.MSELoss()

    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0
    history = []

    for epoch in range(config.max_epochs):
        model.train()
        train_loss_sum, n_train = 0.0, 0
        for X, city_id, y in train_loader:
            X, city_id, y = X.to(device), city_id.to(device), y.to(device)
            optimizer.zero_grad()
            pred = model(X, city_id)
            loss = mse_loss(pred, y) + config.nonneg_penalty_weight * nonneg_penalty(pred)
            loss.backward()
            optimizer.step()
            train_loss_sum += loss.item() * X.size(0)
            n_train += X.size(0)
        train_loss = train_loss_sum / n_train

        model.eval()
        val_loss_sum, n_val = 0.0, 0
        with torch.no_grad():
            for X, city_id, y in val_loader:
                X, city_id, y = X.to(device), city_id.to(device), y.to(device)
                pred = model(X, city_id)
                loss = mse_loss(pred, y) + config.nonneg_penalty_weight * nonneg_penalty(pred)
                val_loss_sum += loss.item() * X.size(0)
                n_val += X.size(0)
        val_loss = val_loss_sum / n_val

        scheduler.step(val_loss)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})

        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= config.early_stop_patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model, history
