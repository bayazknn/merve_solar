"""Descriptive statistics and paper figures for the dataset itself (config-independent).

Read-only over outputs/processed/base_features.parquet; nothing here touches an experiment,
the ledger, or ExperimentConfig. Driven by scripts/02_descriptive_analysis.py.

Three data-handling decisions drive most of this module; the reasoning is in
outputs/eda/README.md and repeated briefly at each function:

1. "Daylight" is defined climatologically (a (city, month, hour) cell whose mean is > 0),
   not as `target > 0`. Filtering on the realised value conditions on the dependent
   variable and deletes 5,266 overcast daylight hours unevenly across cities.
2. Anything month-to-month is computed on DAILY TOTALS, not on hourly values. A box of
   daylight-hourly values is ~91% solar geometry, and it makes winter look *less* variable
   than summer -- the opposite of the truth.
3. The hourly clock is NASA POWER's per-site Local Solar Time, not a shared time zone
   (verified: peak hour orders Konya 11.25 < Ankara 11.26 < Antalya 11.41 < Van 11.56 <
   Rize 11.89, matching UTC+round(lon/15) to within 0.1 h). Hour axes are labelled LST and
   hours are never compared across cities.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from merve_solar.config import (
    CIRCULAR_COLUMNS,
    CITIES,
    RAW_METEO_COLUMNS,
    TARGET_COLUMN,
)
from merve_solar.paper_style import (
    ACCENT,
    COL_WIDTH_IN,
    FULL_WIDTH_IN,
    INK_SECONDARY,
    MONTH_ABBR_TR,
    MONTH_TO_SEASON_TR,
    PAPER_RC,
    SEASON_COLORS,
    SEASON_LINESTYLES,
    SEASON_LINEWIDTHS,
    SEASONS_TR,
    VARIABLE_LABELS_TR,
    VARIABLE_SHORT_TR,
    diverging_cmap,
    grid_y_only,
    radiation_cmap,
    save_figure,
    white_3d_panes,
)

POOLED_LABEL = "Tümü"
SURFACE_YEARS = (2020, 2025)  # complete calendar years only (2019 and 2026 are partial)
CALM_WIND_MIN = 1.0  # m/s; direction of near-calm hours is noise


# ---------------------------------------------------------------------------------------
# data helpers
# ---------------------------------------------------------------------------------------
def daylight_mask(df: pd.DataFrame) -> pd.Series:
    """Climatological daylight: (city, month, hour) cells whose mean irradiance is > 0.

    Deterministic in (city, month, hour) and independent of the realised weather, so it
    does not condition on the dependent variable the way `target > 0` does.
    """
    cell_mean = df.groupby(["city", df["datetime"].dt.month, "HR"], observed=True)[
        TARGET_COLUMN
    ].transform("mean")
    return cell_mean > 0


def add_season(df: pd.DataFrame) -> pd.DataFrame:
    """Add a meteorological-season column (Kış = Dec/Jan/Feb) as an ordered Categorical."""
    df = df.copy()
    df["season"] = pd.Categorical(
        df["MO"].map(MONTH_TO_SEASON_TR), categories=SEASONS_TR, ordered=True
    )
    return df


def daily_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Per (city, date) daily insolation in kWh/m^2/day.

    Summed over all 24 hours: night contributes exactly 0, so this is invariant to the
    daylight filter. kWh (not Wh) because 4.9 reads and 4,944 does not, and five-digit
    ticks break the 3-D z axis layout.
    """
    out = (
        df.assign(date=df["datetime"].dt.normalize())
        .groupby(["city", "date"], observed=True)[TARGET_COLUMN]
        .sum()
        .div(1000.0)
        .reset_index(name="daily_kwh")
    )
    out["MO"] = out["date"].dt.month
    out["YEAR"] = out["date"].dt.year
    return out


