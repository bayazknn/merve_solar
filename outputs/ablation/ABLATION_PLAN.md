# Ablation plan

This document explains the ablation experiments: what they are, why we run them, how we measure
them, and how to read the results. It is written for a reader who does not know the project.
Results are added in the last section once the runs finish.

## 1. The project in one paragraph

We forecast solar irradiance, the power of sunlight reaching the ground (in W/m²), for every hour
of the next 24 hours. We do this for five Turkish provinces with different climates: Ankara,
Antalya, Konya, Rize and Van. The data are hourly NASA POWER weather records. The forecast is not
a single number per hour. It is a **range of likely values** (a predictive distribution), so a
user also knows how uncertain the forecast is.

## 2. The final method

All settings below were chosen in the tuning stage, using only the validation data (1 September
2024 to 11 June 2025). The test data (11 June 2025 to 29 June 2026) were not looked at until the
method was frozen.

### 2.1 How a forecast is made, step by step

1. **Input.** The last 24 hours of 13 weather variables for one province: irradiance itself,
   temperature, humidity, dew point, pressure, wind speed, wind direction, precipitation, and
   the hour of day and day of year (encoded as sine and cosine).
2. **Province code.** A small learned code of 4 numbers tells the network which province it is
   looking at. One network serves all five provinces.
3. **LSTM network.** It reads the 24 hours in order and summarises them in 256 numbers. A small
   head turns that summary into 24 outputs, one per hour of the next day.
4. **Ensemble of 6 networks.** Six copies of the network are trained, each on a different random
   resampling of the training data. The data are resampled in one-week blocks, so weather
   patterns stay intact. The networks disagree more where the data say less.
5. **MC-Dropout.** During prediction, each network randomly switches off 20% of the neurons in
   its head, 100 times. The spread of the answers shows how unsure each network is.
   6 networks × 100 passes = **600 forecast values per hour**.
6. **Conformal correction.** The 600 values are too close together, so the raw ranges miss the
   real value too often. The correction measures, on the validation data, how much too narrow
   they are. It does this separately for each province and each hour ahead, then widens the
   ranges by that factor. It does not move the central forecast.
7. **Night.** When the sun is below the horizon, the forecast is set to exactly zero.

### 2.2 Architecture

```
input: 24 hours x (13 weather variables + 4-number province code) = 24 x 17
  -> LSTM, 1 layer, 256 units          (reads the 24 hours, keeps the last state)
  -> Dropout 20%
  -> Dense 256 -> 128, ReLU
  -> Dropout 20%
  -> Dense 128 -> 24                   (one output per hour ahead)
317,612 trainable parameters per network
```

### 2.3 Final configuration

| Setting | Value | How it was chosen |
|---|---|---|
| Look-back window | 24 hours | Tuning stage 1 (48 h and 72 h were worse) |
| LSTM size | 1 layer, 256 units; head 128 units | Stage 2 (best of 13 sizes) |
| Dropout rate | 0.2 | Stage 3 |
| Learning rate | 0.0005 (Adam optimiser) | Stage 3 |
| Batch size | 128 | Fixed |
| Training stop | Stop after 5 epochs without improvement on validation; at most 100 epochs. The learning rate halves after 7 epochs without improvement. | Fixed, patience from stage 3 |
| Loss | Mean squared error, plus a small penalty (weight 0.1) for predicting below 0 W/m² | Fixed |
| Resampling block | 168 hours (one week) | Stage 4 (block length barely matters) |
| Ensemble size × dropout passes | 6 networks × 100 passes | Stage 5 |
| Conformal correction | Separate factor per province and per hour ahead (5 × 24 = 120 factors) | Validation-only check |

### 2.4 Results on the test year (daylight hours, 5 seeds)

| Metric | Result |
|---|---|
| RMSE | 85.92 ± 0.09 W/m² |
| MAE | 58.16 ± 0.47 W/m² |
| R² | 0.906 |
| Coverage of the 95% range (CP) | **0.953** (0.819 without the correction) |
| Range width (MPIW) | 339.5 W/m² (192.0 without the correction) |
| PINW | 0.329 |
| CRPS | 43.47 ± 0.10 W/m² |

| Province | RMSE | R² | CP | CRPS |
|---|---|---|---|---|
| Ankara | 85.3 | 0.909 | 0.956 | 43.51 |
| Antalya | 73.2 | 0.934 | 0.954 | 37.09 |
| Konya | 83.3 | 0.916 | 0.941 | 43.24 |
| Rize | 106.2 | 0.822 | 0.949 | 53.01 |
| Van | 77.7 | 0.923 | 0.962 | 40.46 |

The error grows with lead time, from RMSE 42 W/m² one hour ahead to 98 W/m² 24 hours ahead. After
the correction, coverage is between 0.950 and 0.957 at every hour ahead. Without it, coverage falls
from 0.95 to 0.77, because the raw range does not widen with lead time.

## 3. What an ablation is

