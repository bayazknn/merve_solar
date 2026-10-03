"""Descriptive statistics and paper figures for the dataset itself (config-independent).

Read-only over outputs/processed/base_features.parquet; nothing here touches an experiment,
the ledger, or ExperimentConfig. Driven by scripts/02_descriptive_analysis.py.

Three data-handling decisions drive most of this module; the reasoning is in
outputs/eda/README.md and repeated briefly at each function:

1. The hourly subset every descriptive statistic is computed on is `target > 0`
   (positive-irradiance hours), not the geometric daylight mask. This is a descriptive choice
   made for the EDA only: modelling and evaluation keep the geometric daylight mask
   (solar_elevation > 0, see solar.py), which does not condition on the answer. The two
   subsets differ by ~2% of rows; see positive_mask() and filter_audit_table().
2. Anything month-to-month is computed on DAILY TOTALS, not on hourly values. A box of
   positive-hourly values is ~91% solar geometry, and it makes winter look *less* variable
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
    AXIS_LABELS,
    AXIS_SHORT,
    DAILY_IRRADIATION_LABEL,
    FULL_WIDTH_IN,
    HOUR_LST_LABEL,
    INK_SECONDARY,
    MONTH_ABBR,
    MONTH_INITIAL,
    MONTH_TO_SEASON,
    PAPER_RC,
    SEASON_COLORS,
    SEASON_LINESTYLES,
    SEASON_LINEWIDTHS,
    SEASONS,
    VARIABLE_LABELS,
    diverging_cmap,
    grid_y_only,
    style_colorbar,
    radiation_cmap,
    save_figure,
    white_3d_panes,
)

POOLED_LABEL = "All"
SURFACE_YEARS = (2020, 2025)  # complete calendar years only (2019 and 2026 are partial)
CALM_WIND_MIN = 1.0  # m/s; direction of near-calm hours is noise


# ---------------------------------------------------------------------------------------
# clearness index (descriptive use only)
# ---------------------------------------------------------------------------------------
def attach_clearness(df: pd.DataFrame) -> pd.DataFrame:
    """Add the clearness index kt = GHI / (I0 cos theta_z).

    This is the solar literature's standard definition, with the TOP-OF-ATMOSPHERE irradiance
    in the denominator. It replaced `ALLSKY / CLRSKY` when the 14-Sep-2026 export dropped
    NASA POWER's clear-sky column; solar.py explains why that is an upgrade rather than a
    fallback. The scale is different and the two must never be mixed: a cloudless hour reads
    kt ~ 0.75-0.80 here where the clear-sky index read ~1.0.

    kt is defined only where the sun is up; elsewhere it is NaN rather than 0/0.
    """
    if "toa_horizontal" not in df.columns:
        raise ValueError(
            "frame has no 'toa_horizontal' column -- rebuild base_features.parquet with "
            "scripts/01_prepare_base_data.py."
        )
    out = df.copy()
    toa = out["toa_horizontal"]
    out["kt"] = np.where(toa > 0, out[TARGET_COLUMN] / toa.where(toa > 0, 1.0), np.nan)
    return out


# ---------------------------------------------------------------------------------------
# data helpers
# ---------------------------------------------------------------------------------------
def positive_mask(df: pd.DataFrame) -> pd.Series:
    """Positive-irradiance hours: `target > 0`. The subset every descriptive EDA output uses.

    NASA POWER marks missing values with -999, which is < 0, so `target > 0` already excludes
    the sentinel; data.py raises before a sentinel can reach this module, and the trimmed
    record holds none. Night hours are exact zeros except for 3,030 twilight hours with
    0.80-11.68 W/m^2 while the sun is up to 2.4 degrees below the horizon.

    Descriptive use only. Evaluation uses the geometric `solar_elevation > 0` mask (solar.py)
    because a `target > 0` subset picks a metric's denominator with the answer, and cannot be
    formed 24 h ahead. The two differ only by those twilight hours and, on this record, no
    daylight hour reads zero.
    """
    return (df[TARGET_COLUMN] > 0).rename("positive")


def filter_audit_table(df: pd.DataFrame) -> pd.DataFrame:
    """What the `target > 0` filter removes, per province and pooled, and how it relates to
    the geometric daylight mask the modelling side uses.

    `removed_*` are the rows the descriptive EDA drops; the `twilight_*` columns are the rows
    that `target > 0` keeps but the geometric mask would drop (sun at or below the horizon,
    target still positive). `geometric_daylight_zero` counts the opposite disagreement.
    """
    pos = positive_mask(df)
    geo = df["solar_elevation"] > 0
    rows = []
    for city, g in list(df.groupby("city", observed=True)) + [(POOLED_LABEL, df)]:
        p, d = pos.loc[g.index], geo.loc[g.index]
        tw = g.loc[p & ~d, TARGET_COLUMN]
        rows.append(
            {
                "city": city,
                "n_rows": int(len(g)),
                "n_sentinel_999": int((g[TARGET_COLUMN] == -999).sum()),
                "n_negative": int((g[TARGET_COLUMN] < 0).sum()),
                "n_zero": int((g[TARGET_COLUMN] == 0).sum()),
                "n_removed": int((~p).sum()),
                "removed_share": float((~p).mean()),
                "n_kept": int(p.sum()),
                "kept_share": float(p.mean()),
                "n_geometric_daylight": int(d.sum()),
                "geometric_daylight_zero": int((d & ~p).sum()),
                "n_twilight_kept": int(len(tw)),
                "twilight_share_of_kept": float(len(tw) / p.sum()),
                "twilight_mean": float(tw.mean()),
                "twilight_max": float(tw.max()),
            }
        )
    return pd.DataFrame(rows)


def require_positive(df: pd.DataFrame, what: str) -> pd.DataFrame:
    """Refuse a frame holding any row with `target <= 0` (zeros, negatives, the -999 sentinel).

    Every descriptive EDA table and figure must be computed on the SAME rows, the `target > 0`
    subset. The functions that take the already-filtered frame call this so that a caller
    passing the full record fails loudly instead of silently mixing populations. The
    sequence-dependent analyses (ramps, lagged references, hourly ACF) need the full series to
    form their lags and therefore take the full frame and apply positive_mask themselves.
    """
    bad = int((~(df[TARGET_COLUMN] > 0)).sum())
    if bad:
        raise ValueError(f"{what}: {bad} rows have {TARGET_COLUMN} <= 0; pass df[positive_mask(df)]")
    return df


def add_season(df: pd.DataFrame) -> pd.DataFrame:
    """Add a meteorological-season column (Winter = Dec/Jan/Feb) as an ordered Categorical."""
    df = df.copy()
    df["season"] = pd.Categorical(
        df["MO"].map(MONTH_TO_SEASON), categories=SEASONS, ordered=True
    )
    return df


def daily_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Per (city, date) daily insolation in kWh/m^2/day.

    Summed over all 24 hours: night contributes exactly 0, so this is invariant to the
    positive-hours filter. kWh (not Wh) because 4.9 reads and 4,944 does not, and five-digit
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
    out["ym_label"] = [f"{MONTH_ABBR[p.month]} {str(p.year)[2:]}" for p in out["ym"]]
    labels = [f"{MONTH_ABBR[p.month]} {str(p.year)[2:]}" for p in months]
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
DESCRIPTIVE_STATISTICS = {
    "N": lambda s: int(s.size),
    "Mean": lambda s: s.mean(),
    "SD": lambda s: s.std(),
    "Min": lambda s: s.min(),
    "Q1": lambda s: s.quantile(0.25),
    "Median": lambda s: s.median(),
    "Q3": lambda s: s.quantile(0.75),
    "Max": lambda s: s.max(),
}


def descriptive_table(df: pd.DataFrame) -> pd.DataFrame:
    """Descriptive statistics with one row per (city, statistic) and one column per variable.

    Cities (plus the pooled "All" row block) run down the rows, the statistic sits beside the
    city, and each variable is a column headed by its raw NASA POWER code and unit -- the
    orientation of a manuscript table, where a reader compares provinces within a variable.
    Wind direction is excluded (circular; see circular_wind_table).
    """
    require_positive(df, "descriptive_table")
    rows = []
    groups = [(city, g) for city, g in df.groupby("city", observed=True)] + [(POOLED_LABEL, df)]
    for city, g in groups:
        for stat, fn in DESCRIPTIVE_STATISTICS.items():
            row = {"city": city, "statistic": stat}
            for var in RAW_METEO_COLUMNS:
                row[VARIABLE_LABELS.get(var, var)] = fn(g[var])
            rows.append(row)
    return pd.DataFrame(rows)


def temporal_coverage_table(df: pd.DataFrame) -> pd.DataFrame:
    """Describe the TIME features on their own scale rather than as sin/cos encodings.

    Computed on the `target > 0` rows only, so `n_hours` counts positive hours, not the full
    record (the record-level coverage and the rows removed are in filter_audit_table).
    mean(hour_sin) ~ 0 and std ~ 0.707 for every city by construction, so those rows would
    carry no information in a paper table. What a Dataset section actually needs is span,
    counts, positive hours per day and how the target moves with season.
    """
    require_positive(df, "temporal_coverage_table")
    work = add_season(df.assign(_date=df["datetime"].dt.normalize()))
    rows = []
    for city, g in work.groupby("city", observed=True):
        for season in [POOLED_LABEL] + SEASONS:
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
                    "mean_positive_hours_per_day": len(sub) / n_days,
                    "target_mean": sub[TARGET_COLUMN].mean(),
                    "daily_total_mean_kwh": sub.groupby("_date", observed=True)[TARGET_COLUMN]
                    .sum()
                    .div(1000.0)
                    .mean(),
                }
            )
    return pd.DataFrame(rows)


def target_by_hour_table(df: pd.DataFrame) -> pd.DataFrame:
    """Target distribution by local-solar hour, per city (the diurnal figure's data)."""
    work = add_season(require_positive(df, "target_by_hour_table"))
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
    require_positive(df, "time_explained_variance_table")
    for scope, sub in (("positive", df),):
        for city, g in list(sub.groupby("city", observed=True)) + [(POOLED_LABEL, sub)]:
            y = g[TARGET_COLUMN].to_numpy()
            doy = g["datetime"].dt.dayofyear.to_numpy()
            rows.append(
                {
                    "city": city, "scope": scope, "factor": "hour (LST)",
                    "eta_squared": eta_squared(y, g["HR"].to_numpy()),
                    "harmonic_r2": harmonic_r2(y, 2 * np.pi * g["HR"].to_numpy() / 24.0),
                }
            )
            rows.append(
                {
                    "city": city, "scope": scope, "factor": "day of year",
                    "eta_squared": eta_squared(y, doy),
                    "harmonic_r2": harmonic_r2(y, 2 * np.pi * doy / 365.25),
                }
            )
    return pd.DataFrame(rows)


def circular_wind_table(df: pd.DataFrame) -> pd.DataFrame:
    """Speed-weighted circular statistics for wind direction, on the `target > 0` rows.

    Uses the sin/cos columns already in the parquet. Near-calm hours are excluded because
    their direction is noise.
    """
    require_positive(df, "circular_wind_table")
    rows = []
    for col in CIRCULAR_COLUMNS:
        # Direction is weighted by the speed measured at the SAME height; a mismatch would
        # silently weight one level's directions by another's gusts.
        speed_col = col.replace("WD", "WS")
        if speed_col not in df.columns:
            raise ValueError(f"no wind-speed column {speed_col!r} to pair with {col!r}")
        sub_all = df[df[speed_col] > CALM_WIND_MIN]
        groups = [(c, g) for c, g in sub_all.groupby("city", observed=True)]
        groups.append((POOLED_LABEL, sub_all))
        for city, g in groups:
            stats = circular_stats(g[f"{col}_sin"], g[f"{col}_cos"], weights=g[speed_col])
            rows.append(
                {
                    "city": city,
                    "variable": col,
                    "variable_label": VARIABLE_LABELS.get(col, col),
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


def correlation_tables(df_pos: pd.DataFrame) -> dict:
    """Pearson and Spearman matrices per city and pooled, plus target correlations.

    Spearman is included for monotone-but-nonlinear relationships, not because of heavy
    tails (on positive rows the target's skew is only 0.44). `partial_r_within_hour` is the
    correlation after removing the (city, month, hour) cell mean, which separates the
    weather signal from the shared solar-geometry driver.
    """
    cols = RAW_METEO_COLUMNS
    out = {"pearson": {}, "spearman": {}}
    require_positive(df_pos, "correlation_tables")
    groups = [(c, g) for c, g in df_pos.groupby("city", observed=True)]
    groups.append((POOLED_LABEL, df_pos))
    for city, g in groups:
        out["pearson"][city] = g[cols].corr(method="pearson")
        out["spearman"][city] = g[cols].corr(method="spearman")

    resid = _within_cell_residuals(df_pos, cols).assign(city=df_pos["city"].values)
    target_rows = []
    for var in cols:
        if var == TARGET_COLUMN:
            continue
        row = {"variable": var, "variable_label": VARIABLE_LABELS.get(var, var)}
        for city in CITIES + [POOLED_LABEL]:
            row[f"pearson_{city}"] = out["pearson"][city].loc[TARGET_COLUMN, var]
        row["partial_r_within_hour_pooled"] = resid[TARGET_COLUMN].corr(resid[var])
        for city in CITIES:
            s = resid[resid["city"] == city]
            row[f"partial_r_within_hour_{city}"] = s[TARGET_COLUMN].corr(s[var])
        target_rows.append(row)
    out["target"] = pd.DataFrame(target_rows)
    return out


COLLINEAR_COLUMNS = ["variable_a", "variable_b", "pearson_r"]


def collinear_pairs(corr: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
    """Feature pairs with |r| > threshold.

    An EMPTY result is a finding, not an error, and since the V2 export that is what this
    returns: WS2M-WS10M (r = 0.987) was the only pair above the threshold and the 10 m wind is
    no longer in the file. The frame is therefore built with an explicit schema -- an empty
    DataFrame has no columns to sort by, and the caller writes a CSV that has to keep its
    header either way.

    Note what an empty table does NOT mean: T2MDEW is still reproducible from T2M and RH2M at
    r = 0.99919, and no pairwise correlation can see that, because it is a two-variable
    function. Pairwise collinearity is a floor on redundancy, never a ceiling.
    """
    rows = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            if abs(r) > threshold:
                rows.append({"variable_a": a, "variable_b": b, "pearson_r": r})
    out = pd.DataFrame(rows, columns=COLLINEAR_COLUMNS)
    if out.empty:
        return out
    return out.sort_values("pearson_r", key=abs, ascending=False)


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
    work = add_season(require_positive(df, "seasonal_target_stats"))
    daily_s = add_season(daily.assign(MO=daily["MO"]))
    rows = []
    for city in CITIES:
        for season in SEASONS:
            h = work[(work["city"] == city) & (work["season"] == season)]
            d = daily_s[(daily_s["city"] == city) & (daily_s["season"] == season)]
            rows.append(
                {
                    "city": city, "season": season,
                    "n_hours": len(h), "n_days": len(d),
                    "hourly_mean": h[TARGET_COLUMN].mean(),
                    "hourly_max": h[TARGET_COLUMN].max(),
                    "daily_kwh_mean": d["daily_kwh"].mean(),
                    "daily_kwh_std": d["daily_kwh"].std(),
                    "daily_kwh_cv": d["daily_kwh"].std() / d["daily_kwh"].mean(),
                    "daily_kwh_q25": d["daily_kwh"].quantile(0.25),
                    "daily_kwh_q75": d["daily_kwh"].quantile(0.75),
                }
            )
    return pd.DataFrame(rows)


def clearness_table(daily: pd.DataFrame) -> pd.DataFrame:
    """Empirical clearness ratio: a day's total over the 95th percentile for that day-of-year.

    Not a clear-sky model -- the envelope is the observed 95th percentile of the same
    day-of-year across all years, which removes the seasonal geometry and leaves a
    dimensionless "how much of an achievable day did this day deliver" ratio. It is what
    makes the cities comparable on cloudiness rather than on latitude.
    """
    work = daily.copy()
    work["doy"] = align_day_of_year(work["date"])
    work = work.dropna(subset=["doy"])
    envelope = work.groupby(["city", "doy"], observed=True)["daily_kwh"].transform(
        lambda s: s.quantile(0.95)
    )
    work["clearness"] = work["daily_kwh"] / envelope
    work = add_season(work.assign(MO=work["date"].dt.month))
    rows = []
    for city, g in work.groupby("city", observed=True):
        for season in [POOLED_LABEL] + SEASONS:
            sub = g if season == POOLED_LABEL else g[g["season"] == season]
            rows.append(
                {
                    "city": city,
                    "season": season,
                    "n_days": int(len(sub)),
                    "clearness_mean": sub["clearness"].mean(),
                    "clearness_median": sub["clearness"].median(),
                    "clear_day_share": (sub["clearness"] > 0.9).mean(),
                    "overcast_day_share": (sub["clearness"] < 0.5).mean(),
                    "daily_kwh_mean": sub["daily_kwh"].mean(),
                    "daily_kwh_cv": sub["daily_kwh"].std() / sub["daily_kwh"].mean(),
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


def _city_panels(plt, height: float, sharex=True, sharey=True):
    """2x3 grid at full text width: 5 city panels + a 6th cell for the legend or colourbar.

    Constrained layout rather than tight_layout: it places the suptitle and the shared y label
    itself, so there is no hand-tuned `rect` leaving a band of white under the title.
    """
    fig, axes = plt.subplots(
        2, 3, figsize=(FULL_WIDTH_IN, height), sharex=sharex, sharey=sharey,
        layout="constrained",
    )
    flat = axes.ravel()
    flat[5].axis("off")
    return fig, flat


def _finish_city_panels(fig, flat, xlabel: str, ylabel: str, title: str) -> None:
    """x tick labels on EVERY panel, one x title per column, one shared y title.

    `sharex` hides the tick labels of the top row, which left Ankara and Antalya without any
    and Konya (no neighbour below it) with labels re-enabled but unformatted. Every panel now
    carries its own tick labels, so a reader never has to look down a column to read an axis.
    The x title goes only under the bottom panel of each column, which is where it is read.
    """
    for ax in flat[:5]:
        ax.tick_params(axis="x", labelbottom=True)
        ax.set_xlabel("")
        ax.set_ylabel("")
    for ax in (flat[2], flat[3], flat[4]):
        ax.set_xlabel(xlabel)
        # sharex hides the axis title of every non-bottom-row panel, not only its ticks.
        ax.xaxis.label.set_visible(True)
    fig.supylabel(ylabel)
    fig.suptitle(title, x=0.01, ha="left")


def _month_initial_ticks(ax, positions) -> None:
    ax.set_xticks(list(positions))
    ax.set_xticklabels([MONTH_INITIAL[m] for m in range(1, 13)], rotation=0)


# Twelve three-letter month names fit unrotated under a ~1.9 in panel only at this size.
MONTH_ABBR_TICK_SIZE = 5.5


def _month_abbr_ticks(ax, months) -> None:
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([MONTH_ABBR[m] for m in months], rotation=0,
                       fontsize=MONTH_ABBR_TICK_SIZE)
    ax.tick_params(axis="x", length=0, pad=2)


def _box_cmap():
    """plasma, stopped short of its palest yellow, which vanishes against a white page."""
    import matplotlib as mpl
    from matplotlib.colors import ListedColormap

    return ListedColormap(mpl.colormaps["plasma"](np.linspace(0.0, 0.88, 256)))


def _median_norm(data: pd.DataFrame, x: str):
    """One colour scale for every panel of a figure, from the largest monthly median."""
    from matplotlib.colors import Normalize

    top = float(data.groupby(["city", x], observed=True)["daily_kwh"].median().max())
    return Normalize(vmin=0.0, vmax=float(np.ceil(top)))


def _plasma_boxes(ax, data: pd.DataFrame, x: str, order, norm) -> None:
    """Box plot whose fill encodes each month's median daily irradiation on plasma.

    Colour is tied to the median rather than to the month: plasma is a sequential map, and
    colouring by month would put January and December at opposite ends of it although they
    are climatologically alike. With one norm shared across the panels, a cloudier province
    reads as darker at a glance. The median line is white, which stays visible from the dark
    end of the map to the orange where it is cut off. `dodge=False` because hue repeats x:
    seaborn would otherwise reserve a slot per hue level and draw hairline boxes.
    """
    import seaborn as sns

    cmap = _box_cmap()
    medians = data.groupby(x, observed=True)["daily_kwh"].median()
    palette = {k: cmap(norm(medians[k])) for k in order}
    sns.boxplot(
        data=data, x=x, y="daily_kwh", order=order, hue=x, hue_order=order,
        palette=palette, legend=False, dodge=False, ax=ax, width=0.7, saturation=1.0,
        linewidth=0.5, linecolor=INK_SECONDARY, fliersize=1.0,
        boxprops={"alpha": 0.9},
        medianprops={"color": "white", "linewidth": 1.4},
        flierprops={"marker": "o", "markerfacecolor": INK_SECONDARY,
                    "markeredgewidth": 0, "alpha": 0.5},
    )


def _median_colorbar(fig, cax_host, norm, orientation="horizontal",
                     label="Monthly median of daily\nsolar irradiation (kWh/m²)", **kwargs):
    import matplotlib as mpl

    cbar = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=_box_cmap()),
                        cax=cax_host, orientation=orientation, **kwargs)
    cbar.set_label(label)
    style_colorbar(cbar)
    return cbar


def plot_correlation_heatmap(corr: pd.DataFrame, title: str, save_path: Path) -> None:
    plt = _plt()
    import seaborn as sns

    labels = [AXIS_SHORT.get(c, c) for c in corr.columns]
    with plt.rc_context(PAPER_RC):
        fig, ax = plt.subplots(figsize=(FULL_WIDTH_IN * 0.65, 3.4), layout="constrained")
        sns.heatmap(
            corr, ax=ax, cmap=diverging_cmap(), vmin=-1, vmax=1, center=0,
            annot=True, fmt=".2f", annot_kws={"size": 6.5}, square=True,
            linewidths=0.6, linecolor="white",
            xticklabels=labels, yticklabels=labels,
            cbar_kws={"shrink": 0.8, "label": "Pearson correlation coefficient"},
        )
        ax.set_title(title)
        ax.tick_params(length=0)
        plt.setp(ax.get_xticklabels(), rotation=40, ha="right", rotation_mode="anchor")
        style_colorbar(ax.collections[0].colorbar)
        save_figure(fig, save_path)


def plot_target_correlation_panel(target_df: pd.DataFrame, save_path: Path) -> None:
    plt = _plt()
    import seaborn as sns

    mat = target_df.set_index("variable")[[f"pearson_{c}" for c in CITIES]]
    mat.columns = CITIES
    mat.index = [AXIS_SHORT.get(v, v) for v in mat.index]
    with plt.rc_context(PAPER_RC):
        fig, ax = plt.subplots(figsize=(FULL_WIDTH_IN * 0.65, 2.6), layout="constrained")
        sns.heatmap(
            mat, ax=ax, cmap=diverging_cmap(), vmin=-1, vmax=1, center=0,
            annot=True, fmt=".2f", annot_kws={"size": 7},
            linewidths=0.6, linecolor="white",
            cbar_kws={"shrink": 0.9, "label": "Pearson correlation coefficient"},
        )
        ax.set_title("Correlation of each variable with irradiance (hours with target > 0)")
        style_colorbar(ax.collections[0].colorbar)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(length=0)
        save_figure(fig, save_path)


def plot_scatter_vs_target(df_pos: pd.DataFrame, city: str, save_path: Path) -> None:
    """Each meteorological variable against irradiance, with a binned-median trend."""
    plt = _plt()

    variables = [c for c in RAW_METEO_COLUMNS if c != TARGET_COLUMN]
    g = require_positive(df_pos, "plot_scatter_vs_target")
    g = g[g["city"] == city]
    # Choose the column count that leaves the fewest empty cells: the export's parameter list
    # has already changed twice (8 raw variables -> 7 -> 6) and a fixed grid leaves a ragged
    # bottom row every time.
    ncols = min((4, 3), key=lambda n: (-(-len(variables) // n) * n - len(variables), n))
    nrows = -(-len(variables) // ncols)
    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(nrows, ncols, figsize=(FULL_WIDTH_IN, 1.85 * nrows + 0.3),
                                 sharey=True, layout="constrained")
        for ax in axes.ravel()[len(variables):]:
            ax.axis("off")
        for ax, var in zip(axes.ravel(), variables):
            ax.scatter(
                g[var], g[TARGET_COLUMN], s=1.5, alpha=0.10, color=ACCENT,
                linewidths=0, rasterized=True,
            )
            bins = pd.qcut(g[var], 20, duplicates="drop")
            trend = g.groupby(bins, observed=True)[TARGET_COLUMN].median()
            centers = [iv.mid for iv in trend.index]
            ax.plot(centers, trend.to_numpy(), color="#7a2d0f", linewidth=1.3)
            lo, hi = g[var].quantile([0.001, 0.999])
            if hi > lo:
                pad = (hi - lo) * 0.03
                ax.set_xlim(lo - pad, hi + pad)
            ax.set_xlabel(AXIS_LABELS.get(var, var))
            grid_y_only(ax)
        fig.supylabel(AXIS_LABELS[TARGET_COLUMN])
        fig.suptitle(f"{city}: meteorological variables against irradiance (hours with target > 0; "
                     "line: binned median)", x=0.01, ha="left")
        save_figure(fig, save_path)


def plot_monthly_boxplot(daily_12m: pd.DataFrame, city, save_path: Path) -> None:
    """Last 12 months of DAILY TOTALS (~30 days per box).

    Deliberately not hourly values: a box of positive-hourly irradiance is ~91% solar
    geometry and makes winter look less variable than summer, which is backwards.
    """
    plt = _plt()

    periods = list(daily_12m["ym"].cat.categories)
    order = list(daily_12m["ym_label"].cat.categories)
    span = (f"{MONTH_ABBR[periods[0].month]} {periods[0].year} – "
            f"{MONTH_ABBR[periods[-1].month]} {periods[-1].year}")
    with plt.rc_context(PAPER_RC):
        if city is None:
            fig, flat = _city_panels(plt, 3.9)
            panels = [(flat[i], c) for i, c in enumerate(CITIES)]
        else:
            fig, ax = plt.subplots(figsize=(FULL_WIDTH_IN * 0.7, 2.6), layout="constrained")
            panels = [(ax, city)]
        norm = _median_norm(daily_12m, "ym_label")
        for ax, c in panels:
            _plasma_boxes(ax, daily_12m[daily_12m["city"] == c], "ym_label", order, norm)
            ax.set_title(c)
            _month_abbr_ticks(ax, [p.month for p in periods])
            ax.set_xlabel("")
            ax.set_ylabel(DAILY_IRRADIATION_LABEL)
            grid_y_only(ax)
        if city is None:
            _median_colorbar(fig, flat[5].inset_axes([0.1, 0.45, 0.8, 0.09]), norm)
            _finish_city_panels(fig, flat, "", DAILY_IRRADIATION_LABEL,
                                f"Daily solar irradiation over the last 12 months ({span})")
        else:
            _median_colorbar(fig, None, norm, orientation="vertical", ax=ax,
                             fraction=0.04, pad=0.02)
            ax.set_title(f"{city}: daily solar irradiation over the last 12 months ({span})")
        save_figure(fig, save_path)


SURFACE_MONTH_TICKS = (1, 3, 5, 7, 9, 11)  # every other month: twelve collide on the slant


def plot_month_year_surface_3d(grids: dict, city, save_path: Path, zlim=None) -> None:
    """x = month, depth = year, height = monthly mean of daily irradiation.

    Styled like the monthly box plots: height is also encoded on the cut-off plasma map with
    one scale for every province, a colour bar replaces the axis titles, and months are
    three-letter names. The all-province figure is two columns by three rows, so each surface
    gets half the page width; the sixth cell holds the colour bar.
    """
    plt = _plt()
    from matplotlib.colors import Normalize
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the 3-D projection)

    if zlim is None:
        top = max(float(g.to_numpy().max()) for g in grids.values())
        zlim = (0.0, float(np.ceil(top)))
    norm = Normalize(vmin=zlim[0], vmax=zlim[1])
    cmap = _box_cmap()
    label = "Monthly mean of daily\nsolar irradiation (kWh/m²)"
    with plt.rc_context(PAPER_RC):
        if city is None:
            fig = plt.figure(figsize=(FULL_WIDTH_IN, 7.7))
            items = [(fig.add_subplot(3, 2, i + 1, projection="3d"), c)
                     for i, c in enumerate(CITIES)]
        else:
            fig = plt.figure(figsize=(FULL_WIDTH_IN * 0.75, 3.3))
            items = [(fig.add_subplot(111, projection="3d"), city)]
        for ax, c in items:
            grid = grids[c]
            months = np.array(grid.columns, dtype=float)
            years = np.array(grid.index, dtype=float)
            mm, yy = np.meshgrid(months, years)
            ax.plot_surface(
                mm, yy, grid.to_numpy(), cmap=cmap, norm=norm, rstride=1, cstride=1,
                edgecolor="white", linewidth=0.3, antialiased=True, shade=False,
            )
            ax.set_xticks(list(SURFACE_MONTH_TICKS))
            ax.set_xticklabels([MONTH_ABBR[m] for m in SURFACE_MONTH_TICKS],
                               fontsize=MONTH_ABBR_TICK_SIZE)
            year_ticks = list(range(int(years.min()), int(years.max()) + 1, 2))
            ax.set_yticks(year_ticks)
            ax.set_yticklabels([str(y) for y in year_ticks], fontsize=MONTH_ABBR_TICK_SIZE)
            ax.tick_params(axis="z", labelsize=MONTH_ABBR_TICK_SIZE, pad=0)
            ax.tick_params(axis="x", pad=-4)
            ax.tick_params(axis="y", pad=-3)
            ax.set_zlim(*zlim)
            ax.view_init(elev=26, azim=-58)
            ax.set_box_aspect(None, zoom=1.1 if city is None else 0.95)
            if city is None:  # a single-city figure names the city in its suptitle
                # Left-aligned like every 2-D panel title, and pulled down onto the cube: a
                # 3-D axes' box is much taller than the cube drawn in it, so a title at the
                # default height floats well above its own chart.
                ax.set_title(c, loc="left", x=0.08, y=0.86)
            white_3d_panes(ax)
        # tight_layout cannot fit 3-D axis decorations; set the margins explicitly instead.
        if city is None:
            cell = fig.add_subplot(3, 2, 6)
            cell.axis("off")
            _median_colorbar(fig, cell.inset_axes([0.15, 0.5, 0.7, 0.07]), norm, label=label)
            fig.suptitle("Monthly mean of daily solar irradiation, 2020–2025",
                         x=0.01, ha="left")
            fig.subplots_adjust(left=-0.02, right=0.97, top=0.93, bottom=0.01,
                                wspace=-0.05, hspace=0.08)
        else:
            cax = fig.add_axes([0.86, 0.22, 0.025, 0.56])
            _median_colorbar(fig, cax, norm, orientation="vertical", label=label)
            fig.suptitle(f"{city}: monthly mean of daily solar irradiation, 2020–2025",
                         x=0.01, ha="left")
            fig.subplots_adjust(left=0.0, right=0.84, top=0.93, bottom=0.02)
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
        fig, flat = _city_panels(plt, 3.3, sharex=False, sharey=False)
        for ax, c in zip(flat[:5], CITIES):
            sns.heatmap(
                anomalies[c], ax=ax, cmap=diverging_cmap(), vmin=-vmax, vmax=vmax, center=0,
                linewidths=0.5, linecolor="white", cbar=False, square=False,
                xticklabels=[MONTH_INITIAL[m] for m in anomalies[c].columns],
            )
            ax.set_title(c)
            ax.tick_params(length=0)
            plt.setp(ax.get_yticklabels(), rotation=0)
            plt.setp(ax.get_xticklabels(), rotation=0)
        # Horizontal colourbar inside the spare sixth cell, so it takes no width from the maps.
        cax = flat[5].inset_axes([0.1, 0.45, 0.8, 0.09])
        cbar = fig.colorbar(flat[0].collections[0], cax=cax, orientation="horizontal")
        cbar.set_label("Daily solar irradiation\nanomaly (kWh/m²)")
        style_colorbar(cbar)
        _finish_city_panels(fig, flat, "Month", "Year",
                            "Monthly solar irradiation anomaly: departure from that month's "
                            "2020–2025 mean")
        save_figure(fig, save_path)


def plot_seasonal_diurnal_profile(df: pd.DataFrame, save_path: Path) -> None:
    """Mean irradiance by local-solar hour, one line per season, over `target > 0` hours.

    Like every other EDA figure it uses the positive-hours subset, so each hour's mean is
    conditional on the hour being positive and the curves start and stop at the first and last
    positive hour of the season rather than at an exact zero.
    IQR bands are drawn for Winter and Summer only -- four overlapping bands turn to mud.
    """
    plt = _plt()

    work = add_season(require_positive(df, "plot_seasonal_diurnal_profile"))
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, 3.7)
        for ax, city in zip(flat[:5], CITIES):
            g = work[work["city"] == city]
            for season in ("Winter", "Summer"):  # bands first, underneath the lines
                s = g[g["season"] == season].groupby("HR", observed=True)[TARGET_COLUMN]
                ax.fill_between(
                    s.mean().index + 0.5, s.quantile(0.25), s.quantile(0.75),
                    color=SEASON_COLORS[season], alpha=0.12, linewidth=0,
                )
            for season in SEASONS:
                m = g[g["season"] == season].groupby("HR", observed=True)[TARGET_COLUMN].mean()
                ax.plot(
                    m.index + 0.5, m.to_numpy(), color=SEASON_COLORS[season],
                    linestyle=SEASON_LINESTYLES[season],
                    linewidth=SEASON_LINEWIDTHS[season] * 0.75, label=season,
                )
            ax.set_title(city)
            ax.set_xlim(0, 24)
            ax.set_xticks([0, 6, 12, 18, 24])
            grid_y_only(ax)
        _finish_city_panels(fig, flat, HOUR_LST_LABEL,
                            "Mean " + AXIS_LABELS[TARGET_COLUMN],
                            "Mean daily cycle of irradiance by season "
                            "(shaded: interquartile range across days)")
        handles, labels = flat[0].get_legend_handles_labels()
        flat[5].legend(handles, labels, loc="center", title="Season", frameon=False)
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
        [MONTH_TO_SEASON[d.month] for d in ref], index=ref.dayofyear
    )
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, 3.7)
        for ax, city in zip(flat[:5], CITIES):
            g = work[work["city"] == city]
            for season in SEASONS:
                days = band_of_doy[band_of_doy == season].index.to_numpy()
                # Winter wraps the year end, so shade its contiguous runs separately.
                for run in np.split(days, np.where(np.diff(days) > 1)[0] + 1):
                    ax.axvspan(
                        run.min() - 0.5, run.max() + 0.5,
                        color=SEASON_COLORS[season], alpha=0.11, linewidth=0,
                    )
            ax.scatter(
                g["doy"], g["daily_kwh"], s=2, alpha=0.15, color=INK_SECONDARY,
                linewidths=0, rasterized=True,
            )
            clim = g.groupby("doy", observed=True)["daily_kwh"].mean().reindex(range(1, 366))
            tiled = pd.concat([clim, clim, clim]).rolling(7, center=True, min_periods=1).mean()
            smooth = tiled.iloc[365:730]
            ax.plot(range(1, 366), smooth.to_numpy(), color="#7a2d0f", linewidth=1.3)
            ax.set_title(city)
            ax.set_xlim(1, 365)
            ax.set_xticks([1, 91, 182, 274, 365])
            grid_y_only(ax)
        _finish_city_panels(fig, flat, "Day of year", DAILY_IRRADIATION_LABEL,
                            "Daily solar irradiation through the year (all years pooled)")
        handles = [
            plt.Line2D([], [], color=SEASON_COLORS[s], alpha=0.5, linewidth=6, label=s)
            for s in SEASONS
        ]
        handles.append(plt.Line2D([], [], color="#7a2d0f", linewidth=1.3,
                                  label="7-day mean"))
        flat[5].legend(handles=handles, loc="center", title="Season", frameon=False)
        save_figure(fig, save_path)


# ---------------------------------------------------------------------------------------
# predictability analyses (added after the first EDA round)
# ---------------------------------------------------------------------------------------
TOA_MIN_FOR_KT = 20.0  # W/m^2; below this, GHI/TOA is a twilight division blow-up

# Sky-condition cut-offs on the CLEARNESS INDEX kt = GHI / (I0 cos theta_z). These are the
# literature's standard bands for this index (Liu & Jordan / Iqbal): clear above 0.65,
# overcast below 0.35, partly cloudy between. They are NOT the 0.7/0.3 pair used while the
# denominator was NASA POWER's clear-sky column -- that scale put a cloudless hour at ~1.0,
# this one puts it at ~0.75-0.80, so carrying the old numbers over silently misclassifies the
# sunniest provinces as the cloudiest.
CLEAR_KT = 0.65
OVERCAST_KT = 0.35


def clearness_index_table(df_kt: pd.DataFrame) -> pd.DataFrame:
    """Standard clearness index kt = GHI / (I0 cos theta_z), per (city, season).

    Reported both hourly (restricted to TOA > TOA_MIN_FOR_KT, since near sunrise and
    sunset the ratio is a division of two near-zero numbers) and daily (ratio of the two
    daily sums, which needs no threshold and is the quantity solar-resource papers report).
    """
    work = add_season(df_kt.assign(_date=df_kt["datetime"].dt.normalize()))
    hourly = work[(work["toa_horizontal"] > TOA_MIN_FOR_KT) & positive_mask(work)]
    daily = (
        work.groupby(["city", "_date"], observed=True)[[TARGET_COLUMN, "toa_horizontal"]]
        .sum()
        .assign(kt_daily=lambda d: d[TARGET_COLUMN] / d["toa_horizontal"])
        .reset_index()
    )
    daily["season"] = pd.Categorical(
        daily["_date"].dt.month.map(MONTH_TO_SEASON), categories=SEASONS, ordered=True
    )
    rows = []
    for city in CITIES:
        for season in [POOLED_LABEL] + SEASONS:
            h = hourly[hourly["city"] == city]
            d = daily[daily["city"] == city]
            if season != POOLED_LABEL:
                h = h[h["season"] == season]
                d = d[d["season"] == season]
            rows.append(
                {
                    "city": city,
                    "season": season,
                    "n_hours": int(len(h)),
                    "n_days": int(len(d)),
                    "kt_hourly_mean": h["kt"].mean(),
                    "kt_hourly_median": h["kt"].median(),
                    "clear_hour_share": (h["kt"] > CLEAR_KT).mean(),
                    "overcast_hour_share": (h["kt"] < OVERCAST_KT).mean(),
                    "kt_daily_mean": d["kt_daily"].mean(),
                    "kt_daily_median": d["kt_daily"].median(),
                    "kt_daily_std": d["kt_daily"].std(),
                    "clear_day_share": (d["kt_daily"] > CLEAR_KT).mean(),
                    "overcast_day_share": (d["kt_daily"] < OVERCAST_KT).mean(),
                }
            )
    return pd.DataFrame(rows)


def _acf(values: np.ndarray, max_lag: int) -> np.ndarray:
    """Sample ACF with pairwise deletion, so a NaN-gapped (night-masked) series works."""
    out = np.full(max_lag + 1, np.nan)
    out[0] = 1.0
    for lag in range(1, max_lag + 1):
        a, b = values[:-lag], values[lag:]
        ok = ~(np.isnan(a) | np.isnan(b))
        if ok.sum() > 30:
            sa, sb = a[ok], b[ok]
            if sa.std() > 0 and sb.std() > 0:
                out[lag] = np.corrcoef(sa, sb)[0, 1]
    return out


def _pacf_from_acf(acf: np.ndarray) -> np.ndarray:
    """Durbin-Levinson recursion. Stops early if the (pairwise) ACF is not consistent."""
    max_lag = len(acf) - 1
    pacf = np.full(max_lag + 1, np.nan)
    pacf[0] = 1.0
    phi = np.zeros((max_lag + 1, max_lag + 1))
    if max_lag >= 1 and not np.isnan(acf[1]):
        phi[1, 1] = acf[1]
        pacf[1] = acf[1]
    for k in range(2, max_lag + 1):
        if np.isnan(acf[k]) or np.isnan(pacf[k - 1]):
            break
        num = acf[k] - sum(phi[k - 1, j] * acf[k - j] for j in range(1, k))
        den = 1.0 - sum(phi[k - 1, j] * acf[j] for j in range(1, k))
        if abs(den) < 1e-10:
            break
        phi[k, k] = num / den
        for j in range(1, k):
            phi[k, j] = phi[k - 1, j] - phi[k, k] * phi[k - 1, k - j]
        pacf[k] = phi[k, k]
        if abs(pacf[k]) > 1.5:  # pairwise ACF lost positive-definiteness
            pacf[k] = np.nan
            break
    return pacf


def autocorrelation_table(df_kt: pd.DataFrame, max_hourly_lag: int = 72,
                          max_daily_lag: int = 30) -> pd.DataFrame:
    """ACF/PACF of the clearness index, per city -- the evidence behind `lookback_hours`.

    Run on kt rather than on raw irradiance: the ACF of raw GHI is dominated by the
    deterministic 24 h cycle and says nothing about how far back *weather* information
    reaches. kt removes the geometry, so what is left is the predictable part.

    Two resolutions: hourly (night masked to NaN, pairwise ACF) answers "does a 24 h
    lookback capture the useful lags"; daily answers "how many days does a weather regime
    persist".
    """
    work = df_kt.copy()
    work.loc[(work["toa_horizontal"] <= TOA_MIN_FOR_KT) | ~positive_mask(work), "kt"] = np.nan
    # The hourly PACF is only reported for short lags. Night masking makes the ACF a
    # pairwise-deleted estimate, which is not guaranteed positive-definite, and past roughly
    # one positive block the Durbin-Levinson recursion starts producing spurious spikes
    # (Rize showed |0.79| at lag 22). A positive block is 10-15 h, so 12 is the safe cap.
    hourly_pacf_max_lag = 12
    rows = []
    for city, g in work.groupby("city", observed=True):
        g = g.sort_values("datetime")
        hourly = g.set_index("datetime")["kt"].asfreq("h").to_numpy()
        acf_h = _acf(hourly, max_hourly_lag)
        pacf_h = _pacf_from_acf(acf_h)
        for lag in range(1, max_hourly_lag + 1):
            rows.append({"city": city, "resolution": "hourly", "lag": lag,
                         "acf": acf_h[lag],
                         "pacf": pacf_h[lag] if lag <= hourly_pacf_max_lag else np.nan})

        daily = (
            g.assign(_date=g["datetime"].dt.normalize())
            .groupby("_date", observed=True)[[TARGET_COLUMN, "toa_horizontal"]]
            .sum()
        )
        kt_daily = (daily[TARGET_COLUMN] / daily["toa_horizontal"]).asfreq("D").to_numpy()
        acf_d = _acf(kt_daily, max_daily_lag)
        pacf_d = _pacf_from_acf(acf_d)
        for lag in range(1, max_daily_lag + 1):
            rows.append({"city": city, "resolution": "daily", "lag": lag,
                         "acf": acf_d[lag], "pacf": pacf_d[lag]})
    return pd.DataFrame(rows)


def ramp_table(df_kt: pd.DataFrame) -> pd.DataFrame:
    """Hour-to-hour change distribution, per (city, season).

    Two flavours, because they answer different questions: raw GHI ramps are what a
    prediction interval must actually cover, while kt ramps isolate the weather-driven part
    from the deterministic sunrise/sunset ramp.
    """
    work = add_season(df_kt.sort_values(["city", "datetime"]))
    work["d_ghi"] = work.groupby("city", observed=True)[TARGET_COLUMN].diff()
    work.loc[work.groupby("city", observed=True)["datetime"].diff() != pd.Timedelta("1h"),
             "d_ghi"] = np.nan
    kt_masked = work["kt"].where(work["toa_horizontal"] > TOA_MIN_FOR_KT)
    work["d_kt"] = kt_masked.groupby(work["city"], observed=True).diff()
    # align by index, not by position: `work` has been re-sorted above
    work = work[positive_mask(df_kt).reindex(work.index).to_numpy()]

    rows = []
    for city in CITIES:
        for season in [POOLED_LABEL] + SEASONS:
            sub = work[work["city"] == city]
            if season != POOLED_LABEL:
                sub = sub[sub["season"] == season]
            g = sub["d_ghi"].dropna().abs()
            k = sub["d_kt"].dropna().abs()
            rows.append(
                {
                    "city": city, "season": season, "n": int(len(g)),
                    "abs_d_ghi_mean": g.mean(),
                    "abs_d_ghi_median": g.median(),
                    "abs_d_ghi_p90": g.quantile(0.90),
                    "abs_d_ghi_p99": g.quantile(0.99),
                    "abs_d_ghi_p999": g.quantile(0.999),
                    "abs_d_ghi_max": g.max(),
                    "share_above_200": (g > 200).mean(),
                    "abs_d_kt_mean": k.mean(),
                    "abs_d_kt_median": k.median(),
                    "abs_d_kt_p90": k.quantile(0.90),
                    "abs_d_kt_p99": k.quantile(0.99),
                    "share_kt_above_0.3": (k > 0.3).mean(),
                }
            )
    return pd.DataFrame(rows)


def positive_block_table(df: pd.DataFrame) -> pd.DataFrame:
    """Contiguous-run lengths if night rows were deleted from the series.

    The permanent evidence behind TODOs.md item A: a 24 h lookback + 24 h horizon needs 48
    contiguous hours, and a positive-hours-only series has none, so night must be masked in the
    loss rather than deleted from the data.
    """
    is_pos = positive_mask(df)
    d = df[is_pos].sort_values(["city", "datetime"])
    rows = []
    for city, g in d.groupby("city", observed=True):
        breaks = (g["datetime"].diff() != pd.Timedelta("1h")).cumsum()
        runs = g.groupby(breaks, observed=True).size()
        rows.append(
            {
                "city": city,
                "n_positive_hours": int(len(g)),
                "n_blocks": int(len(runs)),
                "block_len_min": int(runs.min()),
                "block_len_median": float(runs.median()),
                "block_len_max": int(runs.max()),
                "share_blocks_ge_24h": float((runs >= 24).mean()),
                "share_blocks_ge_48h": float((runs >= 48).mean()),
            }
        )
    return pd.DataFrame(rows)


def persistence_baseline_table(df_kt: pd.DataFrame, config=None) -> pd.DataFrame:
    """Reference forecast floor on the same chronological test window the model uses.

    Two references, both leakage-free (nothing is fitted on test rows):

    - **Kalıcılık (persistence):** yhat(T) = y(T - 24 h). For a 24 h-ahead forecast this is
      the same number at every horizon step, so its skill is flat across the horizon --
      which is exactly the contrast a learned model has to beat at the far steps.
    Smart persistence -- yhat(T) = kt(T - 24 h) * CLRSKY(T) -- used to be the third. It needs a
    clear-sky MAGNITUDE, which the 14-Sep-2026 export no longer supplies. Rebuilt on the
    top-of-atmosphere denominator it degenerates: measured on this record it scores positive-hours
    RMSE 121.93 / MAE 72.42 against plain persistence's 121.85 / 72.38, i.e. it is the same
    rule, because TOA(T) ~ TOA(T-24h) for consecutive days where CLRSKY carried an air-mass
    term that did not cancel. A reference that adds nothing is worse than no reference, so it
    is removed rather than reported.
    - **Klimatoloji:** the (city, month, hour) mean of the TRAINING rows only.

    This is a descriptive reference, deliberately NOT a ledger row: the publishable
    comparison must run through `run_experiment` so it shares the windows, the scaler and
    metrics.py (see CLAUDE.md, Comparability rules).
    """
    from merve_solar.config import ExperimentConfig
    from merve_solar.windows import compute_split_boundaries

    if config is None:
        config = ExperimentConfig(experiment_id="eda_reference")
    _, val_end = compute_split_boundaries(df_kt, config)

    work = df_kt.sort_values(["city", "datetime"]).reset_index(drop=True)
    work["month"] = work["datetime"].dt.month
    lag = config.horizon_hours

    grouped = work.groupby("city", observed=True)
    work["persistence"] = grouped[TARGET_COLUMN].shift(lag)

    train_rows = work[work["datetime"] <= val_end]
    clim = train_rows.groupby(["city", "month", "HR"], observed=True)[TARGET_COLUMN].mean()
    work["climatology"] = work.set_index(["city", "month", "HR"]).index.map(clim)

    test = work[work["datetime"] > val_end]
    is_pos = positive_mask(df_kt).reindex(work.index)
    rows = []
    for scope, sub in (("positive", test[is_pos.reindex(test.index).to_numpy()]),):
        for city in CITIES + [POOLED_LABEL]:
            s = sub if city == POOLED_LABEL else sub[sub["city"] == city]
            y = s[TARGET_COLUMN].to_numpy(dtype=float)
            for name, col in (("persistence", "persistence"),
                              ("climatology", "climatology")):
                yhat = s[col].to_numpy(dtype=float)
                ok = ~(np.isnan(y) | np.isnan(yhat))
                yt, yp = y[ok], yhat[ok]
                err = yp - yt
                sst = ((yt - yt.mean()) ** 2).sum()
                rows.append(
                    {
                        "city": city, "scope": scope, "reference": name, "n": int(ok.sum()),
                        "RMSE": float(np.sqrt((err ** 2).mean())),
                        "MAE": float(np.abs(err).mean()),
                        "R2": float(1.0 - (err ** 2).sum() / sst) if sst > 0 else np.nan,
                        "bias": float(err.mean()),
                    }
                )
    return pd.DataFrame(rows)


def plot_target_histogram(df: pd.DataFrame, save_path: Path) -> None:
    """Positive-hours irradiance distribution per city -- shows the two modes behind the flat
    (excess kurtosis ~ -0.9) shape: a clear-sky mode and an overcast mode."""
    plt = _plt()

    d = require_positive(df, "plot_target_histogram")
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, 3.5)
        for ax, city in zip(flat[:5], CITIES):
            ax.hist(d.loc[d["city"] == city, TARGET_COLUMN], bins=60, color=ACCENT,
                    alpha=0.75, edgecolor="white", linewidth=0.3)
            ax.set_title(city)
            grid_y_only(ax)
        _finish_city_panels(fig, flat, AXIS_LABELS[TARGET_COLUMN], "Number of hours",
                            "Distribution of hourly irradiance (hours with target > 0)")
        save_figure(fig, save_path)


def plot_monthly_boxplot_all_years(daily: pd.DataFrame, save_path: Path) -> None:
    """Month-of-year distribution pooled over every year (~210 days per box).

    Complements the last-12-months figure: that one shows the year actually observed, this
    one shows the seasonal regime free of a single year's weather.
    """
    plt = _plt()

    first, last = daily["date"].min(), daily["date"].max()
    months = list(range(1, 13))
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, 3.7)
        norm = _median_norm(daily, "MO")
        for ax, city in zip(flat[:5], CITIES):
            _plasma_boxes(ax, daily[daily["city"] == city], "MO", months, norm)
            ax.set_title(city)
            _month_abbr_ticks(ax, months)
            grid_y_only(ax)
        _median_colorbar(fig, flat[5].inset_axes([0.1, 0.45, 0.8, 0.09]), norm)
        _finish_city_panels(
            fig, flat, "", DAILY_IRRADIATION_LABEL,
            f"Daily solar irradiation by month ({MONTH_ABBR[first.month]} {first.year} – "
            f"{MONTH_ABBR[last.month]} {last.year}, all years pooled)",
        )
        save_figure(fig, save_path)


def plot_autocorrelation(acf_df: pd.DataFrame, resolution: str, save_path: Path) -> None:
    """ACF and PACF of the clearness index, per city.

    Run on kt, not on raw irradiance: the ACF of GHI just re-derives the 24 h solar cycle.
    """
    plt = _plt()

    sub = acf_df[acf_df["resolution"] == resolution]
    hourly = resolution == "hourly"
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, 3.5)
        for ax, city in zip(flat[:5], CITIES):
            g = sub[sub["city"] == city]
            if hourly:
                for mark in (24, 48):
                    ax.axvline(mark, color=SEASON_COLORS["Autumn"], linewidth=0.7,
                               linestyle=":", alpha=0.7)
            ax.axhline(0, color=INK_SECONDARY, linewidth=0.6)
            ax.plot(g["lag"], g["acf"], color=ACCENT, linewidth=1.3,
                    label="Autocorrelation (ACF)")
            ax.vlines(g["lag"], 0, g["pacf"], color=SEASON_COLORS["Summer"], linewidth=1.1,
                      alpha=0.85, label="Partial autocorrelation (PACF)")
            ax.set_title(city)
            ax.set_ylim(-0.35, 1.02)
            if hourly:
                ax.set_xticks([0, 24, 48, 72])
            grid_y_only(ax)
        title = ("Hourly autocorrelation of the clearness index (dotted: 24 h and 48 h lags)"
                 if hourly else "Day-to-day autocorrelation of the daily clearness index")
        _finish_city_panels(fig, flat, "Lag (hours)" if hourly else "Lag (days)",
                            "Correlation coefficient", title)
        handles, labels = flat[0].get_legend_handles_labels()
        seen, uniq = set(), []
        for h_, l_ in zip(handles, labels):
            if l_ not in seen:
                seen.add(l_); uniq.append((h_, l_))
        flat[5].legend([h_ for h_, _ in uniq], [l_ for _, l_ in uniq], loc="center",
                       frameon=False)
        save_figure(fig, save_path)


def plot_ramp_distribution(df_kt: pd.DataFrame, save_path: Path) -> None:
    """Empirical CDF of |hourly change in irradiance|, by season, per city.

    What a 95% prediction interval has to cover is these ramps; the seasonal spread here is
    the descriptive counterpart of the CP/PINW trade-off.
    """
    plt = _plt()

    work = add_season(df_kt.sort_values(["city", "datetime"]))
    work["d_ghi"] = work.groupby("city", observed=True)[TARGET_COLUMN].diff().abs()
    work.loc[work.groupby("city", observed=True)["datetime"].diff() != pd.Timedelta("1h"),
             "d_ghi"] = np.nan
    work = work[positive_mask(df_kt).reindex(work.index).to_numpy()]
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, 3.5)
        for ax, city in zip(flat[:5], CITIES):
            g = work[work["city"] == city]
            for season in SEASONS:
                v = np.sort(g.loc[g["season"] == season, "d_ghi"].dropna().to_numpy())
                if not len(v):
                    continue
                ax.plot(v, np.arange(1, len(v) + 1) / len(v),
                        color=SEASON_COLORS[season], linestyle=SEASON_LINESTYLES[season],
                        linewidth=SEASON_LINEWIDTHS[season] * 0.75, label=season)
            ax.set_title(city)
            ax.set_xlim(0, 400)
            ax.set_xticks([0, 100, 200, 300, 400])
            grid_y_only(ax)
        _finish_city_panels(fig, flat, "Absolute hour-to-hour change (W/m²)",
                            "Cumulative fraction of hours with target > 0",
                            "Cumulative distribution of hour-to-hour irradiance changes "
                            "(hours with target > 0)")
        handles, labels = flat[0].get_legend_handles_labels()
        flat[5].legend(handles, labels, loc="center", title="Season", frameon=False)
        save_figure(fig, save_path)


