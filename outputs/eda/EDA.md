# Exploratory data analysis — findings and interpretation

**Data version:** `SolarData_Merve(140926_V2).xlsx` (14 September 2026, V2) — the repository's
only data file.
**Document date:** 14 September 2026. All earlier versions are superseded.

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

## 0. Read this first: the dataset and two definitions have changed

The current file is not an update of the July export; it is a **new export taken with different
settings**. Same NASA POWER record, different units, a different parameter list and a longer
span. One of the parameters that disappeared was this project's most-used instrument, so two
**definitions** changed with it. None of the numbers below is comparable to an earlier version.

### 0.1 Units changed

| Column | July export | Current export | What we do |
|---|---|---|---|
| `ALLSKY_SFC_SW_DWN` (target) | W/m² | **MJ/m²/hour** | Converted to W/m² at read time (× 277.78) |
| `PRECTOTCORR` | mm/day | **mm/hour** | Left as is |

The conversion is exact and linear. It was verified by joining the two exports over their
59,184 shared hours: the meteorological columns were bit-identical and the converted irradiance
reproduced the old values to within 1.39 W/m².

We convert to W/m² because the manuscript, the source paper and the irradiance literature all
use it.

**Caveat — there is a price.** The new file stores **two decimals of MJ**, so in W/m² the target
is **quantised to 2.78 W/m² steps**: the whole record contains only 387 distinct target values.
The quantisation noise has sd 2.78/√12 = 0.80 W/m², under 1% of the best reference floor's RMSE,
so no metric is materially affected. It does bear directly on how daylight is defined (§3.2).

Precipitation pays more: the resolution fell from 0.01 mm/day to 0.24 mm/day, and **38.7% of the
hours that used to read as rainy now read exactly zero**. Total precipitation is preserved; what
is lost is drizzle detail.

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
  measured peak hours match that rule to within 0.11 h (§2.1).
- The hour label is the **start** of the interval, and the sun's position is evaluated at its
  **midpoint**.

The threshold is deliberately **untuned**. Sweeping it does find a value that fits the realised
target better (−2.0° cuts disagreement from 3,034 rows to 587), but tuning a geometric mask
against the target destroys the reason the mask exists. The cost of the untuned choice was
measured: the climatology floor's daylight RMSE moves 108.78 → 109.86 W/m² and R² 0.8514 →
0.8456.

**The clearness index now uses the literature's standard definition.** It used to be
`kt = ALLSKY / CLRSKY` (a clear-sky index); it is now

> **kt = GHI / (I₀ · cos θz)**

with **top-of-atmosphere** horizontal irradiance in the denominator. This is an upgrade, not a
fallback:

| | Old (clear-sky denominator) | New (top-of-atmosphere denominator) |
|---|---|---|
| Source | The provider's own product | Pure astronomy, nothing fitted |
| Comparability | Provider-specific | The standard definition, directly comparable to the literature |
| Share with kt > 1 | 2.91% | **0.001%** (2 rows out of 150,746) |
| 99th percentile | 1.003 | **0.801** |

**Caveat — the scale changed and must not be mixed with old numbers.** A cloudless hour reads
kt ≈ 0.75–0.80 on this scale (atmospheric transmittance) where the clear-sky index read ≈ 1.0.
The sky-condition cut-offs were moved to the literature's bands for this index accordingly:
**clear kt > 0.65**, **overcast kt < 0.35**.

### 0.3 Two analyses were removed

Two things needed the clear-sky **magnitude**, not just the sun's position, and could not be
recovered. Both removals are backed by measurement rather than assumption:

- **The smart-persistence reference** (`ŷ(T) = kt(T−24h) × CLRSKY(T)`). Rebuilt on the
  top-of-atmosphere denominator it **collapses into plain persistence**: daylight RMSE 121.93 /
  MAE 72.42 against plain persistence's 121.85 / 72.38. The reason is simple — top-of-atmosphere
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

The cleanest evidence that nothing was lost: the naive reference floor is **unchanged to the
decimal** after the drop.

### 0.5 The record got longer

The `-999` tail fell from 2,208 hours to **744**, and it now affects the target column only.
That adds **1,464 hours (61 days) per province**.

---

## 1. Executive summary — the seven findings that belong in the paper

