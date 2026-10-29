"""Methodology figures that explain individual components, one figure per section.

    uv run python scripts/12_methodology_explainers.py

Writes four figures to outputs/methodology/figures/, each as .png and .pdf:

    network_architecture   Section 6: layer diagram with tensor shapes and parameter counts,
                           and the site embedding as a one-hot vector times a lookup table
                           (the table shown is network 1 of the reference run).
    nonneg_penalty         Section 7: the non-negativity penalty placed at 0 W/m^2 (as trained)
                           and, for comparison, at the standardised zero (the training mean), in
                           W/m^2, and the bias each puts on the loss-minimising forecast.
    interval_reading       Section 8.4: four consecutive day-ahead forecasts with their 95 %
                           intervals from the reference run, and where the observations fell
                           relative to the interval, per site.
    probabilistic_metrics  Section 10.3: coverage vs width, CRPS as an area, and the CWC
                           multiplier. Panels (a) and (b) are illustrative (fixed seed); panel
                           (c) marks the reference run's daylight CP.

Panel (a) of network_architecture needs only the config; the embedding table needs the run's
checkpoints and interval_reading needs its test_predictions.npz (both gitignored), so run this
on the machine that ran the reference experiment.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

from merve_solar import paper_style as ps
from merve_solar.config import (
    CITIES,
    CITY_TO_ID,
    EXPERIMENTS_DIR,
    NUMERIC_FEATURE_COLUMNS,
    OUTPUTS_DIR,
    TARGET_COLUMN,
    ExperimentConfig,
)
from merve_solar.scaling import load_scaler

RUN_ID = "config_005_default_full"
RUN_DIR = EXPERIMENTS_DIR / RUN_ID
FIG_DIR = OUTPUTS_DIR / "methodology" / "figures"

INPUT_COLOR = ps.ACCENT
TARGET_COLOR = ps.SEASON_COLORS["Summer"]
EMBED_COLOR = ps.SEASON_COLORS["Autumn"]
MISS_COLOR = "#c0392b"
BOX_FACE = "#f6f6f3"

# Training-period statistics of the target (Section 5), used to put the scaled-space penalty
# back in W/m^2. Read from the run's scaler below; these are only the fallbacks printed in
# the methodology text, asserted equal to the scaler's.
TARGET_MEAN_DOC, TARGET_STD_DOC = 198.5, 279.7

# interval_reading: Ankara, 6-9 April 2026 (test period): a partly cloudy day, a clear day, a
# heavily overcast day the model did not anticipate, and a clear day again.
READING_SITE = "Ankara"
READING_FIRST_DAY = pd.Timestamp("2026-04-06")
READING_N_DAYS = 4
# probabilistic_metrics: chosen so the calibrated toy interval covers exactly 95 % of its 60
# points, as its label claims.
SEED = 1


def _arrow(ax, start, end, **kw):
    style = dict(arrowstyle="-|>", mutation_scale=8, lw=0.9, color=ps.INK_SECONDARY,
                 shrinkA=0, shrinkB=0)
    style.update(kw)
    ax.add_patch(FancyArrowPatch(start, end, **style))


def _box(ax, x, y, w, h, title, sub=None, edge=ps.INK_MUTED, face=ps.WHITE, lw=0.9, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.05",
                                facecolor=face, edgecolor=edge, lw=lw, ls=ls))
    if sub is None:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=6.8,
                fontweight="semibold")
    else:
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=6.8,
                fontweight="semibold")
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=6.0,
                color=ps.INK_SECONDARY, linespacing=1.15)


def _dropout_tag(ax, x, y):
    ax.text(x, y, "dropout p", ha="center", va="center", fontsize=5.6, color=MISS_COLOR,
            bbox=dict(boxstyle="round,pad=0.18", facecolor=ps.WHITE, edgecolor=MISS_COLOR, lw=0.6))


def _signed(v):
    return f"{v:+.2f}".replace("-", "\u2212")


def _param_counts(config, n_features, n_cities):
    hidden = config.hidden_sizes[0]
    d_in = n_features + config.city_embedding_dim
    emb = n_cities * config.city_embedding_dim
    lstm1 = 4 * (hidden * (d_in + hidden) + 2 * hidden)
    lstm2 = 4 * (hidden * (hidden + hidden) + 2 * hidden)
    dense = hidden * config.hidden_sizes[1] + config.hidden_sizes[1]
    out = config.hidden_sizes[1] * config.horizon_hours + config.horizon_hours
    return dict(emb=emb, lstm1=lstm1, lstm2=lstm2, dense=dense, out=out)


# --------------------------------------------------------------------------------------------
# Figure: network architecture
# --------------------------------------------------------------------------------------------

def _architecture_diagram(ax, config, n_features, counts):
    """Unrolled two-layer LSTM over the input window, then the dense head. Axes units: inches."""
    L, H = config.lookback_hours, config.horizon_hours
    hid, dense, emb_dim = config.hidden_sizes[0], config.hidden_sizes[1], config.city_embedding_dim
    d_in = n_features + emb_dim

    ax.text(0.0, 3.62, "(a) Network: site embedding, two stacked LSTM layers, dense output head",
            fontsize=8, fontweight="semibold", ha="left", va="top")

    # Unrolled time steps: draw 5 columns, the 4th is an ellipsis, the last is hour t.
    col_x = [0.95, 1.55, 2.15, 2.75, 3.35]
    col_lbl = [f"t−{L - 1}", f"t−{L - 2}", f"t−{L - 3}", "…", "t"]
    y_in, y_l1, y_l2 = 0.78, 1.6, 2.45
    cw, ch = 0.46, 0.42

    for x, lbl in zip(col_x, col_lbl):
        ell = lbl == "…"
        ax.text(x + cw / 2, y_in - 0.06, lbl, ha="center", va="top", fontsize=6.2,
                color=ps.INK_SECONDARY)
        if ell:
            for y in (y_in, y_l1, y_l2):
                ax.text(x + cw / 2, y + ch / 2, "…", ha="center", va="center", fontsize=9,
                        color=ps.INK_SECONDARY)
            continue
        # input vector at this hour: 13 features (blue) + 4 embedding values (purple)
        n_feat_cells, n_emb_cells = 6, 2
        cell = cw / (n_feat_cells + n_emb_cells)
        for i in range(n_feat_cells + n_emb_cells):
            ax.add_patch(Rectangle((x + i * cell, y_in), cell, ch * 0.55, lw=0.3,
                                   edgecolor=ps.WHITE,
                                   facecolor=INPUT_COLOR if i < n_feat_cells else EMBED_COLOR,
                                   alpha=0.85))
        for y in (y_l1, y_l2):
            ax.add_patch(FancyBboxPatch((x, y), cw, ch, boxstyle="round,pad=0,rounding_size=0.04",
                                        facecolor=BOX_FACE, edgecolor=ps.INK_MUTED, lw=0.8))
            ax.text(x + cw / 2, y + ch / 2, "LSTM", ha="center", va="center", fontsize=5.8)
        _arrow(ax, (x + cw / 2, y_in + ch * 0.55 + 0.02), (x + cw / 2, y_l1 - 0.02))
        _arrow(ax, (x + cw / 2, y_l1 + ch + 0.02), (x + cw / 2, y_l2 - 0.02))

    # recurrent arrows (hidden and cell state carried forward)
    for x0, x1 in zip(col_x[:-1], col_x[1:]):
        for y in (y_l1, y_l2):
            _arrow(ax, (x0 + cw + 0.02, y + ch / 2), (x1 - 0.02, y + ch / 2), lw=0.7,
                   color=ps.INK_MUTED)

    # dropout between the LSTM layers
    _dropout_tag(ax, col_x[-1] + cw + 0.32, (y_l1 + ch + y_l2) / 2)
    ax.plot([col_x[-1] + cw / 2, col_x[-1] + cw + 0.05], [(y_l1 + ch + y_l2) / 2] * 2,
            color=MISS_COLOR, lw=0.6, ls=":")

    # left-hand row labels
    ax.text(0.0, y_in + 0.12, f"input\n{L} h × {d_in}", fontsize=6.3, va="center",
            color=ps.INK_SECONDARY, linespacing=1.2)
    ax.text(0.0, y_l1 + ch / 2, f"LSTM 1\n{hid} units", fontsize=6.3, va="center",
            color=ps.INK_SECONDARY, linespacing=1.2)
    ax.text(0.0, y_l2 + ch / 2, f"LSTM 2\n{hid} units", fontsize=6.3, va="center",
            color=ps.INK_SECONDARY, linespacing=1.2)
    ax.text(0.95, y_in - 0.30,
            f"each hour: {n_features} standardised features (blue) + {emb_dim}-value site "
            f"embedding (purple), the same at every hour",
            fontsize=6.0, color=ps.INK_SECONDARY, va="top")

    # head: last hidden state -> dropout -> dense -> dropout -> linear -> 24 outputs
    hx = col_x[-1] + cw / 2
    head_x, bw, bh = 4.55, 1.55, 0.44
    ys = [2.98, 2.25, 1.52, 0.79]
    ax.plot([hx, hx], [y_l2 + ch + 0.02, ys[0] + bh / 2], color=ps.INK_SECONDARY, lw=0.9)
    _arrow(ax, (hx, ys[0] + bh / 2), (head_x - 0.02, ys[0] + bh / 2))
    ax.text((hx + head_x) / 2 + 0.05, ys[0] + bh / 2 + 0.04, f"h$_t$ ({hid})",
            ha="center", va="bottom", fontsize=6.0, color=ps.INK_SECONDARY)

    _box(ax, head_x, ys[0], bw, bh, "Last hidden state", f"summary of the window, {hid} values")
    _box(ax, head_x, ys[1], bw, bh, f"Dense, {dense} units", f"ReLU · {counts['dense']:,} params")
    _box(ax, head_x, ys[2], bw, bh, f"Linear, {H} outputs", f"{counts['out']:,} params")
    _box(ax, head_x, ys[3], bw, bh, f"ŷ(t+1), …, ŷ(t+{H})", "standardised forecast",
         edge=TARGET_COLOR, lw=1.2)
    for (a, b), drop in zip(zip(ys[:-1], ys[1:]), (True, True, False)):
        _arrow(ax, (head_x + bw / 2, a - 0.02), (head_x + bw / 2, b + bh + 0.02))
        if drop:
            _dropout_tag(ax, head_x + bw + 0.0 - 0.38, (a + b + bh) / 2)

    ax.text(0.0, 0.0,
            f"Parameters: embedding {counts['emb']}, LSTM 1 {counts['lstm1']:,}, "
            f"LSTM 2 {counts['lstm2']:,}, dense {counts['dense']:,}, output {counts['out']:,}; "
            f"total {sum(counts.values()):,}.  Dropout p = {config.dropout_rate} at the three "
            f"red tags, kept active at prediction (MC Dropout).",
            fontsize=6.0, color=ps.INK_SECONDARY, va="bottom")


def _embedding_panel(fig, ax, table, site):
    """One-hot site vector times the lookup table = that site's embedding row."""
    ax.text(0.0, 1.78, "(b) Site embedding: a one-hot code multiplied by a learned table",
            fontsize=8, fontweight="semibold", ha="left", va="top")
    k = CITY_TO_ID[site]
    n_sites, emb_dim = table.shape
    cell = 0.2
    y0 = 0.35

    # one-hot column
    ox = 0.95
    for i, name in enumerate(CITIES):
        yy = y0 + (n_sites - 1 - i) * cell
        on = i == k
        ax.add_patch(Rectangle((ox, yy), cell, cell, lw=0.5, edgecolor=ps.INK_MUTED,
                               facecolor=EMBED_COLOR if on else ps.WHITE, alpha=0.25 if on else 1))
        ax.text(ox + cell / 2, yy + cell / 2, "1" if on else "0", ha="center", va="center",
                fontsize=6.2, fontweight="semibold" if on else "normal")
        ax.text(ox - 0.06, yy + cell / 2, name, ha="right", va="center", fontsize=6.2,
                fontweight="semibold" if on else "normal")
    ax.text(ox + cell / 2, y0 + n_sites * cell + 0.05, "one-hot\n(5)", ha="center",
            va="bottom", fontsize=5.8, color=ps.INK_SECONDARY, linespacing=1.1)
    ax.text(ox + cell + 0.17, y0 + n_sites * cell / 2, "×", ha="center", va="center", fontsize=10)

    # lookup table
    tx = ox + cell + 0.36
    vmax = np.abs(table).max()
    cmap = plt.get_cmap("PuOr_r")
    for i in range(n_sites):
        for j in range(emb_dim):
            yy = y0 + (n_sites - 1 - i) * cell
            v = table[i, j]
            ax.add_patch(Rectangle((tx + j * cell * 1.9, yy), cell * 1.9, cell, lw=0.4,
                                   edgecolor=ps.WHITE, facecolor=cmap(0.5 + 0.45 * v / vmax)))
            ax.text(tx + (j + 0.5) * cell * 1.9, yy + cell / 2, _signed(v), ha="center",
                    va="center", fontsize=5.4,
                    color=ps.WHITE if abs(v) > 0.6 * vmax else ps.INK)
    yk = y0 + (n_sites - 1 - k) * cell
    tw = emb_dim * cell * 1.9
    ax.add_patch(Rectangle((tx, yk), tw, cell, fill=False, lw=1.3, edgecolor=EMBED_COLOR))
    ax.text(tx + tw / 2, y0 + n_sites * cell + 0.05, f"lookup table (5 × {emb_dim}),\nlearned in training",
            ha="center", va="bottom", fontsize=5.8, color=ps.INK_SECONDARY, linespacing=1.1)
    ax.text(tx + tw + 0.17, y0 + n_sites * cell / 2, "=", ha="center", va="center", fontsize=10)

    # result row
    rx = tx + tw + 0.36
    ry = y0 + n_sites * cell / 2 - cell / 2
    for j in range(emb_dim):
        v = table[k, j]
        ax.add_patch(Rectangle((rx + j * cell * 1.9, ry), cell * 1.9, cell, lw=0.4,
                               edgecolor=ps.WHITE, facecolor=cmap(0.5 + 0.45 * v / vmax)))
        ax.text(rx + (j + 0.5) * cell * 1.9, ry + cell / 2, _signed(v), ha="center",
                va="center", fontsize=5.4, color=ps.WHITE if abs(v) > 0.6 * vmax else ps.INK)
    ax.add_patch(Rectangle((rx, ry), tw, cell, fill=False, lw=1.3, edgecolor=EMBED_COLOR))
    ax.text(rx + tw / 2, ry + cell + 0.06, f"embedding of {site}", ha="center", va="bottom",
            fontsize=5.8, color=ps.INK_SECONDARY)
    ax.text(rx + tw / 2, ry - 0.06, f"appended to every hour\nof the window ({emb_dim} values)",
            ha="center", va="top", fontsize=5.8, color=ps.INK_SECONDARY, linespacing=1.1)
    ax.text(0.0, 0.0,
            "Values: network 1 of the reference run. Each network learns its own table; the "
            "individual numbers have no physical meaning, only how the sites' rows differ.",
            fontsize=6.0, color=ps.INK_SECONDARY, va="bottom")


