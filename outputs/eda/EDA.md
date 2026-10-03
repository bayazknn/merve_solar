# Exploratory data analysis — findings and interpretation

**Data version:** `SolarData_Merve(031026_V3).xlsx` (3 October 2026, V3) — the file every
number below comes from.
**Document date:** 3 October 2026. All earlier versions are superseded; the V2 export
(`SolarData_Merve(140926_V2).xlsx`) is superseded as well and no number here may be mixed with it.

This document explains **what the tables and figures under `outputs/eda/` say**. It is written
for the paper's co-authors: each section carries everything you need in order to quote its
numbers into the manuscript, without having to open a second technical document. *How* the
outputs were produced — code, filters, scope rules — is in `README.md` next to it.

How to read it:

- Every number comes from a file under `outputs/eda/tables/`. §11 maps each claim to its file.
  **If the text and the file disagree, the file wins.**
- Sentences marked **Caveat** are constraints that must travel with the number. Quoted alone,
  the number misleads.
- Sentences marked **Recommendation** are modelling interpretations drawn from the data. They
  are not yet tested results.
- **Figures and tables name variables by their raw NASA POWER column** (`ALLSKY_SFC_SW_DWN`,
  `T2M`, `RH2M`, …) with the unit in parentheses, so a reader can match an axis to the dataset
  documentation and to the methods section's feature list.

---

## 0. Read this first: how the data and two definitions have changed

The current file is the **3 October 2026 export (V3)**. It is the same NASA POWER record as the
14 September export (V2): over the hours the two share, every meteorological column is
bit-identical. Two things differ: **the target is now stored directly in W/m²**, and **the record
is 30 days longer**. Behind that sit the changes of the 14 September round, when the export
settings changed units, parameter list and span relative to the July export; one of the
parameters that disappeared was this project's most-used instrument, so two **definitions**
changed with it (§0.2). None of the numbers below is comparable to an earlier version.

### 0.1 Units: the target is stored in W/m² (no conversion any more)

| Column | V2 (14 Sep) | V3 (current) | What we do |
|---|---|---|---|
| `ALLSKY_SFC_SW_DWN` (target) | MJ/m²/hour, converted to W/m² at read time (× 277.78) | **W/m², two decimals** | Read as is |
| `PRECTOTCORR` | mm/hour | mm/hour | Left as is |

V3 therefore needs no unit conversion, and the manuscript, the source paper and the irradiance
literature all use W/m² as well. The change was checked by joining V2 and V3 on timestamp over
the 60,648 hours per province (303,240 rows) for which both hold a valid target: V2 converted
(× 277.78) differs from V3 by at most **1.40 W/m²** (mean 0.36), which is the rounding of V2's
two-decimal MJ values. `T2M`, `T2MDEW`, `RH2M`, `PS`, `WS2M`, `WD2M` and `PRECTOTCORR` differ by
exactly 0 over those rows (§11).

**What disappears with it.** The V2 target was **quantised to 2.78 W/m² steps** (387 distinct
values over the whole record). V3 holds **38,385 distinct values** pooled (19,007 – 20,991 per
province) at 0.01 W/m² resolution, so the quantisation caveat that used to travel with the
target, its effect on the daylight definition (§3.2) and its effect on the ramp statistics (§5.3)
no longer apply.

**Caveat — precipitation resolution is unchanged and still coarse.** The 14 September round
moved `PRECTOTCORR` from mm/day (July export) to mm/hour, which cut the resolution from 0.01
mm/day to 0.24 mm/day-equivalent; at the time, 38.7% of the hours that used to read as rainy
read exactly zero. That comparison was made against the July export, which is no longer in the
repository, and was **not re-verified for this version**. V3's smallest non-zero value is
0.01 mm/hour and 66.6% of daylight hours are exactly zero (§4.1).

### 0.2 `CLRSKY_SFC_SW_DWN` is gone — solar geometry replaced it

Clear-sky irradiance was never a feature in this project, but it was load-bearing in four
places: it defined the daylight subset, it was the instrument behind the night clamp, it was the
denominator of the clearness index, and it was the multiplier in the smart-persistence
reference.

The new export does not contain it. **Rather than reaching back into the superseded workbook, we
compute what is needed** (`src/merve_solar/solar.py`). The project therefore depends on one
Excel file and on astronomy, and on nothing else.

**Daylight is now defined by computed solar elevation.** From the province coordinates and the
timestamp, the apparent solar elevation at each hour's **midpoint** is computed with the NREL
algorithm (pvlib); `solar elevation > 0` means daylight. Two conventions were verified against
the record itself:

- Timestamps are in each site's own local solar time, specifically `UTC + round(lon/15)`. The
  measured peak hours match that rule to within 0.10 h (§2.1).
- The hour label is the **start** of the interval, and the sun's position is evaluated at its
  **midpoint**.

The threshold is deliberately **untuned**. Sweeping it does find a value that fits the realised
target better (on V3, −2.0° cuts disagreement with `target > 0` from 3,030 rows to 456), but
tuning a geometric mask against the target destroys the reason the mask exists. The cost of the
untuned choice was measured in the September round, when the clear-sky column was still
available: the climatology floor's daylight RMSE moved 108.78 → 109.86 W/m² and R² 0.8514 →
0.8456. **That comparison needs `CLRSKY_SFC_SW_DWN`, which neither current export contains, so it
cannot be repeated on V3 and is quoted as a historical measurement.**

**The clearness index now uses the literature's standard definition.** It used to be
`kt = ALLSKY / CLRSKY` (a clear-sky index); it is now

> **kt = GHI / (I₀ · cos θz)**

with **top-of-atmosphere** horizontal irradiance in the denominator. This is an upgrade, not a
fallback:

| | Old (clear-sky denominator) | New (top-of-atmosphere denominator) |
|---|---|---|
| Source | The provider's own product | Pure astronomy, nothing fitted |
| Comparability | Provider-specific | The standard definition, directly comparable to the literature |
| Share with kt > 1 | 2.91% (V2-era measurement) | **0.001%** (2 rows out of 152,902) |
| 99th percentile | 1.003 (V2-era measurement) | **0.801** |

**Caveat — the scale changed and must not be mixed with old numbers.** A cloudless hour reads
kt ≈ 0.75–0.80 on this scale (atmospheric transmittance) where the clear-sky index read ≈ 1.0.
The sky-condition cut-offs were moved to the literature's bands for this index accordingly:
**clear kt > 0.65**, **overcast kt < 0.35**.

