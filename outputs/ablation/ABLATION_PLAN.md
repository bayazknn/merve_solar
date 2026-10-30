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

## 2. The full model, part by part

The model we test is built from five parts. Each ablation removes or changes one of them.

| Part | What it does, in plain words |
|---|---|
| **LSTM network** | A neural network that reads the last 24 hours of weather and predicts the next 24 hours of irradiance. |
| **City embedding** | A small learned code for each province. One model serves all five provinces, and this code tells it which province it is looking at. |
| **Bootstrap ensemble (6 networks)** | We train 6 copies of the network, each on a different random resampling of the training data (resampled in one-week blocks, to keep weather patterns intact). Their disagreement shows uncertainty that comes from limited data. |
| **MC-Dropout (100 passes)** | During prediction, each network randomly switches off some of its neurons, 100 times. The spread of these 100 answers shows uncertainty inside one network. 6 networks × 100 passes = 600 forecast values per hour. |
| **Conformal correction** | The 600 values are too close together: the raw ranges are too narrow and miss the real value too often. The correction measures how much too narrow they are on held-out data, separately for each province and each forecast hour, and widens them by that factor. It does not change the central forecast. |

All settings of this model were chosen in an earlier tuning stage, using only the validation
data. We call it the **full model** or **reference**. Its test results (five training seeds) are
in Section 6.

## 3. What an ablation is

An ablation takes the full model, **changes exactly one thing**, retrains it, and measures what
changed. If removing a part makes the forecasts worse, that part is doing useful work. If nothing
changes, the part is not needed, and that is also a result worth reporting.

Rules that keep the comparisons fair:
- **One change per arm.** Everything else, including the data split, the training days, the
  scaling and the metrics code, is identical. A test checks this automatically.
- **Same seeds.** Each arm is trained with three random seeds (42, 43, 44). The full model's runs
  with the same seeds are reused, so each comparison is paired seed by seed.
- **Nothing is selected.** Ablations explain the model; they do not tune it. So we report them on
  the **test** data (from 11 June 2025 to 29 June 2026, all four seasons), with the validation
  numbers beside them.

## 4. The metrics: what they mean and why we use them

All headline numbers use **daylight hours only** (sun above the horizon). At night the irradiance
is exactly zero and the model is forced to predict zero. Night hours would make every metric look
better without saying anything about the forecast. "Daylight" is decided from the sun's position
alone, never from the measured value.

### Accuracy of the central forecast

These three metrics use one number per hour: the average of the 600 forecast values.

| Metric | Definition | Purpose | Better when |
|---|---|---|---|
| **RMSE** (W/m²) | Square root of the average squared error. | Main accuracy measure. Large errors count more, so it is sensitive to badly missed cloudy hours. | Lower |
| **MAE** (W/m²) | Average absolute error. | Typical size of an error, in the same unit as the data. Easier to explain than RMSE. | Lower |
| **R²** | Share of the variation in irradiance that the forecast explains (1 = perfect, 0 = no better than always predicting the average). | Lets us compare provinces whose irradiance levels differ. | Higher |

### Quality of the uncertainty range

The **95% interval** is the range between the 2.5th and the 97.5th percentile of the 600 values.
A good interval contains the real value 95% of the time, and is as narrow as possible while doing
so.

| Metric | Definition | Purpose | Better when |
|---|---|---|---|
| **CP**, coverage | Share of hours where the real value fell inside the 95% interval. | Checks that the intervals are **honest**. 0.95 is the target. Below 0.95 the model is overconfident; above 0.95 it is too cautious. | Closer to 0.95 |
| **MPIW** (W/m²) | Average width of the interval. | Measures how **useful** the interval is. A very wide interval is always right but tells the user little. | Narrower, if CP is on target |
| **PINW** | MPIW divided by the range of observed irradiance (about 1,040 W/m²). | The same as MPIW but without units, so it can be compared with other studies. | Lower, if CP is on target |
| **CRPS** (W/m²) | Compares the whole forecast distribution with the real value. It rewards distributions that are both close to the real value and not wider than needed. For a single-number forecast it equals MAE. | **One overall score** for the probabilistic forecast. It joins accuracy and uncertainty in one number, so it is the fairest single number to compare arms. | Lower |

