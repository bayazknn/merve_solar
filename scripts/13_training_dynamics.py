"""Diagnostic: why does every network reach its best validation loss within the first few epochs?

    uv run python scripts/13_training_dynamics.py [--epochs 40]

Trains ONE network with the reference config (configs/config_005_default_full.json) on the
unresampled training windows, with early stopping disabled and everything else unchanged
(same seed, scaler, windows, loss, optimiser and LR schedule). After every epoch the model is
evaluated deterministically (dropout off) on the full training and validation windows, and the
errors are broken down so the two candidate explanations can be told apart:

    overfitting        training error keeps falling while validation error rises everywhere;
    validation mix     validation error rises only in some months or sites, i.e. the stopping
                       signal is driven by what the validation period happens to contain.

The test period is never touched.

Writes outputs/diagnostics/training_dynamics/{history.csv, training_dynamics.png/.pdf}.
"""
import argparse
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from merve_solar import paper_style as ps
from merve_solar.config import (
    BASE_FEATURES_PATH,
    CITIES,
    NUMERIC_FEATURE_COLUMNS,
    OUTPUTS_DIR,
    PROJECT_ROOT,
    ExperimentConfig,
)
from merve_solar.data import load_base_features
from merve_solar.experiment import _fit_scale_window
from merve_solar.model import SolarLSTM
from merve_solar.scaling import inverse_transform_target, scaled_target_zero
from merve_solar.train import make_criterion, nonneg_penalty, train_model
from merve_solar.utils import get_device, set_seed
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

CONFIG_PATH = PROJECT_ROOT / "configs" / "config_005_default_full.json"
OUT_DIR = OUTPUTS_DIR / "diagnostics" / "training_dynamics"
SEASON_ORDER = ps.SEASONS


def _predict(model, X, city_id, device, batch_size=4096):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, X.shape[0], batch_size):
            xb = torch.as_tensor(X[i:i + batch_size], dtype=torch.float32, device=device)
            cb = torch.as_tensor(city_id[i:i + batch_size], dtype=torch.long, device=device)
            out.append(model(xb, cb).cpu().numpy())
    return np.concatenate(out)


def _target_months(window_start, lookback, horizon):
    start = pd.to_datetime(window_start)
    if not np.issubdtype(np.asarray(window_start).dtype, np.datetime64):
        start = pd.to_datetime(np.asarray(window_start) * 3600, unit="s")
    offsets = np.arange(lookback, lookback + horizon) * np.timedelta64(1, "h")
    times = start.values[:, None] + offsets[None, :]
    return pd.DatetimeIndex(times.ravel()).month.values.reshape(times.shape)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args()

    base = ExperimentConfig.from_json(CONFIG_PATH)
    config = dataclasses.replace(
        base, experiment_id="diag_training_dynamics", max_epochs=args.epochs,
        early_stop_patience=10 ** 6, n_bootstrap=1,
    )
    set_seed(config.seed)
    device = get_device()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_base_features(BASE_FEATURES_PATH)
    train_end, val_end = compute_split_boundaries(df, config)
    splits, scaler = _fit_scale_window(df, config, train_end, val_end, None,
                                       OUT_DIR / "scaler.joblib")
    truth = build_experiment_windows(df, config, train_end, val_end, include_X=False)
    floor = scaled_target_zero(scaler)

    sets = {}
    for name in ("train", "val"):
        s, t = splits[name], truth[name]
        assert np.array_equal(s["window_start"], t["window_start"])
        sets[name] = dict(
            X=s["X"], z=s["y"], city=s["city_id"], y=t["y"], day=t["daylight"],
            month=_target_months(t["window_start"], config.lookback_hours, config.horizon_hours),
        )
    month_to_season = np.array([None] + [ps.MONTH_TO_SEASON[m] for m in range(1, 13)])
    criterion = make_criterion(config)
    rows = []

    def record(epoch, model):
        for name, d in sets.items():
            zhat = _predict(model, d["X"], d["city"], device)
            zt = torch.as_tensor(zhat)
            fit = criterion(zt, torch.as_tensor(d["z"])).mean().item()
            pen = nonneg_penalty(zt, floor).item()
            yhat = inverse_transform_target(scaler, zhat)
            err = yhat - d["y"]
            day = d["day"]

            def add(group, key, mask):
                e = err[mask]
                rows.append(dict(epoch=epoch, split=name, group=group, key=key,
                                 rmse=float(np.sqrt(np.mean(e ** 2))), bias=float(e.mean()),
                                 n=int(mask.sum())))

            rows.append(dict(epoch=epoch, split=name, group="loss", key="fit", rmse=fit,
                             bias=np.nan, n=int(err.size)))
            rows.append(dict(epoch=epoch, split=name, group="loss", key="penalty", rmse=pen,
                             bias=np.nan, n=int(err.size)))
            add("daylight", "all", day)
            add("night", "all", ~day)
            seasons = month_to_season[d["month"]]
            for season in SEASON_ORDER:
                if (sel := day & (seasons == season)).any():
                    add("season", season, sel)
            for cid, city in enumerate(CITIES):
                add("city", city, day & (d["city"] == cid)[:, None])
        print(f"epoch {epoch}: val daylight RMSE "
              f"{[r for r in rows if r['split'] == 'val' and r['group'] == 'daylight'][-1]['rmse']:.2f}",
              flush=True)

    model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), len(CITIES), config)
    _, history = train_model(model, splits["train"], splits["val"], config,
                             target_floor=floor, device=device, epoch_callback=record)

    hist = pd.DataFrame(rows)
    lr = pd.DataFrame(history)[["epoch", "train_loss", "val_loss", "lr"]]
    hist.to_csv(OUT_DIR / "history.csv", index=False)
    lr.to_csv(OUT_DIR / "loss_and_lr.csv", index=False)
    plot(hist, lr, OUT_DIR / "training_dynamics")
    print(f"wrote {OUT_DIR}")