**(1) The five provinces do carry the climate-diversity claim, but asymmetrically.** Mean daily
insolation is Van 5.00, Antalya 4.97, Konya 4.89 and Ankara 4.68 kWh/m²/day — a band 7% wide.
Rize sits 21–26% below it at 3.71. The real difference is not in level but in
**predictability**: Rize's daily clearness index is 0.463 against 0.574–0.609, its overcast-day
share **28.9%** against 6.4–11.3%, its clear-day share 13.8% against 43.7–50.0%, and its
between-day coefficient of variation 0.566 against 0.436–0.489. Rize is where the paper's
cross-province transfer claim is actually tested.

**(2) Night rows improve every metric for free.** 49.6% of rows are geometrically night and all
of them are exactly zero. The same climatology reference scores RMSE 78.3 W/m² / R² 0.920 over
24 hours and RMSE 109.9 / R² 0.846 over daylight hours. Night rows cut RMSE by 29% and inflate
R² by 0.074. **The daylight figure is the one comparable to the literature.**

**(3) The floor to beat is climatology — and the winner depends on the metric.** On daylight
hours, in the model's own chronological test window, scored through the pipeline: climatology
RMSE **109.86** / MAE 75.72 / R² **0.8456**; persistence 121.56 / MAE **72.15** / R² 0.8110.
Climatology wins on RMSE and R², persistence on MAE. To be a result, the LSTM has to clear
**all three**.

**(4) Much of the raw correlation is solar geometry.** Pooled over daylight hours, temperature
correlates with the target at +0.515 raw but +0.307 partially, within a (province, month, hour)
cell. Surface pressure flips from −0.038 to **+0.268** and dew point from +0.042 to **−0.272**.
The stronger statement: **three variables have inconsistent raw-correlation signs across the
five provinces, while after conditioning on geometry all six agree in sign everywhere.**

**(5) Information on the time axis is exhausted within a 24-hour window.** At the daily scale —
which is what matters for a 24-hour-ahead forecast — the clearness index's partial
autocorrelation is 0.417–0.561 at lag 1 and drops to **−0.002…0.098** at lag 2. Raising
`lookback_hours` to 48 means adding a second day whose partial correlation is near zero.

**(6) The feature set is now largely clean, with one hidden redundancy left.** Dropping the 10 m
wind in V2 left no pair above |r| = 0.9. But `T2MDEW` is reproducible from `T2M` and `RH2M` by
the Magnus relation at **r = 0.99919 and 0.30 °C RMSE** — it is not a measurement but a
deterministic transform of two columns already present. Pairwise correlation cannot see this
(it is a two-variable function); 12 of the 13 features are independent.

**(7) The test window spans all four seasons; the validation window does not.** Test is 9,097
hours = **379 days** (2025-05-16 → 2026-05-30), so there is no seasonal bias. The validation
window (2024-08-12 → 2025-05-16) **contains no June and no July** — the year's brightest and
steadiest months. That window is the conformal layer's calibration set; see §9.

---

## 2. Dataset and coverage

| | |
|---|---|
| Source | NASA POWER hourly, `SolarData_Merve(140926_V2).xlsx`, one sheet per province |
| Provinces | Ankara, Antalya, Konya, Rize, Van |
| Span | 2019-06-30 00:00 → 2026-05-30 23:00 |
| Hours per province | 60,648 (2,527 days ≈ 6.92 years) |
| Total rows | 303,240 |
| Daylight rows | 152,893 (**50.42%**) |
| Missing values | none |
| Features | 13 |
| Target | `ALLSKY_SFC_SW_DWN`, W/m² |

Coverage is perfectly balanced: all five provinces share the same 60,648 hours. Mean daylight
duration runs 12.07–12.14 h per day; the spread across provinces is the expected consequence of
their latitudes.

The chronological split (train 0.74 / val 0.11 / test 0.15) falls on **identical dates** for all
five:

| Split | Range | Hours | Days |
|---|---|---|---|
| Train | 2019-06-30 → 2024-08-11 | 44,879 | 1,870 |
| Validation | 2024-08-12 → 2025-05-16 | 6,671 | 278 |
| **Test** | **2025-05-16 → 2026-05-30** | **9,097** | **379** |

