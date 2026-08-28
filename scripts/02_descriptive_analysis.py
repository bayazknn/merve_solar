"""Descriptive statistics and paper figures for the dataset (config-independent).

Reads the cached outputs/processed/base_features.parquet and writes every table and figure
under outputs/eda/. Run scripts/01_prepare_base_data.py first.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import argparse

import pandas as pd

from merve_solar import eda
from merve_solar.config import (
    BASE_FEATURES_PATH,
    CITIES,
    EDA_DIR,
    EDA_FIGURES_DIR,
    EDA_TABLES_DIR,
    RAW_METEO_COLUMNS,
)
from merve_solar.data import load_base_features

WRITTEN = []


def _write_csv(df: pd.DataFrame, name: str) -> None:
    path = EDA_TABLES_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    WRITTEN.append(path)


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)


def _write_markdown_and_latex(df: pd.DataFrame, stem: str, caption: str) -> None:
    """Hand-rolled writers: pandas' to_markdown/to_latex would pull in tabulate/jinja2."""
    cols = list(df.columns)
    rows = [[_fmt(v) for v in rec] for rec in df.itertuples(index=False)]

    widths = [max(len(c), *(len(r[i]) for r in rows)) for i, c in enumerate(cols)]
    lines = ["| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols)) + " |",
             "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    lines += ["| " + " | ".join(r[i].ljust(widths[i]) for i in range(len(cols))) + " |"
              for r in rows]
    md_path = EDA_TABLES_DIR / f"{stem}.md"
    md_path.write_text(f"# {caption}\n\n" + "\n".join(lines) + "\n")
    WRITTEN.append(md_path)

    tex = [r"\begin{table}[htbp]", r"\centering", rf"\caption{{{caption}}}",
           rf"\label{{tab:{stem}}}", r"\begin{tabular}{l" + "r" * (len(cols) - 1) + "}",
           r"\hline",
           " & ".join(c.replace("_", r"\_") for c in cols) + r" \\", r"\hline"]
    tex += [" & ".join(v.replace("%", r"\%") for v in r) + r" \\" for r in rows]
    tex += [r"\hline", r"\end{tabular}", r"\end{table}"]
    tex_path = EDA_TABLES_DIR / f"{stem}.tex"
    tex_path.write_text("\n".join(tex) + "\n")
    WRITTEN.append(tex_path)


def _figure(path_stem: str) -> Path:
    path = EDA_FIGURES_DIR / path_stem
    WRITTEN.append(path.with_suffix(".png"))
    WRITTEN.append(path.with_suffix(".pdf"))
    return path