### 0.3 Two analyses were removed

Two things needed the clear-sky **magnitude**, not just the sun's position, and could not be
recovered. Both removals are backed by measurement rather than assumption:

- **The smart-persistence reference** (`ŷ(T) = kt(T−24h) × CLRSKY(T)`). Rebuilt on the
  top-of-atmosphere denominator it **collapses into plain persistence**. Re-measured on V3 in the
  model's test window (rows where both are defined): daylight RMSE 121.06 / MAE 71.69 against
  plain persistence's 120.97 / 71.67 (on V2 it was 121.93 / 72.42 against 121.85 / 72.38). The reason is simple — top-of-atmosphere
  irradiance is nearly identical on consecutive days, whereas the clear-sky column carried an
  air-mass term that did not cancel. A reference that adds nothing is worse than no reference.
- **The `clearsky_index` target transform** (regressing kt directly). Same magnitude problem.
  The axis, its four grid groups and its ledger column are gone. `ABLATION.md` §6–§7 are the
  findings that axis produced; they stand as correct results **about the superseded dataset**
  and cannot be re-measured.

**Recommendation.** Both come back in one move if wanted: a NASA POWER export that also includes
`CLRSKY_SFC_SW_DWN` — a single extra parameter in the same request.

### 0.4 Feature set: 17 → 13

It narrowed in two steps. Moving from the July file to the September one dropped `QV2M` and the
50 m wind and added the 2 m wind; V2 then also dropped the 10 m wind.

| Kept (13) | Dropped |
|---|---|
| `ALLSKY_SFC_SW_DWN` (own lag), `T2M`, `RH2M`, `T2MDEW`, `PS`, `WS2M`, `PRECTOTCORR` | `QV2M` — r = 0.962 with `T2MDEW` |
| `WD2M_sin`, `WD2M_cos` | `WS50M`, `WD50M` — 50 m wind |
| `hour_sin`, `hour_cos`, `doy_sin`, `doy_cos` | `WS10M`, `WD10M` — 10 m wind |
| | `ALLSKY_KT`, `CLRSKY_SFC_SW_DWN` |

**Dropping the 10 m wind is what the EDA had been arguing for, not a loss.** Measured on the V1
export of the same record: `WS2M`–`WS10M` correlated at 0.987, and `WD2M` agreed with `WD10M` to
a median 0.30° with sin/cos correlations of 0.996. The 10 m pair carried almost nothing the 2 m
pair does not.

The consequence is visible in §6.3: **no feature pair is left with |r| > 0.9** — the
`collinear_pairs.csv` table is empty. One hidden redundancy survives, and pairwise correlation
cannot see it: `T2MDEW` is derivable from `T2M` and `RH2M` (§6.3).

The cleanest evidence that nothing was lost: the naive reference floor was **unchanged to the
decimal** after the drop (a V2-era measurement).

### 0.5 The record got longer

| Export | Last valid hour | Hours per province | `-999` tail |
|---|---|---|---|
| July | 2026-03-30 | 59,184 | 2,208 hours |
| V2 (14 Sep) | 2026-05-30 23:00 | 60,648 | 744 hours |
| **V3 (3 Oct, current)** | **2026-06-29 23:00** | **61,368** | **24 hours** (2026-06-30 00:00 – 23:00) |

V3 adds **720 hours (30 days) per province** over V2 and 2,184 hours (91 days) over the July
export. The `-999` tail affects the target column only: the meteorological columns carry values
through the end of the tail and are trimmed with it. All five provinces keep identical row counts
(61,368 each, 306,840 pooled).

---

## 1. Executive summary — the seven findings that belong in the paper

**(1) The five provinces do carry the climate-diversity claim, but asymmetrically.** Mean daily
insolation is Van 5.03, Antalya 5.00, Konya 4.92 and Ankara 4.71 kWh/m²/day — a band 7% wide.
Rize sits 20–25% below it at 3.75. The real difference is not in level but in
**predictability**: Rize's daily clearness index is 0.464 against 0.575–0.610, its overcast-day
share **28.6%** against 6.3–11.2%, its clear-day share 14.2% against 44.0–50.3%, and its
between-day coefficient of variation 0.565 against 0.435–0.488. Rize is where the paper's
cross-province transfer claim is actually tested.

**(2) Night rows improve every metric for free.** 49.5% of rows are geometrically night and all
of them are exactly zero. The same climatology reference scores RMSE 77.2 W/m² / R² 0.924 over
24 hours and RMSE 108.0 / R² 0.853 over daylight hours. Night rows cut RMSE by 29% and inflate
R² by 0.071. **The daylight figure is the one comparable to the literature.**

**(3) The floor to beat is climatology — and the winner depends on the metric.** On daylight
hours, in the model's own chronological test window (V3 split, §2), scored by the descriptive
twin: climatology RMSE **108.00** / MAE 74.17 / R² **0.8528**; persistence 120.90 / MAE
**71.59** / R² 0.8155. Climatology wins on RMSE and R², persistence on MAE. To be a result, the
LSTM has to clear **all three**. **Caveat — these are not yet the pipeline's numbers.** The
ledger's two naive rows (climatology 109.86 / 75.72 / 0.8456, persistence 121.56 / 72.15 /
0.8110) were produced on the V2 data and V2's split; they stay stale until
`scripts/03_run_naive_baselines.py` is re-run on V3 (§8).

**(4) Much of the raw correlation is solar geometry.** Pooled over daylight hours, temperature
correlates with the target at +0.515 raw but +0.307 partially, within a (province, month, hour)
cell. Surface pressure flips from −0.038 to **+0.268** and dew point from +0.045 to **−0.272**.
The stronger statement: **two variables (`PS`, `WS2M`) have inconsistent raw-correlation signs
across the five provinces, while after conditioning on geometry all six agree in sign
everywhere.**

**(5) Information on the time axis is exhausted within a 24-hour window.** At the daily scale —
which is what matters for a 24-hour-ahead forecast — the clearness index's partial
autocorrelation is 0.420–0.562 at lag 1 and drops to **−0.001…0.094** at lag 2. Raising
`lookback_hours` to 48 means adding a second day whose partial correlation is near zero.