The test window covers 13 calendar months and all four seasons (Spring 12,725, Summer 11,040,
Autumn 10,920, Winter 10,800 hours).

**Caveat.** `train_ratio`/`val_ratio` were chosen so the test window exceeds a full year.
Changing them breaks the four-season property and makes the score season-biased.

### 2.1 The clock is per-site local solar time, not a shared time zone

The hour column is not a common time zone; each province is recorded in its own local solar
time. Taking the centre of mass of mean irradiance as the peak hour gives

> Konya 11.24 ≈ Ankara 11.24 < Antalya 11.41 < Van 11.58 < Rize 11.91

which is the **reverse** of the ordering a shared clock would produce, and matches the
`UTC + round(lon/15)` expectation to within 0.11 h. This is no longer just an observation: it is
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

Pooled, daylight hours: mean **384.2 W/m²**, median 341.7, sd 277.7, maximum 1216.7 (Van).
Skew +0.425, excess kurtosis −0.944. Between-province sd 44.7.

Over all 24 hours: mean 193.7, median 8.3, skew +1.279.

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
303,204 of 303,240 rows. It is still inadmissible, for two reasons, the second decisive:

1. *It selects the evaluation set using the answer.* The daylight subset is the denominator of
   every headline metric. If membership depends on the realised target, a heavily overcast
   twilight hour reads zero and quietly leaves the subset — the hours where the model is worst
   are the ones that drop out. On this record quantisation makes 36 rows behave that way; small,
   but the mechanism is not bounded by anything.
2. *It cannot be evaluated at prediction time.* `clamp_night_to_zero` has to decide, for an hour
   24 h ahead, whether the sun will be up, and `y` is not available then. A target-based rule
   would report skill that is unattainable operationally. Geometry is therefore required
   regardless — and once it exists, a second definition for the metric would be incoherent.

**A climatological (province, month, hour) cell mean.** Used in the first EDA round and too
coarse: within one month sunrise shifts 30–60 minutes, so the cell mean marks the whole edge
hour as daylight. It admitted 5,266 rows of genuine night.

**How the new definition sits against the data.** Comparing the geometric mask with `target > 0`:

- Hours called daylight that read exactly zero: **1** (in 303,240 rows).
- Hours called night that carry irradiance: 2,968. These are twilight hours in which the sun
  rises part-way through the interval. They carry **0.024% of total daylight energy**, and
  dropping them makes the daylight subset *harder*, not easier. That is the safe direction.

### 3.3 Diurnal and seasonal structure

Hour of day alone explains **73.1%** of the variance over 24 hours (pooled η²); within the
daylight subset that falls to 48.8%. Day of year explains 8.6% and 14.8% respectively.

- Three quarters of a 24-hour score comes from knowing the day/night cycle — not from the model.
- Within daylight, hour is still dominant but the seasonal share nearly doubles.

A harmonic (sin/cos) fit captures essentially all of the η² (24 h: 0.7285 against 0.7313).
**Recommendation:** the current sin/cos encoding loses nothing relative to categorical hour
dummies and should be kept.

### 3.4 Seasonality: irradiance and predictability move in opposite directions

Coefficient of variation of the daily total:

| Province | Winter | Summer | Winter/Summer |
|---|---|---|---|
| Ankara | 0.432 | 0.142 | 3.04× |
| Antalya | 0.383 | 0.100 | 3.82× |
| Konya | 0.397 | 0.130 | 3.05× |
| Van | 0.326 | 0.120 | 2.72× |
| Rize | 0.504 | 0.279 | **1.81×** |

Summer days are not only brighter but **1.8–3.8 times less variable**. Error metrics will behave
very differently by season, and a small absolute error in winter does not mean the model is good
in winter — there is simply less to predict.

**Caveat.** Rize is outside the band: even its summer carries variability close to the other
provinces' winter. Any sentence covering Rize must give the range as **1.8–3.8×**, not "3–4×".

### 3.5 Between-year variability: small, but not zero

Complete calendar years (2020–2025), mean daily insolation in kWh/m²/day:

| Province | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | Best/worst |
|---|---|---|---|---|---|---|---|
| Ankara | 4.83 | 4.73 | 4.64 | 4.56 | 4.72 | 4.90 | 7.2% |
| Antalya | 5.06 | 5.13 | 5.04 | 4.86 | 4.99 | 5.04 | 5.6% |
| Konya | 5.01 | 4.98 | 4.87 | 4.84 | 4.90 | 5.09 | 5.1% |
| Rize | 3.91 | 3.75 | 3.54 | 3.68 | 3.82 | 3.74 | **10.3%** |
| Van | 4.95 | 5.26 | 5.16 | 4.87 | 4.95 | 5.05 | 8.0% |

The between-year relative sd is 1.8–3.3%. Training and test years being different is not by
itself a large shift — but Rize carries a **10% year effect**, which means part of the variation
in Rize's test score comes from the year rather than from the model.

---

## 4. Meteorological variables

Pooled, daylight hours:

| Column | Mean | SD | Range | Between-province SD | Note |
|---|---|---|---|---|---|
| `T2M` (°C) | 15.60 | 10.32 | −23.6 … 42.3 | 3.83 | |
| `RH2M` (%) | 53.60 | 23.63 | 3.4 … 100 | **11.19** | Most discriminating; the one real predictor |
| `T2MDEW` (°C) | 4.27 | 7.05 | −27.5 … 22.9 | 4.43 | Derivable (§6.3) |
| `PS` (kPa) | 88.28 | 6.03 | 75.8 … 97.7 | **6.72** | Variance is entirely elevation |
| `WS2M` (m/s) | 2.61 | 1.54 | 0.01 … 13.7 | 0.51 | |
| `PRECTOTCORR` (mm/hour) | 0.072 | 0.263 | 0 … 7.4 | 0.049 | Skew +8.1 |

**Surface pressure does not behave like a meteorological variable here.** Its pooled sd is
6.03 kPa but its between-province sd is 6.72 — the variance is entirely across provinces, not
within them (Van 77.7, Konya 87.9, Ankara 88.8, Rize 91.2, Antalya 96.0 kPa). In a pooled model
`PS` effectively acts as an **elevation / province-identity indicator** and duplicates what the
city embedding already carries. Its within-province variation (sd ≈ 0.4–0.5 kPa) is the real
synoptic signal, and it explains why the partial correlation flips sign in §6.1.

### 4.1 Precipitation: effectively a binary variable

**66.7% of daylight hours are exactly zero**, and the non-zero tail is heavily skewed (skew
+8.1). Correlation with the target under three encodings:

| Province | Binary (rain / no rain) | Raw amount | `log1p(amount)` |
|---|---|---|---|
| Ankara | **−0.168** | −0.101 | −0.115 |
| Antalya | −0.215 | −0.178 | −0.206 |
| Konya | **−0.192** | −0.116 | −0.138 |
| Rize | −0.222 | −0.219 | **−0.250** |
| Van | **−0.188** | −0.139 | −0.162 |

In three provinces a simple "is it raining" indicator is more informative than the raw amount;
in Rize `log1p` leads.

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
| Van | 215° | **0.468** | 71° |
| Rize | 270° | 0.244 | 96° |
| Konya | 337° | 0.227 | 99° |
| Antalya | 43° | 0.188 | 105° |
| Ankara | 332° | 0.124 | 117° |

The resultant length runs from 0 (completely dispersed) to 1 (a single direction). **Only Van
has a dominant direction**; in the other four, wind direction is practically uniform and
therefore almost empty as a predictor.

**Caveat.** The share of calm hours differs sharply between provinces (`WS2M ≤ 1 m/s`: Rize
16,175 hours, Konya 8,606), and in those hours the direction is noise; the filter must be stated
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
| PACF lag 1 | 0.905 | 0.866 | 0.900 | 0.920 | 0.867 |
| PACF lag 2 | −0.295 | −0.373 | −0.270 | −0.345 | −0.215 |
| PACF lag 3 | −0.013 | +0.087 | −0.016 | −0.006 | −0.006 |
| ACF lag 24 | 0.630 | 0.724 | 0.653 | 0.531 | 0.678 |

Lag 1 is above 0.87 everywhere, lag 2 is clearly negative and lag 3 sits at zero: hourly kt
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
| PACF day 1 | 0.541 | 0.545 | 0.557 | **0.417** | 0.561 |
| PACF day 2 | 0.098 | 0.094 | 0.076 | **−0.002** | 0.069 |
| PACF day 3 | 0.112 | 0.122 | 0.082 | 0.066 | 0.110 |
| ACF day 30 | 0.177 | 0.229 | 0.164 | **0.083** | 0.165 |

