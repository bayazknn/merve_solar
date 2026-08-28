"""Descriptive statistics and paper figures for the dataset itself (config-independent).

Read-only over outputs/processed/base_features.parquet; nothing here touches an experiment,
the ledger, or ExperimentConfig. Driven by scripts/02_descriptive_analysis.py.

Three data-handling decisions drive most of this module; the reasoning is in
outputs/eda/README.md and repeated briefly at each function:

1. "Daylight" is defined geometrically, from NASA POWER's own clear-sky column
   (CLRSKY_SFC_SW_DWN > 0), not from the realised target and not from a monthly cell mean.
   See daylight_mask() for why both alternatives are wrong.
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
# clear-sky reference (descriptive use only)
# ---------------------------------------------------------------------------------------
def build_clearsky_reference() -> pd.DataFrame:
    """Read CLRSKY_SFC_SW_DWN back out of the source xlsx and cache it.

    `CLRSKY_SFC_SW_DWN` is in DROPPED_COLUMNS: it is a near-deterministic geometric envelope
    of the target, so using it as a model feature would turn part of the task into a
    clear-sky-index fit and inflate skill relative to what is available operationally. That
    argument is about *model input* and does not apply to describing the dataset, where the
    clearness index kt = ALLSKY / CLRSKY is the standard way to compare sites on cloudiness
    instead of on latitude.

    This cache is written to a separate parquet that nothing under experiment.py reads.
    """
    import openpyxl  # noqa: F401  (pandas needs the engine)

    from merve_solar.config import (
        CLEARSKY_REFERENCE_PATH,
        EXPECTED_TRIMMED_ROWS_PER_SHEET,
        LAST_VALID_TIMESTAMP,
        MISSING_SENTINEL,
        RAW_XLSX_PATH,
    )

    frames = []
    for city in CITIES:
        raw = pd.read_excel(
            RAW_XLSX_PATH, sheet_name=city, engine="openpyxl",
            usecols=["YEAR", "MO", "DY", "HR", "CLRSKY_SFC_SW_DWN"],
        )
        raw["datetime"] = pd.to_datetime(
            raw[["YEAR", "MO", "DY", "HR"]].rename(
                columns={"YEAR": "year", "MO": "month", "DY": "day", "HR": "hour"}
            )
        )
        raw = raw.sort_values("datetime").reset_index(drop=True)
        before = len(raw)
        raw = raw[raw["datetime"] <= pd.Timestamp(LAST_VALID_TIMESTAMP)].reset_index(drop=True)
        if before - len(raw) != EXPECTED_TRIMMED_ROWS_PER_SHEET:
            raise ValueError(
                f"{city}: clear-sky sheet trimmed {before - len(raw)} rows, expected "
                f"{EXPECTED_TRIMMED_ROWS_PER_SHEET}"
            )
        if (raw["CLRSKY_SFC_SW_DWN"] == MISSING_SENTINEL).any():
            raise ValueError(f"{city}: -999 remains in CLRSKY_SFC_SW_DWN after trimming.")
        raw["city"] = city
        frames.append(raw[["datetime", "city", "CLRSKY_SFC_SW_DWN"]])

    out = pd.concat(frames, ignore_index=True)
    CLEARSKY_REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CLEARSKY_REFERENCE_PATH, index=False)
    return out


_CLEARSKY_CACHE = None


def load_clearsky_reference() -> pd.DataFrame:
    """Cached clear-sky reference; builds it from the xlsx on first call (~1 min).

    Memoised in-process because daylight_mask() is called many times per run.
    """
    global _CLEARSKY_CACHE
    if _CLEARSKY_CACHE is None:
        from merve_solar.config import CLEARSKY_REFERENCE_PATH

        _CLEARSKY_CACHE = (
            pd.read_parquet(CLEARSKY_REFERENCE_PATH)
            if CLEARSKY_REFERENCE_PATH.exists()
            else build_clearsky_reference()
        )
    return _CLEARSKY_CACHE


def attach_clearness(df: pd.DataFrame) -> pd.DataFrame:
    """Add CLRSKY_SFC_SW_DWN and the clearness index kt = ALLSKY / CLRSKY.

    kt is defined only where the clear-sky reference is positive (i.e. astronomical
    daylight); elsewhere it is NaN rather than 0/0.
    """
    if "CLRSKY_SFC_SW_DWN" in df.columns:
        # base_features.parquet now carries the column as metadata (never a model feature),
        # so prefer it: one source of truth rather than two.
        out = df.copy()
    else:
        out = df.merge(
            load_clearsky_reference(), on=["datetime", "city"], how="left",
            validate="one_to_one",
        )
        if out["CLRSKY_SFC_SW_DWN"].isna().any():
            raise ValueError("clear-sky reference does not cover every (datetime, city) row.")
    out["kt"] = np.where(
        out["CLRSKY_SFC_SW_DWN"] > 0, out[TARGET_COLUMN] / out["CLRSKY_SFC_SW_DWN"], np.nan
    )
    return out


# ---------------------------------------------------------------------------------------
# data helpers
# ---------------------------------------------------------------------------------------
def daylight_mask(df: pd.DataFrame) -> pd.Series:
    """Geometric daylight: NASA POWER's clear-sky reference is positive.

    Reads CLRSKY_SFC_SW_DWN from the frame when it is present (base_features.parquet now
    carries it as metadata that is never a model feature) and falls back to the standalone
    EDA cache otherwise.

    Clear-sky irradiance is a purely geometric quantity, so CLRSKY > 0 means exactly "the
    sun is above the horizon at this site and hour" -- computed by the data provider with
    the real grid coordinates and its own time convention, which is why this is preferable
    to re-deriving solar elevation ourselves.

    Only the boolean is used. A sun-up flag carries public astronomical information, not
    weather, so it is not the leakage that putting CLRSKY itself in NUMERIC_FEATURE_COLUMNS
    would be (see DROPPED_COLUMNS in config.py).

    Two alternatives were tried and are wrong:

    - `target > 0` looks like it conditions on the dependent variable. On this dataset it
      does not: it selects exactly the same 151,643 rows as CLRSKY > 0, to the row. No
      interior daylight hour is ever exactly 0 (minimum 3.78 W/m^2), so a zero reading
      always means "sun down", never "overcast". The geometric form is preferred anyway
      because it stays correct by construction rather than by coincidence.
    - A climatological (city, month, hour) cell mean > 0 was used in the first EDA round
      and is too coarse. Within one month sunrise and sunset shift 30-60 minutes, so the
      edge hour of the cell is lit for part of the month and dark for the rest; the cell
      mean marks the whole hour as daylight and admits 5,266 rows whose clear-sky value is
      exactly 0 -- i.e. night. That pulled every city's daylight mean down by 10-14 W/m^2.
    """
    if "CLRSKY_SFC_SW_DWN" in df.columns:
        clrsky = df["CLRSKY_SFC_SW_DWN"]
    else:
        merged = df[["datetime", "city"]].merge(
            load_clearsky_reference(), on=["datetime", "city"], how="left",
            validate="one_to_one",
        )
        if merged["CLRSKY_SFC_SW_DWN"].isna().any():
            raise ValueError("clear-sky reference does not cover every (datetime, city) row.")
        clrsky = merged["CLRSKY_SFC_SW_DWN"]
    return pd.Series((clrsky > 0).to_numpy(), index=df.index, name="daylight")


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
        for season in [POOLED_LABEL] + SEASONS_TR:
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


# ---------------------------------------------------------------------------------------
# predictability analyses (added after the first EDA round)
# ---------------------------------------------------------------------------------------
CLEARSKY_MIN_FOR_KT = 20.0  # W/m^2; below this, ALLSKY/CLRSKY is a twilight division blow-up


def clearness_index_table(df_kt: pd.DataFrame) -> pd.DataFrame:
    """Physical clearness index kt = ALLSKY / CLRSKY, per (city, season).

    Reported both hourly (restricted to CLRSKY > CLEARSKY_MIN_FOR_KT, since near sunrise and
    sunset the ratio is a division of two near-zero numbers) and daily (ratio of the two
    daily sums, which needs no threshold and is the quantity solar-resource papers report).
    """
    work = add_season(df_kt.assign(_date=df_kt["datetime"].dt.normalize()))
    hourly = work[work["CLRSKY_SFC_SW_DWN"] > CLEARSKY_MIN_FOR_KT]
    daily = (
        work.groupby(["city", "_date"], observed=True)[[TARGET_COLUMN, "CLRSKY_SFC_SW_DWN"]]
        .sum()
        .assign(kt_daily=lambda d: d[TARGET_COLUMN] / d["CLRSKY_SFC_SW_DWN"])
        .reset_index()
    )
    daily["season"] = pd.Categorical(
        daily["_date"].dt.month.map(MONTH_TO_SEASON_TR), categories=SEASONS_TR, ordered=True
    )
    rows = []
    for city in CITIES:
        for season in [POOLED_LABEL] + SEASONS_TR:
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
                    "clear_hour_share": (h["kt"] > 0.7).mean(),
                    "overcast_hour_share": (h["kt"] < 0.3).mean(),
                    "kt_daily_mean": d["kt_daily"].mean(),
                    "kt_daily_median": d["kt_daily"].median(),
                    "kt_daily_std": d["kt_daily"].std(),
                    "clear_day_share": (d["kt_daily"] > 0.7).mean(),
                    "overcast_day_share": (d["kt_daily"] < 0.3).mean(),
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
    work.loc[work["CLRSKY_SFC_SW_DWN"] <= CLEARSKY_MIN_FOR_KT, "kt"] = np.nan
    # The hourly PACF is only reported for short lags. Night masking makes the ACF a
    # pairwise-deleted estimate, which is not guaranteed positive-definite, and past roughly
    # one daylight block the Durbin-Levinson recursion starts producing spurious spikes
    # (Rize showed |0.79| at lag 22). A daylight block is 10-15 h, so 12 is the safe cap.
    hourly_pacf_max_lag = 12
    rows = []
    for city, g in work.groupby("city", observed=True):
        g = g.sort_values("datetime")
        hourly = g.set_index("datetime")["kt"].asfreq("h").to_numpy()
        acf_h = _acf(hourly, max_hourly_lag)
        pacf_h = _pacf_from_acf(acf_h)
        for lag in range(1, max_hourly_lag + 1):
            rows.append({"city": city, "resolution": "saatlik", "lag": lag,
                         "acf": acf_h[lag],
                         "pacf": pacf_h[lag] if lag <= hourly_pacf_max_lag else np.nan})

        daily = (
            g.assign(_date=g["datetime"].dt.normalize())
            .groupby("_date", observed=True)[[TARGET_COLUMN, "CLRSKY_SFC_SW_DWN"]]
            .sum()
        )
        kt_daily = (daily[TARGET_COLUMN] / daily["CLRSKY_SFC_SW_DWN"]).asfreq("D").to_numpy()
        acf_d = _acf(kt_daily, max_daily_lag)
        pacf_d = _pacf_from_acf(acf_d)
        for lag in range(1, max_daily_lag + 1):
            rows.append({"city": city, "resolution": "günlük", "lag": lag,
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
    kt_masked = work["kt"].where(work["CLRSKY_SFC_SW_DWN"] > CLEARSKY_MIN_FOR_KT)
    work["d_kt"] = kt_masked.groupby(work["city"], observed=True).diff()
    # align by index, not by position: `work` has been re-sorted above
    work = work[daylight_mask(df_kt).reindex(work.index).to_numpy()]

    rows = []
    for city in CITIES:
        for season in [POOLED_LABEL] + SEASONS_TR:
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


def daylight_block_table(df: pd.DataFrame) -> pd.DataFrame:
    """Contiguous-run lengths if night rows were deleted from the series.

    The permanent evidence behind TODOs.md item A: a 24 h lookback + 24 h horizon needs 48
    contiguous hours, and a daylight-only series has none, so night must be masked in the
    loss rather than deleted from the data.
    """
    is_day = daylight_mask(df)
    d = df[is_day].sort_values(["city", "datetime"])
    rows = []
    for city, g in d.groupby("city", observed=True):
        breaks = (g["datetime"].diff() != pd.Timedelta("1h")).cumsum()
        runs = g.groupby(breaks, observed=True).size()
        rows.append(
            {
                "city": city,
                "n_daylight_hours": int(len(g)),
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

    Three references, all leakage-free (nothing is fitted on test rows):

    - **Kalıcılık (persistence):** yhat(T) = y(T - 24 h). For a 24 h-ahead forecast this is
      the same number at every horizon step, so its skill is flat across the horizon --
      which is exactly the contrast a learned model has to beat at the far steps.
    - **Akıllı kalıcılık (smart persistence):** carry yesterday's clearness forward and
      re-apply today's clear-sky reference: yhat(T) = kt(T - 24 h) * CLRSKY(T). This is the
      honest floor in solar forecasting -- plain persistence is easy to beat only because it
      ignores the deterministic geometry.
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
    # kt is undefined at night (CLRSKY = 0). Carrying that NaN forward would silently drop
    # every night row from this reference only, making its scope="24 saat" row incomparable
    # with the others. Yesterday's night carries clearness 0, and CLRSKY(T) = 0 tonight, so
    # the prediction is 0 either way -- which is the correct forecast.
    kt_lag = grouped["kt"].shift(lag).clip(upper=1.1).fillna(0.0)
    work["smart_persistence"] = (kt_lag * work["CLRSKY_SFC_SW_DWN"]).clip(lower=0.0)
    # ...but a genuinely missing lag (the first 24 h of the record) must stay missing.
    work.loc[grouped[TARGET_COLUMN].shift(lag).isna(), "smart_persistence"] = np.nan

    train_rows = work[work["datetime"] <= val_end]
    clim = train_rows.groupby(["city", "month", "HR"], observed=True)[TARGET_COLUMN].mean()
    work["climatology"] = work.set_index(["city", "month", "HR"]).index.map(clim)

    test = work[work["datetime"] > val_end]
    is_day = daylight_mask(df_kt).reindex(work.index)
    rows = []
    for scope, sub in (("24 saat", test), ("gündüz", test[is_day.reindex(test.index).to_numpy()])):
        for city in CITIES + [POOLED_LABEL]:
            s = sub if city == POOLED_LABEL else sub[sub["city"] == city]
            y = s[TARGET_COLUMN].to_numpy(dtype=float)
            for name, col in (("kalıcılık", "persistence"),
                              ("akıllı kalıcılık", "smart_persistence"),
                              ("klimatoloji", "climatology")):
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
    """Daylight irradiance distribution per city -- shows the two modes behind the flat
    (excess kurtosis ~ -0.9) shape: a clear-sky mode and an overcast mode."""
    plt = _plt()

    d = df[daylight_mask(df)]
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 4.0))
        for ax, city in zip(flat[:5], CITIES):
            ax.hist(d.loc[d["city"] == city, TARGET_COLUMN], bins=60, color=ACCENT,
                    alpha=0.75, edgecolor="white", linewidth=0.3)
            ax.set_title(city)
            grid_y_only(ax)
        _finish_city_panels(plt, fig, flat, "Işınım (W/m²)", "Saat sayısı")
        fig.suptitle("Gündüz saatlik ışınımın dağılımı", x=0.03, ha="left",
                     fontsize=11, fontweight="semibold")
        fig.tight_layout(rect=(0.03, 0, 1, 0.94))
        save_figure(fig, save_path)


def plot_monthly_boxplot_all_years(daily: pd.DataFrame, save_path: Path) -> None:
    """Month-of-year box plot pooled over every year (~200 days per box).

    Complements the last-12-months figure: that one shows the year actually observed, this
    one shows the seasonal regime free of a single year's weather.
    """
    plt = _plt()
    import seaborn as sns

    work = daily.copy()
    work["month_label"] = pd.Categorical(
        work["MO"].map(MONTH_ABBR_TR), categories=[MONTH_ABBR_TR[m] for m in range(1, 13)],
        ordered=True,
    )
    order = list(work["month_label"].cat.categories)
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 4.4))
        for ax, city in zip(flat[:5], CITIES):
            sns.boxplot(
                data=work[work["city"] == city], x="month_label", y="daily_kwh", order=order,
                ax=ax, color=ACCENT, width=0.62, fliersize=1.2, linewidth=0.7,
                boxprops={"alpha": 0.55},
                medianprops={"color": "#7a2d0f", "linewidth": 1.2},
                flierprops={"markerfacecolor": INK_SECONDARY, "markeredgewidth": 0,
                            "alpha": 0.35},
            )
            ax.set_title(city)
            grid_y_only(ax)
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=7)
        _finish_city_panels(plt, fig, flat, "", "Günlük toplam ışınım (kWh/m²)")
        fig.suptitle(
            "Aylara göre günlük toplam ışınım (2019–2026, tüm yıllar havuzlanmış)",
            x=0.03, ha="left", fontsize=11, fontweight="semibold",
        )
        fig.tight_layout(rect=(0.03, 0, 1, 0.94))
        save_figure(fig, save_path)


def plot_autocorrelation(acf_df: pd.DataFrame, resolution: str, save_path: Path) -> None:
    """ACF and PACF of the clearness index, per city.

    Run on kt, not on raw irradiance: the ACF of GHI just re-derives the 24 h solar cycle.
    """
    plt = _plt()

    sub = acf_df[acf_df["resolution"] == resolution]
    hourly = resolution == "saatlik"
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 4.2))
        for ax, city in zip(flat[:5], CITIES):
            g = sub[sub["city"] == city]
            if hourly:
                for mark in (24, 48):
                    ax.axvline(mark, color=SEASON_COLORS["Sonbahar"], linewidth=0.8,
                               linestyle=":", alpha=0.7)
            ax.axhline(0, color=INK_SECONDARY, linewidth=0.8)
            ax.plot(g["lag"], g["acf"], color=ACCENT, linewidth=1.6, label="ACF")
            ax.vlines(g["lag"], 0, g["pacf"], color=SEASON_COLORS["Yaz"], linewidth=1.4,
                      alpha=0.85, label="PACF")
            ax.set_title(city)
            ax.set_ylim(-0.35, 1.02)
            grid_y_only(ax)
        _finish_city_panels(
            plt, fig, flat,
            "Gecikme (saat)" if hourly else "Gecikme (gün)", "Korelasyon",
        )
        handles, labels = flat[0].get_legend_handles_labels()
        seen, uniq = set(), []
        for h_, l_ in zip(handles, labels):
            if l_ not in seen:
                seen.add(l_); uniq.append((h_, l_))
        flat[5].legend([h_ for h_, _ in uniq], [l_ for _, l_ in uniq], loc="center",
                       frameon=False)
        title = ("Berraklık indeksinin saatlik otokorelasyonu (noktalı çizgiler: 24 ve 48 saat)"
                 if hourly else "Berraklık indeksinin günlük otokorelasyonu")
        fig.suptitle(title, x=0.03, ha="left", fontsize=11, fontweight="semibold")
        fig.tight_layout(rect=(0.03, 0, 1, 0.94))
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
    work = work[daylight_mask(df_kt).reindex(work.index).to_numpy()]
    with plt.rc_context(PAPER_RC):
        fig, flat = _city_panels(plt, figsize=(FULL_WIDTH_IN, 4.2))
        for ax, city in zip(flat[:5], CITIES):
            g = work[work["city"] == city]
            for season in SEASONS_TR:
                v = np.sort(g.loc[g["season"] == season, "d_ghi"].dropna().to_numpy())
                if not len(v):
                    continue
                ax.plot(v, np.arange(1, len(v) + 1) / len(v),
                        color=SEASON_COLORS[season], linestyle=SEASON_LINESTYLES[season],
                        linewidth=SEASON_LINEWIDTHS[season], label=season)
            ax.set_title(city)
            ax.set_xlim(0, 400)
            grid_y_only(ax)
        _finish_city_panels(plt, fig, flat, "|Saatlik değişim| (W/m²)", "Birikimli oran")
        handles, labels = flat[0].get_legend_handles_labels()
        flat[5].legend(handles, labels, loc="center", title="Mevsim", frameon=False)
        fig.suptitle("Saatlik ışınım rampalarının birikimli dağılımı (gündüz)",
                     x=0.03, ha="left", fontsize=11, fontweight="semibold")
        fig.tight_layout(rect=(0.03, 0, 1, 0.94))
        save_figure(fig, save_path)


def plot_persistence_baseline(baseline: pd.DataFrame, save_path: Path) -> None:
    """The forecast floor the model has to beat, per city, daylight hours only."""
    plt = _plt()

    refs = ["kalıcılık", "akıllı kalıcılık", "klimatoloji"]
    colors = [SEASON_COLORS["Kış"], SEASON_COLORS["İlkbahar"], SEASON_COLORS["Yaz"]]
    sub = baseline[baseline["scope"] == "gündüz"]
    order = CITIES + [POOLED_LABEL]
    x = np.arange(len(order))
    width = 0.26
    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(1, 2, figsize=(FULL_WIDTH_IN, 2.9))
        for ax, metric, label in zip(axes, ["RMSE", "R2"],
                                     ["RMSE (W/m²)", "R² (gündüz)"]):
            for i, (ref, color) in enumerate(zip(refs, colors)):
                vals = [sub[(sub["city"] == c) & (sub["reference"] == ref)][metric].iloc[0]
                        for c in order]
                ax.bar(x + (i - 1) * width, vals, width * 0.92, color=color, alpha=0.85,
                       label=ref)
            ax.set_xticks(x)
            ax.set_xticklabels(order, rotation=30, ha="right", fontsize=8)
            ax.set_ylabel(label)
            grid_y_only(ax)
            if metric == "R2":
                ax.set_ylim(0.6, 1.0)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper right", ncol=3, frameon=False, fontsize=8,
                   bbox_to_anchor=(0.99, 0.99))
        fig.suptitle(
            "Referans tahmin zemini: 24 saat ilerisi, modelin test penceresi, gündüz saatleri",
            x=0.02, y=0.99, ha="left", va="top", fontsize=11, fontweight="semibold",
        )
        fig.tight_layout(rect=(0, 0, 1, 0.86))
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
    rize_color, other_color = SEASON_COLORS["Yaz"], ACCENT
    daily = (
        df_kt.assign(_date=df_kt["datetime"].dt.normalize())
        .groupby(["city", "_date"], observed=True)[[TARGET_COLUMN, "CLRSKY_SFC_SW_DWN"]]
        .sum()
    )
    daily["kt_daily"] = daily[TARGET_COLUMN] / daily["CLRSKY_SFC_SW_DWN"]
    daily = daily.reset_index()
    daily["month"] = daily["_date"].dt.month

    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(2, 2, figsize=(FULL_WIDTH_IN, 5.0))

        ax = axes[0, 0]
        for city in CITIES:
            v = np.sort(daily.loc[daily["city"] == city, "kt_daily"].dropna().to_numpy())
            is_rize = city == "Rize"
            ax.plot(v, np.arange(1, len(v) + 1) / len(v),
                    color=rize_color if is_rize else other_color,
                    linewidth=2.0 if is_rize else 1.2, alpha=1.0 if is_rize else 0.55,
                    label="Rize" if is_rize else ("Diğer 4 il" if city == others[0] else None))
        ax.set_xlabel("Günlük berraklık indeksi kt")
        ax.set_ylabel("Birikimli oran")
        ax.set_title("Berraklık dağılımı")
        ax.legend(fontsize=8)
        grid_y_only(ax)

        ax = axes[0, 1]
        for city in CITIES:
            m = daily[daily["city"] == city].groupby("month", observed=True)["kt_daily"].mean()
            is_rize = city == "Rize"
            ax.plot(m.index, m.to_numpy(), color=rize_color if is_rize else other_color,
                    linewidth=2.0 if is_rize else 1.2, alpha=1.0 if is_rize else 0.55,
                    marker="o" if is_rize else None, markersize=3)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels([str(m) for m in range(1, 13)], fontsize=7)
        ax.set_xlabel("Ay")
        ax.set_ylabel("Ortalama kt")
        ax.set_title("Aylık berraklık")
        grid_y_only(ax)

        ax = axes[1, 0]
        x = np.arange(len(SEASONS_TR))
        for i, city in enumerate(CITIES):
            vals = [seasonal[(seasonal["city"] == city) & (seasonal["season"] == s)]
                    ["daily_kwh_cv"].iloc[0] for s in SEASONS_TR]
            is_rize = city == "Rize"
            ax.plot(x, vals, color=rize_color if is_rize else other_color,
                    linewidth=2.0 if is_rize else 1.2, alpha=1.0 if is_rize else 0.55,
                    marker="o" if is_rize else None, markersize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(SEASONS_TR, fontsize=8)
        ax.set_ylabel("Günler arası CV")
        ax.set_title("Mevsimsel değişkenlik")
        grid_y_only(ax)

        ax = axes[1, 1]
        sub = baseline[(baseline["scope"] == "gündüz")
                       & (baseline["reference"] == "akıllı kalıcılık")]
        vals = [sub[sub["city"] == c]["R2"].iloc[0] for c in CITIES]
        ax.bar(range(len(CITIES)), vals,
               color=[rize_color if c == "Rize" else other_color for c in CITIES],
               alpha=0.85, width=0.6)
        ax.set_xticks(range(len(CITIES)))
        ax.set_xticklabels(CITIES, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel("R² (akıllı kalıcılık)")
        ax.set_ylim(0.6, 1.0)
        ax.set_title("Referans tahmin edilebilirliği")
        grid_y_only(ax)

        fig.suptitle("Rize, diğer dört ilden ayrı bir rejim", x=0.02, ha="left",
                     fontsize=11, fontweight="semibold")
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        save_figure(fig, save_path)