**(6) The feature set is now largely clean, with one hidden redundancy left.** Dropping the 10 m
wind in V2 left no pair above |r| = 0.9. But `T2MDEW` is reproducible from `T2M` and `RH2M` by
the Magnus relation at **r = 0.99919 and 0.30 °C RMSE** — it is not a measurement but a
deterministic transform of two columns already present. Pairwise correlation cannot see this
(it is a two-variable function); 12 of the 13 features are independent.

**(7) The test window spans all four seasons; the validation window does not.** Test is 9,206
hours = **383.6 days** (2025-06-11 10:00 → 2026-06-29 23:00) and contains every calendar month.
**Caveat:** June is in it twice (11–30 June 2025 and 1–29 June 2026), so Summer carries 28.8%
of test hours against 23.5–24.0% for each of the other seasons; report seasonal metrics
alongside the pooled one. The validation window (2024-09-03 04:00 → 2025-06-11 09:00) contains
**no July and no August, and only 11 days of June (1–11 June 2025)** — the year's brightest and
steadiest months. That window is the conformal layer's calibration set; see §9.

---

## 2. Dataset and coverage

| | |
|---|---|
| Source | NASA POWER hourly, `SolarData_Merve(031026_V3).xlsx`, one sheet per province |
| Provinces | Ankara, Antalya, Konya, Rize, Van |
| Span | 2019-06-30 00:00 → 2026-06-29 23:00 |
| Hours per province | 61,368 (2,557 days ≈ 7.00 years) |
| Total rows | 306,840 |
| Daylight rows | 155,081 (**50.54%**) |
| Missing values | none (after trimming the 24-hour `-999` tail, §0.5) |
| Features | 13 |
| Target | `ALLSKY_SFC_SW_DWN`, W/m² |

Coverage is perfectly balanced: all five provinces share the same 61,368 hours. Mean daylight
duration runs 12.10–12.16 h per day; the spread across provinces is the expected consequence of
their latitudes.

The chronological split (train 0.74 / val 0.11 / test 0.15) falls on **identical dates** for all
five:

| Split | Range | Hours | Days |
|---|---|---|---|
| Train | 2019-06-30 00:00 → 2024-09-03 03:00 | 45,412 | 1,892.2 |
| Validation | 2024-09-03 04:00 → 2025-06-11 09:00 | 6,750 | 281.3 |
| **Test** | **2025-06-11 10:00 → 2026-06-29 23:00** | **9,206** | **383.6** |

The boundaries fall mid-day because they are counted in hours (round(61,368 × ratio)), not days.
The test window covers 13 calendar months and all four seasons (per province: Summer 2,654,
Spring 2,208, Autumn 2,184, Winter 2,160 hours; pooled over the five provinces 13,270 / 11,040 /
10,920 / 10,800). Summer is over-represented because June appears twice in the window.

**Caveat.** `train_ratio`/`val_ratio` were chosen so the test window exceeds a full year. With
V3 the month counted twice is June (on V2 it was May), which tilts the pooled score toward the
easiest season (§3.4). Changing the ratios further risks breaking the four-season property
altogether.

### 2.1 The clock is per-site local solar time, not a shared time zone

The hour column is not a common time zone; each province is recorded in its own local solar
time. Taking the centre of mass of mean irradiance as the peak hour gives

> Konya 11.25 ≈ Ankara 11.25 < Antalya 11.41 < Van 11.56 < Rize 11.89

which is the **reverse** of the ordering a shared clock would produce, and matches the
`UTC + round(lon/15)` expectation to within 0.10 h (largest deviation 0.09 h, Rize). This is no longer just an observation: it is
**the convention the daylight mask rests on**, since the sun's position is computed with that
offset.

Two consequences:

- **Hours are never comparable across provinces.** Hour 11 in Rize is not the same physical
  instant as hour 11 in Ankara. Axes are labelled "Local solar time (LST)" and hour labels are
  interval starts.
- **`hour_sin`/`hour_cos` is a better encoding than it looks**, because each province is encoded
  in its own solar time. This deserves a sentence in the paper's methods section.

---

## 3. The target variable

### 3.1 Distribution

Pooled, daylight hours: mean **386.0 W/m²**, median 343.7, sd 278.6, maximum 1215.9 (Van).
Skew +0.419, excess kurtosis −0.955. Between-province sd 44.5.

Over all 24 hours: mean 195.1, median 7.8, skew +1.272.

The gap between those two lines is the substance of §1(2). The 24-hour distribution is a mixture
of two masses: a spike of exact zeros at night, and the daylight distribution. The daylight
distribution itself has **negative excess kurtosis** — not peaked but broad and flat, the direct
consequence of geometry sweeping from 0 to ~1000 across the day.

**Caveat — scaling.** The target is not normally distributed and no transform assuming otherwise
is applied. `StandardScaler` is fitted on training rows only.

### 3.2 How daylight is defined, and why

**Daylight = computed solar elevation > 0**, at the midpoint of the hour (§0.2).

Two alternatives were tried and rejected.

**`target > 0`.** The obvious candidate, and on this record it agrees with the geometry on
303,810 of 306,840 rows (99.0%). It is still inadmissible, for two reasons, the second decisive:

1. *It selects the evaluation set using the answer.* The daylight subset is the denominator of
   every headline metric. If membership depends on the realised target, a heavily overcast
   twilight hour reads zero and quietly leaves the subset — the hours where the model is worst
   are the ones that drop out. On V3 no daylight row reads exactly zero (the target now has 0.01
   W/m² resolution, and the V2 quantisation that used to produce a handful of such rows is gone),
   so on this record the effect happens to be nil; but nothing bounds it on another record, and
   it is not a property to rely on.
2. *It cannot be evaluated at prediction time.* `clamp_night_to_zero` has to decide, for an hour
   24 h ahead, whether the sun will be up, and `y` is not available then. A target-based rule
   would report skill that is unattainable operationally. Geometry is therefore required
   regardless — and once it exists, a second definition for the metric would be incoherent.

**A climatological (province, month, hour) cell mean.** Used in the first EDA round and too
coarse: within one month sunrise shifts 30–60 minutes, so the cell mean marks the whole edge
hour as daylight. It admitted 5,266 rows of genuine night (measured in that first round, on the
July export).

**How the new definition sits against the data.** Comparing the geometric mask with `target > 0`:

- Hours called daylight that read exactly zero: **0** (in 306,840 rows).
- Hours called night that carry irradiance: 3,030. These are twilight hours in which the sun
  rises part-way through the interval (computed elevation between −2.4° and 0°, mean target 4.7
  W/m²). They carry **0.024% of total daylight energy**, and dropping them makes the daylight
  subset *harder*, not easier. That is the safe direction.

### 3.3 Diurnal and seasonal structure

Hour of day alone explains **73.2%** of the variance over 24 hours (pooled η²); within the
daylight subset that falls to 48.9%. Day of year explains 8.7% and 14.8% respectively.

- Three quarters of a 24-hour score comes from knowing the day/night cycle — not from the model.
- Within daylight, hour is still dominant but the seasonal share nearly doubles.

A harmonic (sin/cos) fit captures essentially all of the η² (24 h: 0.7291 against 0.7318).
**Recommendation:** the current sin/cos encoding loses nothing relative to categorical hour
dummies and should be kept.

### 3.4 Seasonality: irradiance and predictability move in opposite directions

Coefficient of variation of the daily total:

| Province | Winter | Summer | Winter/Summer |
|---|---|---|---|
| Ankara | 0.432 | 0.145 | 2.98× |
| Antalya | 0.383 | 0.100 | 3.83× |
| Konya | 0.397 | 0.131 | 3.04× |
| Van | 0.326 | 0.119 | 2.74× |
| Rize | 0.504 | 0.277 | **1.82×** |

Summer days are not only brighter but **1.8–3.8 times less variable**. (The coefficients are
computed over the whole record; the V3 test window's extra weight on June, §2, therefore makes
the pooled test score slightly easier than a uniform-season window would.) Error metrics will behave
very differently by season, and a small absolute error in winter does not mean the model is good
in winter — there is simply less to predict.

**Caveat.** Rize is outside the band: even its summer carries variability close to the other
provinces' winter. Any sentence covering Rize must give the range as **1.8–3.8×**, not "3–4×".

### 3.5 Between-year variability: small, but not zero

Complete calendar years (2020–2025), mean daily insolation in kWh/m²/day:

| Province | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Best/worst |
|---|---|---|---|---|---|---|---|
| Ankara | 4.83 | 4.73 | 4.64 | 4.56 | 4.72 | 4.90 | 7.2% |
| Antalya | 5.06 | 5.13 | 5.04 | 4.85 | 4.99 | 5.04 | 5.8% |
| Konya | 5.01 | 4.98 | 4.87 | 4.84 | 4.90 | 5.09 | 5.2% |
| Rize | 3.91 | 3.75 | 3.54 | 3.68 | 3.82 | 3.74 | **10.5%** |
| Van | 4.95 | 5.26 | 5.16 | 4.87 | 4.95 | 5.05 | 8.0% |

("Best/worst" is the best year over the worst year, minus one.) The between-year relative sd is
1.9–3.4%. Training and test years being different is not by
itself a large shift — but Rize carries a **10% year effect**, which means part of the variation
in Rize's test score comes from the year rather than from the model.

---

## 4. Meteorological variables

Pooled, daylight hours:

| Column | Mean | SD | Range | Between-province SD | Note |
|---|---|---|---|---|---|
| `T2M` (°C) | 15.68 | 10.29 | −23.6 … 42.3 | 3.83 | |
| `RH2M` (%) | 53.61 | 23.56 | 3.4 … 100 | **11.18** | Most discriminating; the one real predictor |
| `T2MDEW` (°C) | 4.36 | 7.06 | −27.5 … 22.9 | 4.42 | Derivable (§6.3) |
| `PS` (kPa) | 88.29 | 6.03 | 75.8 … 97.7 | **6.72** | Variance is entirely elevation |
| `WS2M` (m/s) | 2.60 | 1.53 | 0.01 … 13.65 | 0.51 | |
| `PRECTOTCORR` (mm/hour) | 0.071 | 0.261 | 0 … 7.38 | 0.049 | Skew +8.2 |

**Surface pressure does not behave like a meteorological variable here.** Its pooled sd is
6.03 kPa but its between-province sd is 6.72 — the variance is entirely across provinces, not
within them (Van 77.7, Konya 87.9, Ankara 88.8, Rize 91.2, Antalya 96.0 kPa). In a pooled model
`PS` effectively acts as an **elevation / province-identity indicator** and duplicates what the
city embedding already carries. Its within-province variation (sd ≈ 0.4–0.5 kPa) is the real
synoptic signal, and it explains why the partial correlation flips sign in §6.1.

### 4.1 Precipitation: effectively a binary variable

**66.6% of daylight hours are exactly zero**, and the non-zero tail is heavily skewed (skew
+8.2). Correlation with the target under three encodings:

| Province | Binary (rain / no rain) | Raw amount | `log1p(amount)` |
|---|---|---|---|
| Ankara | **−0.166** | −0.101 | −0.114 |
| Antalya | **−0.213** | −0.177 | −0.204 |
| Konya | **−0.189** | −0.116 | −0.138 |
| Rize | −0.217 | −0.219 | **−0.250** |
| Van | **−0.186** | −0.139 | −0.162 |

In four provinces a simple "is it raining" indicator is more informative than the raw amount
and than `log1p`; in Rize `log1p` leads. (The previous version of this table bolded only three
provinces and left Antalya unmarked although its binary encoding was also the strongest.)

**Recommendation.** Supplying precipitation as **`log1p(PRECTOTCORR)` plus a binary rain
indicator** covers both Rize and the dry provinces. It requires a new experiment id.

**Unit check.** Reading the column as mm/hour and summing over a year (2020–2025 average) gives
Ankara 340, Konya 326, Van 343, Antalya 664 and Rize 1399 mm/year. The ordering and magnitude
are consistent with Turkish climate normals — NASA POWER, as a satellite product, is known to
under-estimate Rize and Antalya. This independently confirms the mm/hour reading.

### 4.2 Wind direction: informative only in Van

Speed-weighted circular statistics, with calm hours (≤ 1 m/s) excluded:

| Province | `WD2M` mean direction | Resultant length *R* | Circular SD |
|---|---|---|---|
| Van | 216° | **0.468** | 71° |
| Rize | 271° | 0.246 | 96° |
| Konya | 338° | 0.229 | 98° |
| Antalya | 43° | 0.189 | 105° |
| Ankara | 335° | 0.124 | 117° |

