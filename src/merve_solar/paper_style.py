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
# Sized for a Word page, where the figures are pasted: the text block is 6.30 in on A4 with
# 2.5 cm margins and 6.50 in on Letter with 1 in margins. A figure wider than the text block is
# scaled down on paste, which shrinks every font with it, so FULL_WIDTH_IN is the narrower of
# the two and the font sizes below are the sizes that actually print.
COL_WIDTH_IN = 3.10   # half the text block, for side-by-side placement
FULL_WIDTH_IN = 6.30  # full text block, A4 / 2.5 cm margins
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

# Table variable labels: the RAW NASA POWER column names plus unit. These values are join keys
# in the descriptive tables (`variable_label`), so they stay raw; figures use AXIS_LABELS below.
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

# Bare identifiers, for places where the axis is too tight for a unit.
VARIABLE_SHORT = {name: name for name in VARIABLE_LABELS}

# Figure axis titles: plain-English physical quantity plus unit. VARIABLE_LABELS keeps the raw
# NASA POWER codes because its values are join keys in the descriptive tables; a figure is read
# by people, and "ALLSKY_SFC_SW_DWN" on an axis tells a reader nothing. The code-to-name mapping
# belongs in the manuscript's variable table, which is where the traceability now lives.
AXIS_LABELS = {
    "ALLSKY_SFC_SW_DWN": "Global horizontal irradiance (W/m²)",
    "T2M": "Air temperature at 2 m (°C)",
    "RH2M": "Relative humidity at 2 m (%)",
    "T2MDEW": "Dew-point temperature at 2 m (°C)",
    "PS": "Surface pressure (kPa)",
    "WS2M": "Wind speed at 2 m (m/s)",
    "PRECTOTCORR": "Precipitation (mm/h)",
    "WD2M": "Wind direction at 2 m (°)",
    "WS10M": "Wind speed at 10 m (m/s)",
    "WD10M": "Wind direction at 10 m (°)",
    "QV2M": "Specific humidity at 2 m (g/kg)",
    "WS50M": "Wind speed at 50 m (m/s)",
    "WD50M": "Wind direction at 50 m (°)",
}

# Unit-less English names for tight spots: correlation-matrix ticks and heatmap rows.
AXIS_SHORT = {
    "ALLSKY_SFC_SW_DWN": "Irradiance (GHI)",
    "T2M": "Air temperature",
    "RH2M": "Relative humidity",
    "T2MDEW": "Dew point",
    "PS": "Surface pressure",
    "WS2M": "Wind speed",
    "PRECTOTCORR": "Precipitation",
    "WD2M": "Wind direction",
    "WS10M": "Wind speed (10 m)",
    "WD10M": "Wind direction (10 m)",
    "QV2M": "Specific humidity",
    "WS50M": "Wind speed (50 m)",
    "WD50M": "Wind direction (50 m)",
}

# Derived quantities that appear on several figures.
DAILY_IRRADIATION_LABEL = "Daily irradiation (kWh/m²)"
HOUR_LST_LABEL = "Hour of day (local solar time)"

# One-letter month ticks: twelve three-letter abbreviations do not fit unrotated under a
# 2-inch panel, and rotated ones collide with the panel below.
MONTH_INITIAL = {m: "JFMAMJJASOND"[m - 1] for m in range(1, 13)}

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
    # Sizes are as printed at FULL_WIDTH_IN: 7 pt ticks and 8 pt labels against a 10-11 pt
    # body text, the usual journal ratio.
    "font.size": 7.5,
    "figure.titlesize": 9,
    "figure.titleweight": "semibold",
    "figure.labelsize": 8,
    "figure.constrained_layout.h_pad": 0.03,
    "figure.constrained_layout.w_pad": 0.03,
    "axes.titlesize": 8,
    "axes.titleweight": "semibold",
    "axes.titlelocation": "left",
    "axes.titlepad": 4,
    "axes.labelsize": 8,
    "axes.labelpad": 3,
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
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "xtick.major.pad": 2,
    "ytick.major.pad": 2,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "legend.frameon": False,
    "legend.fontsize": 7,
    "legend.title_fontsize": 7.5,
    "lines.linewidth": 1.2,
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