def last_12_months(df: pd.DataFrame, date_col: str = "datetime") -> pd.DataFrame:
    """The last 12 complete-ish calendar months, with an ORDERED month column.

    Anchored on periods, not on a timedelta: `max - DateOffset(months=12)` yields 13
    distinct year-months with two ragged edges. The ordered Categorical is what stops a
    groupby/boxplot from sorting 2026-01..03 to the front of the axis.
    """
    last = df[date_col].max().to_period("M")
    months = pd.period_range(last - 11, last, freq="M")
    period = df[date_col].dt.to_period("M")
    out = df[period.isin(months)].copy()
    out["ym"] = pd.Categorical(period[period.isin(months)], categories=months, ordered=True)
    out["ym_label"] = [f"{MONTH_ABBR_TR[p.month]} {str(p.year)[2:]}" for p in out["ym"]]
    labels = [f"{MONTH_ABBR_TR[p.month]} {str(p.year)[2:]}" for p in months]
    out["ym_label"] = pd.Categorical(out["ym_label"], categories=labels, ordered=True)
    return out


def align_day_of_year(dates: pd.Series) -> pd.Series:
    """Day-of-year aligned across leap and non-leap years (29 Feb rows become NaN).

    Without this, every day from March onward in 2020/2024 sits one day right of the same
    calendar date in other years, smearing the climatology by a day.
    """
    doy = dates.dt.dayofyear
    is_leap = dates.dt.is_leap_year
    feb29 = is_leap & (doy == 60)
    aligned = doy.where(~(is_leap & (doy > 60)), doy - 1).astype("float")
    aligned[feb29] = np.nan
    return aligned


def circular_stats(sin_vals, cos_vals, weights=None) -> dict:
    """Mean direction (deg), resultant length R, and circular SD (deg)."""
    sin_vals = np.asarray(sin_vals, dtype=float)
    cos_vals = np.asarray(cos_vals, dtype=float)
    if weights is None:
        mean_sin, mean_cos = sin_vals.mean(), cos_vals.mean()
    else:
        w = np.asarray(weights, dtype=float)
        mean_sin = np.average(sin_vals, weights=w)
        mean_cos = np.average(cos_vals, weights=w)
    r = float(np.hypot(mean_sin, mean_cos))
    mean_deg = float(np.degrees(np.arctan2(mean_sin, mean_cos)) % 360.0)
    # A mean direction of exactly north comes back as arctan2(-1e-16, 1) -> -1e-14, and
    # `% 360` turns that into 360.0. Report it as 0 deg.
    if mean_deg > 360.0 - 1e-9:
        mean_deg = 0.0
    circ_sd = float(np.degrees(np.sqrt(-2.0 * np.log(r)))) if r > 0 else float("nan")
    return {"mean_deg": mean_deg, "resultant_length": r, "circular_sd_deg": circ_sd}


# ---------------------------------------------------------------------------------------
# tables
# ---------------------------------------------------------------------------------------
def descriptive_table(df: pd.DataFrame) -> pd.DataFrame:
    """Long-format descriptive statistics per (city, variable), plus a pooled row.

    Kurtosis is pandas' Fisher (excess) kurtosis with the G2 bias correction -- 0, not 3,
    means normal. Wind direction is excluded (circular; see circular_wind_table).
    """
    rows = []
    groups = [(city, g) for city, g in df.groupby("city", observed=True)] + [(POOLED_LABEL, df)]
    for city, g in groups:
        for var in RAW_METEO_COLUMNS:
            s = g[var]
            row = {
                "city": city,
                "variable": var,
                "variable_tr": VARIABLE_LABELS_TR.get(var, var),
                "n": int(s.size),
                "mean": s.mean(),
                "std": s.std(),
                "min": s.min(),
                "q25": s.quantile(0.25),
                "median": s.median(),
                "q75": s.quantile(0.75),
                "max": s.max(),
                "skew": s.skew(),
                "excess_kurtosis": s.kurt(),
            }
            if city == POOLED_LABEL:
                # The pooled std mixes within- and between-city variance; report the
                # between-city component so the decomposition is visible.
                row["between_city_sd"] = df.groupby("city", observed=True)[var].mean().std()
            rows.append(row)
    return pd.DataFrame(rows)