The resultant length runs from 0 (completely dispersed) to 1 (a single direction). **Only Van
has a dominant direction**; in the other four, wind direction is practically uniform and
therefore almost empty as a predictor.

**Caveat.** The share of calm hours differs sharply between provinces (`WS2M ≤ 1 m/s`: Rize
16,407 hours, Konya 8,755), and in those hours the direction is noise; the filter must be stated
if direction features are discussed. Because the threshold now applies to the 2 m wind rather
than the 10 m wind, the excluded count is markedly higher than in V1 — wind is slower at 2 m.
This is a definitional change, not a physical one.

---

## 5. Temporal structure and the `lookback_hours` decision

Autocorrelation is computed **on the clearness index kt**, not on raw irradiance: the
autocorrelation of raw irradiance is almost entirely the diurnal cycle and teaches nothing,
whereas dividing out the geometry leaves **the atmosphere's memory** — the thing that actually
has to be forecast.

### 5.1 Hourly scale

| | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| PACF lag 1 | 0.905 | 0.866 | 0.900 | 0.920 | 0.868 |
| PACF lag 2 | −0.302 | −0.376 | −0.274 | −0.350 | −0.218 |
| PACF lag 3 | −0.010 | +0.089 | −0.016 | −0.004 | −0.004 |
| ACF lag 24 | 0.630 | 0.726 | 0.655 | 0.533 | 0.680 |

Lag 1 is above 0.86 everywhere, lag 2 is clearly negative and lag 3 sits at zero: hourly kt
behaves like an **AR(2)**.

**Caveat — this differs from the earlier data version.** With the clear-sky denominator, lag 2
hovered around zero and the series read as "almost AR(1)". With the top-of-atmosphere
denominator a clear second term appears. The sentence "hourly kt is an AR(1)" must not be
carried over from older documents.

**Technical note.** The PACF truncates between lags 10 and 12 depending on the province, because
kt is undefined at night and the series is therefore split into daily blocks. Values beyond that
are not reported.

### 5.2 Daily scale: this is what decides a 24-hour-ahead forecast

| | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| PACF day 1 | 0.540 | 0.546 | 0.558 | **0.420** | 0.562 |
| PACF day 2 | 0.094 | 0.094 | 0.073 | **−0.001** | 0.069 |
| PACF day 3 | 0.113 | 0.122 | 0.081 | 0.071 | 0.110 |
| ACF day 30 | 0.174 | 0.229 | 0.162 | **0.083** | 0.162 |

The fall from day 1 to day 2 is six- to eight-fold in the four non-Rize provinces and to zero in
Rize. **This is the evidence behind
`lookback_hours = 24`:** going to 48 hours means adding a second day whose partial correlation
lies between −0.001 (Rize) and 0.094 (Ankara and Antalya). The conclusion is unchanged from the earlier data
version despite the denominator change — so the finding the decision rests on is not sensitive
to the definition.

The residual autocorrelation at day 30 (0.08–0.23) is seasonal trend, not memory;
`doy_sin`/`doy_cos` already carries it.

**Caveat.** Rize is outside the band on every line, and always in the direction of less memory.

### 5.3 Ramps

Absolute change between consecutive daylight hours:

| Province | Median \|Δ\| | p90 | p99 | Share > 200 W/m² | \|Δkt\| p99 |
|---|---|---|---|---|---|
| Ankara | 106.4 | 187.9 | 211.4 | 3.8% | 0.220 |
| Antalya | 116.4 | 193.0 | 218.9 | 6.3% | 0.216 |
| Konya | 111.3 | 193.5 | 216.3 | 6.5% | 0.221 |
| Rize | 83.1 | 167.9 | 213.6 | 1.8% | 0.206 |
| Van | 115.9 | 194.7 | 217.2 | 7.2% | 0.222 |

Most of the ramp in raw irradiance is geometry. In the Δkt column the provinces are strikingly
**close together** (0.206–0.222): Rize's raw ramps look small only because its sun is weak to
begin with, not because its atmosphere is steadier.

### 5.4 Daylight blocks

Daylight hours arrive in uninterrupted blocks: 2,557 blocks per province (one per day), median
length 12 hours, shortest 9 (Ankara, Konya, Rize) or 10 (Antalya, Van), longest 14 (Antalya) /
15 (the others). No block reaches 24 hours.

**Caveat.** This means a 24-hour forecast horizon **always contains at least one night**. No
prediction window can be entirely daylight, so `clamp_night_to_zero` directly affects roughly
half of every window.

---

## 6. Relationships between variables, and feature selection

### 6.1 Raw correlation is confounded with solar geometry

`target_correlation_by_city.csv` gives both the raw Pearson correlation and the **partial
correlation within a (province, month, hour) cell**. The latter measures the relationship with
the target holding solar geometry and season fixed. Pooled, daylight hours:

| Column | Raw r | Partial r | Reading |
|---|---|---|---|
| `RH2M` | −0.626 | **−0.529** | The one real predictor; strong under both measures |
| `T2M` | +0.515 | +0.307 | Half of it is geometry |
| `PRECTOTCORR` | −0.168 | **−0.328** | **Doubles** once geometry is held fixed |
| `T2MDEW` | +0.045 | **−0.272** | **Changes sign** |
| `PS` | −0.038 | **+0.268** | **Changes sign** |
| `WS2M` | +0.142 | −0.148 | **Changes sign** |

Three variables change sign and precipitation doubles. The mechanism is simple: warm, windy,
high-dew-point hours are also **summer midday hours**, when irradiance is already geometrically
high. Holding geometry fixed removes that spurious association and reveals the physical one
(moisture and cloud → less irradiance).

**The single strongest argument:** in raw correlation the signs of `PS` and `WS2M` are
**inconsistent** across the five provinces; in partial correlation **all six variables have the
same sign in all five**. Once geometry is removed, the provinces agree about the physics.

**Recommendation.** If predictor importance is discussed in the paper, **the partial correlation
table is the one to use**; the raw matrix should appear only to demonstrate why it misleads.

### 6.2 Linearity: Spearman and Pearson agree

Pooled over daylight hours (Spearman minus Pearson), the largest difference is **−0.057** for
precipitation, followed by +0.047 for `WS2M`. No variable exceeds 0.06 (`T2M` −0.015, `T2MDEW`
−0.009, `PS` −0.008, `RH2M` +0.001). There is no non-monotonic relationship.