def figure_architecture(config) -> None:
    n_features, n_cities = len(NUMERIC_FEATURE_COLUMNS), len(CITIES)
    counts = _param_counts(config, n_features, n_cities)

    state = torch.load(RUN_DIR / "checkpoints" / "bootstrap_model_0.pt", map_location="cpu")
    n_params = sum(v.numel() for v in state.values())
    assert n_params == sum(counts.values()), (n_params, counts)
    table = state["city_embedding.weight"].numpy()

    W, H = ps.FULL_WIDTH_IN, 5.75
    with plt.rc_context(ps.PAPER_RC):
        fig = plt.figure(figsize=(W, H))
        ax = fig.add_axes([0, 1.95 / H, 1, 3.7 / H])
        ax.set_xlim(0, W)
        ax.set_ylim(0, 3.7)
        ax.axis("off")
        _architecture_diagram(ax, config, n_features, counts)
        ax2 = fig.add_axes([0, 0, 1, 1.85 / H])
        ax2.set_xlim(0, W)
        ax2.set_ylim(0, 1.85)
        ax2.axis("off")
        _embedding_panel(fig, ax2, table, "Rize")
        ps.save_figure(fig, FIG_DIR / "network_architecture")
        plt.close(fig)


# --------------------------------------------------------------------------------------------
# Figure: non-negativity penalty
# --------------------------------------------------------------------------------------------