An ablation changes part of the method, retrains it, and measures what changed. If removing a
part makes the forecasts worse, that part is doing useful work. If nothing changes, the part is
not needed, and that is also a result worth reporting.

Rules that keep the comparisons fair:
- **Same everything else.** All arms share the data split, the training days, the network
  architecture, the training settings and the metrics code. A test checks that each arm differs
  from the final method only in the settings its name says.
- **Paired seeds.** The method's own runs (seeds 42, 43) are reused, so each comparison is made
  seed by seed.
- **Nothing is selected.** Ablations explain the method; they do not tune it. So they are
  reported on the **test** year, with the validation numbers beside them.

## 4. The metrics: what they mean and why we use them

All headline numbers use **daylight hours only** (sun above the horizon). At night the irradiance
is exactly zero and every arm predicts zero. Night hours would make every metric look better
without saying anything about the forecast. "Daylight" is decided from the sun's position alone,
never from the measured value.

### Accuracy of the central forecast

These three metrics use one number per hour: the average of all forecast values for that hour.

| Metric | Definition | Purpose | Better when |
|---|---|---|---|
| **RMSE** (W/m²) | Square root of the average squared error. | Main accuracy measure. Large errors count more, so it is sensitive to badly missed cloudy hours. | Lower |
| **MAE** (W/m²) | Average absolute error. | Typical size of an error, in the same unit as the data. Easier to explain than RMSE. | Lower |
| **R²** | Share of the variation in irradiance that the forecast explains (1 = perfect, 0 = no better than always predicting the average). | Lets us compare provinces whose irradiance levels differ. | Higher |

### Quality of the uncertainty range

The **95% range** (interval) runs from the 2.5th to the 97.5th percentile of the forecast values.
A good range contains the real value 95% of the time, and is as narrow as possible while doing so.

| Metric | Definition | Purpose | Better when |
|---|---|---|---|
| **CP**, coverage | Share of hours where the real value fell inside the 95% range. | Checks that the ranges are **honest**. 0.95 is the target. Below 0.95 the method is overconfident; above 0.95 it is too cautious. | Closer to 0.95 |
| **MPIW** (W/m²) | Average width of the range. | Measures how **useful** the range is. A very wide range is always right but tells the user little. | Narrower, if CP is on target |
| **PINW** | MPIW divided by the range of observed irradiance (about 1,040 W/m²). | The same as MPIW but without units, so it can be compared with other studies. | Lower, if CP is on target |
| **CRPS** (W/m²) | Compares the whole forecast distribution with the real value. It rewards distributions that are both close to the real value and no wider than needed. For a single-number forecast it equals MAE. | **One overall score** for the probabilistic forecast. It joins accuracy and uncertainty in one number, so it is the fairest single number for comparing a range forecast with a single-number one. | Lower |

**How to read CP and width together.** Coverage first, width second. CP 0.95 with width 340 is
better than CP 0.95 with width 380. CP 0.80 with width 190 is not better: that range is narrow
because it is wrong one hour in five.

### By province and by forecast hour

Every metric is also reported for each province and for each hour ahead (1 to 24). The aggregate
can hide a problem in one province, for example Rize, which is much cloudier than the others. It
can also hide a problem at long lead times.

### When is a difference real?

The ensemble arms have 2 seeds, and the benchmark arms 3 (Section 5.3 explains why). A difference
between two arms counts as real when:
1. it has the same sign on every seed, and
2. it is larger than three times the seed-to-seed variation of the final method (0.3 W/m² in
   RMSE or CRPS), and
3. a paired test over the test days agrees. Both arms forecast the same days, so we compare them
   day by day and resample whole weeks to get a confidence interval for the difference.

## 5. The experiments

### 5.1 Design: two questions, one table

The ablation crosses two questions:

- **One model for all provinces, or one per province?** (rows)
- **MC-Dropout, normal dropout, or a plain LSTM?** (columns)

| | **MC-Dropout** (final method) | **Normal dropout** | **Plain LSTM** (benchmark) |
|---|---|---|---|
| **One model, all provinces** | `global_mc_dropout` (already run) | `global_normal_dropout` | `global_plain_lstm` |
| **One model per province** | `per_city_mc_dropout` | `per_city_normal_dropout` | `per_city_plain_lstm` |

What each column means:

| Column | Networks | Values per hour | Correction | In plain words |
|---|---|---|---|---|
| **MC-Dropout** | 6 | 600 | yes | The final method. |
| **Normal dropout** | 6 | 6 | yes | The same 6 trained networks, but dropout is switched off when predicting, as in a standard network. Each network gives one answer. |
| **Plain LSTM** | 1 | 1 | none | The **benchmark**: one network of the same architecture, trained the same way, with dropout off at prediction. No ensemble and no range. This is what a standard LSTM study would report. |

Dropout is used **during training** in all three columns. The columns differ in what happens
**at prediction time**, and in how many networks are trained.

**One model per province** means five separate networks (or ensembles), each trained only on its
own province's data and scaled on its own data. It has no province code, because each model only
sees one province.