**How to read CP and width together.** Coverage first, width second. An arm with CP 0.95 and
width 340 is better than one with CP 0.95 and width 380. An arm with CP 0.80 and width 190 is not
better: its intervals are narrow because they are wrong one hour in five. Since most arms keep the
conformal correction, most arms will have CP close to 0.95. For them, the comparison comes down to
**width and CRPS**.

### By province and by forecast hour

Every metric is also reported for each province and for each forecast hour (1 to 24 hours ahead).
The aggregate can hide a problem in one province, for example Rize, which is much cloudier than the
others. It can also hide a problem at long lead times.

### When is a difference real?

Each arm has three seeds. For each seed we compute *arm minus full model*, which gives three
paired differences. A difference counts as real only when its average is larger than the
seed-to-seed variation of those three differences. The tuning stages used the same rule. For the
paper we will add a day-by-day paired test on the test days. On the reference, five seeds vary by
only 0.10 W/m² in CRPS and 0.09 W/m² in RMSE, so differences of a few tenths of a W/m² can be
detected.

## 5. The experiments

There are 30 new runs in three groups, plus an optional fourth group of 12 runs. Every arm below
changes one thing from the full model.

### Group A: the uncertainty layer (`abl_uncertainty`, 15 runs)

**Question:** which parts of the uncertainty layer are needed, and what does each one add?

| Arm | What changes | What it isolates |
|---|---|---|
| `plain_lstm` | One network, no MC-Dropout, no ensemble, no correction. | The starting point: a standard LSTM giving one number per hour. |
| `single_mc_dropout` | One network with MC-Dropout (600 passes, so the same 600 values per hour as the full model). Correction kept. | What the bootstrap ensemble adds on top of MC-Dropout. |
| `bootstrap_only` | 6 networks, MC-Dropout off (6 values per hour), no correction. | What MC-Dropout adds on top of the ensemble. Compared with `no_conformal`, which is also uncorrected. |
| `seed_ensemble` | 6 networks trained on the **same** data, differing only in their random start, instead of resampled data. | Whether data resampling (the "bootstrap") matters, or any ensemble of 6 would do. |
| `no_conformal` | Full model without the correction. | What the correction adds. |

**How to read the results:**
- `plain_lstm` has no real interval, so its CP is close to 0 and its CRPS equals its MAE. The gap
  between its CRPS and the full model's CRPS is **the value of forecasting a range instead of a
  number**. Its RMSE shows whether ensembling also improves the central forecast.
- `single_mc_dropout` keeps the correction, so its CP should be near 0.95. Compare **width and
  CRPS** with the full model. If it is almost as good, the 6-network ensemble costs 6 times the
  training for little gain. The tuning results point this way, since the ensemble size
  mattered little there.
- `bootstrap_only` runs **without** the correction, and is compared with `no_conformal` (the
  full model without the correction), so both sides are uncorrected. The reason: its interval
  comes from only 6 values per hour. The correction would have to widen it many times over, and
  the CRPS would then mostly measure that blow-up, not the model. (A trial run with 2 networks
  needed a widening factor of about 73.) In tuning, the uncorrected coverage of 6 networks
  without MC-Dropout was only 0.28, against 0.79 with it. If the CRPS gap is also large,
  MC-Dropout is the part of the uncertainty layer that matters most.
- If `seed_ensemble` matches the full model, the resampling is not what makes the ensemble work.
  The paper should then say "ensemble", not "bootstrap".
- `no_conformal` should have nearly the same RMSE as the full model, since the correction does not
  touch the central forecast; any gap is run-to-run noise of the hardware. Its CP should fall to
  about 0.82 on test. The difference in CRPS is what the correction is worth. From the reference
  we already know the uncorrected intervals have the **same width at every lead time** while the
  error doubles. This arm turns that into a measured CRPS loss.

### Group B: one model for five provinces (`abl_transfer`, 9 runs)

**Question:** does training one shared model on all five provinces help each province, compared
with training each province separately? This is a central claim of the paper.

| Arm | What changes | What it isolates |
|---|---|---|
| `per_province` | Five separate models, one per province, each trained on its own data only. | The value of sharing data across provinces. |
| `no_city_embedding` | One shared model, but it is not told which province it is forecasting. | Whether the model needs to know the province, or learns enough from the weather alone. |
| `without_rize` | The shared model trained and tested on four provinces, without Rize. | Whether mixing in Rize's very different (much cloudier) climate helps or hurts the other four. |