def figure_penalty(config, y_mean, y_std) -> None:
    lam = config.nonneg_penalty_weight
    yhat = np.linspace(-150, 450, 601)
    implemented = lam * np.maximum(0, (y_mean - yhat) / y_std) ** 2
    intended = lam * np.maximum(0, -yhat / y_std) ** 2

    obs = np.linspace(0, 450, 451)
    bias_impl = np.where(obs < y_mean, lam / (1 + lam) * (y_mean - obs), 0.0)

    with plt.rc_context(ps.PAPER_RC):
        fig, (a, b) = plt.subplots(1, 2, figsize=(ps.FULL_WIDTH_IN, 2.5), layout="constrained")

        a.axvspan(-150, 0, color=ps.GRID, alpha=0.6, lw=0)
        a.text(-75, 0.088, "physically\nimpossible", ha="center", va="top", fontsize=6.2,
               color=ps.INK_SECONDARY)
        a.plot(yhat, intended, color=INPUT_COLOR, lw=1.6, label="at 0 W/m² (this study)")
        a.plot(yhat, implemented, color=MISS_COLOR, lw=1.6, ls="--", label="at standardised zero")
        a.axvline(y_mean, color=ps.INK_MUTED, lw=0.7, ls=":")
        a.text(y_mean + 6, 0.06, f"training mean\n{y_mean:.1f} W/m²", fontsize=6.0,
               color=ps.INK_SECONDARY, va="bottom")
        a.set_xlim(-150, 450)
        a.set_ylim(0, 0.09)
        a.set_xlabel("Forecast ŷ (W/m²)")
        a.set_ylabel(f"Penalty term, λ = {lam}")
        a.set_title("(a) Penalty added to the loss")
        a.legend(loc="upper right", frameon=False, fontsize=6.3)

        b.plot(obs, np.zeros_like(obs), color=INPUT_COLOR, lw=1.6, label="at 0 W/m² (this study)")
        b.plot(obs, bias_impl, color=MISS_COLOR, lw=1.6, ls="--", label="at standardised zero")
        b.axvline(y_mean, color=ps.INK_MUTED, lw=0.7, ls=":")
        b.annotate(f"+{lam / (1 + lam) * y_mean:.1f} W/m²\nat 0 W/m²",
                   xy=(0, lam / (1 + lam) * y_mean), xytext=(60, 16.5), fontsize=6.0,
                   color=ps.INK_SECONDARY,
                   arrowprops=dict(arrowstyle="-", lw=0.6, color=ps.INK_MUTED))
        b.set_xlim(0, 450)
        b.set_ylim(-1.5, 21)
        b.set_xlabel("Expected irradiance E[y] (W/m²)")
        b.set_ylabel("Upward bias (W/m²)")
        b.set_title("(b) Effect on the loss-minimising forecast")
        b.legend(loc="upper right", frameon=False, fontsize=6.3)
        ps.save_figure(fig, FIG_DIR / "nonneg_penalty")
        plt.close(fig)


