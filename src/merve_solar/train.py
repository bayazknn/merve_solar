"""Training loop: config-selected fit criterion + a soft non-negativity penalty, early
stopping, LR scheduling.

The non-negativity penalty is the one piece of the source paper's physics-constraint
machinery that transfers directly to irradiance (irradiance can't be negative either);
the paper's capacity-ceiling term has no analog for irradiance and is not included. It is
added on top of whichever fit criterion is selected -- it is a physics constraint, not part
of the fit criterion, so it must not change when the criterion does.
"""
import copy

import torch
import torch.nn as nn

from merve_solar.datasets import make_dataloader
from merve_solar.utils import get_device

# config.loss_function -> criterion. MSE optimises the conditional mean, L1 the conditional
# median; on a right-skewed error distribution those are different forecasts. See
# config.LOSS_FUNCTIONS for why that matters here.
LOSS_CRITERIA = {"mse": nn.MSELoss, "mae": nn.L1Loss, "huber": nn.HuberLoss}


def make_criterion(config) -> nn.Module:
    """The fit criterion for this config, in SCALED target space (unchanged from before).

    Exposed separately so a test can assert on the criterion itself rather than inferring the
    choice from a metric, which a lucky seed could fake. reduction="none" so the daylight mask
    can be applied per element; the unmasked path takes the plain mean and is unchanged.
    """
    kwargs = {"reduction": "none"}
    if config.loss_function == "huber":
        kwargs["delta"] = config.huber_delta
    return LOSS_CRITERIA[config.loss_function](**kwargs)


def fit_loss(criterion, pred, target, daylight, daylight_only: bool):
    """Mean fit loss, over daylight elements only when the config asks for it.

    Returns None when a batch has no daylight element at all, so the caller can skip it rather
    than propagate a NaN. Night rows are ~48.8% of the target and identical across provinces,
    so masking them concentrates the gradient on the hours that actually carry signal -- but it
    leaves night outputs unsupervised, which is why it is off by default.
    """
    per_element = criterion(pred, target)
    if not daylight_only:
        return per_element.mean()
    if not daylight.any():
        return None
    return per_element[daylight].mean()


def nonneg_penalty(pred: torch.Tensor) -> torch.Tensor:
    return torch.relu(-pred).pow(2).mean()


def train_model(model: nn.Module, train_data: dict, val_data: dict, config, device: str | None = None):
    device = device or get_device()
    train_loader = make_dataloader(
        train_data["X"], train_data["y"], train_data["city_id"], config.batch_size,
        shuffle=True, daylight=train_data.get("daylight"),
    )
    # The validation loss must use the same masking as training, or early stopping and the LR
    # schedule would be selecting on a different objective than the one being optimised.
    val_loader = make_dataloader(
        val_data["X"], val_data["y"], val_data["city_id"], config.batch_size,
        shuffle=False, daylight=val_data.get("daylight"),
    )

    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=config.lr_reduce_factor, patience=config.lr_reduce_patience
    )
    criterion = make_criterion(config)

    best_val_loss = float("inf")
    best_state = None
    patience_counter = 0
    history = []

    for epoch in range(config.max_epochs):
        model.train()
        train_loss_sum, n_train = 0.0, 0
        for X, city_id, y, daylight in train_loader:
            X, city_id, y = X.to(device), city_id.to(device), y.to(device)
            daylight = daylight.to(device)
            optimizer.zero_grad()
            pred = model(X, city_id)
            fit = fit_loss(criterion, pred, y, daylight, config.loss_daylight_only)
            if fit is None:  # no daylight element in this batch; nothing to learn from
                continue
            loss = fit + config.nonneg_penalty_weight * nonneg_penalty(pred)
            loss.backward()
            optimizer.step()
            train_loss_sum += loss.item() * X.size(0)
            n_train += X.size(0)
        train_loss = train_loss_sum / max(n_train, 1)

        model.eval()
        val_loss_sum, n_val = 0.0, 0
        with torch.no_grad():
            for X, city_id, y, daylight in val_loader:
                X, city_id, y = X.to(device), city_id.to(device), y.to(device)
                daylight = daylight.to(device)
                pred = model(X, city_id)
                fit = fit_loss(criterion, pred, y, daylight, config.loss_daylight_only)
                if fit is None:
                    continue
                loss = fit + config.nonneg_penalty_weight * nonneg_penalty(pred)
                val_loss_sum += loss.item() * X.size(0)
                n_val += X.size(0)
        val_loss = val_loss_sum / max(n_val, 1)

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