def temporal_coverage_table(df: pd.DataFrame) -> pd.DataFrame:
    """Describe the TIME features on their own scale rather than as sin/cos encodings.

    mean(hour_sin) ~ 0 and std ~ 0.707 for every city by construction, so those rows would
    carry no information in a paper table. What a Dataset section actually needs is span,
    counts, daylight share and how the target moves with hour / month / season.
    """
    day = df["datetime"].dt.normalize()
    is_day = daylight_mask(df)
    work = add_season(df.assign(_date=day, _daylight=is_day))
    rows = []
    for city, g in work.groupby("city", observed=True):
        for season in [POOLED_LABEL] + SEASONS_TR:
            sub = g if season == POOLED_LABEL else g[g["season"] == season]
            n_days = sub["_date"].nunique()
            rows.append(
                {
                    "city": city,
                    "season": season,
                    "start": sub["datetime"].min(),
                    "end": sub["datetime"].max(),
                    "n_hours": int(len(sub)),
                    "n_days": int(n_days),
                    "daylight_hour_share": sub["_daylight"].mean(),
                    "mean_daylight_hours_per_day": sub["_daylight"].sum() / n_days,
                    "target_mean_24h": sub[TARGET_COLUMN].mean(),
                    "target_mean_daylight": sub.loc[sub["_daylight"], TARGET_COLUMN].mean(),
                    "daily_total_mean_kwh": sub.groupby("_date", observed=True)[TARGET_COLUMN]
                    .sum()
                    .div(1000.0)
                    .mean(),
                }
            )
    return pd.DataFrame(rows)


def target_by_hour_table(df: pd.DataFrame) -> pd.DataFrame:
    """Target distribution by local-solar hour, per city (the diurnal figure's data)."""
    work = add_season(df)
    g = work.groupby(["city", "season", "HR"], observed=True)[TARGET_COLUMN]
    out = g.agg(
        n="size", mean="mean", median="median",
        q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75),
    ).reset_index()
    return out


def time_explained_variance_table(df: pd.DataFrame) -> pd.DataFrame:
    """How much target variance the time keys explain: eta^2 and harmonic R^2.

    Reported instead of Pearson r against hour_sin/doy_cos -- a correlation against a
    deterministic clock function is not interpretable, but "hour-of-day explains 71% of the
    variance" is.
    """
    def eta_squared(values, groups):
        values = np.asarray(values, dtype=float)
        total = ((values - values.mean()) ** 2).sum()
        if total == 0:
            return np.nan
        grand = pd.Series(values).groupby(np.asarray(groups)).transform("mean").to_numpy()
        return float(1.0 - ((values - grand) ** 2).sum() / total)

    def harmonic_r2(values, phase):
        values = np.asarray(values, dtype=float)
        x = np.column_stack(
            [np.ones_like(phase), np.sin(phase), np.cos(phase),
             np.sin(2 * phase), np.cos(2 * phase)]
        )
        beta, *_ = np.linalg.lstsq(x, values, rcond=None)
        resid = values - x @ beta
        total = ((values - values.mean()) ** 2).sum()
        return float(1.0 - (resid ** 2).sum() / total) if total else np.nan

    rows = []
    is_day = daylight_mask(df)
    for scope, sub in (("24 saat", df), ("gündüz", df[is_day])):
        for city, g in list(sub.groupby("city", observed=True)) + [(POOLED_LABEL, sub)]:
            y = g[TARGET_COLUMN].to_numpy()
            doy = g["datetime"].dt.dayofyear.to_numpy()
            rows.append(
                {
                    "city": city, "scope": scope, "factor": "saat (LST)",
                    "eta_squared": eta_squared(y, g["HR"].to_numpy()),
                    "harmonic_r2": harmonic_r2(y, 2 * np.pi * g["HR"].to_numpy() / 24.0),
                }
            )
            rows.append(
                {
                    "city": city, "scope": scope, "factor": "yılın günü",
                    "eta_squared": eta_squared(y, doy),
                    "harmonic_r2": harmonic_r2(y, 2 * np.pi * doy / 365.25),
                }
            )
    return pd.DataFrame(rows)


def circular_wind_table(df: pd.DataFrame) -> pd.DataFrame:
    """Speed-weighted circular statistics for wind direction, over all 24 hours.

    Uses the sin/cos columns already in the parquet. Near-calm hours are excluded because
    their direction is noise; wind-direction climatology is not a daylight-only quantity.
    """
    rows = []
    for col in CIRCULAR_COLUMNS:
        speed_col = "WS10M" if col == "WD10M" else "WS50M"
        sub_all = df[df[speed_col] > CALM_WIND_MIN]
        groups = [(c, g) for c, g in sub_all.groupby("city", observed=True)]
        groups.append((POOLED_LABEL, sub_all))
        for city, g in groups:
            stats = circular_stats(g[f"{col}_sin"], g[f"{col}_cos"], weights=g[speed_col])
            rows.append(
                {
                    "city": city,
                    "variable": col,
                    "variable_tr": VARIABLE_LABELS_TR.get(col, col),
                    "n": int(len(g)),
                    "excluded_calm_hours": int((df[speed_col] <= CALM_WIND_MIN).sum())
                    if city == POOLED_LABEL else int((df.loc[df["city"] == city, speed_col]
                                                      <= CALM_WIND_MIN).sum()),
                    "speed_weighted_mean_deg": stats["mean_deg"],
                    "resultant_length": stats["resultant_length"],
                    "circular_sd_deg": stats["circular_sd_deg"],
                }
            )
    return pd.DataFrame(rows)


