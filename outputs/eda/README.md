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
| Source file | `SolarData_Merve(031026_V3).xlsx` (3 October 2026, V3) — the file every table and figure here is built from |
| Intermediate | `outputs/processed/base_features.parquet` |
| Span | 2019-06-30 00:00 → 2026-06-29 23:00 |
| Rows per province | 61,368 uninterrupted hourly rows (2,557 days) |
| Pooled | 306,840 rows; descriptive subset (`target > 0`) **158,111** (51.53%); geometric daylight **155,081** (50.54%) |
| Features | 13 |

**V3 differs from V2 in two ways:** the target `ALLSKY_SFC_SW_DWN` is now stored directly in
W/m² (V2 stored MJ/m²/hour and was converted at read time), and the record is 30 days longer.
Every meteorological column is bit-identical to V2. Earlier, the 14 September export had changed
units, parameter selection and record length relative to the July export, `CLRSKY_SFC_SW_DWN`
was gone, and V2 additionally dropped the 10 m wind. The full account is in `EDA.md` §0; no
number here should be compared with an earlier version without reading it.

**Solar geometry replaced the clear-sky column** (`src/merve_solar/solar.py`). Everything derives
from the Excel file and from astronomy. (The V2 workbook may still sit in the repository root for
reference; no table here reads it.)

- `solar_elevation` — apparent solar elevation at each hour's midpoint (degrees), computed from
  the province coordinates and the timestamp with the NREL algorithm. `> 0` means geometric
  daylight, the subset the modelling side is scored on, and `clamp_night_to_zero` acts on the same
  sign. The tables and figures in this folder do **not** use that mask for their daytime subset;
  they use `target > 0` (method point 1).
- `toa_horizontal` — top-of-atmosphere horizontal irradiance (W/m²), the denominator of the
  clearness index.

Both sit in the frame as **masks** and never enter the model as features.

---

## Seven method points to keep in mind when writing the paper

**1. Two subsets, two jobs.** The descriptive EDA and the forecasting evaluation do not use the same
daytime subset, on purpose.

