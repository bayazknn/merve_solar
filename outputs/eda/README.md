# Descriptive-statistics outputs (EDA) — how they were produced

This document records **how** each output under `outputs/eda/` was produced, what data it
covers, and which decision was taken against which pitfall.

**What the findings mean is not here; it is in `EDA.md` next to it.** The two are deliberately
separated: in an earlier round the findings narrative was kept in both documents and the result
was **15 separate inconsistencies** between the README and the CSV files. Interpretation now
lives in one place (`EDA.md`), production method in one place (here). In either document, if a
number and a file under `tables/` disagree, **the file wins**.

To reproduce:

```bash
uv run python scripts/01_prepare_base_data.py     # base_features.parquet (once)
uv run python scripts/02_descriptive_analysis.py  # every table and figure
```

## Input

| | |
|---|---|
| Source file | `SolarData_Merve(140926_V2).xlsx` (14 September 2026, V2) — **the repository's only data file** |
| Intermediate | `outputs/processed/base_features.parquet` |
| Span | 2019-06-30 00:00 → 2026-05-30 23:00 |
| Rows per province | 60,648 uninterrupted hourly rows (2,527 days) |
| Pooled | 303,240 rows; daylight subset **152,893** (50.42%) |
| Features | 13 |

**This file was taken with different settings from the July export** — units, parameter
selection and record length all changed, `CLRSKY_SFC_SW_DWN` is gone, and V2 additionally
dropped the 10 m wind. The full account is in `EDA.md` §0; no number here should be compared
with an earlier version without reading it.

**Solar geometry replaced the clear-sky column** (`src/merve_solar/solar.py`). There is no other
data file in the repository; everything derives from this Excel file and from astronomy.

- `solar_elevation` — apparent solar elevation at each hour's midpoint (degrees), computed from
  the province coordinates and the timestamp with the NREL algorithm. `> 0` means daylight, and
  `clamp_night_to_zero` acts on the same sign.
- `toa_horizontal` — top-of-atmosphere horizontal irradiance (W/m²), the denominator of the
  clearness index.

Both sit in the frame as **masks** and never enter the model as features.

---

## Seven method points to keep in mind when writing the paper

**1. "Daylight" is defined by computed solar elevation: `solar_elevation > 0`,** taken at the
midpoint of the hour. It is a function of (province, timestamp) only; it reads no measurement,
and in particular not the target.

Two alternatives were tried and rejected:

- *A `target > 0` threshold.* It agrees with the geometry on 303,204 of 303,240 rows here, and
  is still inadmissible: (a) it selects the denominator of the headline metrics using the
  answer — an overcast twilight hour reads zero and drops out exactly where the model is worst;
  (b) **it cannot be computed 24 h ahead**, which is precisely where `clamp_night_to_zero` has
  to decide. The second point is decisive: geometry is required regardless, and with geometry in
  hand a second definition for the metric would be incoherent. The full argument is at the top
  of `solar.py`.
- *A climatological (province, month, hour) cell mean > 0* was used in the first EDA round and
  **was wrong because it is too coarse** — see the *Correction log* at the bottom.

**The threshold is untuned.** Sweeping it finds a value that fits the target better (−2.0°, which
cuts disagreement from 3,034 rows to 587), but tuning a geometric mask against the target
destroys the reason the mask exists. The cost was measured: the climatology floor's daylight
RMSE moves 108.78 → 109.86.

**2. Monthly boxplots use daily totals, not hourly values.** Most of the width of a box drawn
from daylight *hourly* values is the within-day solar geometry, and the box narrows in winter —
so a reader concludes "winter is more stable". The truth is the opposite (see `EDA.md` §3.4).
Daily totals are also independent of the daylight filter, since night contributes exactly 0.

**3. The hour axis is per-province local solar time (LST), not a shared time zone.** Verification
and consequences are in `EDA.md` §2.1. Practical rules:

- Hour 11 is a different physical instant in Rize and in Ankara; **hours are never compared
  across provinces** — each province is read from its own panel.
- The hour label is the **start** of its interval; figures plot it at the interval centre
  (`HR + 0.5`).
- Axes are labelled "Local solar time (LST)".

**4. There are deliberately no p-values and no significance stars.** With n ≈ 153,000
autocorrelated hourly rows every |r| > 0.01 comes out "p < 0.001", while the effective sample
size is far smaller. Effect sizes and `partial_r_within_hour` are reported instead.

**5. The partial correlation (`partial_r_within_hour`) should be read before the raw one.** It is
the correlation after removing the (province, month, hour) cell mean, which separates the
weather signal from solar geometry. The difference is not merely large, it is **large enough to
flip signs** (`EDA.md` §6.1).

