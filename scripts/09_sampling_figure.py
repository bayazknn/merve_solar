"""Methodology figure: how windows, bootstrap blocks and MC-Dropout passes are sampled.

    uv run python scripts/09_sampling_figure.py

Writes outputs/methodology/figures/sampling_schematic.{png,pdf}.

Panels (b) and (c) show the ACTUAL replicates of the reference run, not an illustration: the
block draws are replayed with the same generator, seed and call order that experiment.py uses
(one np.random.default_rng(seed) shared by all replicates, cities in id order), so they are the
windows the eight networks were really trained on. Panel (d) runs those eight trained networks,
so it needs the run's checkpoints (*.pt, gitignored): regenerate it on the machine that ran the
experiment.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle

from merve_solar import paper_style as ps
from merve_solar.bootstrap import _moving_block_bootstrap_indices
from merve_solar.config import (
    BASE_FEATURES_PATH,
    CITIES,
    CITY_TO_ID,
    EXPERIMENTS_DIR,
    NUMERIC_FEATURE_COLUMNS,
    OUTPUTS_DIR,
    ExperimentConfig,
)
from merve_solar.data import load_base_features
from merve_solar.mc_dropout import mc_dropout_predict
from merve_solar.model import SolarLSTM
from merve_solar.scaling import apply_scaler, inverse_transform_target, load_scaler
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

RUN_ID = "config_002_default_full"
SITE = "Ankara"
# A partly cloudy spring day in the test period (daily irradiation 60% of the month's clearest),
# forecast from the window whose origin is 23:00 the evening before.
EXAMPLE_ORIGIN = pd.Timestamp("2026-04-16 23:00")
# Panel (b) zooms on six weeks of training windows chosen to show all three cases
# (left out, drawn once, drawn more than once).
ZOOM_WINDOWS = 6 * 168
OUT_PATH = OUTPUTS_DIR / "methodology" / "figures" / "sampling_schematic"

INPUT_COLOR = ps.ACCENT
TARGET_COLOR = ps.SEASON_COLORS["Summer"]
REST_GREY = "#d9d8d2"


def replay_block_starts(config, n_per_city: dict) -> list[dict]:
    """Block start indices of every replicate, per city, exactly as the run drew them."""
    rng = np.random.default_rng(config.seed)
    replicates = []
    for _ in range(config.n_bootstrap):
        draws = {}
        for city in sorted(n_per_city, key=CITY_TO_ID.get):
            idx = _moving_block_bootstrap_indices(n_per_city[city], config.bootstrap_block_length, rng)
            draws[city] = idx[:: config.bootstrap_block_length]
        replicates.append(draws)
    return replicates


def multiplicity(starts: np.ndarray, n: int, block: int) -> np.ndarray:
    """How many times each training window appears in one replicate (the final block is cut)."""
    counts = np.zeros(n, dtype=np.int64)
    remaining = n
    for s in starts:
        take = min(block, remaining)
        counts[s:s + take] += 1
        remaining -= take
    return counts


def panel_windows(ax) -> None:
    for r in range(5):
        y = 4 - r
        ax.add_patch(Rectangle((r - 23.5, y - 0.35), 24, 0.7, color=INPUT_COLOR, alpha=0.85, lw=0))
        ax.add_patch(Rectangle((r + 0.5, y - 0.35), 24, 0.7, color=TARGET_COLOR, alpha=0.85, lw=0))
        ax.plot([r + 0.5], [y], marker="|", color=ps.INK, ms=9, mew=1.2)
    ax.axvline(0.5, color=ps.INK_SECONDARY, lw=0.8, ls="--")
    ax.text(-11.5, 4.55, "24 input hours", ha="center", va="bottom", fontsize=7, color=INPUT_COLOR)
    ax.text(12.5, 4.55, "24 target hours", ha="center", va="bottom", fontsize=7, color=TARGET_COLOR)
    ax.text(0.9, -0.95, "forecast origin of window k", fontsize=6.5, color=ps.INK_SECONDARY, va="center")
    ax.set_yticks(range(5), [f"window k+{4 - y}" if y < 4 else "window k" for y in range(5)])
    ax.set_xlim(-24.5, 29.5)
    ax.set_ylim(-1.4, 5.3)
    ax.set_xticks([-23, -12, 0, 1, 12, 24])
    ax.set_xlabel("Hour relative to the forecast origin of window k")
    ax.grid(False)
    ax.set_title("(a) Windows: 48 h each, one per hour; neighbours share 47 h")


def pick_zoom(counts: np.ndarray, starts: np.ndarray, block: int) -> int:
    """The first six-week stretch that is typical -- about as many blocks as expected,
    (ZOOM + block - 1) / block = 7, and no window drawn more than twice -- and still shows
    windows left out, drawn once, and drawn twice. Deterministic, so reruns give the same figure."""
    expected = round((ZOOM_WINDOWS + block - 1) / block)
    for start in range(0, len(counts) - ZOOM_WINDOWS, 24):
        seg = counts[start:start + ZOOM_WINDOWS]
        n = int(((starts < start + ZOOM_WINDOWS) & (starts + block > start)).sum())
        if n == expected and seg.max() == 2 and (seg == 0).any() and (seg == 1).any():
            return start
    return 0


def panel_blocks(ax_blocks, ax_count, starts, counts, origins, block) -> None:
    lo = pick_zoom(counts, np.asarray(starts), block)
    hi = lo + ZOOM_WINDOWS
    x = origins[lo:hi]
    visible = [(i, s) for i, s in enumerate(starts) if s < hi and s + block > lo]
    for row, (draw, s) in enumerate(sorted(visible, key=lambda t: t[1])):
        a, b = max(s, lo), min(s + block, hi)
        ax_blocks.add_patch(Rectangle((origins[a], row - 0.35), origins[b - 1] - origins[a],
                                      0.7, color=ps.ACCENT, alpha=0.85, lw=0))
        ax_blocks.text(origins[a], row, f" #{draw + 1}", va="center", ha="left",
                       fontsize=6, color=ps.WHITE)
    ax_blocks.set_ylim(-0.8, len(visible) - 0.2)
    ax_blocks.set_yticks([])
    ax_blocks.set_xlim(x[0], x[-1])
    ax_blocks.grid(False)
    ax_blocks.tick_params(labelbottom=False)
    ax_blocks.set_title(f"(b) Replicate 1, {SITE}: blocks of {block} consecutive training "
                        "windows (6-week zoom)")

    seg = counts[lo:hi]
    ax_count.fill_between(x, seg, step="post", color=ps.ACCENT, alpha=0.35, lw=0)
    ax_count.step(x, seg, where="post", color=ps.ACCENT, lw=0.9)
    zero = seg == 0
    ax_count.fill_between(x, 0, 1, where=zero, step="post", color="#c94a4a", alpha=0.25, lw=0,
                          transform=ax_count.get_xaxis_transform())
    ax_count.set_ylim(0, max(3, seg.max()) + 0.3)
    ax_count.set_yticks(range(int(ax_count.get_ylim()[1]) + 1))
    ax_count.set_ylabel("Times\nin replicate")
    ax_count.set_xlim(x[0], x[-1])
    ax_count.set_xlabel("Forecast origin of the training window (red: left out of this replicate)")


def panel_replicates(ax, all_counts, origins, train_end, val_end, record_end) -> None:
    counts = np.stack(all_counts)[:, ::24]  # one window per day: blocks are 7 days long
    cmap = ListedColormap(["#ffffff", "#a9c8ee", "#4f8fdb", "#1c4f94"])
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 99], cmap.N)
    x0, x1 = origins[0], origins[-1]
    ax.imshow(np.minimum(counts, 3), aspect="auto", cmap=cmap, norm=norm, interpolation="nearest",
              extent=[x0, x1, len(counts) + 0.5, 0.5])
    for start, end, label in ((train_end, val_end, "validation:\nnot resampled"),
                              (val_end, record_end, "test:\nnot resampled")):
        ax.axvspan(start, end, color=REST_GREY, lw=0)
        ax.text(start + (end - start) / 2, (len(counts) + 1) / 2, label, ha="center", va="center",
                fontsize=6.5, color=ps.INK_SECONDARY)
    ax.set_xlim(origins[0], record_end)
    ax.set_yticks(range(1, len(counts) + 1))
    ax.set_ylabel("Replicate")
    ax.grid(False)
    ax.legend(handles=[Patch(facecolor=c, edgecolor=ps.AXIS, lw=0.5, label=l) for c, l in
                       zip(cmap.colors, ["left out", "once", "twice", "3+ times"])],
              ncols=4, loc="upper left", bbox_to_anchor=(0, -0.13), fontsize=6.5,
              handlelength=1.2, columnspacing=1.2)
    ax.set_title(f"(c) All {len(counts)} replicates, {SITE}: each keeps different weeks")


def panel_mc(ax, config, base_df, train_end, val_end, scaler, exp_dir) -> None:
    cfg = ExperimentConfig(**{**config.__dict__, "excluded_cities": []})
    splits = build_experiment_windows(apply_scaler(base_df, scaler), cfg, train_end, val_end)
    test = splits["test"]
    origin_of = pd.to_datetime(test["window_start"]) + pd.Timedelta(hours=cfg.lookback_hours - 1)
    pick = np.flatnonzero((origin_of == EXAMPLE_ORIGIN) & (test["city_id"] == CITY_TO_ID[SITE]))
    if pick.size != 1:
        raise SystemExit(f"expected one {SITE} test window with origin {EXAMPLE_ORIGIN}, got {pick.size}")
    X, city = test["X"][pick], test["city_id"][pick]

    samples = []
    for b in range(cfg.n_bootstrap):
        torch.manual_seed(cfg.seed + b)
        model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), len(CITIES), cfg)
        model.load_state_dict(torch.load(exp_dir / "checkpoints" / f"bootstrap_model_{b}.pt",
                                         map_location="cpu"))
        samples.append(mc_dropout_predict(model, X, city, cfg.mc_dropout_passes, device="cpu")[:, 0])
    pred = inverse_transform_target(scaler, np.concatenate(samples))  # (B*M, 24)

    layout = build_experiment_windows(base_df, cfg, train_end, val_end, include_X=False)["test"]
    y_true, daylight = layout["y"][pick[0]], layout["daylight"][pick[0]]
    pred[:, ~daylight] = 0.0  # the night constraint, as in the pipeline

    hours = np.arange(cfg.horizon_hours)  # target hour h=1 is 00:00 of the next day
    for s in pred[cfg.mc_dropout_passes:]:
        ax.plot(hours, s, color=ps.INK_MUTED, lw=0.3, alpha=0.06)
    for s in pred[:cfg.mc_dropout_passes]:
        ax.plot(hours, s, color=ps.ACCENT, lw=0.3, alpha=0.18)
    lower, upper = np.percentile(pred, [2.5, 97.5], axis=0)
    ax.plot(hours, lower, color=ps.INK, lw=0.8, ls="--")
    ax.plot(hours, upper, color=ps.INK, lw=0.8, ls="--", label="95% interval (2.5th–97.5th percentile)")
    ax.plot(hours, pred.mean(axis=0), color=ps.INK, lw=1.6, label="mean of 800 forecasts")
    ax.plot(hours, y_true, "o", color=TARGET_COLOR, ms=3, label="observed")
    ax.plot([], [], color=ps.ACCENT, lw=1, label=f"{cfg.mc_dropout_passes} passes of network 1")
    ax.plot([], [], color=ps.INK_MUTED, lw=1,
            label=f"{cfg.mc_dropout_passes} passes of each of networks 2–{cfg.n_bootstrap}")
    ax.set_xlim(0, 23)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel(f"Hour of {(EXAMPLE_ORIGIN + pd.Timedelta(hours=1)).date():%d %b %Y} "
                  "(local solar time)")
    ax.set_ylabel(ps.AXIS_LABELS["ALLSKY_SFC_SW_DWN"])
    ax.legend(loc="upper left", fontsize=6)
    ax.set_title(f"(d) MC Dropout, one test window, {SITE}: {cfg.n_bootstrap} networks × "
                 f"{cfg.mc_dropout_passes} passes = {cfg.n_bootstrap * cfg.mc_dropout_passes} forecasts")


def main() -> None:
    exp_dir = EXPERIMENTS_DIR / RUN_ID
    config = ExperimentConfig.from_json(exp_dir / "config.json")
    base_df = load_base_features(BASE_FEATURES_PATH)
    train_end, val_end = compute_split_boundaries(base_df, config)
    scaler = load_scaler(exp_dir / "checkpoints" / "scaler.joblib")

    layout = build_experiment_windows(base_df, config, train_end, val_end, include_X=False)
    train = layout["train"]
    n_per_city = {c: int((train["city_id"] == CITY_TO_ID[c]).sum()) for c in config.active_cities}
    site_mask = train["city_id"] == CITY_TO_ID[SITE]
    origins = (pd.to_datetime(train["window_start"][site_mask])
               + pd.Timedelta(hours=config.lookback_hours - 1)).to_numpy()

    block = config.bootstrap_block_length
    replicates = replay_block_starts(config, n_per_city)
    all_counts = [multiplicity(r[SITE], n_per_city[SITE], block) for r in replicates]
    record_end = base_df["datetime"].max()

    with plt.rc_context(ps.PAPER_RC):
        fig = plt.figure(figsize=(ps.FULL_WIDTH_IN, 8.6), layout="constrained")
        grid = fig.add_gridspec(5, 1, height_ratios=[1.15, 1.35, 0.6, 1.25, 1.9])
        panel_windows(fig.add_subplot(grid[0]))
        ax_blocks = fig.add_subplot(grid[1])
        panel_blocks(ax_blocks, fig.add_subplot(grid[2], sharex=ax_blocks),
                     replicates[0][SITE], all_counts[0], origins, block)
        panel_replicates(fig.add_subplot(grid[3]), all_counts, origins, train_end, val_end, record_end)
        panel_mc(fig.add_subplot(grid[4]), config, base_df, train_end, val_end, scaler, exp_dir)
        ps.save_figure(fig, OUT_PATH)

    distinct = [float((c > 0).mean()) for c in all_counts]
    print(f"{OUT_PATH}.png/.pdf  distinct training windows per replicate ({SITE}): "
          f"{min(distinct):.1%}–{max(distinct):.1%}")


if __name__ == "__main__":
    main()
