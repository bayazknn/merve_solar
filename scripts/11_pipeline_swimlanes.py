"""Methodology figure: the forecasting pipeline as swimlanes, one lane per data period.

    uv run python scripts/11_pipeline_swimlanes.py

Writes outputs/methodology/figures/pipeline_swimlanes.{png,pdf}.

Lanes are the training, validation and test periods, rows are pipeline phases, so the figure
shows which period every step touches: the scaler and the bootstrap see training rows only, the
validation period drives early stopping and (optionally) the conformal factor, and the test
period is only ever predicted and scored. Counts shown (B = 8, M = 100, split proportions) are
the ExperimentConfig defaults; dashed boxes are the optional conformal layer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

from merve_solar import paper_style as ps
from merve_solar.config import OUTPUTS_DIR

SAVE_PATH = OUTPUTS_DIR / "methodology" / "figures" / "pipeline_swimlanes"

FIG_W, FIG_H = ps.FULL_WIDTH_IN, 7.05
LABEL_W = 0.95                       # left column holding the phase labels
LANE_W = (FIG_W - LABEL_W) / 3
BOX_W = 1.55
FONT = 6.5

LANES = [
    ("Training period · 74 %", "30 Jun 2019 – 3 Sep 2024", "#eef4fc", "#d6e4f7"),
    ("Validation period · 11 %", "3 Sep 2024 – 11 Jun 2025", "#f6f3ea", "#e9e3d2"),
    ("Test period · 15 %", "11 Jun 2025 – 29 Jun 2026", "#fdf0ea", "#f6dccf"),
]
LANE_TOP, HEADER_H = 6.0, 0.45

# (label, top, bottom) in inches from the figure bottom
PHASES = [
    ("Data preparation\n(once, all data)", 7.05, 6.0),
    ("Pre-processing", 5.55, 4.75),
    ("Ensemble\ntraining", 4.75, 3.15),
    ("Prediction\n(MC Dropout)", 3.15, 2.05),
    ("Post-processing", 2.05, 0.85),
    ("Evaluation", 0.85, 0.0),
]


def _cx(lane):
    return LABEL_W + LANE_W * (lane + 0.5)


def _box(ax, x, y, text, h=0.42, w=BOX_W, dashed=False, accent=False, bold_first=True):
    """Rounded box centred at (x, y); returns its edges for arrow anchoring."""
    edge = ps.ACCENT if accent else ps.INK_MUTED
    ax.add_patch(FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.05",
        facecolor="#e8f0fb" if accent else ps.WHITE, edgecolor=edge,
        lw=1.1 if accent else 0.7, ls=(0, (3, 2)) if dashed else "-", zorder=3,
    ))
    lines = text.split("\n")
    n = len(lines)
    step = 0.115
    for i, line in enumerate(lines):
        yy = y + (n - 1) / 2 * step - i * step
        ax.text(x, yy, line, ha="center", va="center", fontsize=FONT, zorder=4,
                color=ps.INK if (i == 0 and bold_first) else ps.INK_SECONDARY,
                fontweight="semibold" if (i == 0 and bold_first) else "normal")
    return dict(left=x - w / 2, right=x + w / 2, top=y + h / 2, bottom=y - h / 2, x=x, y=y)


def _arrow(ax, start, end, style="-|>", **kw):
    props = dict(arrowstyle=style, mutation_scale=7, lw=0.8, color=ps.INK_SECONDARY,
                 shrinkA=0, shrinkB=0, zorder=2)
    props.update(kw)
    ax.add_patch(FancyArrowPatch(start, end, **props))


def _label(ax, x, y, text, **kw):
    ax.text(x, y, text, fontsize=6, color=ps.INK_SECONDARY, ha="center", va="bottom",
            zorder=4, **kw)


def build_figure():
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, FIG_W)
    ax.set_ylim(0, FIG_H)
    ax.axis("off")

    # Lane backgrounds and headers
    for i, (title, dates, fill, head) in enumerate(LANES):
        x0 = LABEL_W + i * LANE_W
        ax.add_patch(Rectangle((x0 + 0.02, 0), LANE_W - 0.04, LANE_TOP, facecolor=fill,
                               edgecolor="none", zorder=0))
        ax.add_patch(Rectangle((x0 + 0.02, LANE_TOP - HEADER_H), LANE_W - 0.04, HEADER_H,
                               facecolor=head, edgecolor="none", zorder=1))
        ax.text(_cx(i), LANE_TOP - 0.15, title, ha="center", va="center", fontsize=7,
                fontweight="semibold", color=ps.INK, zorder=4)
        ax.text(_cx(i), LANE_TOP - 0.32, dates, ha="center", va="center", fontsize=6,
                color=ps.INK_SECONDARY, zorder=4)

    # Phase labels and separators
    for label, top, bottom in PHASES:
        ax.text(0.06, (top + bottom) / 2, label, ha="left", va="center", fontsize=7,
                fontweight="semibold", color=ps.INK, linespacing=1.3)
        if bottom > 0:
            ax.plot([0.04, FIG_W - 0.02], [bottom, bottom], color=ps.AXIS, lw=0.5, zorder=1)

    # 1. Data preparation: one box across all lanes, then the chronological split
    prep = _box(ax, (LABEL_W + FIG_W) / 2, 6.62,
                "NASA POWER hourly data, 5 provinces, 30 Jun 2019 – 29 Jun 2026\n"
                "trim the −999 latency tail · sin/cos encodings of hour, day of year, wind direction\n"
                "solar elevation from site and time (daylight mask only, never a model input)",
                h=0.52, w=FIG_W - LABEL_W - 0.25)
    for i in range(3):
        _arrow(ax, (_cx(i), prep["bottom"]), (_cx(i), LANE_TOP))
    ax.text(_cx(1) + 0.08, (prep["bottom"] + LANE_TOP) / 2,
            "chronological split,\nsame dates for every province", fontsize=6, linespacing=1.3,
            color=ps.INK_SECONDARY, ha="left", va="center", style="italic")

    # 2. Pre-processing: scaler fitted on training rows, applied unchanged elsewhere
    y2 = 5.15
    pre_tr = _box(ax, _cx(0), y2, "Fit z-score scaler\nmake 24 h → 24 h windows", h=0.46)
    pre_va = _box(ax, _cx(1), y2, "Apply training scaler\nmake 24 h → 24 h windows", h=0.46)
    pre_te = _box(ax, _cx(2), y2, "Apply training scaler\nmake 24 h → 24 h windows", h=0.46)
    _arrow(ax, (pre_tr["right"], y2), (pre_va["left"], y2))
    _arrow(ax, (pre_va["right"], y2), (pre_te["left"], y2))
    _label(ax, (pre_tr["right"] + pre_va["left"]) / 2, y2 + 0.03, "μ, σ")
    _label(ax, (pre_va["right"] + pre_te["left"]) / 2, y2 + 0.03, "μ, σ")

    # 3. Ensemble training, repeated per bootstrap replicate
    loop = FancyBboxPatch((LABEL_W + 0.07, 3.22), 2 * LANE_W - 0.14, 1.46,
                          boxstyle="round,pad=0,rounding_size=0.08", facecolor="none",
                          edgecolor=ps.INK_MUTED, lw=0.7, ls=(0, (1, 1.5)), zorder=1)
    ax.add_patch(loop)
    # The validation arrow runs down the lane's left half so this label has the right half.
    val_arrow_x = _cx(1) - 0.5
    ax.text(_cx(1) + 0.2, 4.4, "repeated for b = 1, …, B\n(B = 8), one network each",
            ha="center", va="center", fontsize=6, style="italic", color=ps.INK_SECONDARY,
            linespacing=1.3)
    boot = _box(ax, _cx(0), 4.32, "Moving-block bootstrap\n1-week blocks, per province")
    train = _box(ax, _cx(0), 3.6, "Train LSTM (replicate b)\nAdam · MSE + non-neg. penalty")
    val = _box(ax, _cx(1), 3.6, "Validation loss\nearly stopping · LR decay")
    _arrow(ax, (pre_tr["x"], pre_tr["bottom"]), (boot["x"], boot["top"]))
    _arrow(ax, (boot["x"], boot["bottom"]), (train["x"], train["top"]))
    _arrow(ax, (val_arrow_x, pre_va["bottom"]), (val_arrow_x, val["top"]))
    _arrow(ax, (train["right"], 3.6), (val["left"], 3.6), style="<|-|>")

    # 4. Prediction with dropout kept active
    nets = _box(ax, _cx(0), 2.6, "B trained networks\ndropout kept on\nat prediction", h=0.72)
    mc_va = _box(ax, _cx(1), 2.85, "MC Dropout on validation\nM = 100 passes per network",
                 h=0.4, dashed=True)
    mc_te = _box(ax, _cx(2), 2.35, "MC Dropout on test\nM = 100 passes per network", h=0.4)
    _arrow(ax, (train["x"], train["bottom"]), (nets["x"], nets["top"]))
    _arrow(ax, (nets["right"], 2.85), (mc_va["left"], 2.85), ls=(0, (3, 2)))
    _arrow(ax, (nets["right"], 2.35), (mc_te["left"], 2.35))
    _arrow(ax, (pre_te["x"], pre_te["bottom"]), (mc_te["x"], mc_te["top"]))

    # 5. Post-processing: pool, back to W/m^2, night clamp, optional conformal rescaling
    pool = _box(ax, _cx(2), 1.72, "Pool B × M = 800 samples\nback-transform to W/m²\nsun below horizon → 0",
                h=0.5)
    fit_k = _box(ax, _cx(1), 1.12, "Fit conformal factor k\ntarget coverage 95 %", h=0.38,
                 dashed=True)
    rescale = _box(ax, _cx(2), 1.12, "Rescale spread\nx → m + k (x − m)", h=0.38, dashed=True)
    _arrow(ax, (mc_te["x"], mc_te["bottom"]), (pool["x"], pool["top"]))
    _arrow(ax, (mc_va["x"], mc_va["bottom"]), (fit_k["x"], fit_k["top"]), ls=(0, (3, 2)))
    _arrow(ax, (pool["x"], pool["bottom"]), (rescale["x"], rescale["top"]))
    _arrow(ax, (fit_k["right"], 1.12), (rescale["left"], 1.12), ls=(0, (3, 2)))
    _label(ax, (fit_k["right"] + rescale["left"]) / 2, 1.15, "k")

    # 6. Evaluation
    fc = _box(ax, _cx(2), 0.42, "Forecast\nmean and 2.5–97.5 % interval\nscored on daylight hours",
              h=0.52, accent=True)
    _arrow(ax, (rescale["x"], rescale["bottom"]), (fc["x"], fc["top"]))

    # Legend for the optional layer
    leg_x, leg_y = _cx(0) - 0.62, 0.42
    ax.add_patch(FancyBboxPatch((leg_x, leg_y - 0.09), 0.3, 0.18,
                                boxstyle="round,pad=0,rounding_size=0.03", facecolor=ps.WHITE,
                                edgecolor=ps.INK_MUTED, lw=0.7, ls=(0, (3, 2))))
    ax.text(leg_x + 0.38, leg_y, "optional conformal\nrecalibration", fontsize=6,
            color=ps.INK_SECONDARY, ha="left", va="center", linespacing=1.3)
    return fig


def main():
    with plt.rc_context(ps.PAPER_RC):
        fig = build_figure()
        ps.save_figure(fig, SAVE_PATH)
    print(f"{SAVE_PATH.with_suffix('.png')}")


if __name__ == "__main__":
    main()