**6. Variable names are the raw column identifiers, not translations.** Figure axes and table
rows read `ALLSKY_SFC_SW_DWN`, `T2M`, `RH2M`, … with the unit in parentheses. The reason: a
reader has to be able to match an axis one-to-one with the NASA POWER documentation and with the
methods section's feature list, and a gloss breaks that chain. The mapping lives in
`paper_style.VARIABLE_LABELS` (with unit) and `VARIABLE_SHORT` (bare); in the descriptive tables
the column is called `variable_label`.

**7. Partial years do not enter the 3-D surface.** 2019 (starting 30 June) and 2026 (ending
30 May) are partial; `month_year_surface_*` and `month_year_anomaly_panel` use complete calendar
years only (2020–2025).

---

## Tables (`tables/`)

**Scope rule: with one exception every table uses the whole record** — 2019-06-30 → 2026-05-30,
60,648 hours / 2,527 days per province, 303,240 rows pooled (daylight subset 152,893). The one
exception is `monthly_target_stats.csv`, which is the data behind the last-12-months boxplot and
is deliberately limited to 2025-06 → 2026-05. Two exceptions exist among the figures:
`monthly_boxplot_last12m_*` (last 12 months) and `month_year_surface_*` /
`month_year_anomaly_panel` (2020–2025 only).

| File | Contents | Scope |
|---|---|---|
| `descriptive_stats_by_city_daylight.csv/.md/.tex` | **Primary table.** Daylight hours, per province + pooled. | full record (daylight, n = 152,893) |
| `descriptive_stats_by_city_24h.csv/.md/.tex` | The same table over 24 hours — this is the distribution the model is trained on. | full record (n = 303,240) |
| `temporal_coverage_by_city.csv` | Coverage, hour/day counts, daylight share, mean daylight duration by season, seasonal summaries of the target. | full record |
| `target_by_hour_by_city.csv` | The target's (province, season, LST hour) distribution — the data behind the diurnal-profile figure. | full record |
| `time_feature_explained_variance.csv` | η² and harmonic R² for hour and day of year. Reported instead of a Pearson *r* against the sin/cos columns, because a correlation against a deterministic function of the hour is not interpretable. | full record (both 24 h and daylight) |
| `wind_direction_circular_stats.csv` | Circular statistics for wind direction (see below). | full record (24 h, speed > 1 m/s) |
| `correlation_pearson_<province>.csv`, `correlation_spearman_<province>.csv`, `..._pooled.csv` | Correlation matrices of the 7 physical variables. | full record (daylight) |
| `target_correlation_by_city.csv` | Raw correlation with the target plus `partial_r_within_hour`. | full record (daylight) |
| `collinear_pairs.csv` | Pairs with \|r\| > 0.9. **Empty since V2** (the only such pair was `WS2M`–`WS10M`); an empty table is a finding here, not an error, and the header row is preserved. | full record (daylight) |
| `seasonal_target_stats.csv` | Hourly and daily-total summaries by season. | full record (2,527 days/province) |
| `daily_clearness_by_city.csv` | **Empirical** clearness ratio (daily total ÷ the observed 95th percentile for that day of year) and clear/overcast day shares — compares provinces on cloudiness rather than latitude. | full record (2,525 days/province; 29 February dropped for alignment) |
| `monthly_target_stats.csv` | Daily-total summaries for the last 12 months — the boxplot's data. | **2025-06 → 2026-05 ONLY** |
| `clearness_index_by_city.csv` | **Standard** clearness index kt = GHI / (I₀ cos θz), hourly and daily, province × season. Hourly values are restricted to `toa_horizontal > 20 W/m²` (the division blows up at twilight). Sky-condition cut-offs are the literature's bands for this index: clear kt > 0.65, overcast kt < 0.35. | full record |
| `autocorrelation_clearness.csv` | ACF and PACF of kt, hourly (lags 1–72) and daily (1–30). The evidence behind `lookback_hours`. | full record |
| `ramp_stats_by_city.csv` | Distribution of hourly \|Δirradiance\| and \|Δkt\|, province × season. | full record (daylight) |
| `daylight_block_structure.csv` | Lengths of the uninterrupted blocks that would remain if night rows were deleted. | full record (daylight) |
| `persistence_baseline.csv` | Reference floor: RMSE/MAE/R²/bias for persistence and climatology. Smart persistence was removed (`EDA.md` §0.3). This table is a descriptive twin; the numbers destined for the paper come from `scripts/03_run_naive_baselines.py`, which runs through the pipeline and therefore differs in the last decimals (it counts scored elements where this counts hours). | **the model's test window** (after val_end, 9,097 hours/province) |