# --------------------------------------------------------------------------------------------
# Figure: reading a prediction interval
# --------------------------------------------------------------------------------------------

def figure_interval_reading(pred) -> None:
    starts = pd.to_datetime(pred["window_start"] * 3600, unit="s")
    origins = starts + pd.Timedelta(hours=23)
    city = pred["city_id"]

    # (a) day-ahead forecasts issued at 23:00 the evening before, one window per day
    times, y, mu, lo, hi = [], [], [], [], []
    for d in range(READING_N_DAYS):
        origin = READING_FIRST_DAY + pd.Timedelta(days=d) - pd.Timedelta(hours=1)
        (i,) = np.where((city == CITY_TO_ID[READING_SITE]) & (origins == origin))[0]
        times.append(origin + pd.to_timedelta(np.arange(1, 25), unit="h"))
        y.append(pred["y_true"][i]); mu.append(pred["mean"][i])
        lo.append(pred["lower"][i]); hi.append(pred["upper"][i])
    times = np.concatenate(times); y = np.concatenate(y); mu = np.concatenate(mu)
    lo = np.concatenate(lo); hi = np.concatenate(hi)
    miss = (y < lo) | (y > hi)

    # (b) where daylight observations fall relative to the interval, per site and pooled
    dl = pred["daylight"]
    rows = []
    for name in CITIES + ["All sites"]:
        sel = dl if name == "All sites" else dl & (city == CITY_TO_ID[name])[:, None]
        yy, l, u = pred["y_true"][sel], pred["lower"][sel], pred["upper"][sel]
        rows.append((name, (yy < l).mean(), ((yy >= l) & (yy <= u)).mean(), (yy > u).mean()))

    with plt.rc_context(ps.PAPER_RC):
        fig, (a, b) = plt.subplots(2, 1, figsize=(ps.FULL_WIDTH_IN, 4.9), layout="constrained",
                                   height_ratios=[1.45, 1])
        a.fill_between(times, lo, hi, color=TARGET_COLOR, alpha=0.18, lw=0, step=None,
                       label="95% prediction interval")
        a.plot(times, mu, color=TARGET_COLOR, lw=1.3, label="point forecast (mean)")
        a.plot(times, y, color=ps.INK, lw=0.9, marker="o", ms=1.8, label="observed")
        a.scatter(times[miss], y[miss], s=16, facecolor="none", edgecolor=MISS_COLOR, lw=0.9,
                  zorder=5, label="observed outside interval")
        for d in range(READING_N_DAYS):
            day = READING_FIRST_DAY + pd.Timedelta(days=d)
            a.axvline(day, color=ps.GRID, lw=0.8)
            a.text(day + pd.Timedelta(hours=12), 1040, day.strftime("%-d %b %Y"), ha="center",
                   va="top", fontsize=6.3, color=ps.INK_SECONDARY)
        a.set_ylim(0, 1060)
        a.set_xlim(times[0] - pd.Timedelta(hours=1), times[-1] + pd.Timedelta(hours=1))
        a.set_ylabel(ps.AXIS_LABELS["ALLSKY_SFC_SW_DWN"])
        a.set_xlabel(f"{READING_SITE}, local solar time; each day forecast at 23:00 the evening before")
        a.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))
        a.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        a.set_title("(a) Day-ahead forecasts and their 95% intervals")
        a.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4, frameon=False,
                 fontsize=6.0)

        names = [r[0] for r in rows][::-1]
        below = np.array([r[1] for r in rows])[::-1] * 100
        inside = np.array([r[2] for r in rows])[::-1] * 100
        above = np.array([r[3] for r in rows])[::-1] * 100
        yy = np.arange(len(names))
        b.barh(yy, below, color=INPUT_COLOR, height=0.62, label="below interval (forecast too high)")
        b.barh(yy, inside, left=below, color="#d9d8d2", height=0.62, label="inside interval")
        b.barh(yy, above, left=below + inside, color=TARGET_COLOR, height=0.62,
               label="above interval (forecast too low)")
        for i in range(len(names)):
            b.text(below[i] + inside[i] / 2, yy[i], f"{inside[i]:.1f}%", ha="center",
                   va="center", fontsize=6.0)
            b.text(below[i] + 0.3, yy[i], f"{below[i]:.1f}", ha="left", va="center",
                   fontsize=5.6, color=ps.WHITE if below[i] > 3 else ps.INK)
            b.text(100.6, yy[i], f"{above[i]:.1f}", ha="left", va="center", fontsize=5.6)
        b.axvline(2.5, color=ps.INK, lw=0.7, ls="--")
        b.axvline(97.5, color=ps.INK, lw=0.7, ls="--")
        b.text(97.5, len(names) - 0.35, "nominal 2.5% | 95% | 2.5%", ha="right", va="bottom",
               fontsize=6.0, color=ps.INK_SECONDARY)
        b.set_yticks(yy, names)
        b.set_xlim(0, 100)
        b.set_clip_on(False)
        b.set_ylim(-0.5, len(names) + 0.1)
        b.grid(False)
        b.set_xlabel("Share of daylight test elements (%), all horizon steps")
        b.set_title("(b) Where observations fall relative to the interval")
        b.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False,
                 fontsize=6.0)
        ps.save_figure(fig, FIG_DIR / "interval_reading")
        plt.close(fig)
    return rows, int(miss.sum()), int((y > 0).sum())


