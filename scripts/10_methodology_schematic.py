"""Methodology figure: symbolic schematic of the forecasting and uncertainty pipeline.

    uv run python scripts/10_methodology_schematic.py

Writes outputs/methodology/figures/methodology_schematic.{png,pdf}.

Unlike sampling_schematic (script 09), which replays the reference run, this figure carries no
run-specific numbers: window lengths, block length, replicate and pass counts are symbols
(L, H, n_s, l, B, M) matching the notation of METHODOLOGY.md, so it stays valid for any config.
Every curve and block draw here is illustrative, from a fixed seed. Panels:
(a) windowing, (b) moving-block bootstrap, (c) B networks x M MC-Dropout passes, pooling,
mean and percentile interval.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

from merve_solar import paper_style as ps
from merve_solar.config import OUTPUTS_DIR

SAVE_PATH = OUTPUTS_DIR / "methodology" / "figures" / "methodology_schematic"

INPUT_COLOR = ps.ACCENT
TARGET_COLOR = "#eb6834"
POOL_COLOR = "#9a9993"
BLOCK_CMAP = plt.get_cmap("viridis")

# Drawing proportions only: the figure labels them L, H, n_s and l, never with values.
N_IN, N_OUT = 9, 7          # cells drawn for the L input and H target hours
N_SERIES, BLOCK = 60, 10    # cells drawn for the n_s training windows and a block of l
N_NETWORKS_DRAWN = 3        # rows drawn for networks 1, 2 and B
N_PASSES_DRAWN = 25         # curves drawn per network for its M passes

FIG_W, FIG_H = ps.FULL_WIDTH_IN, 7.25
SEED = 7


def _arrow(ax, start, end, **kw):
    style = dict(arrowstyle="-|>", mutation_scale=8, lw=0.9, color=ps.INK_SECONDARY,
                 shrinkA=0, shrinkB=0)
    style.update(kw)
    ax.add_patch(FancyArrowPatch(start, end, **style))


def _brace(ax, x0, x1, y, text, color, above=True):
    """Horizontal bracket from x0 to x1 at height y, with a centred label."""
    d = 0.05 if above else -0.05
    ax.plot([x0, x0, x1, x1], [y - d, y, y, y - d], color=color, lw=0.8)
    ax.text((x0 + x1) / 2, y + (0.04 if above else -0.04), text, color=color,
            ha="center", va="bottom" if above else "top", fontsize=7)


def _strip(ax, x0, y0, width, height, positions, n_total, edges=()):
    """A row of window cells coloured by their position in the training period."""
    cell = width / len(positions)
    for i, p in enumerate(positions):
        ax.add_patch(Rectangle((x0 + i * cell, y0), cell, height, lw=0,
                               facecolor=BLOCK_CMAP(0.08 + 0.84 * p / (n_total - 1))))
    for e in edges:  # white seams between concatenated blocks
        ax.plot([x0 + e * cell] * 2, [y0, y0 + height], color=ps.WHITE, lw=1.4)
    ax.add_patch(Rectangle((x0, y0), width, height, fill=False, lw=0.5, edgecolor=ps.INK_MUTED))


def _panel_title(ax, x, y, text):
    ax.text(x, y, text, fontsize=8, fontweight="semibold", ha="left", va="top", color=ps.INK)


def _panel_windows(ax, top):
    _panel_title(ax, 0.0, top, r"(a) Windowing: one window per hour, $L$ input hours and $H$ target hours")
    cell = 0.16
    x0 = 0.95
    y = top - 0.48
    row_h, gap = 0.17, 0.09
    labels = [r"window $k$", r"window $k{+}1$", r"window $k{+}2$"]
    for r, label in enumerate(labels):
        yy = y - r * (row_h + gap)
        xs = x0 + r * cell
        ax.add_patch(Rectangle((xs, yy), N_IN * cell, row_h, facecolor=INPUT_COLOR, lw=0))
        ax.add_patch(Rectangle((xs + N_IN * cell, yy), N_OUT * cell, row_h,
                               facecolor=TARGET_COLOR, lw=0))
        for c in range(1, N_IN + N_OUT):
            ax.plot([xs + c * cell] * 2, [yy, yy + row_h], color=ps.WHITE, lw=0.5)
        ax.text(x0 - 0.1, yy + row_h / 2, label, ha="right", va="center", fontsize=7)
    ax.text(x0 + 1.5 * cell, y - 3 * (row_h + gap) + 0.12, r"$\vdots$", ha="center",
            va="center", fontsize=8, color=ps.INK_SECONDARY)

    origin = x0 + N_IN * cell
    ax.plot([origin] * 2, [y - 2 * (row_h + gap) - 0.05, y + row_h + 0.06], color=ps.INK,
            lw=0.8, ls="--")
    ax.text(origin, y - 2 * (row_h + gap) - 0.09, r"forecast origin $t$ of window $k$",
            ha="center", va="top", fontsize=6.5, color=ps.INK_SECONDARY)
    _brace(ax, x0, origin, y + row_h + 0.07,
           r"$L$ input hours", INPUT_COLOR)
    _brace(ax, origin, origin + N_OUT * cell, y + row_h + 0.07,
           r"$H$ target hours", TARGET_COLOR)

    # Right-hand notes: what a window becomes downstream.
    nx = origin + N_OUT * cell + 2 * cell + 0.25
    ax.text(nx, y + 0.12,
            r"Inputs $\mathbf{x}_{t-L+1},\dots,\mathbf{x}_{t}$; targets $y_{t+1},\dots,y_{t+H}$." "\n"
            "Consecutive windows are shifted by one hour.\n"
            "Windows never cross a site or a period boundary.\n"
            r"Site $s$ contributes $n_s$ training windows $w_1,\dots,w_{n_s}$.",
            ha="left", va="top", fontsize=6.8, color=ps.INK_SECONDARY, linespacing=1.5)


def _panel_bootstrap(ax, top, rng):
    _panel_title(ax, 0.0, top,
                 r"(b) Moving-block bootstrap: $B$ replicates of the training windows, per site")
    x0, width, h = 0.95, 4.2, 0.17
    y_orig = top - 0.62
    _strip(ax, x0, y_orig, width, h, np.arange(N_SERIES), N_SERIES)
    ax.text(x0 - 0.1, y_orig + h / 2, "training\nwindows", ha="right", va="center",
            fontsize=7, linespacing=1.1)
    ax.text(x0, y_orig - 0.04, r"$w_1$", ha="left", va="top", fontsize=6.5)
    ax.text(x0 + width, y_orig - 0.04, r"$w_{n_s}$", ha="right", va="top", fontsize=6.5)
    ax.text(x0 + width / 2, y_orig - 0.04, "chronological order", ha="center", va="top",
            fontsize=6.5, color=ps.INK_SECONDARY)

    n_blocks = int(np.ceil(N_SERIES / BLOCK))
    starts = [rng.integers(0, N_SERIES - BLOCK + 1, size=n_blocks) for _ in range(N_NETWORKS_DRAWN)]
    # Force one visibly overlapping pair in replicate 1, so "drawn with replacement" shows.
    starts[0][1], starts[0][4] = 21, 21

    cell = width / N_SERIES
    for k, s in enumerate(sorted(starts[0][:3])):
        lift = 0.07 + 0.09 * k
        _brace(ax, x0 + s * cell, x0 + (s + BLOCK) * cell, y_orig + h + lift, "", ps.INK_SECONDARY)
    s = sorted(starts[0][:3])[-1]
    ax.text(x0 + (s + BLOCK) * cell + 0.05, y_orig + h + 0.25,
            r"blocks of $\ell$ consecutive windows," "\n"
            r"$\lceil n_s/\ell\rceil$ start points drawn uniformly with replacement",
            ha="left", va="center", fontsize=6.5, color=ps.INK_SECONDARY, linespacing=1.3)

    y_rep = y_orig - 0.62
    labels = [r"$\mathcal{D}^{(1)}$", r"$\mathcal{D}^{(2)}$", r"$\mathcal{D}^{(B)}$"]
    rep_rows = []
    for r in range(N_NETWORKS_DRAWN):
        yy = y_rep - r * 0.3 - (0.16 if r == N_NETWORKS_DRAWN - 1 else 0)
        pos = np.concatenate([np.arange(s, s + BLOCK) for s in starts[r]])[:N_SERIES]
        _strip(ax, x0, yy, width, h, pos, N_SERIES, edges=range(BLOCK, N_SERIES, BLOCK))
        ax.text(x0 - 0.1, yy + h / 2, labels[r], ha="right", va="center", fontsize=8)
        rep_rows.append(yy)
    # Outline the block that replicate 1 drew twice.
    bw = BLOCK * cell
    for j in (1, 4):
        ax.add_patch(Rectangle((x0 + j * bw, rep_rows[0]), bw, h, fill=False, lw=1.0,
                               edgecolor=ps.INK))
    ax.plot([x0 + 1.5 * bw, x0 + 1.5 * bw, x0 + 4.5 * bw, x0 + 4.5 * bw],
            [rep_rows[0] + h + 0.02, rep_rows[0] + h + 0.08, rep_rows[0] + h + 0.08,
             rep_rows[0] + h + 0.02], color=ps.INK, lw=0.6)
    ax.text(x0 + 3 * bw, rep_rows[0] + h + 0.1, "the same block, drawn twice",
            ha="center", va="bottom", fontsize=6.3, color=ps.INK)
    ax.text(x0 + width / 2, rep_rows[1] - 0.12, r"$\vdots$", ha="center", va="center",
            fontsize=8, color=ps.INK_SECONDARY)
    _arrow(ax, (x0 + width + 0.15, y_orig + h / 2), (x0 + width + 0.15, rep_rows[0] + h / 2),
           connectionstyle="arc3,rad=0")
    ax.text(x0 + width + 0.24, (y_orig + rep_rows[-1]) / 2 + 0.05,
            "concatenate the blocks,\n"
            r"cut to $n_s$ windows;" "\n"
            r"repeat $B$ times" "\n\n"
            "colour: position of the\nwindow in the training\nperiod",
            ha="left", va="center", fontsize=6.5, color=ps.INK_SECONDARY, linespacing=1.35)
    return rep_rows


def _pass_curves(rng, n_networks):
    """Illustrative forecasts over the horizon: per-network offset plus per-pass jitter."""
    h = np.linspace(0, 1, 40)
    shape = np.clip(np.sin(np.pi * (h - 0.18) / 0.64), 0, None) ** 1.3
    curves = []
    for b in range(n_networks):
        bias = rng.normal(0, 0.10)
        scale = 1 + bias + rng.normal(0, 0.15, size=(N_PASSES_DRAWN, 1))
        wobble = rng.normal(0, 0.04, size=(N_PASSES_DRAWN, 1)) * np.cos(3 * np.pi * h)
        curves.append(np.clip(shape * scale + wobble * shape, 0, None))
    return h, curves


def _clean_axes(a):
    a.set_xticks([])
    a.set_yticks([])
    a.grid(False)
    for side in ("top", "right"):
        a.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        a.spines[side].set_color(ps.AXIS)


def _panel_ensemble(fig, ax, top, rng):
    _panel_title(ax, 0.0, top,
                 r"(c) $B$ LSTMs $\times$ $M$ MC-Dropout passes $\rightarrow$ pooled forecasts, mean and 95% interval")
    h, curves = _pass_curves(rng, N_NETWORKS_DRAWN)
    row_y = [top - 0.62, top - 1.22, top - 2.02]
    names = ["1", "2", "B"]
    mini_w, mini_h = 0.95, 0.46
    mini_x = 2.55

    def to_fig(x, y):
        return x / FIG_W, y / FIG_H

    for r, (yc, nm) in enumerate(zip(row_y, names)):
        ax.text(0.85, yc, rf"$\mathcal{{D}}^{{({nm})}}$", ha="right", va="center", fontsize=8)
        _arrow(ax, (0.9, yc), (1.18, yc))
        ax.text(1.04, yc + 0.06, "train", ha="center", va="bottom", fontsize=6,
                color=ps.INK_SECONDARY)
        ax.add_patch(FancyBboxPatch((1.2, yc - 0.17), 0.8, 0.34,
                                    boxstyle="round,pad=0.0,rounding_size=0.05",
                                    facecolor="#eaf1fb", edgecolor=INPUT_COLOR, lw=0.8))
        ax.text(1.6, yc, rf"LSTM $f_{{\theta_{{{nm}}}}}$",
                ha="center", va="center", fontsize=7.5)
        _arrow(ax, (2.02, yc), (mini_x - 0.04, yc))
        ax.text((2.02 + mini_x) / 2, yc + 0.05, r"$M$ passes", ha="center", va="bottom",
                fontsize=6, color=ps.INK_SECONDARY)
        ax.text((2.02 + mini_x) / 2, yc - 0.05, "dropout on", ha="center", va="top",
                fontsize=6, color=ps.INK_SECONDARY)

        a = fig.add_axes([*to_fig(mini_x, yc - mini_h / 2), mini_w / FIG_W, mini_h / FIG_H])
        color = BLOCK_CMAP(0.15 + 0.35 * r)
        for c in curves[r]:
            a.plot(h, c, color=color, lw=0.4, alpha=0.55)
        a.plot(h, curves[r].mean(axis=0), color=ps.INK, lw=0.9)
        _clean_axes(a)
        a.set_ylim(0, 1.6)
        a.text(1.02, 0.95, rf"$\hat{{y}}^{{({nm},1)}},\dots,\hat{{y}}^{{({nm},M)}}$",
               transform=a.transAxes, ha="left", va="top", fontsize=6.3)
        a.text(1.02, 0.55, rf"mean $\hat{{\mu}}_{{{nm}}}$", transform=a.transAxes,
               ha="left", va="top", fontsize=6.3, color=ps.INK_SECONDARY)
    ax.text(1.6, (row_y[1] + row_y[2]) / 2 + 0.05, r"$\vdots$", ha="center", va="center",
            fontsize=9, color=ps.INK_SECONDARY)
    ax.text(mini_x + mini_w / 2, (row_y[1] + row_y[2]) / 2 + 0.05, r"$\vdots$", ha="center",
            va="center", fontsize=9, color=ps.INK_SECONDARY)

    # Test-window input shared by all networks.
    ax.text(1.6, row_y[0] + 0.36, r"same test window ($L$ input hours) into every network",
            ha="center", va="bottom", fontsize=6.3, color=ps.INK_SECONDARY)

    # Converging arrows into the pool.
    pool_x, pool_w = 4.6, 1.6
    pool_y0, pool_h = row_y[2] - 0.3, row_y[0] - row_y[2] + 0.55
    for yc in row_y:
        _arrow(ax, (mini_x + mini_w + 0.62, yc), (pool_x - 0.1, pool_y0 + pool_h / 2),
               connectionstyle="arc3,rad=0", color=ps.INK_MUTED)
    ax.text(pool_x + pool_w / 2, pool_y0 + pool_h + 0.08,
            r"pool all $B\times M$ forecasts",
            ha="center", va="bottom", fontsize=6.8, color=ps.INK)

    a = fig.add_axes([*to_fig(pool_x, pool_y0), pool_w / FIG_W, pool_h / FIG_H])
    pooled = np.vstack(curves)
    for c in pooled:
        a.plot(h, c, color=POOL_COLOR, lw=0.3, alpha=0.35)
    mean = pooled.mean(axis=0)
    lo, hi = np.percentile(pooled, [2.5, 97.5], axis=0)
    a.fill_between(h, lo, hi, color=TARGET_COLOR, alpha=0.15, lw=0)
    a.plot(h, lo, color=TARGET_COLOR, lw=0.9, ls="--")
    a.plot(h, hi, color=TARGET_COLOR, lw=0.9, ls="--", label=r"$Q_{0.025}$, $Q_{0.975}$")
    a.plot(h, mean, color=ps.INK, lw=1.3, label=r"mean $\hat{\mu}$")
    _clean_axes(a)
    a.set_ylim(0, 1.75)
    a.set_xlabel(r"horizon step $h = 1,\dots,H$", fontsize=6.5, labelpad=2)
    a.legend(loc="upper right", fontsize=5.8, frameon=False, handlelength=1.6,
             borderaxespad=0.2)

    # Formulas under the pooled plot.
    fy = pool_y0 - 0.32
    ax.text(pool_x + pool_w / 2, fy,
            r"$\hat{\mu} = \dfrac{1}{BM}\sum_{b=1}^{B}\,\sum_{m=1}^{M}\hat{y}^{(b,m)}$",
            ha="center", va="top", fontsize=7.5)
    ax.text(pool_x + pool_w / 2, fy - 0.36,
            r"$\mathrm{PI}_{95} = [\,Q_{0.025},\ Q_{0.975}\,]$ of $\{\hat{y}^{(b,m)}\}$",
            ha="center", va="top", fontsize=7.5)
    ax.text(pool_x + pool_w / 2, fy - 0.62,
            "for every window and horizon step",
            ha="center", va="top", fontsize=6.3, color=ps.INK_SECONDARY)


def main() -> None:
    rng = np.random.default_rng(SEED)
    with plt.rc_context(ps.PAPER_RC):
        fig = plt.figure(figsize=(FIG_W, FIG_H))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, FIG_W)
        ax.set_ylim(0, FIG_H)
        ax.axis("off")
        _panel_windows(ax, FIG_H - 0.05)
        _panel_bootstrap(ax, FIG_H - 1.45, rng)
        _panel_ensemble(fig, ax, FIG_H - 3.7, rng)
        ps.save_figure(fig, SAVE_PATH)
    print(f"wrote {SAVE_PATH}.png/.pdf")


if __name__ == "__main__":
    main()