The fall from day 1 to day 2 is five- to six-fold. **This is the evidence behind
`lookback_hours = 24`:** going to 48 hours means adding a second day whose partial correlation
lies between −0.002 (Rize) and 0.098 (Ankara). The conclusion is unchanged from the earlier data
version despite the denominator change — so the finding the decision rests on is not sensitive
to the definition.

The residual autocorrelation at day 30 (0.08–0.23) is seasonal trend, not memory;
`doy_sin`/`doy_cos` already carries it.

**Caveat.** Rize is outside the band on every line, and always in the direction of less memory.

### 5.3 Ramps

Absolute change between consecutive daylight hours:

| Province | Median \|Δ\| | p90 | p99 | Share > 200 W/m² | \|Δkt\| p99 |
|---|---|---|---|---|---|
| Ankara | 105.6 | 188.9 | 211.1 | 3.4% | 0.222 |
| Antalya | 116.7 | 191.7 | 219.4 | 6.0% | 0.218 |
| Konya | 111.1 | 194.4 | 216.7 | 6.1% | 0.222 |
| Rize | 83.3 | 166.7 | 213.9 | 1.7% | 0.206 |
| Van | 116.7 | 194.4 | 216.7 | 6.7% | 0.224 |

Most of the ramp in raw irradiance is geometry. In the Δkt column the provinces are strikingly
**close together** (0.206–0.224): Rize's raw ramps look small only because its sun is weak to
begin with, not because its atmosphere is steadier.

### 5.4 Daylight blocks

Daylight hours arrive in uninterrupted blocks: 2,527 blocks per province (one per day), median
length 12 hours, shortest 9, longest 14 (Antalya) / 15 (the others). No block reaches 24 hours.

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
| `RH2M` | −0.628 | **−0.530** | The one real predictor; strong under both measures |
| `T2M` | +0.515 | +0.307 | Half of it is geometry |
| `PRECTOTCORR` | −0.168 | **−0.328** | **Doubles** once geometry is held fixed |
| `T2MDEW` | +0.042 | **−0.272** | **Changes sign** |
| `PS` | −0.038 | **+0.268** | **Changes sign** |
| `WS2M` | +0.143 | −0.150 | **Changes sign** |

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

Pooled over daylight hours, the largest difference is **−0.059** for precipitation, followed by
+0.047 for `WS2M`. No variable exceeds 0.06 (`T2M` −0.017, `T2MDEW` −0.009, `PS` −0.008, `RH2M`
+0.001). There is no non-monotonic relationship.

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
| `T2M` – `RH2M` | −0.673 | −0.676 |
| `T2M` – `T2MDEW` | +0.609 | +0.594 |
| `T2MDEW` – `PS` | +0.521 | +0.482 |

**Caveat — pairwise correlation cannot see the redundancy that matters.** `T2MDEW` is not a
measurement but a formula: reproduced from `T2M` and `RH2M` by the Magnus relation it reaches
r = **0.99919**, RMSE = **0.30 °C** over 24 hours (daylight: r = 0.99957, RMSE 0.23 °C), i.e.
measurement-noise level. Pairwise correlation misses it because it is a two-variable function —
the `T2M`–`T2MDEW` correlation is only 0.609. A collinearity table is a **lower bound** on
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
| Daily insolation | 3.71 kWh/m²/day | 4.68 – 5.00 |
| Daily clearness index kt | **0.463** | 0.574 – 0.609 |
| Hourly kt median | **0.422** | 0.565 – 0.600 |
| Clear-day share (kt > 0.65) | **13.8%** | 43.7 – 50.0% |
| Overcast-day share (kt < 0.35) | **28.9%** | 6.4 – 11.3% |
| Between-day CV | **0.566** | 0.436 – 0.489 |
| Daily PACF, day 1 | **0.417** | 0.541 – 0.561 |
| Daily ACF, day 30 | **0.083** | 0.164 – 0.229 |
| Climatology daylight RMSE | **133.8 W/m²** | 97.2 – 108.2 |
| Climatology daylight R² | **0.710** | 0.853 – 0.883 |