# --------------------------------------------------------------------------------------------
# Figure: probabilistic metrics
# --------------------------------------------------------------------------------------------

def figure_metrics(cp_reference) -> None:
    rng = np.random.default_rng(SEED)
    n = 60
    truth_mean = 500 + 120 * np.sin(np.linspace(0, 3 * np.pi, n))
    sigma = 90
    y = truth_mean + rng.normal(0, sigma, n)
    forecasters = [("too narrow", 0.35), ("calibrated", 1.0), ("too wide", 2.2)]

    with plt.rc_context(ps.PAPER_RC):
        fig = plt.figure(figsize=(ps.FULL_WIDTH_IN, 4.5), layout="constrained")
        top, bottom = fig.subfigures(2, 1, height_ratios=[1, 1.05])
        axs = top.subplots(1, 3, sharey=True)
        x = np.arange(n)
        for a, (name, scale) in zip(axs, forecasters):
            half = 1.96 * sigma * scale
            lo, hi = truth_mean - half, truth_mean + half
            inside = (y >= lo) & (y <= hi)
            a.fill_between(x, lo, hi, color=TARGET_COLOR, alpha=0.18, lw=0)
            a.plot(x, truth_mean, color=TARGET_COLOR, lw=1.0)
            a.scatter(x[inside], y[inside], s=6, color=ps.INK, lw=0)
            a.scatter(x[~inside], y[~inside], s=14, facecolor="none", edgecolor=MISS_COLOR, lw=0.8)
            a.set_title(f"{name}\nCP = {inside.mean():.2f}, MPIW = {2 * half:.0f} W/m²",
                        fontsize=7, loc="center")
            a.set_ylim(0, 1000)
            a.set_xlabel("Forecast element")
            a.set_xticks([0, 29, 59], ["1", "30", "60"])
        axs[0].set_ylabel(ps.AXIS_LABELS["ALLSKY_SFC_SW_DWN"])
        top.suptitle("(a) Coverage and width: same forecasts, three interval widths",
                     x=0.0, ha="left", fontsize=8, fontweight="semibold")

        b, c = bottom.subplots(1, 2)
        samples = np.sort(np.clip(rng.normal(650, 160, 800), 0, None))
        cdf = np.arange(1, samples.size + 1) / samples.size
        obs = 820
        grid = np.linspace(150, 1150, 1001)
        F = np.searchsorted(samples, grid, side="right") / samples.size
        step = (grid >= obs).astype(float)
        b.fill_between(grid, F, step, color=TARGET_COLOR, alpha=0.25, lw=0,
                       label="gap between F and step; CRPS = ∫(F − step)²")
        b.plot(samples, cdf, color=TARGET_COLOR, lw=1.3, label="forecast CDF F (800 samples)")
        b.plot(grid, step, color=ps.INK, lw=1.1, label=f"observation, y = {obs} W/m²")
        crps = (np.abs(samples - obs).mean()
                - np.abs(samples[:, None] - samples[None, :]).mean() / 2)
        b.text(0.03, 0.97, f"CRPS = {crps:.0f} W/m²\n|mean − y| = {abs(samples.mean() - obs):.0f} W/m²",
               transform=b.transAxes, ha="left", va="top", fontsize=6.3)
        b.set_xlim(150, 1150)
        b.set_ylim(0, 1.02)
        b.set_xlabel("Irradiance (W/m²)")
        b.set_ylabel("Cumulative probability")
        b.set_title("(b) CRPS as an area")
        b.legend(loc="lower right", frameon=False, fontsize=5.8)

        cp = np.linspace(0.80, 1.0, 401)
        mult = np.where(cp < 0.95, 1 + np.exp(-50 * (cp - 0.95)), 1.0)
        c.plot(cp, mult, color=INPUT_COLOR, lw=1.5)
        m_ref = 1 + np.exp(-50 * (cp_reference - 0.95))
        c.plot([cp_reference], [m_ref], "o", color=MISS_COLOR, ms=4)
        c.annotate(f"reference run, daylight\nCP = {cp_reference:.3f} → × {m_ref:.1f}",
                   xy=(cp_reference, m_ref), xytext=(0.84, 12), fontsize=6.2,
                   color=ps.INK_SECONDARY,
                   arrowprops=dict(arrowstyle="-", lw=0.6, color=ps.INK_MUTED))
        c.axvline(0.95, color=ps.INK_MUTED, lw=0.7, ls=":")
        c.set_yscale("log")
        c.set_xlim(0.80, 1.0)
        c.set_ylim(0.8, 3e3)
        c.set_xlabel("Coverage probability CP")
        c.set_ylabel("CWC / PINW (log scale)")
        c.set_title("(c) CWC penalty below CP = 0.95")
        ps.save_figure(fig, FIG_DIR / "probabilistic_metrics")
        plt.close(fig)