That the difference concentrates in precipitation and wind is the expected direction — both are
heavily skewed — and **Spearman being larger in absolute value** strengthens the recommendation
in §4.1: precipitation's relationship is rank-based rather than linear.

### 6.3 Collinearity: the obvious redundancy is gone, one hidden one remains

**`collinear_pairs.csv` is now empty**: no feature pair exceeds |r| = 0.9. In V1 the only such
pair was `WS2M`–`WS10M` (r = 0.987), and the 10 m wind was dropped in V2. An empty table here is
a result, not an error.

Pairs above |r| = 0.5, pooled over daylight hours — all physical, none at removal level:

| Pair | Pearson | Spearman |
|---|---|---|
| `T2M` – `RH2M` | −0.671 | −0.675 |
| `T2M` – `T2MDEW` | +0.610 | +0.593 |
| `T2MDEW` – `PS` | +0.520 | +0.482 |

**Caveat — pairwise correlation cannot see the redundancy that matters.** `T2MDEW` is not a
measurement but a formula: reproduced from `T2M` and `RH2M` by the Magnus relation it reaches
r = **0.99920**, RMSE = **0.30 °C** over 24 hours (daylight: r = 0.99958, RMSE 0.22 °C), i.e.
measurement-noise level. Pairwise correlation misses it because it is a two-variable function —
the `T2M`–`T2MDEW` correlation is only 0.610. A collinearity table is a **lower bound** on
redundancy, never an upper one.

**Recommendation — run a single-axis arm dropping `T2MDEW`,** 13 → 12. The expected effect is
small but has not been measured, and since the LSTM's input layer scales with the feature count
it is a genuine parameter reduction.

---

## 7. Regional differentiation: Rize and Van, the two extremes

### 7.1 Rize is a separate climatic regime

Rize does not sit at a different point from the other four; it sits in a **different
distribution**.

| Measure | Rize | Other four |
|---|---|---|
| Daily insolation | 3.75 kWh/m²/day | 4.71 – 5.03 |
| Daily clearness index kt | **0.464** | 0.575 – 0.610 |
| Hourly kt median | **0.424** | 0.566 – 0.601 |
| Clear-day share (kt > 0.65) | **14.2%** | 44.0 – 50.3% |
| Overcast-day share (kt < 0.35) | **28.6%** | 6.3 – 11.2% |
| Between-day CV | **0.565** | 0.435 – 0.488 |
| Daily PACF, day 1 | **0.420** | 0.540 – 0.562 |
| Daily ACF, day 30 | **0.083** | 0.162 – 0.229 |
| Climatology daylight RMSE (descriptive twin, §8) | **133.4 W/m²** | 92.6 – 108.2 |
| Climatology daylight R² (descriptive twin, §8) | **0.721** | 0.855 – 0.895 |

Rize's **best season** (summer, kt = 0.525) is close to the other provinces' **winter**
(0.477–0.556). This is not a seasonal difference but a regime difference.

**Caveat — the pooled average buries Rize.** With four provinces clustered together, the pooled
mean outvotes Rize four to one. That is exactly why the metric table carries a separate
`Aggregate_excl_Rize` row: without it, the contribution of cross-province transfer is invisible.

**Recommendation.** In the paper Rize should be introduced not as "the difficult province" but as
**the second regime**. The climate-diversity claim is only accurate in that framing: four
provinces are variations on one regime, and Rize is a second one on its own.

### 7.2 Van is the clearest, and the most extreme

Van has the highest daily insolation (5.03 kWh/m²/day), the highest clearness index (0.610), the
lowest overcast-day share (6.3%) and the lowest winter CV (0.326) — even its winter is
predictable. It is also the only province with a dominant wind direction (§4.2).

**Caveat — Van's 1215.9 W/m² maximum is not a physical finding.** That row (2020-02-17 15:00)
corresponds to kt = 2.23: the measured irradiance is more than twice what reaches the top of the
atmosphere at that hour (544 W/m²). It is physically impossible, i.e. a measurement or back-fill
artefact. Van's combination of altitude and dry air is a real phenomenon, but **it must not be
argued from this row**.

### 7.3 The limits of the clearness index

Under the new definition kt behaves impeccably: only **2** of 152,902 lit hours (top-of-atmosphere
irradiance above 20 W/m²) exceed 1.0 and the 99th percentile is 0.801. One of the two is the Van
row above. This is a marked improvement over the clear-sky denominator, where 2.9% of hours read
above 1 (a V2-era measurement; the column is no longer available to re-check it, and the
earlier attribution of that excess to the V2 quantisation was not tested).

**Caveat.** kt is not clipped anywhere and must not be.

---

## 8. The reference floor: the numbers the model has to beat

Two naive references are scored **in the model's own chronological test window** with **the same
windowing**:

- **Persistence:** repeat the value from 24 hours earlier.
- **Climatology:** the training-rows mean of the (province, month, hour) cell.

**Which numbers these are.** The table below is `persistence_baseline.csv`, the descriptive twin
computed on V3 in the V3 test window (2025-06-11 10:00 → 2026-06-29 23:00; 46,030 hours pooled,
23,499 of them daylight). The pipeline's own run (`scripts/03_run_naive_baselines.py`, which writes
the ledger rows) counts scored elements rather than hours and differs from the twin in the last
decimals (on V2: climatology daylight RMSE 109.83 twin vs 109.86 pipeline).

**Caveat — the ledger is stale.** `outputs/experiments_ledger.csv` currently holds the two naive
rows produced on the **V2** data (V2 split, 9,097-hour test window, quantised target):
climatology daylight RMSE 109.86 / MAE 75.72 / R² 0.8456 and persistence 121.56 / 72.15 / 0.8110.
They are not V3 numbers. Until `scripts/03_run_naive_baselines.py` is re-run, the V3 floor in
the paper-facing documents is the twin below, and any ledger row compared against it must be
re-run on V3 first.

| Reference | Scope | RMSE | MAE | R² |
|---|---|---|---|---|
| Persistence | 24 h | 86.38 | 36.56 | 0.9046 |
| Climatology | 24 h | 77.17 | 37.94 | 0.9239 |
| Persistence | **daylight** | 120.90 | **71.59** | 0.8155 |
| Climatology | **daylight** | **108.00** | 74.17 | **0.8528** |