Rize's **best season** (summer, kt = 0.522) is close to the other provinces' **winter**
(0.477–0.556). This is not a seasonal difference but a regime difference.

**Caveat — the pooled average buries Rize.** With four provinces clustered together, the pooled
mean outvotes Rize four to one. That is exactly why the metric table carries a separate
`Aggregate_excl_Rize` row: without it, the contribution of cross-province transfer is invisible.

**Recommendation.** In the paper Rize should be introduced not as "the difficult province" but as
**the second regime**. The climate-diversity claim is only accurate in that framing: four
provinces are variations on one regime, and Rize is a second one on its own.

### 7.2 Van is the clearest, and the most extreme

Van has the highest daily insolation (5.00 kWh/m²/day), the highest clearness index (0.609), the
lowest overcast-day share (6.4%) and the lowest winter CV (0.326) — even its winter is
predictable. It is also the only province with a dominant wind direction (§4.2).

**Caveat — Van's 1216.7 W/m² maximum is not a physical finding.** That row (2020-02-17 15:00)
corresponds to kt = 2.24: the measured irradiance is more than twice what reaches the top of the
atmosphere at that hour (544 W/m²). It is physically impossible, i.e. a measurement or back-fill
artefact. Van's combination of altitude and dry air is a real phenomenon, but **it must not be
argued from this row**.

### 7.3 The limits of the clearness index

Under the new definition kt behaves impeccably: only **2** of 150,746 lit hours exceed 1.0 and
the 99th percentile is 0.801. This is a marked improvement over the clear-sky denominator, where
2.9% of hours read above 1 — all of it a quantisation artefact.

**Caveat.** kt is not clipped anywhere and must not be.

---

## 8. The reference floor: the numbers the model has to beat

Two naive references are scored **in the model's own chronological test window** with **the same
windowing**:

- **Persistence:** repeat the value from 24 hours earlier.
- **Climatology:** the training-rows mean of the (province, month, hour) cell.

Pooled results, through the pipeline (`scripts/03_run_naive_baselines.py`):

| Reference | Scope | RMSE | MAE | R² |
|---|---|---|---|---|
| Persistence | 24 h | 86.67 | 36.72 | 0.9021 |
| Climatology | 24 h | 78.33 | 38.53 | 0.9200 |
| Persistence | **daylight** | 121.56 | **72.15** | 0.8110 |
| Climatology | **daylight** | **109.86** | 75.72 | **0.8456** |

By province, daylight, climatology: Antalya 97.2 / Van 98.8 / Konya 107.1 / Ankara 108.2 /
**Rize 133.8** W/m²; R² 0.883 / 0.876 / 0.861 / 0.853 / **0.710**.

**To be a result, the LSTM must beat 109.86 W/m² on RMSE and 0.8456 on R² (climatology) *and*
72.15 W/m² on MAE (persistence), on daylight hours.** Winning on one metric is not enough; the
champion changes with the metric.

**Caveat — smart persistence is absent from this table.** It required a clear-sky magnitude and
collapses into plain persistence on the top-of-atmosphere denominator (§0.3). In the earlier data
version it was the MAE champion; that role now belongs to plain persistence.

**Caveat — 24-hour R² values must not enter the paper.** Climatology scores R² = 0.920 over 24
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
climatology's daylight RMSE is 133.8 in Rize against 97.2 in Antalya — a 38% gap. That is why a
single scalar calibration factor cannot work.

**(3) Night elements inflate interval metrics structurally.** With `clamp_night_to_zero` on,
every night element receives a degenerate `[0, 0]` interval around a true value of exactly 0, so
it is covered **by definition**. 49.6% of elements are night, so roughly half of the 24-hour CP
mixture is 1.0 before the model contributes anything. **A run must be judged on daylight
CP ≈ 0.95 first**, then on daylight PINW/CWC/CRPS.

**(4) The calibration set's defect has changed direction.** The conformal layer uses the
validation split as its calibration set, and that split has two known defects: early stopping
already saw it, and it does not cover the whole calendar. **With the new data the missing months
moved from April–May to June–July** (validation window 2024-08-12 → 2025-05-16). This is worse: a
season-indexed grid's Summer cell would be fitted from 12–31 August alone, i.e. 7% of the
validation window. The bias also runs in the dangerous direction — August is *less* variable than
the June–July it stands in for (daily kt sd lower by 0.007–0.036 in all five provinces), so the
factor learned there produces intervals that are **too narrow**.