def _descriptive_outputs(df: pd.DataFrame, is_day: pd.Series) -> None:
    for scope, sub in (("daylight", df[is_day]), ("24h", df)):
        table = eda.descriptive_table(sub)
        _write_csv(table, f"descriptive_stats_by_city_{scope}.csv")
        pretty = table[
            ["city", "variable_tr", "n", "mean", "std", "min", "q25", "median", "q75",
             "max", "skew", "excess_kurtosis"]
        ].rename(
            columns={"city": "İl", "variable_tr": "Değişken", "n": "N", "mean": "Ort.",
                     "std": "SS", "min": "Min", "q25": "Q1", "median": "Medyan",
                     "q75": "Q3", "max": "Maks", "skew": "Çarpıklık",
                     "excess_kurtosis": "Basıklık"}
        )
        label = "gündüz saatleri" if scope == "daylight" else "24 saat"
        _write_markdown_and_latex(
            pretty, f"descriptive_stats_by_city_{scope}",
            f"Betimsel istatistikler, il bazında ({label}). "
            "Basıklık Fisher (fazlalık) tanımıdır: normal dağılım için 0.",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    df = load_base_features(BASE_FEATURES_PATH)
    is_day = eda.daylight_mask(df)
    df_daylight = df[is_day]
    daily = eda.daily_totals(df)
    daily_12m = eda.last_12_months(daily, date_col="date")

    print(f"{len(df):,} satır, {df['city'].nunique()} il, "
          f"{df['datetime'].min()} → {df['datetime'].max()}")
    print(f"gündüz (klimatolojik) satır payı: {is_day.mean():.3f}")

    # --- tables ---------------------------------------------------------------------
    _descriptive_outputs(df, is_day)
    _write_csv(eda.temporal_coverage_table(df), "temporal_coverage_by_city.csv")
    _write_csv(eda.target_by_hour_table(df), "target_by_hour_by_city.csv")
    _write_csv(eda.time_explained_variance_table(df), "time_feature_explained_variance.csv")
    _write_csv(eda.circular_wind_table(df), "wind_direction_circular_stats.csv")
    _write_csv(eda.monthly_target_stats(daily_12m), "monthly_target_stats.csv")
    _write_csv(eda.seasonal_target_stats(df, daily), "seasonal_target_stats.csv")
    _write_csv(eda.clearness_table(daily), "daily_clearness_by_city.csv")

    # Clear-sky reference (descriptive use only -- CLRSKY never becomes a model feature).
    df_kt = eda.attach_clearness(df)
    kt_table = eda.clearness_index_table(df_kt)
    acf_table = eda.autocorrelation_table(df_kt)
    baseline = eda.persistence_baseline_table(df_kt)
    seasonal = eda.seasonal_target_stats(df, daily)
    _write_csv(kt_table, "clearness_index_by_city.csv")
    _write_csv(acf_table, "autocorrelation_clearness.csv")
    _write_csv(eda.ramp_table(df_kt), "ramp_stats_by_city.csv")
    _write_csv(eda.daylight_block_table(df), "daylight_block_structure.csv")
    _write_csv(baseline, "persistence_baseline.csv")

    corr = eda.correlation_tables(df_daylight)
    for method in ("pearson", "spearman"):
        for city, matrix in corr[method].items():
            suffix = "pooled" if city == eda.POOLED_LABEL else city
            _write_csv(matrix.rename_axis("variable").reset_index(),
                       f"correlation_{method}_{suffix}.csv")
    _write_csv(corr["target"], "target_correlation_by_city.csv")
    _write_csv(eda.collinear_pairs(corr["pearson"][eda.POOLED_LABEL]), "collinear_pairs.csv")

    # --- figures --------------------------------------------------------------------
    for city, matrix in corr["pearson"].items():
        suffix = "pooled" if city == eda.POOLED_LABEL else city
        title = ("Tüm iller: korelasyon matrisi (gündüz)" if city == eda.POOLED_LABEL
                 else f"{city}: korelasyon matrisi (gündüz)")
        eda.plot_correlation_heatmap(matrix, title, _figure(f"correlation_heatmap_{suffix}"))
    eda.plot_target_correlation_panel(corr["target"], _figure("target_correlation_panel"))

    for city in CITIES:
        eda.plot_scatter_vs_target(df_daylight, city, _figure(f"scatter_vs_target_{city}"))
        eda.plot_monthly_boxplot(daily_12m, city, _figure(f"monthly_boxplot_last12m_{city}"))
    eda.plot_monthly_boxplot(daily_12m, None, _figure("monthly_boxplot_last12m_panel"))

    grids = {city: eda.month_year_grid(daily, city) for city in CITIES}
    zlo = min(float(g.to_numpy().min()) for g in grids.values())
    zhi = max(float(g.to_numpy().max()) for g in grids.values())
    zlim = (0.0, zhi * 1.02) if zlo > 0 else (zlo, zhi)
    for city in CITIES:
        eda.plot_month_year_surface_3d(grids, city, _figure(f"month_year_surface_{city}"),
                                       zlim=zlim)
    eda.plot_month_year_surface_3d(grids, None, _figure("month_year_surface_panel"), zlim=zlim)
    eda.plot_month_year_anomaly(grids, _figure("month_year_anomaly_panel"))

    eda.plot_seasonal_diurnal_profile(df, _figure("seasonal_diurnal_profile"))
    eda.plot_seasonal_dayofyear(daily, _figure("seasonal_dayofyear"))

    eda.plot_target_histogram(df, _figure("target_histogram"))
    eda.plot_monthly_boxplot_all_years(daily, _figure("monthly_boxplot_all_years"))
    eda.plot_autocorrelation(acf_table, "saatlik", _figure("autocorrelation_hourly"))
    eda.plot_autocorrelation(acf_table, "günlük", _figure("autocorrelation_daily"))
    eda.plot_ramp_distribution(df_kt, _figure("ramp_distribution"))
    eda.plot_persistence_baseline(baseline, _figure("persistence_baseline"))
    eda.plot_rize_comparison(kt_table, seasonal, baseline, df_kt,
                             _figure("rize_comparison"))

    print(f"\n{len(WRITTEN)} dosya yazıldı → {EDA_DIR}")
    for path in WRITTEN:
        print("  ", path.relative_to(EDA_DIR.parent.parent))


if __name__ == "__main__":
    main()