### 5.2 What each comparison answers

**A. All provinces or one per province?** Compare each column's two rows.
- Look at **each province's** RMSE and CRPS, not only the aggregate.
- If the shared model is better in most provinces, sharing data across provinces helps
  (positive transfer). This is a claim the paper wants to make.
- If only some provinces gain, for example the ones with similar climates, the paper must say
  so. Rize, whose climate differs most, is the province to watch.
- Repeating the comparison in all three columns shows whether the answer depends on the
  uncertainty layer. If the plain LSTM also gains from sharing, the gain comes from the data,
  not from the ensemble.
- Caveat: each per-province model also scales its data on its own, which by itself may favour
  that arm slightly.

**B. MC-Dropout or normal dropout?** Compare the first two columns in the same row.
- RMSE, MAE and R² show whether averaging 100 dropout passes improves the central forecast. In
  tuning the difference was very small (about 0.05 W/m²).
- **Before correction**, CP and width show how much of the range MC-Dropout creates. In tuning,
  6 networks without MC-Dropout covered only 28% of hours, against 79% with it.
- **After correction**, both should cover about 95%. Then compare **width and CRPS**: this is the
  practical cost of dropping MC-Dropout. With only 6 values per hour, the correction must widen
  the range a lot, and the distribution is coarse. So expect a clearly higher CRPS.
- Both raw and corrected numbers come from each run's correction table, so no extra runs are
  needed.

**C. How much does the method gain over the benchmark?** Compare the first and third columns.
- **CRPS**: the plain LSTM gives one number per hour, so its CRPS equals its MAE. The gap
  between that and the method's CRPS (43.5 W/m²) is the value of forecasting a range instead of a
  number. This is the paper's headline comparison.
- **RMSE and MAE**: whether the ensemble also makes the central forecast more accurate. A single
  network in tuning had a test RMSE 0.5 to 1.7 W/m² higher than the ensemble.
- The plain LSTM has no range, so CP, MPIW and PINW are not reported for it.

### 5.3 Number of runs and seeds

| Arm | Seeds | New runs | Relative cost per run |
|---|---|---|---|
| `global_mc_dropout` | 42, 43 | 0 (final runs reused) | n/a |
| `per_city_mc_dropout` | 42, 43 | 2 | full (5 provinces × 6 networks, each on a fifth of the data) |
| `global_normal_dropout` | 42, 43 | 2 | full |
| `per_city_normal_dropout` | 42, 43 | 2 | full |
| `global_plain_lstm` | 42, 43, 44 | 3 | about a sixth |
| `per_city_plain_lstm` | 42, 43, 44 | 3 | about a sixth |
| **Total** | | **12** | |

Why these seed counts:
- **Ensemble arms, 2 seeds.** With 6 networks, results barely change from seed to seed: over the
  final method's 5 seeds, RMSE varies by 0.09 W/m² and CRPS by 0.10 W/m². Two seeds are enough to
  check that a difference has the same sign twice.
- **Plain LSTM, 3 seeds.** A single network varies 3 to 5 times more between seeds (0.25 to
  0.5 W/m² in tuning). It is also cheap to train. As the benchmark, it should not look better or
  worse by the luck of one seed.

The earlier draft had 30 runs (42 with the optional group). This design has 12, and the full
method's runs are reused.

### 5.4 Candidates for later discussion

These were in the earlier draft and are left out to save time. Each can be added later without
changing the runs above:
- 6 networks trained on the same data instead of resampled data (does the resampling matter?)
- the shared model without the province code
- the shared model without Rize, or without each other province in turn
- training only on daylight hours
- no penalty for negative forecasts
- input-feature changes (these need a code change first)

## 6. Running it

The runs train on the remote Mac (Apple GPU, "MPS"). Rough estimate: about 2 hours with three runs
in parallel. Each new code path passed a short trial run first: per-province models with the
correction, and with dropout off.

```bash
git pull && uv sync --dev
uv run python scripts/run_all_experiments.py --group abl_scope_dropout --list
uv run python scripts/run_all_experiments.py --group abl_scope_dropout --skip-existing --continue-on-error --shard 0/3
uv run python scripts/run_all_experiments.py --group abl_scope_dropout --skip-existing --continue-on-error --shard 1/3
uv run python scripts/run_all_experiments.py --group abl_scope_dropout --skip-existing --continue-on-error --shard 2/3
uv run python scripts/check_outputs.py --group abl_scope_dropout
git add outputs/experiments outputs/experiments_ledger.csv && git commit -m "Ablation abl_scope_dropout: 12 runs on Mac mini, check_outputs passed" && git push
```

Run each shard command in its own terminal. Run the check and the commit once all three finish.

## 7. Results

*To be filled in after the runs.* The plan is the table in Section 5.1, filled with daylight test
metrics (mean ± sd over seeds), then per-province tables for question A, raw and corrected
numbers for question B, and the method against the benchmark for question C. Each table is
followed by a short reading in the terms of Section 4.