**Recommendation.** This shift must be documented before the season-indexed conformal grid is
re-run. The fix should not be sought in the split ratios (the test window's four-season property
is worth more); taking the calibration set from a separate slice of the last training year is
testable and costs seconds.

---

## 10. Limitations that must be stated in the paper

1. **The data is satellite-derived, not ground-station.** NASA POWER derives irradiance from
   satellite observations; precipitation totals are known to run low in Rize and Antalya.

2. **The target is quantised to 2.78 W/m² steps** (§0.1). The effect on metrics is negligible
   (sd 0.80 W/m²) but it bears directly on the definition of daylight (§3.2).

3. **The daylight mask is computed, not measured** (§0.2). The province coordinates, the time
   convention and the threshold choice must be stated explicitly in the methods section. The cost
   of the untuned threshold is measured: climatology floor RMSE 108.78 → 109.86.

4. **The clearness index changed scale** (§0.2). kt values from earlier documents (Rize 0.697,
   others 0.806–0.840) **cannot** be carried over to this data.

5. **There is no smart-persistence reference and no `clearsky_index` arm** (§0.3). `ABLATION.md`
   §6–§7 stand as correct results about the superseded dataset but cannot be re-measured.

6. **The feature set narrowed twice** (17 → 16 → 13) across three different exports (§0.4). A
   single column change makes ledger rows incomparable; any runs meant to be compared must come
   from the same version.

7. **There are only five provinces and four of them share a regime** (§7.1). The
   "climate diversity" claim must be presented with that asymmetry.

8. **Between-year variability is small but non-zero** (§3.5); 10.3% in Rize.

9. **Every pre-existing ledger row is invalid** and has been moved to `outputs/archive/`. They
   were produced under a different feature set, different units, a different daylight definition
   and a record 61 days shorter. They must be re-run under **new ids**.

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
| `persistence_baseline.csv` | §8 (descriptive twin; the quoted floor comes from the pipeline) |
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
| Unit-conversion verification | max deviation 1.39 W/m², mean 0.70, over the 59,184 shared hours | §0.1 |
| Precipitation resolution loss | 38.7% of previously rainy hours now read exactly zero | §0.1 |
| Cost of the geometric mask | climatology daylight RMSE 108.78 → 109.86, R² 0.8514 → 0.8456 | §0.2, §10(3) |
| Rejection of a tuned threshold | a tuned −2.0° gives 587 disagreements, the untuned 0° gives 3,034 | §0.2 |
| Mask vs `target > 0` | daylight-but-zero: 1 row; night-but-positive: 2,968 rows, 0.024% of daylight energy | §3.2 |
| Smart persistence degenerating | on the TOA denominator, daylight RMSE 121.93 / MAE 72.42; plain persistence 121.85 / 72.38 | §0.3, §8 |
| `WD2M` – `WD10M` redundancy (measured on V1; the 10 m column is gone in V2) | median angular difference 0.30°, mean 1.56°, p95 6.30°; sin/cos r = 0.996 / 0.997; `WS2M`–`WS10M` r = 0.987 | §0.4, §6.3 |
| Dew point reproduced by Magnus | r = 0.99919, RMSE 0.30 °C (24 h); r = 0.99957, RMSE 0.23 °C (daylight) | §1(6), §6.3 |
| Precipitation encodings vs the target | table in §4.1; daylight zero share 66.7% | §4.1 |
| Annual precipitation totals (unit check) | Ankara 340, Konya 326, Van 343, Antalya 664, Rize 1399 mm/year | §4.1 |
| Peak hours (local-solar-time check) | Konya 11.2406, Ankara 11.2409, Antalya 11.4107, Van 11.5751, Rize 11.9069 | §2.1 |
| Split boundaries and the validation window's missing months | test 9,097 hours / 379 days; no June or July in validation, Summer cell 480 hours | §2, §9(4) |
| Direction of the calibration gap | August's daily kt sd is 0.007–0.036 lower than June–July's | §9(4) |
| Between-year variability | table in §3.5 | §3.5 |