By province, daylight, climatology: Antalya 92.6 / Van 96.2 / Konya 104.7 / Ankara 108.2 /
**Rize 133.4** W/m²; R² 0.895 / 0.883 / 0.868 / 0.855 / **0.721**.

**To be a result, the LSTM must beat 108.00 W/m² on RMSE and 0.8528 on R² (climatology) *and*
71.59 W/m² on MAE (persistence), on daylight hours.** Winning on one metric is not enough; the
champion changes with the metric. (Provisional: replace with the pipeline's V3 numbers once the
naive baselines are re-run.)

**Caveat — smart persistence is absent from this table.** It required a clear-sky magnitude and
collapses into plain persistence on the top-of-atmosphere denominator (§0.3). In the earlier data
version it was the MAE champion; that role now belongs to plain persistence.

**Caveat — 24-hour R² values must not enter the paper.** Climatology scores R² = 0.924 over 24
hours. Because R² is normalised by the subset's own variance, the day/night swing dominates it.
**A 24-hour R² above 0.9 is evidence of nothing.** The same normalisation argument applies to
PINW.

**Caveat — beating 24-hour persistence is not a result.** For a 24-hour-ahead forecast,
persistence is already aligned with the diurnal cycle, so it carries free geometric information.
The comparison must be made against climatology.

**Caveat — interval metrics are undefined for the naive references.** A single deterministic
forecast has zero interval width, so CP degenerates into an equality test. CP/PINW/MPIW/CWC are
`NaN` on those rows; CRPS is kept, because there it reduces exactly to MAE.

---

## 9. Implications for the uncertainty (UQ) layer

**(1) The target is heteroscedastic and its variance structure runs opposite to its level.**
§3.4: winter CV is 1.8–3.8× summer CV. A fixed-width interval is too narrow in winter and too
wide in summer. This is the data-side justification for a **season-indexed** conformal grid.

**(2) The between-province difference is no smaller than the between-season one.** §7:
climatology's daylight RMSE is 133.4 in Rize against 92.6 in Antalya — a 44% gap. That is why a
single scalar calibration factor cannot work.

**(3) Night elements inflate interval metrics structurally.** With `clamp_night_to_zero` on,
every night element receives a degenerate `[0, 0]` interval around a true value of exactly 0, so
it is covered **by definition**. 49.5% of elements are night, so roughly half of the 24-hour CP
mixture is 1.0 before the model contributes anything. **A run must be judged on daylight
CP ≈ 0.95 first**, then on daylight PINW/CWC/CRPS.

**(4) The calibration set's defect has moved again.** The conformal layer uses the
validation split as its calibration set, and that split has two known defects: early stopping
already saw it, and it does not cover the whole calendar. With V3 the validation window is
2024-09-03 04:00 → 2025-06-11 09:00: it holds **no July and no August, and only 1–11 June 2025
of the summer** (on V2 it held 12–31 August and no June or July; on the July export the gap was
April–May). A season-indexed grid's Summer cell would be fitted from **250 hours (11 days) per
province, 3.7% of the validation window** (on V2: 480 hours, 7.2%), and from a single year.
Whether that biases the intervals in a particular direction is **not supported by the data**:
the daily kt sd of 1–11 June 2025 is within −0.011…+0.002 of the June–July sd over 2019–2025
in every province (Ankara 0.096 vs 0.100, Antalya 0.054 vs 0.065, Konya 0.094 vs 0.092, Rize
0.135 vs 0.142, Van 0.069 vs 0.074), and with 11 daily values per province that comparison is
too noisy to carry a conclusion. The earlier statement that the calibration gap pushes toward
too-narrow intervals applied to V2's August cell and is **not carried over**. The defect that
does stand is sample size: 11 days cannot calibrate a seasonal cell.

**Recommendation.** This shift must be documented before the season-indexed conformal grid is
re-run. The fix should not be sought in the split ratios (the test window's four-season property
is worth more); taking the calibration set from a separate slice of the last training year is
testable and costs seconds.

---

## 10. Limitations that must be stated in the paper

1. **The data is satellite-derived, not ground-station.** NASA POWER derives irradiance from
   satellite observations; precipitation totals are known to run low in Rize and Antalya.

2. **The target comes from one provider export in W/m² at 0.01 resolution** (§0.1). The V2
   quantisation (2.78 W/m² steps) is gone. One physically impossible value remains, Van
   2020-02-17 15:00 (kt = 2.23, §7.2), and the other kt > 1 row (1.03) is a plausible
   cloud-enhancement value; neither has been removed.

3. **The daylight mask is computed, not measured** (§0.2). The province coordinates, the time
   convention and the threshold choice must be stated explicitly in the methods section. The cost
   of the untuned threshold was measured in the September round (climatology floor RMSE 108.78 →
   109.86) and cannot be re-measured on V3.

4. **The clearness index changed scale** (§0.2). kt values from earlier documents (Rize 0.697,
   others 0.806–0.840) **cannot** be carried over to this data.

5. **There is no smart-persistence reference and no `clearsky_index` arm** (§0.3). `ABLATION.md`
   §6–§7 stand as correct results about the superseded dataset but cannot be re-measured.

6. **The feature set narrowed twice** (17 → 16 → 13) across the July, September and V2 exports
   (§0.4); V3 keeps the 13 features but changes the target's storage and the record length. A
   single column or span change makes ledger rows incomparable; any runs meant to be compared
   must come from the same version.

7. **There are only five provinces and four of them share a regime** (§7.1). The
   "climate diversity" claim must be presented with that asymmetry.

8. **Between-year variability is small but non-zero** (§3.5); 10.5% in Rize.

9. **Every pre-V3 ledger row is stale.** The ledger's older rows were moved to
   `outputs/archive/`; the two that remain (the naive baselines) were produced on the **V2**
   data — a record 30 days shorter, a quantised target and different split boundaries — so their
   numbers differ from the V3 floor of §8. They must be re-run on V3 (the baselines via
   `scripts/03_run_naive_baselines.py`, which overwrites its own rows) and any model run must
   get a **new id**.

10. **The map of the five provinces and the written paragraph on their climatic and geographic
    differences are still missing.** The coordinates are now available in
    `config.py::PROVINCE_SITES`.

11. **Figures and tables use raw NASA POWER column names.** The manuscript should gloss each one
    on first use (e.g. "`RH2M`, relative humidity at 2 m"); the figures rely on that gloss.

