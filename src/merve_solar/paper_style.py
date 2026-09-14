"""Shared figure style for the manuscript's descriptive-statistics figures.

Contract: academic but not sterile, and the background is ALWAYS pure white -- including
Axes3D panes, which stay blue-grey unless set explicitly.

Nothing here touches global rcParams. seaborn's set_theme() writes process-wide rcParams,
which would silently change the look of the experiment figures in utils.py whenever both
modules are imported in one process (a combined script, a notebook, `pytest tests/`). Every
plotting function instead wraps its body in `with plt.rc_context(PAPER_RC):`.
"""
from pathlib import Path

# --- print geometry -------------------------------------------------------------------
COL_WIDTH_IN = 3.46   # 88 mm, single journal column
FULL_WIDTH_IN = 7.09  # 180 mm, double column
DPI = 300

# --- ink and chrome -------------------------------------------------------------------
WHITE = "#FFFFFF"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
PANE_EDGE = "#E6E6E6"

# Single accent: cities are separated by panel, never by colour, so no 5-hue qualitative
# palette is needed (and none would clear the colour-vision checks at 5 slots anyway).
ACCENT = "#2a78d6"

# --- season palette -------------------------------------------------------------------
# Validated with the dataviz skill's validate_palette.js against a white surface with
# --pairs all: worst pair CVD dE 9.2 (deutan), normal-vision 16.3 -- both above threshold.
# The "natural" green+amber+brick triad was rejected: it drops to dE 7.2 under protanopia.
SEASONS = ["Winter", "Spring", "Summer", "Autumn"]
MONTH_TO_SEASON = {
    12: "Winter", 1: "Winter", 2: "Winter",
    3: "Spring", 4: "Spring", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Summer",
    9: "Autumn", 10: "Autumn", 11: "Autumn",
}
SEASON_COLORS = {
    "Winter": "#2a78d6",
    "Spring": "#1baf7a",
    "Summer": "#eb6834",
    "Autumn": "#4a3aa7",
}
# Second channel, so identity survives greyscale printing and colour-vision deficiency.
SEASON_LINESTYLES = {
    "Winter": "-",
    "Spring": "--",
    "Summer": "-",
    "Autumn": "-.",
}
SEASON_LINEWIDTHS = {"Winter": 1.6, "Spring": 1.6, "Summer": 2.2, "Autumn": 1.6}

MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# Variable labels. These are the RAW NASA POWER column names, not translations: a reader of
# the manuscript has to be able to match a figure axis to the dataset documentation and to the
# feature list in the methods section, and a gloss breaks that chain. The unit stays, because an
# irradiance axis without W/m² is not readable -- the project's figure contract requires it and
# the name alone does not carry it.
VARIABLE_LABELS = {
    "ALLSKY_SFC_SW_DWN": "ALLSKY_SFC_SW_DWN (W/m²)",
    "T2M": "T2M (°C)",
    "RH2M": "RH2M (%)",
    "T2MDEW": "T2MDEW (°C)",
    "PS": "PS (kPa)",
    "WS2M": "WS2M (m/s)",
    "PRECTOTCORR": "PRECTOTCORR (mm/hour)",
    "WD2M": "WD2M (°)",
    # Retired columns, kept so a figure regenerated from an older cached parquet still labels
    # correctly rather than falling through to the bare name.
    "WS10M": "WS10M (m/s)",
    "WD10M": "WD10M (°)",
    "QV2M": "QV2M (g/kg)",
    "WS50M": "WS50M (m/s)",
    "WD50M": "WD50M (°)",
}

# Bare identifiers, for places where the axis is too tight for a unit -- correlation-matrix
# tick labels above all.
VARIABLE_SHORT = {name: name for name in VARIABLE_LABELS}

PAPER_RC = {
    "figure.facecolor": WHITE,
    "figure.edgecolor": WHITE,
    "axes.facecolor": WHITE,
    "savefig.facecolor": WHITE,
    "savefig.edgecolor": WHITE,
    "savefig.transparent": False,
    "savefig.bbox": "tight",
    "figure.dpi": 120,
    "savefig.dpi": DPI,
    # Type 3 fonts are routinely rejected by Elsevier/IEEE/Springer production.
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],  # ships with matplotlib, full Latin-1 coverage
    "font.size": 9,
    "axes.titlesize": 11,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.titlepad": 6,
    "axes.labelsize": 10,
    "axes.labelcolor": INK_SECONDARY,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "text.color": INK,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "legend.frameon": False,
    "legend.fontsize": 9,
    "lines.linewidth": 1.6,
    "lines.solid_capstyle": "round",
}


def radiation_cmap():
    """Single-hue light->dark orange ramp for irradiance magnitude (never a rainbow)."""
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "solar_warm", ["#fdf0e8", "#f6b98f", "#eb6834", "#b8431b", "#7a2d0f"]
    )


def diverging_cmap():
    """Blue <-> red with a NEUTRAL GREY midpoint.

    A white midpoint would let near-zero cells merge into the white page and make the cell
    grid disappear; #f0efec keeps every cell visible while still reading as "nothing".
    """
    from matplotlib.colors import LinearSegmentedColormap

    return LinearSegmentedColormap.from_list(
        "corr_bwr", ["#184f95", "#2a78d6", "#a8c8ee", "#f0efec", "#f0a9a9", "#d03b3b", "#8f2020"]
    )


def grid_y_only(ax):
    """Hairline grid on the y axis only, plus despined top/right spines (2-D axes only)."""
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.grid(False, axis="x")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)


def white_3d_panes(ax):
    """Force an Axes3D onto a white background.

    Axes3D panes default to a blue-grey that axes.facecolor, set_facecolor() and
    sns.despine() all leave untouched, so it has to be set on each axis explicitly.
    """
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor(WHITE)
        axis.pane.set_alpha(1.0)
        axis.pane.set_edgecolor(PANE_EDGE)
        axis.line.set_color(AXIS)
    ax.set_facecolor(WHITE)
    ax.grid(True, color=PANE_EDGE, linewidth=0.5)


def save_figure(fig, save_path: Path) -> None:
    """Write PNG (raster, 300 dpi) and PDF (vector) of the same figure, then close it.

    `CreationDate` is suppressed in the PDF. Without it matplotlib stamps the wall clock into
    every file, so re-running the analysis marks all 30-odd PDFs as modified even when the
    figures are byte-identical -- noise in a repo whose outputs are tracked in git, and the
    kind of spurious diff that invites a careless `git add -A`.
    """
    import matplotlib.pyplot as plt

    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_path.with_suffix(".png"), dpi=DPI)
    fig.savefig(save_path.with_suffix(".pdf"), metadata={"CreationDate": None})
    plt.close(fig)