def plot(hist, lr, save_path):
    best = int(lr.loc[lr["val_loss"].idxmin(), "epoch"])
    with plt.rc_context(ps.PAPER_RC):
        fig, axs = plt.subplots(2, 2, figsize=(ps.FULL_WIDTH_IN, 4.8), layout="constrained")
        a = axs[0, 0]
        for split, color, ls in (("train", ps.INK_MUTED, "--"), ("val", ps.ACCENT, "-")):
            h = hist.query("split == @split and group == 'daylight'")
            a.plot(h["epoch"], h["rmse"], color=color, ls=ls, label=f"{split}, daylight RMSE")
        a.axvline(best, color=ps.INK_MUTED, lw=0.7, ls=":")
        a.set_xlabel("Epoch")
        a.set_ylabel("RMSE (W/m²)")
        a.set_title("(a) Training vs validation error")
        a.legend(frameon=False, fontsize=6.3)

        a = axs[0, 1]
        a.plot(lr["epoch"], lr["train_loss"], color=ps.INK_MUTED, ls="--", label="train loss (dropout on)")
        a.plot(lr["epoch"], lr["val_loss"], color=ps.ACCENT, label="validation loss (Eq. 3)")
        a2 = a.twinx()
        a2.step(lr["epoch"], lr["lr"], where="post", color=ps.SEASON_COLORS["Summer"], lw=0.8)
        a2.set_yscale("log")
        a2.set_ylabel("Learning rate", color=ps.SEASON_COLORS["Summer"])
        a2.grid(False)
        a.axvline(best, color=ps.INK_MUTED, lw=0.7, ls=":")
        a.set_xlabel("Epoch")
        a.set_ylabel("Loss (standardised)")
        a.set_title("(b) Loss and learning rate")
        a.legend(frameon=False, fontsize=6.3)

        for a, group, title in ((axs[1, 0], "season", "(c) Validation, by season of target"),
                                (axs[1, 1], "city", "(d) Validation, by site")):
            h = hist.query("split == 'val' and group == @group")
            for key, g in h.groupby("key", sort=False):
                change = g["rmse"].values - g["rmse"].values[best]
                kw = dict(color=ps.SEASON_COLORS[key], ls=ps.SEASON_LINESTYLES[key]) if group == "season" else {}
                a.plot(g["epoch"], change, label=key, lw=1.1, **kw)
            a.axhline(0, color=ps.INK_MUTED, lw=0.6)
            a.axvline(best, color=ps.INK_MUTED, lw=0.7, ls=":")
            a.set_xlabel("Epoch")
            a.set_ylabel("Daylight RMSE change\nfrom best epoch (W/m²)")
            a.set_title(title)
            a.legend(frameon=False, fontsize=6.0, ncol=2)
        ps.save_figure(fig, save_path)
        plt.close(fig)


if __name__ == "__main__":
    main()