def plot_persistence_baseline(baseline: pd.DataFrame, save_path: Path) -> None:
    """The forecast floor the model has to beat, per city, hours with target > 0 only."""
    plt = _plt()

    refs = ["persistence", "climatology"]
    ref_labels = {"persistence": "Persistence (same hour, previous day)",
                  "climatology": "Climatology (monthly-hourly mean)"}
    colors = [SEASON_COLORS["Winter"], SEASON_COLORS["Summer"]]
    sub = baseline[baseline["scope"] == "positive"]
    order = CITIES + [POOLED_LABEL]
    tick_labels = CITIES + ["All provinces"]
    x = np.arange(len(order))
    width = 0.38
    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(1, 2, figsize=(FULL_WIDTH_IN, 2.5), layout="constrained")
        for ax, metric, label in zip(axes, ["RMSE", "R2"],
                                     ["Root-mean-square error (W/m²)",
                                      "Coefficient of determination R²"]):
            for i, (ref, color) in enumerate(zip(refs, colors)):
                vals = [sub[(sub["city"] == c) & (sub["reference"] == ref)][metric].iloc[0]
                        for c in order]
                ax.bar(x + (i - 0.5) * width, vals, width * 0.92, color=color, alpha=0.85,
                       label=ref_labels[ref])
            ax.set_xticks(x)
            ax.set_xticklabels(tick_labels, rotation=30, ha="right", rotation_mode="anchor")
            ax.set_ylabel(label)
            grid_y_only(ax)
            if metric == "R2":
                ax.set_ylim(0.6, 1.0)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="outside lower center", ncol=len(labels),
                   frameon=False)
        fig.suptitle("Reference forecasts, 24 h ahead, on the test period (hours with target > 0)",
                     x=0.01, ha="left")
        save_figure(fig, save_path)