def main() -> None:
    config = ExperimentConfig.from_json(RUN_DIR / "config.json")
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    scaler = load_scaler(RUN_DIR / "checkpoints" / "scaler.joblib")
    y_mean, y_std = _target_stats(scaler)
    assert abs(y_mean - TARGET_MEAN_DOC) < 0.05 and abs(y_std - TARGET_STD_DOC) < 0.05, (y_mean, y_std)

    figure_architecture(config)
    figure_penalty(config, y_mean, y_std)
    pred = np.load(RUN_DIR / "metrics" / "test_predictions.npz")
    rows, n_miss, n_lit = figure_interval_reading(pred)
    summary = pd.read_csv(RUN_DIR / "metrics" / "results_summary.csv")
    cp_ref = float(summary.query("group == 'Aggregate' and subset == 'daylight'")["CP"].iloc[0])
    figure_metrics(cp_ref)

    for name, below, inside, above in rows:
        print(f"{name:10s} below {below:.4f} inside {inside:.4f} above {above:.4f}")
    print(f"interval_reading panel (a): {n_miss} of {n_lit} lit hours outside the interval")
    print(f"wrote {FIG_DIR}/{{network_architecture,nonneg_penalty,interval_reading,probabilistic_metrics}}")


def _target_stats(scaler):
    """Training-period mean and std of the target, from the run's saved scaler."""
    i = NUMERIC_FEATURE_COLUMNS.index(TARGET_COLUMN)
    return float(scaler.mean_[i]), float(scaler.scale_[i])


if __name__ == "__main__":
    main()