- *Descriptive subset: `target > 0`* (`eda.positive_mask`; scope name `positive`, label "hours with
  target > 0"; since 2026-10-04). Every table and figure here that restricts to daytime keeps the
  rows whose recorded `ALLSKY_SFC_SW_DWN` is strictly positive. Describing recorded data may
  condition on the recorded value. The rule also drops NASA POWER's `-999` marker (negative), but
  none is present after the trim and no negative value exists. It removes 148,729 of 306,840 rows
  (48.47%) and keeps 158,111 (51.53%): per province Ankara 31,750, Antalya 31,399, Konya 31,701,
  Rize 31,567, Van 31,694 kept (`target_positive_filter_audit.csv`).
- *Evaluation subset: geometric daylight*, `solar_elevation > 0` at the midpoint of the hour, 155,081
  rows (50.54%). It is a function of (province, timestamp) only. Model metrics, the night clamp and
  `scripts/03_run_naive_baselines.py` (the ledger) use it, **because `target > 0` picks the
  denominator of a metric using the answer** (an overcast twilight hour reads zero and drops out
  exactly where the model is worst) **and cannot be computed 24 h ahead**, which is precisely where
  `clamp_night_to_zero` has to decide. The second point is decisive. The full argument is at the top
  of `solar.py`.

The two subsets differ by 3,030 twilight rows (1.9% of the kept rows, 0.024% of the kept energy):
`target > 0` keeps them (the sun is up to 2.4° below the horizon at the interval midpoint, local solar
hours 04–07 and 16–19, target 0.80–11.68 W/m², mean 4.74) and the geometric mask drops them.
No geometric-daylight row reads zero, so the `target > 0` subset contains the geometric one. The
rule that follows: **a descriptive number is never quoted as a model-side number.** In particular
`persistence_baseline.csv` is a descriptive twin on `target > 0` rows, not the pipeline's floor.

A climatological (province, month, hour) cell mean > 0 was used in the first EDA round and **was
wrong because it is too coarse** — see the *Correction log* at the bottom.

**The geometric threshold is untuned.** Sweeping it finds a value that fits the target better
(−2.0°, which cuts disagreement with `target > 0` from 3,030 rows to 456 on V3), but tuning a
geometric mask against the target destroys the reason the mask exists. The cost was measured in the
September round, when the clear-sky column was still available: the climatology floor's daylight RMSE
moved 108.78 → 109.86. That comparison cannot be repeated on V3 (neither current export has the
clear-sky column).

**2. Monthly boxplots use daily totals, not hourly values.** Most of the width of a box drawn
from daylight *hourly* values is the within-day solar geometry, and the box narrows in winter —
so a reader concludes "winter is more stable". The truth is the opposite (see `EDA.md` §3.4).
Daily totals are also independent of the subset filter, since night contributes exactly 0 and the twilight rows add under 0.03% of the energy.

**3. The hour axis is per-province local solar time (LST), not a shared time zone.** Verification
and consequences are in `EDA.md` §2.1. Practical rules:

- Hour 11 is a different physical instant in Rize and in Ankara; **hours are never compared
  across provinces** — each province is read from its own panel.
- The hour label is the **start** of its interval; figures plot it at the interval centre
  (`HR + 0.5`).
- Axes are labelled "Local solar time (LST)".

**4. There are deliberately no p-values and no significance stars.** With n ≈ 158,000
autocorrelated hourly rows every |r| > 0.01 comes out "p < 0.001", while the effective sample
size is far smaller. Effect sizes and `partial_r_within_hour` are reported instead.

**5. The partial correlation (`partial_r_within_hour`) should be read before the raw one.** It is
the correlation after removing the (province, month, hour) cell mean, which separates the
weather signal from solar geometry. The difference is not merely large, it is **large enough to
flip signs** (`EDA.md` §6.1).

**6. Figures and tables use the raw column identifiers.** Axis titles and ticks read
`ALLSKY_SFC_SW_DWN (W/m²)`, `T2M (°C)`, `RH2M (%)`, … exactly as in the tables; variable names
are never renamed. The mappings live in `paper_style.AXIS_LABELS` (with unit) and `AXIS_SHORT`
(bare, for correlation-matrix ticks) for figures, and `paper_style.VARIABLE_LABELS` for tables,
where the column is called `variable_label`.

Figures are sized for a Word page: 6.3 in wide (the A4 text block at 2.5 cm margins; Letter's is
6.5 in), with 7 pt ticks, 8 pt axis titles and a 9 pt figure title, so they paste at 100% and
print at those sizes. Every panel of a multi-panel figure carries its own x tick labels. Box
plots tick months by three-letter name at 5.5 pt and carry no x title; other month axes use
initials (J F M …). Each box is filled by its month's median daily irradiation on the plasma
colour map (cut before its palest yellow), with one scale shared by every panel of a figure and
a colour bar alongside, so a cloudier province reads as darker. Colour follows the median, not
the month, because plasma is sequential and would otherwise set January and December at
opposite ends.

**7. Partial years do not enter the 3-D surface.** 2019 (starting 30 June) and 2026 (ending
29 June) are partial; `month_year_surface_*` and `month_year_anomaly_panel` use complete calendar
years only (2020–2025).

---

## Tables (`tables/`)

**Scope rule: with one exception every table uses the whole record** — 2019-06-30 → 2026-06-29,
61,368 hours / 2,557 days per province, 306,840 rows pooled (`target > 0` subset 158,111). The one
exception is `monthly_target_stats.csv`, which is the data behind the last-12-months boxplot and
is deliberately limited to 2025-07 → 2026-06 (the final month stops on 29 June: 29 days). Two exceptions exist among the figures:
`monthly_boxplot_last12m_*` (last 12 months) and `month_year_surface_*` /
`month_year_anomaly_panel` (2020–2025 only).

| File | Contents | Scope |
|---|---|---|
| `descriptive_stats_by_city_positive.csv/.md/.tex` | **Primary table.** Hours with `target > 0`, per province + pooled. One row per (province, statistic: N, Mean, SD, Min, Q1, Median, Q3, Max), one column per variable. | full record (`target > 0`, n = 158,111) |
| `descriptive_stats_by_city_24h.csv/.md/.tex` | The same table over 24 hours — this is the distribution the model is trained on. | full record (n = 306,840) |
| `temporal_coverage_by_city.csv` | Coverage, hour/day counts, `positive_hour_share`, `mean_positive_hours_per_day` by season, `target_mean_24h` / `target_mean_positive`, daily totals. | full record |
| `target_by_hour_by_city.csv` | The target's (province, season, LST hour) distribution — the data behind the diurnal-profile figure. | full record |
| `time_feature_explained_variance.csv` | η² and harmonic R² for hour and day of year. Reported instead of a Pearson *r* against the sin/cos columns, because a correlation against a deterministic function of the hour is not interpretable. | full record (`scope` = `24h` and `positive`) |
| `wind_direction_circular_stats.csv` | Circular statistics for wind direction (see below). | full record (24 h, speed > 1 m/s) |
| `correlation_pearson_<province>.csv`, `correlation_spearman_<province>.csv`, `..._pooled.csv` | Correlation matrices of the 7 physical variables. | full record (`target > 0`) |
| `target_correlation_by_city.csv` | Raw correlation with the target plus `partial_r_within_hour`. | full record (`target > 0`) |
| `collinear_pairs.csv` | Pairs with \|r\| > 0.9. **Empty since V2** (the only such pair was `WS2M`–`WS10M`); an empty table is a finding here, not an error, and the header row is preserved. | full record (`target > 0`) |
| `seasonal_target_stats.csv` | Hourly (`hourly_mean_24h`, `hourly_mean_positive`) and daily-total summaries by season. | full record (2,557 days/province; hourly means 24 h and `target > 0`) |
| `daily_clearness_by_city.csv` | **Empirical** clearness ratio (daily total ÷ the observed 95th percentile for that day of year) and clear/overcast day shares — compares provinces on cloudiness rather than latitude. | full record (2,555 days/province; 29 February dropped for alignment) |
| `monthly_target_stats.csv` | Daily-total summaries for the last 12 months — the boxplot's data. | **2025-07 → 2026-06 ONLY** |
| `clearness_index_by_city.csv` | **Standard** clearness index kt = GHI / (I₀ cos θz), hourly and daily, province × season. Hourly values are restricted to `toa_horizontal > 20 W/m²` (the division blows up at twilight) and to `target > 0` (no row is affected by the second condition on this record, so the table is numerically identical to the geometric-mask version). Sky-condition cut-offs are the literature's bands for this index: clear kt > 0.65, overcast kt < 0.35. | full record |
| `autocorrelation_clearness.csv` | ACF and PACF of kt, hourly (lags 1–72) and daily (1–30). The evidence behind `lookback_hours`. | full record |
| `ramp_stats_by_city.csv` | Distribution of hourly \|Δirradiance\| and \|Δkt\|, province × season. | full record (`target > 0`) |
| `positive_block_structure.csv` | Lengths of the uninterrupted blocks that would remain if the rows with `target = 0` were deleted (column `n_positive_hours`). | full record (`target > 0`) |
| `target_positive_filter_audit.csv` | What the `target > 0` filter does, per province + pooled (`All`): rows, `-999` sentinels (0), negatives (0), zeros removed, kept rows and shares, geometric-daylight rows, geometric-daylight rows reading zero (0), and the 3,030 twilight rows that `target > 0` keeps and the geometric mask drops (count, share of kept, mean, max). | full record |
| `persistence_baseline.csv` | Reference forecasts: RMSE/MAE/R²/bias for persistence and climatology, `scope` = `24h` or `positive` (`target > 0`; the old value `daylight` is gone). Smart persistence was removed (`EDA.md` §0.3). This table is a descriptive twin **on `target > 0` rows, not the pipeline floor** (the pipeline scores geometric daylight, 449 fewer test-window hours); the numbers destined for the paper come from `scripts/03_run_naive_baselines.py`, which runs through the pipeline and therefore differs in the last decimals (it counts scored elements where this counts hours). **The two naive rows now in `outputs/experiments_ledger.csv` were produced on V2 data and are stale until that script is re-run on V3** (`EDA.md` §8). | **the model's test window** (after val_end, 9,206 hours/province) |

Three reading notes:

**The pooled ("All") block's standard deviation** mixes within-province and between-province
variance, so it is larger than any single province's.

**Wind direction is kept out of the main table:** the arithmetic mean of a circular variable is
meaningless. A separate table gives the speed-weighted circular mean, the resultant length *R*
(0 = no preferred direction, 1 = a single direction) and the circular SD; calm hours with the
corresponding speed column ≤ 1 m/s are excluded and the excluded count is recorded in the table.
The direction climatology is not restricted to the `target > 0` subset; it is computed over all 24 hours.

## Figures (`figures/`)

Every figure is written both as `.png` (300 dpi) and `.pdf` (vector, Type 42 fonts). The
background is white everywhere; seasons are distinguished by colour **and** line style, so
identity survives greyscale printing and colour-vision deficiency.

| File | What it shows | Filter |
|---|---|---|
| `correlation_heatmap_<province>`, `_pooled` | Correlation matrix of the 7 variables | `target > 0` |
| `target_correlation_panel` | Variable × province, correlation with the target | `target > 0` |
| `scatter_vs_target_<province>` | Each variable against the target plus a binned-median trend | `target > 0` |
| `monthly_boxplot_last12m_<province>`, `_panel` | Daily totals over the last 12 months | 24 h (totals) |
| `month_year_surface_<province>`, `_panel` | 3-D month × year × irradiance surface, 2020–2025, coloured by height on the box plots' plasma scale; `_panel` is two columns × three rows with the colour bar in the sixth cell | 24 h (totals) |
| `month_year_anomaly_panel` | The same data as a 2-D anomaly view | 24 h (totals) |
| `seasonal_diurnal_profile` | Diurnal profile by season, LST hour | **24 h** |
| `seasonal_dayofyear` | Day of year × daily total, banded by season | 24 h (totals) |
| `target_histogram` | Distribution of irradiance over hours with `target > 0`, per province | `target > 0` |
| `monthly_boxplot_all_years` | Boxplot by month, all years pooled | 24 h (totals) |
| `autocorrelation_hourly`, `autocorrelation_daily` | ACF/PACF of kt, per province | `target > 0` (hours where kt is defined) |
| `ramp_distribution` | Cumulative distribution of \|hour-to-hour change\|, by season | `target > 0` |
| `persistence_baseline` | RMSE and R² of the reference forecasts (descriptive twin, not the pipeline floor) | `target > 0` |
| `rize_comparison` | Four-panel summary of Rize against the other four provinces | mixed (stated per panel) |

**The scatter panel's grid is derived from the feature set.** The number of raw meteorological
variables has changed twice (8 → 7 → 6). The grid is now computed from `RAW_METEO_COLUMNS`: the
column count is chosen from 4 or 3 to minimise empty cells, and any surplus axes are switched
off.

**The diurnal-profile figure deliberately does not apply the `target > 0` filter:** the night zeros
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

### 2026-10-04 — EDA subset changed from geometric daylight to `target > 0`

Every descriptive output that restricted to daytime used the geometric mask (`solar_elevation > 0`,
155,081 rows). It now uses `target > 0` (158,111 rows, 51.53%; `eda.positive_mask`, scope name
`positive`). Modelling, evaluation, the night clamp, `scripts/03_run_naive_baselines.py` and the
ledger are **unchanged** and still use geometric daylight: `target > 0` conditions on the outcome and
cannot be formed 24 h ahead (method point 1). `scripts/02_descriptive_analysis.py` was re-run; every
table and figure listed below was regenerated, and figure titles now read "(hours with target > 0)".

| | Before | After |
|---|---|---|
| Descriptive daytime subset | geometric daylight, 155,081 rows (50.54%) | `target > 0`, 158,111 rows (51.53%) |
| Rows removed | 151,759 (night, geometric) | 148,729 (`target = 0`; no `-999`, no negatives) |
| Disagreement | | 3,030 twilight rows kept by `target > 0` only; 0 geometric-daylight rows read zero |
| `descriptive_stats_by_city_daylight.*` | | renamed `descriptive_stats_by_city_positive.*` |
| `daylight_block_structure.csv` | column `n_daylight_hours` | renamed `positive_block_structure.csv`, column `n_positive_hours` |
| `temporal_coverage_by_city.csv` | `daylight_hour_share`, `mean_daylight_hours_per_day`, `target_mean_daylight` | `positive_hour_share`, `mean_positive_hours_per_day`, `target_mean_positive` |
| `seasonal_target_stats.csv` | `hourly_mean_daylight` | `hourly_mean_positive` |
| `scope` in `time_feature_explained_variance.csv`, `persistence_baseline.csv` | `daylight` | `positive` |
| New table | | `target_positive_filter_audit.csv` |

What moved (pooled): target mean over the daytime subset 385.98 → 378.67 W/m² (sd 278.58 → 280.80,
median 343.70 → 334.58); hour-of-day η² within the subset 48.9% → 50.4%, day-of-year 14.8% → 14.4%;
raw / partial correlation with the target: `T2M` +0.515 / +0.307 → +0.517 / +0.305, `RH2M` −0.626 /
−0.529 → −0.627 / −0.523, `PS` −0.038 / +0.268 → −0.035 / +0.266, `T2MDEW` +0.045 / −0.272 → +0.045 /
−0.269, `WS2M` +0.142 / −0.148 → +0.154 / −0.148, `PRECTOTCORR` −0.168 / −0.328 → −0.162 / −0.326; the
descriptive reference forecasts on the test window, climatology RMSE / MAE / R² 108.00 / 74.17 /
0.8528 → 106.99 / 72.84 / 0.8577 and persistence 120.90 / 71.59 / 0.8155 → 119.76 / 70.27 / 0.8217
(24 h rows unchanged); the precipitation zero share 66.6% → 66.7%; the median ramp |Δ irradiance|
by province (Ankara 106.4 → 104.9 W/m², Rize 83.1 → 82.2); the block lengths (Rize median block
12 → 13 h, shortest block 9 → 10 h at Ankara and Konya). **Numerically unchanged:** the
clearness-index and autocorrelation tables, `descriptive_stats_by_city_24h.*`, the 24 h seasonal
and diurnal summaries, `wind_direction_circular_stats.csv`, the daily totals and CVs.

The descriptive reference-forecast twin is no longer on the same subset as the pipeline floor; the
pipeline floor on V3 still has to be produced by re-running `scripts/03_run_naive_baselines.py`
(`EDA.md` §8). `EDA.md` §0.2, §3.2 and §10(12) carry the argument; the few numbers computed outside
`tables/` (twilight sd and minimum, energy share) are listed in `EDA.md` §11.

### 2026-10-03 — the V3 export: target stored in W/m², record 30 days longer

`SolarData_Merve(140926_V2).xlsx` → `SolarData_Merve(031026_V3).xlsx` (export dated 3 October
2026). The meteorological columns are bit-identical to V2 over the shared hours; two things
changed, and every table and figure in this folder was regenerated.

| | V2 (14 Sep) | V3 (3 Oct) |
|---|---|---|
| Target unit in the file | MJ/m²/hour, converted to W/m² at read time (× 277.78) | **W/m², two decimals** (no conversion) |
| Distinct target values | 387 (quantised to 2.78 W/m² steps) | **38,385** pooled |
| Last valid hour | 2026-05-30 23:00 | **2026-06-29 23:00** |
| `-999` tail | 744 hours | **24 hours** (2026-06-30) |
| Rows per province | 60,648 (2,527 days) | **61,368 (2,557 days)** |
| Rows pooled / daylight | 303,240 / 152,893 (50.42%) | **306,840 / 155,081 (50.54%)** |
| Train | 2019-06-30 → 2024-08-11 (44,879 h) | **2019-06-30 → 2024-09-03 03:00 (45,412 h)** |
| Validation | 2024-08-12 → 2025-05-16 (6,671 h) | **2024-09-03 04:00 → 2025-06-11 09:00 (6,750 h)** |
| Test | 2025-05-16 → 2026-05-30 (9,097 h / 379 days) | **2025-06-11 10:00 → 2026-06-29 23:00 (9,206 h / 383.6 days)** |
| Validation seasons | no June, no July | **no July, no August; June only 1–11 (250 h per province)** |
| Naive floor, daylight (descriptive twin) | clim. 109.83 / pers. 121.85 | clim. **108.00** / pers. **120.90** |

What this means for the folder:

- **The V2 quantisation story is gone.** No unit conversion, no 2.78 W/m² grid, no "387 distinct
  values", and no daylight-but-zero rows (V2's EDA reported one).
  Ramp statistics are no longer multiples of 2.78 W/m².
- **Test-window composition changed.** June now appears twice in the test window, so Summer
  carries 28.8% of its hours (per province: Summer 2,654, Spring 2,208, Autumn 2,184, Winter
  2,160). The previous statement "the validation window contains no June and no July" is
  replaced by the V3 fact above.
- **Ledger rows are stale.** `outputs/experiments_ledger.csv` holds the two naive rows produced on
  V2; they stay stale until `scripts/03_run_naive_baselines.py` is re-run on V3. `EDA.md` §8
  quotes the descriptive twin (`persistence_baseline.csv`) in the meantime and says so.
- **Not re-measurable on V3:** the cost of the untuned geometric threshold (it needed the clear-sky
  column, 108.78 → 109.86) and the precipitation-resolution loss against the July export. Both
  are quoted in `EDA.md` as historical measurements.
- **Statements corrected while re-checking `EDA.md`** (they were wrong before V3, not because of
  it): the number of variables with inconsistent raw-correlation signs is two (`PS`, `WS2M`), not
  three; the binary rain indicator is the strongest precipitation encoding in four provinces,
  not three; and the old "agrees with the geometry on 303,204 of 303,240 rows" did not match
  the 2,969 disagreements reported next to it.
- **Date bookkeeping:** `monthly_target_stats.csv` now covers 2025-07 → 2026-06 (June 2026 stops on
  the 29th); the 3-D surfaces still use complete calendar years 2020–2025 only.

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