def plot_rize_comparison(kt_table: pd.DataFrame, seasonal: pd.DataFrame,
                         baseline: pd.DataFrame, df_kt: pd.DataFrame,
                         save_path: Path) -> None:
    """Rize against the other four provinces on the four axes that separate them.

    The dataset is two regimes, not five: Ankara/Antalya/Konya/Van sit inside a 6% band and
    Rize is a different climate. This is the figure that makes that argument at a glance.
    """
    plt = _plt()

    others = [c for c in CITIES if c != "Rize"]
    rize_color, other_color = SEASON_COLORS["Summer"], ACCENT
    daily = (
        df_kt.assign(_date=df_kt["datetime"].dt.normalize())
        .groupby(["city", "_date"], observed=True)[[TARGET_COLUMN, "toa_horizontal"]]
        .sum()
    )
    daily["kt_daily"] = daily[TARGET_COLUMN] / daily["toa_horizontal"]
    daily = daily.reset_index()
    daily["month"] = daily["_date"].dt.month

    def style(city):
        is_rize = city == "Rize"
        return {"color": rize_color if is_rize else other_color,
                "linewidth": 1.6 if is_rize else 1.0, "alpha": 1.0 if is_rize else 0.55}

    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(2, 2, figsize=(FULL_WIDTH_IN, 4.2), layout="constrained")

        ax = axes[0, 0]
        for city in CITIES:
            v = np.sort(daily.loc[daily["city"] == city, "kt_daily"].dropna().to_numpy())
            ax.plot(v, np.arange(1, len(v) + 1) / len(v), **style(city),
                    label="Rize" if city == "Rize"
                    else ("Other four provinces" if city == others[0] else None))
        ax.set_xlabel("Daily clearness index")
        ax.set_ylabel("Cumulative fraction of days")
        ax.set_title("(a) Distribution of daily clearness")
        ax.legend(loc="upper left")
        grid_y_only(ax)

        ax = axes[0, 1]
        for city in CITIES:
            m = daily[daily["city"] == city].groupby("month", observed=True)["kt_daily"].mean()
            ax.plot(m.index, m.to_numpy(), **style(city),
                    marker="o" if city == "Rize" else None, markersize=2.5)
        _month_initial_ticks(ax, range(1, 13))
        ax.set_xlabel("Month")
        ax.set_ylabel("Mean daily clearness index")
        ax.set_title("(b) Clearness by month")
        grid_y_only(ax)

        ax = axes[1, 0]
        x = np.arange(len(SEASONS))
        for city in CITIES:
            vals = [seasonal[(seasonal["city"] == city) & (seasonal["season"] == s)]
                    ["daily_kwh_cv"].iloc[0] for s in SEASONS]
            ax.plot(x, vals, **style(city),
                    marker="o" if city == "Rize" else None, markersize=2.5)
        ax.set_xticks(x)
        ax.set_xticklabels(SEASONS)
        ax.set_xlim(-0.3, len(SEASONS) - 0.7)
        ax.set_xlabel("Season")
        ax.set_ylabel("CV of daily irradiation")
        ax.set_title("(c) Day-to-day variability")
        grid_y_only(ax)

        ax = axes[1, 1]
        sub = baseline[(baseline["scope"] == "positive")
                       & (baseline["reference"] == "climatology")]
        vals = [sub[sub["city"] == c]["R2"].iloc[0] for c in CITIES]
        ax.bar(range(len(CITIES)), vals,
               color=[rize_color if c == "Rize" else other_color for c in CITIES],
               alpha=0.85, width=0.6)
        ax.set_xticks(range(len(CITIES)))
        ax.set_xticklabels(CITIES)
        ax.set_xlabel("Province")
        ax.set_ylabel("R² of climatology forecast")
        ax.set_ylim(0.6, 1.0)
        ax.set_title("(d) Predictability by climatology")
        grid_y_only(ax)

        fig.suptitle("Rize forms a separate climate regime from the other four provinces",
                     x=0.01, ha="left")
        save_figure(fig, save_path)