Three reading notes:

**Kurtosis is Fisher's excess definition** — 0 for a normal distribution, not 3.

**The pooled ("All") row's standard deviation** mixes within-province and between-province
variance; the between-province component is given separately in the `between_city_sd` column.

**Wind direction is kept out of the main table:** the arithmetic mean of a circular variable is
meaningless. A separate table gives the speed-weighted circular mean, the resultant length *R*
(0 = no preferred direction, 1 = a single direction) and the circular SD; calm hours with the
corresponding speed column ≤ 1 m/s are excluded and the excluded count is recorded in the table.
The direction climatology is not restricted to daylight; it is computed over all 24 hours.

## Figures (`figures/`)

Every figure is written both as `.png` (300 dpi) and `.pdf` (vector, Type 42 fonts). The
background is white everywhere; seasons are distinguished by colour **and** line style, so
identity survives greyscale printing and colour-vision deficiency.

| File | What it shows | Filter |
|---|---|---|
| `correlation_heatmap_<province>`, `_pooled` | Correlation matrix of the 7 variables | daylight |
| `target_correlation_panel` | Variable × province, correlation with the target | daylight |
| `scatter_vs_target_<province>` | Each variable against the target plus a binned-median trend | daylight |
| `monthly_boxplot_last12m_<province>`, `_panel` | Daily totals over the last 12 months | 24 h (totals) |
| `month_year_surface_<province>`, `_panel` | 3-D month × year × irradiance surface, 2020–2025 | 24 h (totals) |
| `month_year_anomaly_panel` | The same data as a 2-D anomaly view | 24 h (totals) |
| `seasonal_diurnal_profile` | Diurnal profile by season, LST hour | **24 h** |
| `seasonal_dayofyear` | Day of year × daily total, banded by season | 24 h (totals) |
| `target_histogram` | Distribution of daylight irradiance per province | daylight |
| `monthly_boxplot_all_years` | Boxplot by month, all years pooled | 24 h (totals) |
| `autocorrelation_hourly`, `autocorrelation_daily` | ACF/PACF of kt, per province | daylight (hours where kt is defined) |
| `ramp_distribution` | Cumulative distribution of \|hour-to-hour change\|, by season | daylight |
| `persistence_baseline` | The RMSE and R² floor the model has to clear | daylight |
| `rize_comparison` | Four-panel summary of Rize against the other four provinces | mixed (stated per panel) |

**The scatter panel's grid is derived from the feature set.** The number of raw meteorological
variables has changed twice (8 → 7 → 6). The grid is now computed from `RAW_METEO_COLUMNS`: the
column count is chosen from 4 or 3 to minimise empty cells, and any surplus axes are switched
off.

**The diurnal-profile figure deliberately does not apply the daylight filter:** the night zeros
are physical information, and filtering them makes the curve start and end away from zero and
produces an artificial jump in sparsely-sampled hours such as winter mornings. The IQR band is
drawn for Winter and Summer only (four overlapping bands are unreadable) and it is the
**between-day IQR, not a confidence interval**.

**The 3-D surface is misleading on its own** and must be read together with
`month_year_anomaly_panel`: most of the surface's relief is the seasonal curve repeated six
times, and the figure that actually shows the between-year signal is the anomaly map.

In `seasonal_dayofyear`, **29 February is dropped** and days after March in leap years are
shifted back by one; otherwise 2020 and 2024 slip by a day against the other years and the
climatology blurs. The smoothing is a 7-day centred moving average of the per-day climatological
mean, computed on the series tiled 3×, so there is no discontinuity at the 31 December /
1 January seam.

## Season definition

Meteorological seasons: **Winter** = December, January, February · **Spring** = March, April,
May · **Summer** = June, July, August · **Autumn** = September, October, November.

---

## Correction log

### 2026-09-14 (c) — figures, tables and EDA.md switched to English

The manuscript will be written in English, so the artifacts follow. Figure titles, axis labels,
legend titles and the Turkish values inside tables are all translated, and `EDA.md` is rewritten
in English.

**Table values changed, not only labels.** Anything reading these CSVs must know:

| Column | Before | After |
|---|---|---|
| pooled row label | `Tümü` | `All` |
| `scope` | `24 saat`, `gündüz` | `24h`, `daylight` |
| `reference` | `kalıcılık`, `klimatoloji` | `persistence`, `climatology` |
| `resolution` | `saatlik`, `günlük` | `hourly`, `daily` |
| `factor` | `saat (LST)`, `yılın günü` | `hour (LST)`, `day of year` |
| `season` | `Kış`, `İlkbahar`, `Yaz`, `Sonbahar` | `Winter`, `Spring`, `Summer`, `Autumn` |
| `ym_label` | `Haz 25` | `Jun 25` |

In the code, `SEASONS_TR` / `MONTH_TO_SEASON_TR` / `MONTH_ABBR_TR` became `SEASONS` /
`MONTH_TO_SEASON` / `MONTH_ABBR`, and the season colour/linestyle dictionaries were re-keyed to
match. No number moved.

### 2026-09-14 (b) — the V2 export: 10 m wind removed, 13 features

`SolarData_Merve(140926).xlsx` → `SolarData_Merve(140926_V2).xlsx`. Every shared column is
bit-identical and the `-999` tail is the same 744 hours, so nothing about the target, the
geometry or the splits moves. V2 simply drops `WS10M` and `WD10M`.

This is the reduction the EDA had been arguing for. Measured on V1: `WS2M`–`WS10M` r = 0.987,
`WD2M` vs `WD10M` agreeing to a median 0.30° with sin/cos correlations of 0.996. The naive floor
is unchanged to the decimal after the drop, which is the cleanest possible evidence that the
dropped columns carried nothing.

Side effect worth knowing: `collinear_pairs.csv` is now empty, because that pair was the only
one above |r| = 0.9.

### 2026-09-14 (a) — the dataset changed and the whole EDA was regenerated

Source file `SolarData_Merve_All(16July).xlsx` → the 14 September export. Same NASA POWER record,
different export settings. Every number in this folder was regenerated; no figure quoted from an
earlier version is valid.

| | Before | After |
|---|---|---|
| Target unit | W/m² | MJ/m²/hour → converted to W/m² at read time |
| Precipitation unit | mm/day | mm/hour |
| Feature count | 17 | **13** (`QV2M`, the 50 m and 10 m wind gone; 2 m wind added) |
| Daylight definition | `CLRSKY_SFC_SW_DWN > 0` | **`solar_elevation > 0`** (computed) |
| Clearness index | `ALLSKY / CLRSKY` | **`GHI / (I₀ cos θz)`** (the standard definition) |
| Record end | 2026-03-30 | 2026-05-30 (+61 days) |
| Rows per province | 59,184 | 60,648 |
| Daylight rows / share | 151,643 / 51.2% | 152,893 / 50.42% |
| Test window | 8,878 hours / 370 days | 9,097 hours / 379 days |
| Naive floor (daylight) | clim. 106.8 / pers. 116.4 | clim. **109.86** / pers. **121.56** |

**The old Excel file (`SolarData_Merve_All(16July).xlsx`) was deleted from the repository.** An
intermediate version reconstructed `CLRSKY_SFC_SW_DWN` from it; that bridge was removed and solar
geometry took its place, so the project depends on a single data file. This has two costs, both
measured and accepted: the daylight mask shifts by 1% (climatology RMSE 108.78 → 109.86), and the
two analyses that needed the clear-sky **magnitude** — the smart-persistence reference and the
`clearsky_index` target transform — were removed. The reasoning is in `EDA.md` §0.2 and §0.3.

Two statements previously written in this document were also corrected:

1. *"Clear-sky irradiance is a purely geometric quantity."* Measured and found too strong: even
   at a fixed solar position NASA POWER's value moves 4–8% across years. Only its **sign** was
   geometric. This is now a historical note — the column is out of use entirely, replaced by
   computed solar elevation, which really is pure geometry.
2. *"The unit label on `PRECTOTCORR` is suspect."* Resolved: the old file was mm/day, the new one
   is mm/hour. The "mm/hour" label was wrong for the old data and is correct for the new.

### 2026-08-28 — the daylight definition changed

In the first EDA round daylight was defined by a climatological (province, month, hour) cell
mean. The stated reason — that an `irradiance > 0` threshold conditions on the dependent
variable — was correct, but the chosen remedy was not: **the cell was far too coarse.**

Sunrise and sunset shift 30–60 minutes within a single month, so the cell's edge hour is lit for
part of the month and dark for the rest; the cell mean counted the whole hour as daylight. The
result was that **5,266 rows** whose clear-sky value was exactly zero — i.e. night — entered the
daylight subset and pulled every province's daylight mean down by 10–14 W/m².

None of the qualitative conclusions changed in that round. The numbers in this entry belong to
the 16 July data version and stand only as a historical record.