def _within_cell_residuals(df: pd.DataFrame, cols) -> pd.DataFrame:
    """Subtract each (city, month, hour) cell mean -- removes the solar-geometry component."""
    keys = ["city", df["datetime"].dt.month.rename("_mo"), "HR"]
    return df[cols] - df.groupby(keys, observed=True)[cols].transform("mean")


def correlation_tables(df_daylight: pd.DataFrame) -> dict:
    """Pearson and Spearman matrices per city and pooled, plus target correlations.

    Spearman is included for monotone-but-nonlinear relationships, not because of heavy
    tails (on daylight rows the target's skew is only 0.44). `partial_r_within_hour` is the
    correlation after removing the (city, month, hour) cell mean, which separates the
    weather signal from the shared solar-geometry driver.
    """
    cols = RAW_METEO_COLUMNS
    out = {"pearson": {}, "spearman": {}}
    groups = [(c, g) for c, g in df_daylight.groupby("city", observed=True)]
    groups.append((POOLED_LABEL, df_daylight))
    for city, g in groups:
        out["pearson"][city] = g[cols].corr(method="pearson")
        out["spearman"][city] = g[cols].corr(method="spearman")

    resid = _within_cell_residuals(df_daylight, cols).assign(city=df_daylight["city"].values)
    target_rows = []
    for var in cols:
        if var == TARGET_COLUMN:
            continue
        row = {"variable": var, "variable_tr": VARIABLE_LABELS_TR.get(var, var)}
        for city in CITIES + [POOLED_LABEL]:
            row[f"pearson_{city}"] = out["pearson"][city].loc[TARGET_COLUMN, var]
        row["partial_r_within_hour_pooled"] = resid[TARGET_COLUMN].corr(resid[var])
        for city in CITIES:
            s = resid[resid["city"] == city]
            row[f"partial_r_within_hour_{city}"] = s[TARGET_COLUMN].corr(s[var])
        target_rows.append(row)
    out["target"] = pd.DataFrame(target_rows)
    return out