---

## 11. Which claim comes from which file

### Tables (`outputs/eda/tables/`)

| File | Sections |
|---|---|
| `temporal_coverage_by_city.csv` | §2, §3.3 |
| `descriptive_stats_by_city_daylight.csv` / `_24h.csv` (+ `.md`, `.tex`) | §3.1, §4 |
| `target_by_hour_by_city.csv` | §2.1, §3.3 |
| `time_feature_explained_variance.csv` | §3.3 |
| `seasonal_target_stats.csv` | §3.4, §7 |
| `monthly_target_stats.csv` | §3.4 |
| `daily_clearness_by_city.csv` | §1(1), §7.1 (empirical clearness; independent of kt) |
| `clearness_index_by_city.csv` | §7.1, §7.2, §7.3 |
| `autocorrelation_clearness.csv` | §5.1, §5.2 |
| `ramp_stats_by_city.csv` | §5.3 |
| `daylight_block_structure.csv` | §5.4 |
| `persistence_baseline.csv` | §1(2–3), §7.1, §8, §9(2) (descriptive twin; the ledger's naive rows are V2-era until the baselines are re-run) |
| `target_correlation_by_city.csv` | §6.1 |
| `correlation_pearson_*.csv`, `correlation_spearman_*.csv` | §6.2, §6.3 |
| `collinear_pairs.csv` | §6.3 (empty since V2 — that is the finding) |
| `wind_direction_circular_stats.csv` | §4.2 |

### Figures (`outputs/eda/figures/`, PNG at 300 dpi + vector PDF)

| File | What it shows |
|---|---|
| `target_histogram` | The two-mass structure of §3.1 |
| `seasonal_diurnal_profile` | §2.1, §3.3 — diurnal profile by season, local solar time |
| `seasonal_dayofyear` | §3.4 |
| `monthly_boxplot_last12m_*`, `monthly_boxplot_all_years` | §3.4 |
| `month_year_surface_*`, `month_year_anomaly_panel` | §3.5 |
| `autocorrelation_hourly`, `autocorrelation_daily` | §5.1, §5.2 |
| `ramp_distribution` | §5.3 |
| `correlation_heatmap_*`, `target_correlation_panel` | §6.1 – §6.3 |
| `scatter_vs_target_*` | §4, §6.2 |
| `persistence_baseline` | §8 |
| `rize_comparison` | §7.1 |

### Computed for this document, outside the tables

If any of these go into the paper they should be added to
`scripts/02_descriptive_analysis.py` as permanent tables; otherwise the traceability rule is
broken.

| Result | Value | Section |
|---|---|---|
| V2 → V3 target comparison | V2 × 277.78 vs V3 over the 60,648 shared valid hours per province: max deviation 1.40 W/m², mean 0.36; the seven other raw columns differ by exactly 0 | §0.1 |
| Distinct target values | V3: 38,385 pooled (Ankara 20,665, Antalya 20,917, Konya 20,919, Rize 19,007, Van 20,991); V2: 387 (as documented for V2, not recomputed) | §0.1 |
| Precipitation resolution loss (V2-era, July export gone) | 38.7% of previously rainy hours read exactly zero; **not re-verified** | §0.1 |
| Cost of the geometric mask (V2-era, needs the clear-sky column) | climatology daylight RMSE 108.78 → 109.86, R² 0.8514 → 0.8456; **cannot be re-measured on V3** | §0.2, §10(3) |
| Threshold sweep | a tuned −2.0° gives 456 disagreements with `target > 0`, the untuned 0° gives 3,030 | §0.2 |
| Mask vs `target > 0` | daylight-but-zero: 0 rows; night-but-positive: 3,030 rows (elevation −2.4° … 0°), 0.024% of daylight energy | §3.2 |
| Smart persistence degenerating | on the TOA denominator, V3 test window, daylight RMSE 121.06 / MAE 71.69; plain persistence on the same rows 120.97 / 71.67 | §0.3, §8 |
| `WD2M` – `WD10M` redundancy (measured on V1; the 10 m column is gone since V2) | median angular difference 0.30°, mean 1.56°, p95 6.30°; sin/cos r = 0.996 / 0.997; `WS2M`–`WS10M` r = 0.987 | §0.4, §6.3 |
| Dew point reproduced by Magnus | r = 0.99920, RMSE 0.30 °C (24 h); r = 0.99958, RMSE 0.22 °C (daylight) | §1(6), §6.3 |
| Precipitation encodings vs the target | table in §4.1; daylight zero share 66.6% | §4.1 |
| Annual precipitation totals (unit check) | Ankara 340, Konya 326, Van 343, Antalya 664, Rize 1399 mm/year | §4.1 |
| Peak hours (local-solar-time check; centre of mass of the mean diurnal profile on the hour label) | Konya 11.2493, Ankara 11.2516, Antalya 11.4070, Van 11.5594, Rize 11.8922; deviation from the `UTC + round(lon/15)` expectation −0.085 … +0.094 h | §2.1 |
| Split boundaries and the validation window's missing months | test 9,206 hours / 383.6 days; validation has no July or August and 1–11 June 2025 only (Summer cell 250 hours, 3.7%) | §1(7), §2, §9(4) |
| Seasonal hours in the test window | per province Summer 2,654, Spring 2,208, Autumn 2,184, Winter 2,160 | §2 |
| Calibration-gap check | daily kt sd, 1–11 June 2025 vs June–July 2019–2025: Ankara 0.096 / 0.100, Antalya 0.054 / 0.065, Konya 0.094 / 0.092, Rize 0.135 / 0.142, Van 0.069 / 0.074 | §9(4) |
| kt > 1 rows | 2 of 152,902 lit hours: Van 2020-02-17 15:00 (kt 2.23) and Van 2022-01-24 11:00 (kt 1.03) | §7.2, §7.3 |
| Between-year variability | table in §3.5 | §3.5 |
| Pooled daylight and 24 h target moments | daylight skew +0.419, excess kurtosis −0.955, between-province sd 44.5 (sd of the five province means); 24 h skew +1.272 | §3.1 |
| Between-province sd of each meteorological column; pooled skew of `PRECTOTCORR` | table in §4 (sd of the five province means, computed from `base_features.parquet`; the descriptive-statistics table holds the other columns) | §4 |