**How to read the results:**
- `per_province`: compare **each province's** RMSE and CRPS with the same province in the full
  model. If the shared model is better in most provinces, sharing helps (positive transfer). If
  only data-rich or similar provinces gain, the paper must say so. One caveat: each separate model
  also scales its data on its own, which by itself may favour this arm slightly.
- `no_city_embedding`: if nothing changes, the weather inputs already identify the province. If
  results get worse, especially in Rize or Antalya, the province code is doing real work.
- `without_rize`: compare the four provinces' numbers with the full model's "all provinces except
  Rize" row. Better without Rize means pooling different climates hurts; worse means even a
  different climate adds useful training data.

### Group C: training choices (`abl_training`, 6 runs)

**Question:** do two training choices actually help?

| Arm | What changes | What it isolates |
|---|---|---|
| `daylight_only_loss` | The network is trained only on daylight hours; night hours are ignored during training. | Whether training on night hours, which are always zero, wastes effort or helps. |
| `no_nonneg_penalty` | Remove the training penalty for predicting negative irradiance. | Whether the penalty matters. Irradiance cannot be negative. |

**How to read the results:**
- `daylight_only_loss`: the model always outputs zero at night after prediction, so the
  night hours do not affect the metrics. If daylight RMSE and CRPS improve, training on night
  hours was a distraction. If they get worse, the night hours helped the model learn the shape
  of the day.
- `no_nonneg_penalty`: the metrics are on daylight hours, where predictions are rarely negative,
  so a null result is likely and acceptable. It would show the penalty is a safety rule, not a
  source of accuracy.

### Group D (optional): leave one province out (`abl_transfer_lopo`, 12 runs)

The same as `without_rize`, for each of the other four provinces. Together with `without_rize`
it gives a **5 × 5 table**: how much each province's forecast changes when one other province is
removed from training. Run it only if Group B shows that sharing matters. If it does not, the
table would only show noise.

### Not in this round

- **Input features** (for example removing dew point, which can be computed from temperature and
  humidity, or transforming precipitation). The code does not yet support changing the feature
  set per run; this will be added before that group is drafted.
- **Other model types** (SVM, GRU, random forest and similar) are comparisons, not ablations.
  They will be planned separately.
- **A benchmark**, a standard reference forecast the model must beat, has not been declared yet.
  Ablations compare the model with itself, so they do not need one.

## 6. Reference values (full model, test year, daylight, 5 seeds)

These are the numbers every ablation is compared with. The paired comparison uses seeds 42 to 44.

| Metric | Value |
|---|---|
| RMSE | 85.92 ± 0.09 W/m² |
| MAE | 58.16 ± 0.47 W/m² |
| R² | 0.906 |
| CP (target 0.95) | 0.953 (0.819 before correction) |
| MPIW | 339.5 W/m² (192.0 before correction) |
| PINW | 0.329 |
| CRPS | 43.47 ± 0.10 W/m² |

By province, RMSE goes from 73.2 (Antalya) to 106.2 W/m² (Rize). By lead time, it goes from 42 W/m²
one hour ahead to 98 W/m² 24 hours ahead.

## 7. Running it

The runs train on the remote Mac (Apple GPU, "MPS"). The estimate is about 5 hours for Groups A to C
with three runs in parallel, and about 2.5 hours more for Group D. The one-network arms are much
cheaper than the rest. The new code paths (correction on separate province models, no province code)
passed a short smoke run first.

```bash
git pull && uv sync --dev
uv run python scripts/run_all_experiments.py --group abl_uncertainty --list
uv run python scripts/run_all_experiments.py --group abl_uncertainty --skip-existing --continue-on-error --shard 0/3
uv run python scripts/run_all_experiments.py --group abl_uncertainty --skip-existing --continue-on-error --shard 1/3
uv run python scripts/run_all_experiments.py --group abl_uncertainty --skip-existing --continue-on-error --shard 2/3
uv run python scripts/check_outputs.py --group abl_uncertainty
```

Then repeat with `abl_transfer` and `abl_training`. Run each shard command in its own terminal.
After each group's check passes, commit the results:

```bash
git add outputs/experiments outputs/experiments_ledger.csv && git commit -m "Ablation <group>: N runs on Mac mini, check_outputs passed" && git push
```

## 8. Results

*To be filled in after the runs.* For each group: a table of every arm's daylight test metrics
(mean ± sd over three seeds) and the paired difference from the full model, followed by a short
reading in the terms of Section 4.