def collinear_pairs(corr: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """Feature pairs with |r| > threshold -- a finding about the 17-feature model, not noise."""
    rows = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            if abs(r) > threshold:
                rows.append({"variable_a": a, "variable_b": b, "pearson_r": r})
    return pd.DataFrame(rows).sort_values("pearson_r", key=abs, ascending=False)


def monthly_target_stats(daily: pd.DataFrame) -> pd.DataFrame:
    """Per (city, year-month) daily-total summary -- the boxplot's underlying numbers."""
    g = daily.groupby(["city", "ym_label"], observed=True)["daily_kwh"]
    return g.agg(
        n="size", mean="mean", std="std", min="min",
        q25=lambda s: s.quantile(0.25), median="median",
        q75=lambda s: s.quantile(0.75), max="max",
    ).reset_index()


def seasonal_target_stats(df: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Per (city, season) hourly and daily-total summary."""
    work = add_season(df)
    is_day = daylight_mask(df)
    daily_s = add_season(daily.assign(MO=daily["MO"]))
    rows = []
    for city in CITIES:
        for season in SEASONS_TR:
            h = work[(work["city"] == city) & (work["season"] == season)]
            hd = h[is_day.loc[h.index]]
            d = daily_s[(daily_s["city"] == city) & (daily_s["season"] == season)]
            rows.append(
                {
                    "city": city, "season": season,
                    "n_hours": len(h), "n_days": len(d),
                    "hourly_mean_24h": h[TARGET_COLUMN].mean(),
                    "hourly_mean_daylight": hd[TARGET_COLUMN].mean(),
                    "hourly_max": h[TARGET_COLUMN].max(),
                    "daily_kwh_mean": d["daily_kwh"].mean(),
                    "daily_kwh_std": d["daily_kwh"].std(),
                    "daily_kwh_cv": d["daily_kwh"].std() / d["daily_kwh"].mean(),
                    "daily_kwh_q25": d["daily_kwh"].quantile(0.25),
                    "daily_kwh_q75": d["daily_kwh"].quantile(0.75),
                }
            )
    return pd.DataFrame(rows)


def month_year_grid(daily: pd.DataFrame, city: str) -> pd.DataFrame:
    """Monthly mean daily total (kWh/m^2/day) on a complete year x month grid.

    Restricted to complete calendar years; reindexed and asserted so a future data refresh
    with a hole fails loudly instead of drawing a mangled surface.
    """
    lo, hi = SURFACE_YEARS
    sub = daily[(daily["city"] == city) & daily["YEAR"].between(lo, hi)]
    grid = sub.groupby(["YEAR", "MO"], observed=True)["daily_kwh"].mean()
    full = pd.MultiIndex.from_product(
        [range(lo, hi + 1), range(1, 13)], names=["YEAR", "MO"]
    )
    grid = grid.reindex(full)
    if not grid.notna().all():
        missing = grid[grid.isna()].index.tolist()
        raise ValueError(f"{city}: month-year grid has empty cells {missing}")
    return grid.unstack("MO")


# ---------------------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------------------
def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _city_panels(plt, figsize=None, sharex=True, sharey=True):
    """2x3 grid: 5 city panels + a 6th cell reserved for the legend or colourbar."""
    fig, axes = plt.subplots(
        2, 3, figsize=figsize or (FULL_WIDTH_IN, 4.6), sharex=sharex, sharey=sharey
    )
    flat = axes.ravel()
    flat[5].axis("off")
    return fig, flat


def _finish_city_panels(plt, fig, flat, xlabel: str, ylabel: str) -> None:
    """One shared y label, and x tick labels on the top-right panel.

    With 5 panels in a 2x3 grid the third panel has no neighbour below it, so `sharex`
    would otherwise leave it without tick labels; and a per-axes y label on rows 0 and 1
    collides in the middle of the figure.
    """
    for ax in (flat[2], flat[3], flat[4]):
        ax.set_xlabel(xlabel)
        ax.tick_params(labelbottom=True)
        plt.setp(ax.get_xticklabels(), visible=True)
    for ax in flat[:5]:
        ax.set_ylabel("")
    fig.supylabel(ylabel, fontsize=10, color=INK_SECONDARY, x=0.005)


def plot_correlation_heatmap(corr: pd.DataFrame, title: str, save_path: Path) -> None:
    plt = _plt()
    import seaborn as sns

    labels = [VARIABLE_SHORT_TR.get(c, c) for c in corr.columns]
    with plt.rc_context(PAPER_RC):
        fig, ax = plt.subplots(figsize=(5.2, 4.6))
        sns.heatmap(
            corr, ax=ax, cmap=diverging_cmap(), vmin=-1, vmax=1, center=0,
            annot=True, fmt=".2f", annot_kws={"size": 7}, square=True,
            linewidths=0.6, linecolor="white",
            xticklabels=labels, yticklabels=labels,
            cbar_kws={"shrink": 0.75, "label": "Pearson r"},
        )
        ax.set_title(title)
        ax.tick_params(length=0)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        fig.tight_layout()
        save_figure(fig, save_path)


def plot_target_correlation_panel(target_df: pd.DataFrame, save_path: Path) -> None:
    plt = _plt()
    import seaborn as sns

    mat = target_df.set_index("variable_tr")[[f"pearson_{c}" for c in CITIES]]
    mat.columns = CITIES
    with plt.rc_context(PAPER_RC):
        fig, ax = plt.subplots(figsize=(COL_WIDTH_IN * 1.5, 3.4))
        sns.heatmap(
            mat, ax=ax, cmap=diverging_cmap(), vmin=-1, vmax=1, center=0,
            annot=True, fmt=".2f", annot_kws={"size": 8},
            linewidths=0.6, linecolor="white",
            cbar_kws={"shrink": 0.8, "label": "Pearson r"},
        )
        ax.set_title("Güneş ışınımı ile korelasyon (gündüz saatleri)")
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(length=0)
        fig.tight_layout()
        save_figure(fig, save_path)


def plot_scatter_vs_target(df_daylight: pd.DataFrame, city: str, save_path: Path) -> None:
    """Each meteorological variable against irradiance, with a binned-median trend."""
    plt = _plt()

    variables = [c for c in RAW_METEO_COLUMNS if c != TARGET_COLUMN]
    g = df_daylight[df_daylight["city"] == city]
    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(2, 4, figsize=(FULL_WIDTH_IN, 4.0))
        for ax, var in zip(axes.ravel(), variables):
            ax.scatter(
                g[var], g[TARGET_COLUMN], s=2, alpha=0.10, color=ACCENT,
                linewidths=0, rasterized=True,
            )
            bins = pd.qcut(g[var], 20, duplicates="drop")
            trend = g.groupby(bins, observed=True)[TARGET_COLUMN].median()
            centers = [iv.mid for iv in trend.index]
            ax.plot(centers, trend.to_numpy(), color="#7a2d0f", linewidth=1.6)
            lo, hi = g[var].quantile([0.001, 0.999])
            if hi > lo:
                pad = (hi - lo) * 0.03
                ax.set_xlim(lo - pad, hi + pad)
            ax.set_xlabel(VARIABLE_LABELS_TR.get(var, var), fontsize=8)
            grid_y_only(ax)
        for ax in axes[:, 0]:
            ax.set_ylabel("Işınım (W/m²)", fontsize=8)
        fig.suptitle(
            f"{city}: değişkenlerin güneş ışınımına karşı dağılımı (gündüz saatleri)",
            x=0.02, ha="left", fontsize=11, fontweight="semibold",
        )
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        save_figure(fig, save_path)


def plot_monthly_boxplot(daily_12m: pd.DataFrame, city, save_path: Path) -> None:
    """Last 12 months of DAILY TOTALS.

    Deliberately not hourly values: a box of daylight-hourly irradiance is ~91% solar
    geometry and makes winter look less variable than summer, which is backwards.
    """
    plt = _plt()
    import seaborn as sns

    order = list(daily_12m["ym_label"].cat.categories)
    with plt.rc_context(PAPER_RC):
        if city is None:
            fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 4.8))
            panels = [(flat[i], c) for i, c in enumerate(CITIES)]
            flat[5].axis("off")
        else:
            fig, ax = plt.subplots(figsize=(COL_WIDTH_IN * 1.6, 3.0))
            panels = [(ax, city)]
        for ax, c in panels:
            sub = daily_12m[daily_12m["city"] == c]
            sns.boxplot(
                data=sub, x="ym_label", y="daily_kwh", order=order, ax=ax,
                color=ACCENT, width=0.62, fliersize=1.6, linewidth=0.8,
                boxprops={"alpha": 0.55},
                medianprops={"color": "#7a2d0f", "linewidth": 1.4},
                flierprops={"markerfacecolor": INK_SECONDARY, "markeredgewidth": 0,
                            "alpha": 0.5},
            )
            ax.set_title(c)
            ax.set_xlabel("")
            ax.set_ylabel("Günlük toplam ışınım (kWh/m²)")
            grid_y_only(ax)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
        if city is None:
            _finish_city_panels(plt, fig, flat, "", "Günlük toplam ışınım (kWh/m²)")
            fig.suptitle(
                "Son 12 ayın günlük toplam güneş ışınımı", x=0.03, ha="left",
                fontsize=11, fontweight="semibold",
            )
            fig.tight_layout(rect=(0.03, 0, 1, 0.95))
        else:
            fig.tight_layout()
        save_figure(fig, save_path)


def plot_month_year_surface_3d(grids: dict, city, save_path: Path, zlim=None) -> None:
    """x = month, z (depth) = year, y (height) = monthly mean daily total."""
    plt = _plt()
    from matplotlib import cm  # noqa: F401  (registers 3-D projection deps)
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    cmap = radiation_cmap()
    with plt.rc_context(PAPER_RC):
        if city is None:
            fig = plt.figure(figsize=(FULL_WIDTH_IN, 5.4))
            items = [(fig.add_subplot(2, 3, i + 1, projection="3d"), c)
                     for i, c in enumerate(CITIES)]
        else:
            fig = plt.figure(figsize=(COL_WIDTH_IN * 1.6, 3.4))
            items = [(fig.add_subplot(111, projection="3d"), city)]
        for ax, c in items:
            grid = grids[c]
            months = np.array(grid.columns, dtype=float)
            years = np.array(grid.index, dtype=float)
            mm, yy = np.meshgrid(months, years)
            zz = grid.to_numpy()
            ax.plot_surface(
                mm, yy, zz, cmap=cmap, rstride=1, cstride=1,
                edgecolor="white", linewidth=0.3, antialiased=True, shade=False,
                vmin=zlim[0] if zlim else None, vmax=zlim[1] if zlim else None,
            )
            ax.set_xticks([1, 4, 7, 10])
            ax.set_xticklabels([MONTH_ABBR_TR[m] for m in (1, 4, 7, 10)], fontsize=7)
            ax.set_yticks(list(range(int(years.min()), int(years.max()) + 1)))
            ax.set_yticklabels([str(int(y)) for y in range(int(years.min()),
                                                           int(years.max()) + 1)], fontsize=7)
            ax.tick_params(axis="z", labelsize=7)
            ax.set_xlabel("Ay", fontsize=8, labelpad=-2)
            ax.set_ylabel("Yıl", fontsize=8, labelpad=2)
            if city is not None:
                ax.set_zlabel("kWh/m²/gün", fontsize=8, labelpad=-2)
            if zlim:
                ax.set_zlim(*zlim)
            ax.view_init(elev=26, azim=-58)
            ax.set_title(c, fontsize=10)
            white_3d_panes(ax)
        # tight_layout cannot fit 3-D axis decorations; set the margins explicitly instead.
        if city is None:
            fig.suptitle(
                "Aylık ortalama günlük toplam ışınım, kWh/m²/gün (2020–2025)",
                x=0.02, ha="left", fontsize=11, fontweight="semibold",
            )
            fig.subplots_adjust(left=0.0, right=1.0, top=0.88, bottom=0.0,
                                wspace=0.0, hspace=0.30)
        else:
            fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.04)
        save_figure(fig, save_path)


def plot_month_year_anomaly(grids: dict, save_path: Path) -> None:
    """2-D companion to the 3-D surface: the interannual signal the surface hides.

    The surface's relief is ~95% the seasonal curve extruded six times (seasonal range
    ~2.6 kWh vs interannual SD ~0.2 kWh); subtracting each month's six-year mean is what
    makes the year axis readable.
    """
    plt = _plt()
    import seaborn as sns

    anomalies = {c: g.sub(g.mean(axis=0), axis=1) for c, g in grids.items()}
    vmax = max(float(np.abs(a.to_numpy()).max()) for a in anomalies.values())
    vmax = float(np.ceil(vmax * 10) / 10)
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 3.6),
                                 sharex=False, sharey=False)
        for ax, c in zip(flat[:5], CITIES):
            sns.heatmap(
                anomalies[c], ax=ax, cmap=diverging_cmap(), vmin=-vmax, vmax=vmax, center=0,
                linewidths=0.5, linecolor="white", cbar=False, square=False,
                xticklabels=[str(m) for m in anomalies[c].columns],
            )
            ax.set_title(c, fontsize=10)
            ax.set_xlabel("Ay", fontsize=9)
            ax.set_ylabel("")
            ax.tick_params(length=0, labelsize=8)
            plt.setp(ax.get_yticklabels(), rotation=0)
            plt.setp(ax.get_xticklabels(), rotation=0)
        mappable = flat[0].collections[0]
        cbar = fig.colorbar(mappable, ax=flat[5], fraction=0.5, shrink=0.9, pad=0.0)
        cbar.set_label("Anomali (kWh/m²/gün)", fontsize=9)
        cbar.ax.tick_params(labelsize=8)
        fig.suptitle(
            "Aylık ışınım anomalisi: o ayın 6 yıllık ortalamasından sapma",
            x=0.02, ha="left", fontsize=11, fontweight="semibold",
        )
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        save_figure(fig, save_path)


def plot_seasonal_diurnal_profile(df: pd.DataFrame, save_path: Path) -> None:
    """Mean irradiance by local-solar hour, one line per season, over ALL 24 hours.

    The daylight filter is deliberately NOT applied: night zeros are physical information
    here, and filtering them would stop the curve rising from and returning to zero.
    IQR bands are drawn for Kış and Yaz only -- four overlapping bands turn to mud.
    """
    plt = _plt()

    work = add_season(df)
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 4.4))
        for ax, city in zip(flat[:5], CITIES):
            g = work[work["city"] == city]
            for season in ("Kış", "Yaz"):  # bands first, underneath the lines
                s = g[g["season"] == season].groupby("HR", observed=True)[TARGET_COLUMN]
                ax.fill_between(
                    s.mean().index + 0.5, s.quantile(0.25), s.quantile(0.75),
                    color=SEASON_COLORS[season], alpha=0.12, linewidth=0,
                )
            for season in SEASONS_TR:
                m = g[g["season"] == season].groupby("HR", observed=True)[TARGET_COLUMN].mean()
                ax.plot(
                    m.index + 0.5, m.to_numpy(), color=SEASON_COLORS[season],
                    linestyle=SEASON_LINESTYLES[season], linewidth=SEASON_LINEWIDTHS[season],
                    label=season,
                )
            ax.set_title(city)
            ax.set_xlim(0, 24)
            ax.set_xticks([0, 6, 12, 18, 24])
            grid_y_only(ax)
        _finish_city_panels(plt, fig, flat, "Yerel saat (LST)", "Ortalama ışınım (W/m²)")
        handles, labels = flat[0].get_legend_handles_labels()
        flat[5].legend(handles, labels, loc="center", title="Mevsim", frameon=False)
        fig.suptitle(
            "Mevsimlere göre ortalama günlük ışınım profili (bant: günler arası IQR)",
            x=0.03, ha="left", fontsize=11, fontweight="semibold",
        )
        fig.tight_layout(rect=(0.03, 0, 1, 0.94))
        save_figure(fig, save_path)


def plot_seasonal_dayofyear(daily: pd.DataFrame, save_path: Path) -> None:
    """Daily total against day-of-year, with season bands and a wrapped 7-day climatology."""
    plt = _plt()

    work = daily.copy()
    work["doy"] = align_day_of_year(work["date"])
    work = work.dropna(subset=["doy"])
    work["doy"] = work["doy"].astype(int)

    # Season band edges on the aligned (non-leap) day-of-year axis.
    ref = pd.date_range("2021-01-01", "2021-12-31", freq="D")
    band_of_doy = pd.Series(
        [MONTH_TO_SEASON_TR[d.month] for d in ref], index=ref.dayofyear
    )
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 4.4))
        for ax, city in zip(flat[:5], CITIES):
            g = work[work["city"] == city]
            for season in SEASONS_TR:
                days = band_of_doy[band_of_doy == season].index.to_numpy()
                # Kış wraps the year end, so shade its contiguous runs separately.
                for run in np.split(days, np.where(np.diff(days) > 1)[0] + 1):
                    ax.axvspan(
                        run.min() - 0.5, run.max() + 0.5,
                        color=SEASON_COLORS[season], alpha=0.11, linewidth=0,
                    )
            ax.scatter(
                g["doy"], g["daily_kwh"], s=3, alpha=0.15, color=INK_SECONDARY,
                linewidths=0, rasterized=True,
            )
            clim = g.groupby("doy", observed=True)["daily_kwh"].mean().reindex(range(1, 366))
            tiled = pd.concat([clim, clim, clim]).rolling(7, center=True, min_periods=1).mean()
            smooth = tiled.iloc[365:730]
            ax.plot(range(1, 366), smooth.to_numpy(), color="#7a2d0f", linewidth=1.6)
            ax.set_title(city)
            ax.set_xlim(1, 365)
            ax.set_xticks([1, 91, 182, 274, 365])
            grid_y_only(ax)
        _finish_city_panels(plt, fig, flat, "Yılın günü", "Günlük toplam (kWh/m²)")
        handles = [
            plt.Line2D([], [], color=SEASON_COLORS[s], alpha=0.5, linewidth=8, label=s)
            for s in SEASONS_TR
        ]
        handles.append(plt.Line2D([], [], color="#7a2d0f", linewidth=1.6,
                                  label="7 günlük ortalama"))
        flat[5].legend(handles=handles, loc="center", title="Mevsim", frameon=False)
        fig.suptitle(
            "Yıl içinde günlük toplam ışınım (tüm yıllar, artık gün hizalı)",
            x=0.03, ha="left", fontsize=11, fontweight="semibold",
        )
        fig.tight_layout(rect=(0.03, 0, 1, 0.94))
        save_figure(fig, save_path)
