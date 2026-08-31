# Solar Irradiance Forecasting: LSTM + Bootstrap-Ensemble / MC-Dropout UQ

Forecasts hourly solar irradiance (`ALLSKY_SFC_SW_DWN`, W/m²) 24 hours ahead
for 5 Turkish cities (Ankara, Antalya, Konya, Rize, Van) using an LSTM, with
uncertainty quantification via a **Bootstrap Ensemble × Monte Carlo Dropout**
hybrid — adapted from the reference paper's PCNN + UQ methodology
(`main_methodology.md`, `main_methodology_paper.pdf`), substituting the PCNN
backbone with an LSTM and the target from PV power output to solar
irradiance.

The headline configuration trains **one global model across all 5 cities**
(city is a learned embedding); a per-province arm exists only as an ablation
(`training_scope="per_city"`) that tests the cross-city transfer claim. Every
training+evaluation run is a **configuration** (a "facet") that gets its own
persisted directory and a row in a shared comparison ledger — see
[Interpreting results](#interpreting-results) below.

`main_methodology.md` (Turkish) is the paper's Method text and the source of
truth for every formula and design justification; this README is the operating
manual and does not repeat its derivations.

## Installation

Requires **Python 3.10+**. Works on Linux, macOS (including Apple Silicon),
and Windows — the training code auto-detects the best available device
(MPS on Apple Silicon, CUDA if an Nvidia GPU is present, otherwise CPU) with
no code changes needed.

### Option A — [uv](https://docs.astral.sh/uv/) (recommended)

```bash
# install uv, if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

cd merve_makale
uv sync --dev
```

`uv sync` creates a `.venv/` and installs everything from `pyproject.toml` +
`uv.lock` (exact pinned versions). Run any script with `uv run python ...`
(shown throughout this README) — no need to manually activate the venv.

> **Note:** `pyproject.toml` pins `torch` to PyTorch's `cpu` wheel index.
> This only matters on Linux/Windows, where PyTorch ships separate
> CPU/CUDA wheel variants — on macOS there is a single wheel that already
> includes MPS (Apple GPU) support, so `uv sync` on a Mac still gets a
> fully GPU-capable PyTorch build.

### Option B — plain `venv` + `pip`

```bash
cd merve_makale
python3 -m venv .venv
source .venv/bin/activate      # macOS/Linux
pip install -e .
pip install pytest             # optional, for running tests
```

Then run scripts with `python scripts/...` instead of `uv run python
scripts/...`.

### Verify the install

```bash
uv run python -m pytest tests/ -v
```

(`uv run python -m pytest` rather than `uv run pytest`: `-m` pins the
interpreter to the project venv. Both work, but only the explicit form is
immune to a stray `pytest` earlier on `PATH`.)

All tests should pass (they load the real dataset and check the cleaning/
windowing logic — no network or GPU required).

## Running an experiment

### 1. One-time data preparation

Before any experiment, build the cleaned/feature-engineered cache (loads all
5 city sheets from `SolarData_Merve_All(16July).xlsx`, trims the trailing
NASA POWER data-latency gap, drops the columns listed in `DROPPED_COLUMNS`
(`ALLSKY_KT` only — dropped at read time, the xlsx itself is never modified),
adds cyclical time/wind-direction features). `CLRSKY_SFC_SW_DWN` is *not*
dropped: it is a `MASK_COLUMNS` entry, kept in the frame but never a model
input, because `CLRSKY_SFC_SW_DWN > 0` is the project's definition of daylight.
The final feature set is 17 columns. Only needs to be run once — every
experiment reuses the cached file:

```bash
uv run python scripts/01_prepare_base_data.py
```

This writes `outputs/processed/base_features.parquet` and prints a
per-city row count / date-range sanity check.

### 2. Descriptive statistics of the dataset (optional, seconds)

```bash
uv run python scripts/02_descriptive_analysis.py
```

Produces the manuscript's dataset-description tables and figures under
`outputs/eda/` — per-city descriptive statistics, correlation heatmaps,
per-variable scatter plots against irradiance, monthly box plots, the 3-D
month × year × irradiance surface (plus its 2-D anomaly companion), the two
seasonal views, clearness-index and ramp statistics, autocorrelation of the
clearness index, and a naive forecast floor. Figure and table labels are in
Turkish. This reads the cached parquet only; it does not touch any
experiment.

Two documents come with the outputs:

- **`outputs/eda/README.md`** — *how*: every file, its span, the filter applied
  to it, and the caveats that have to travel with its numbers.
- **`outputs/eda/EDA.md`** — *what it means*: the discussion written to be
  quoted into the manuscript, one section per table group, with a
  claim-to-file mapping at the end.

Three analysis decisions are worth knowing before reading either. Daylight is
defined **geometrically**, as `CLRSKY_SFC_SW_DWN > 0` — clear-sky irradiance is
pure solar geometry, so this is an exact "is the sun up" indicator that never
reads the realised target. Everything month-to-month is computed on **daily
totals**, because a box of daylight-hourly values is mostly solar geometry and
makes winter look *less* variable than summer, which is backwards. And the
hourly clock is NASA POWER's **per-site Local Solar Time**, so hours are never
compared across cities.

### 3. Run a single experiment

```bash
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json
```

`--config` points at a JSON file describing one **`ExperimentConfig`** (see
[Configuration reference](#configuration-reference) below). A few example
configs already exist in `configs/` — `config_000_smoke.json` is a fast
(~a few minutes) sanity-check config, `config_002_default_full.json` is the
full-fidelity default (8 bootstrap replicas × 100 MC-Dropout passes). Budget
generously for the latter: it has not yet been run to completion, and the one
measurement available (CPU-only, 12 cores) is 25.7 s/epoch and 1.83 s per MC
pass on the pooled five-province split, which puts a full run in the many-hours
range and a multi-arm study in days. On MPS/CUDA it is hours.

Always smoke-test a changed code path first (`n_bootstrap=1, max_epochs=5,
mc_dropout_passes=10`). A crash at the metrics step after two hours of training
is the expensive failure mode here.

Example configs written before the arm-selection axes existed omit those fields;
`ExperimentConfig.from_json` fills them from the defaults, so they still load.

Results print to the console (one line per metric subset: `all_hours` and
`daylight`) and are persisted under `outputs/experiments/<experiment_id>/` —
see [Interpreting results](#interpreting-results).

**All flags:**

| Flag | Meaning |
|---|---|
| `--config PATH` | *(required)* the `ExperimentConfig` JSON to run. |
| `--exclude-city NAME` | Drop this province from train, val **and** test. Repeatable (`--exclude-city Ankara --exclude-city Van`). Sets `excluded_cities`. |
| `--loss {mse,mae,huber}` | Override the training criterion (`loss_function`). Default: whatever the config says. |
| `--experiment-id ID` | Rename the run. **Required whenever any other override is given** — otherwise the run would overwrite the config's own output directory and append a ledger row that misdescribes it. The script refuses rather than doing that. |

Overrides are applied *before* the run, so the `config.json` written into the
experiment directory is the effective one and the run stays reproducible from
that file alone.

```bash
# same config, four provinces instead of five
uv run python scripts/run_experiment.py --config configs/config_002_default_full.json \
    --exclude-city Rize --experiment-id full_excl_rize

# same config, L1 criterion instead of MSE
uv run python scripts/run_experiment.py --config configs/config_002_default_full.json \
    --loss mae --experiment-id full_loss_mae
```

### 4. Run a sweep of experiments

`configs/experiment_grid.py` enumerates the `ExperimentConfig`s in **named
groups**, so an hours-long study can be selected precisely instead of running
everything: `smoke` (minutes, proves the code path), `main` (the hyperparameter
sweep — hidden sizes, lookback, dropout, split ratio), `ablation`
(global vs. per-province over 3 seeds, plus two sensitivity arms),
`rize_curve` / `rize_curve_b1` / `rize_curve_smoke` (the province-exclusion
transfer curve at full, reduced and smoke fidelity). Edit this file to add
your own.

```bash
uv run python scripts/run_all_experiments.py --list                # print what would run, exit
uv run python scripts/run_all_experiments.py --group smoke         # one group
uv run python scripts/run_all_experiments.py --group ablation --skip-existing --continue-on-error
uv run python scripts/run_all_experiments.py --only abl_loss_mae_s42 abl_loss_huber_s42
```

| Flag | Meaning |
|---|---|
| `--group NAME` | Repeatable; restrict to these groups. Default: every group. |
| `--only ID [ID ...]` | Run exactly these `experiment_id`s (intersected with `--group` if both are given). Errors if an id is not in the selection. |
| `--list` | Print the selected ids and exit without running anything. Use this before every long sweep. |
| `--skip-existing` | Skip configs that already have `metrics/results_summary.csv`, so an interrupted sweep resumes instead of restarting. Keyed on the results file, not `config.json`, so a run that crashed mid-training is retried while a completed one is skipped. |
| `--continue-on-error` | Keep going if one config raises; the failures are listed at the end and the script exits non-zero. |

Every selected config runs one after another, each writing to its own
`outputs/experiments/<experiment_id>/` and appending one row to
`outputs/experiments_ledger.csv`. The ledger schema is checked once up front,
so a header mismatch fails in milliseconds instead of after hours of training.

### 5. Naive reference baselines (seconds)

```bash
uv run python scripts/03_run_naive_baselines.py
```

Scores three reference forecasts — **climatology** (the training-rows
`(city, month, hour)` mean), **persistence** (the same hour one day earlier)
and **smart persistence** (yesterday's clear-sky index re-applied to today's
clear-sky irradiance) — through the same windows, the same chronological
splits and the same `metrics.py` as every model run, writing
`outputs/experiments/baseline_<name>/` and one ledger row each. They are the
floor the LSTM has to clear; the script also prints the all-hours numbers next
to the daylight ones to show how much night inflates them.

Two things to know when reading their rows: they take no arguments and use no
scaler (none of these rules needs one), and their interval metrics
(`CP`, `PINW`, `MPIW`, `Reliability`, `CWC`) are `NaN` by design — a single
deterministic forecast has a zero-width interval, which would make CP an
equality test. `CRPS` is kept, because for a point forecast it equals MAE.

### 5b. Post-hoc analysis of finished runs (seconds, no retraining)

Two scripts re-read what a finished run already wrote, so they work on the
machine that ran it (the `.npz` dumps are gitignored):

```bash
uv run python scripts/06_city_horizon_metrics.py --all      # per (city x horizon step) metrics
uv run python scripts/07_conformal_diagnostic.py            # which conformal grid geometry to use
```

`06` writes `metrics/results_by_city_horizon.csv` — the cross of the two tables
the pipeline emits — and cross-checks it against them, so a transposed slice
fails loudly instead of silently swapping two provinces' numbers.

`07` fits every `conformal_mode` on half of each run's test windows and scores
the other half, under four calibration geometries (a random half; the
chronologically first half; alternating months; and a random half with April and
May removed, which mimics the real validation split's seasonal hole). It writes
`outputs/tables/conformal_mode_selection.csv` and
`conformal_month_stability_test.csv`. This is method **selection**, not a result
— it fits and scores inside the test period — which is why every conformal run
also saves `calibration_predictions.npz` so the same comparison can be redone on
the validation split.

### 6. Creating your own config

Two ways:

**(a) One-off, from Python:**

```python
from merve_solar.config import ExperimentConfig
from pathlib import Path

config = ExperimentConfig(
    experiment_id="my_experiment",
    hidden_sizes=[64, 64],
    lookback_hours=48,
    n_bootstrap=5,
)
config.to_json(Path("configs/my_experiment.json"))
```

Then `uv run python scripts/run_experiment.py --config configs/my_experiment.json`.

**(b) Add it to the sweep:** append an `ExperimentConfig(...)` entry to the
list returned by one of the group builders in `EXPERIMENT_GROUPS`
(`configs/experiment_grid.py`), or register a new group there, then run
`run_all_experiments.py --group <name>`. `build_experiment_grid()` assembles
the selected groups and raises on a duplicate `experiment_id`.
`uv run python configs/experiment_grid.py` prints every group and its ids.

Every field has a sensible default (see below), so you only need to specify
the fields you actually want to change from the default.

## Configuration reference

All fields live in the `ExperimentConfig` dataclass
(`src/merve_solar/config.py`). Every field is optional except
`experiment_id`.

| Field | Default | What it controls |
|---|---|---|
| `experiment_id` | *(required)* | Name for this run — becomes its output directory name (`outputs/experiments/<experiment_id>/`) and its row's identifier in the ledger. Must be unique per run (a rerun with the same id overwrites that run's outputs). |
| `lookback_hours` | `24` | How many past hours of data the model sees as input ("time lag"). |
| `horizon_hours` | `24` | How many future hours the model forecasts in one shot (a single forward pass predicts all of them at once). |
| `window_stride` | `1` | Step size (in hours) between consecutive training windows. `1` = a new window every hour (more training data, slower to build); `24` = one window per calendar day. |
| `train_ratio` | `0.74` | Fraction of the usable date range (chronologically, earliest first) used for training. |
| `val_ratio` | `0.11` | Fraction used for validation/early-stopping (immediately after the training range). The remainder (`1 - train_ratio - val_ratio`, ≈`0.15` by default) is the held-out test set (the most recent data — with the defaults it spans 8,878 hours = 369 days 22 hours ≈ 370 days, i.e. slightly over a full seasonal year, so all four seasons are covered; important for solar irradiance, otherwise the test score is biased toward one season). |
| `hidden_sizes` | `[64, 32]` | Model size/depth. The first number is the LSTM's hidden size, and `len(hidden_sizes)` is the number of stacked LSTM layers. Any additional numbers become extra `Linear` layers in the output head (e.g. `[64, 32]` → a 1-layer-hidden LSTM(64) feeding a Linear(64→32)→Linear(32→horizon_hours) head; `[128, 64, 32]` → a 2-layer LSTM(128) feeding a deeper head). |
| `dropout_rate` | `0.3` | Dropout probability, used both for regularization during training *and* as the source of randomness for Monte Carlo Dropout at inference — don't set this to `0`, or MC-Dropout will produce identical predictions every pass (no epistemic uncertainty). |
| `city_embedding_dim` | `4` | Size of the learned vector representing which city a window belongs to. |
| `learning_rate` | `1e-3` | Adam optimizer's initial learning rate. |
| `batch_size` | `128` | Training/validation batch size. |
| `max_epochs` | `100` | Hard cap on training epochs per model (early stopping usually kicks in well before this). |
| `early_stop_patience` | `10` | Stop training if validation loss hasn't improved for this many consecutive epochs. |
| `lr_reduce_factor` / `lr_reduce_patience` | `0.5` / `7` | Learning-rate is multiplied by `lr_reduce_factor` if validation loss plateaus for `lr_reduce_patience` epochs. |
| `nonneg_penalty_weight` | `0.1` | Weight of a soft penalty discouraging negative irradiance predictions (irradiance can't physically be negative). `0` disables it. It is added on top of whichever `loss_function` is selected — it is a physics constraint, not part of the fit criterion. |
| `loss_function` | `"mse"` | Training criterion, in *scaled* target space: `"mse"`, `"mae"` or `"huber"`. MSE is minimised by the conditional mean and MAE by the conditional median, and this target's error distribution is strongly right-skewed, so the choice moves RMSE and MAE in opposite directions — that trade-off is a recorded experiment axis, not a tuning knob. |
| `huber_delta` | `1.0` | Huber transition point, in scaled target space (quadratic below, linear above). Only used when `loss_function="huber"`. |
| `target_transform` | `"raw"` | What the network regresses. `"raw"` is the irradiance in W/m², `"clearsky_index"` is the clearness index `kt = ALLSKY / CLRSKY`, multiplied back by the target hour's clear-sky value after the inverse scaling. The point is that the naive baselines get that envelope for free — smart persistence multiplies a carried-forward `kt` by `CLRSKY(t+h)` and the climatology cell memorises the same geometry — while a `"raw"` model has to infer it from `hour_sin/cos` and the day-of-year encoding. `CLRSKY` is pure astronomy with no weather term, so this is not leakage, and it still never becomes a feature. Under `"clearsky_index"` night output is exactly zero by construction (`CLRSKY = 0`), which makes `clamp_night_to_zero` a no-op rather than a correction. No clipping is applied: measured on the base frame, daylight `CLRSKY` has a floor of 2.40 W/m² and `kt` has median 0.885 and p99 = 1.000. |
| `loss_daylight_only` | `False` | Mask the *training* loss to daylight steps only. Off by default and deliberately so: it leaves night outputs unsupervised, keeps only ~13 of the 24 horizon steps supervised (and which 13 shifts with the season), and leaves the UQ layer unconstrained at night. Evaluate it as its own experiment, never folded into another comparison. Independent of the metric subsets, which are always both reported. |
| `training_scope` | `"global"` | `"global"` = one model over all active provinces, city identity entering as a learned embedding (the headline configuration). `"per_city"` = an independent model set per province, assembled back into the same pooled test layout; this exists only as the ablation arm that tests the cross-city transfer claim. |
| `per_city_scaler` | `True` | Only meaningful when `training_scope="per_city"`. `True` gives each province its own scaler, so the isolated arm contains no cross-province information at all. `False` reuses the pooled scaler, which separates "a per-province model" from "a per-province normalisation of the loss and the early-stopping signal". Either way the scaler is fit on train rows only. |
| `excluded_cities` | `[]` | Provinces dropped from this run **entirely** — train, val and test alike — so the metric table covers only the remainder. City ids are *not* renumbered (the embedding table keeps a row per province; the excluded row simply never receives a gradient), so checkpoints and predictions stay comparable across runs. Split boundaries are computed on the full frame before the exclusion, so every arm splits on identical dates. Leaving a single province is allowed only with `training_scope="per_city"`. |
| `model_family` | `"lstm"` | Which model produced the row. `"lstm"` is the only value `run_experiment` trains; `"climatology"`, `"persistence"` and `"smart_persistence"` are written by `scripts/03_run_naive_baselines.py` so their rows are identifiable in the ledger. |
| `clamp_night_to_zero` | `True` | Zero every prediction at hours where `CLRSKY_SFC_SW_DWN = 0`, applied after the inverse transform to W/m². Not a heuristic: below the horizon the target is exactly `0` and this is known from solar geometry alone, without reading the target. It improves all-hours MAE by ~27% at no cost, **but it also inflates all-hours CP by construction** — see [Metrics explained](#metrics-explained). |
| `conformal_mode` | `"none"` | Granularity of the split-conformal recalibration of the predictive interval: `"none"`, `"global"`, `"per_horizon"`, `"per_city"`, `"city_horizon"`, `"per_season"`, `"city_season"`. Anything but `"none"` makes the run additionally predict the **validation** split, pooled over the same `n_bootstrap × mc_dropout_passes` passes, and fit one factor `k` per grid cell; the predictive distribution is then rescaled about its own mean, `x → m + k(x − m)`. That rescales the interval and CRPS coherently and leaves the mean — hence RMSE/MAE/R² — bit-identical, so a conformal row differs from its uncorrected twin in the interval alone. Costs roughly 13% wall clock. The recommended value is `"city_season"`: measured over 16 finished runs, the horizon axis is null while the season axis is not, because `k` swings 1.7×–2.5× across the year (cloud variability is seasonal, epistemic spread is not). Night is never calibrated and never corrected. Two limitations are real and stated: the calibration set is the same validation split early stopping used, and it covers ten of twelve months — no April, no May. See `ABLATION.md` §8 and `main_methodology.md` §11.6. |
| `n_bootstrap` | `8` | Number of bootstrap-resampled model replicas trained for the ensemble (the paper recommends 5–10). **Set to `1` for a fast sanity-check run** — with only one replica there's no resampling, just a single trained LSTM, still scored via MC-Dropout alone. |
| `mc_dropout_passes` | `100` | Number of stochastic forward passes per replica at inference time (the paper recommends 50–100). Total predictions pooled per test point = `n_bootstrap × mc_dropout_passes` (e.g. 8×100=800 by default). |
| `bootstrap_block_length` | `168` | Block length (in windows) for the moving-block bootstrap resampling — resampling in contiguous blocks (default ≈1 week) rather than individually preserves the data's temporal autocorrelation. Only relevant when `n_bootstrap > 1`. |
| `seed` | `42` | Random seed (each bootstrap replica additionally offsets this so replicas aren't identical). |

## Interpreting results

### Where things are written

```
outputs/
├── experiments/<experiment_id>/
│   ├── config.json                    # the exact (post-override) config used for this run
│   ├── log.txt                        # device, scope/loss/active cities, split dates,
│   │                                  #   per-replica val loss, night elements clamped, total time
│   ├── checkpoints/                   # *.pt are gitignored; regenerate from the seeded config
│   │   ├── bootstrap_model_<b>.pt      # global arm: trained weights per replica
│   │   ├── bootstrap_model_<city>_<b>.pt  # per_city arm: per province, per replica
│   │   ├── scaler.joblib               # the fitted feature scaler (needed to interpret raw model outputs)
│   │   └── scaler_<city>.joblib        # per_city arm with per_city_scaler=True, one per province
│   ├── metrics/
│   │   ├── results_summary.csv         # one row per (subset, group); group ∈ {Aggregate,
│   │   │                               #   Aggregate_excl_Rize, and each active city}
│   │   ├── results_by_horizon.csv      # one row per (subset, horizon step 1..24)
│   │   ├── conformal_grid.csv          # conformal_mode != "none": per cell n, k, fallback flag
│   │   ├── conformal_effect.csv        # before/after CP, MPIW, Reliability, CWC per group and step
│   │   ├── conformal_month_stability.csv  # k refitted month by month on the calibration split
│   │   ├── calibration_predictions.npz # the validation split's summary (gitignored) — lets the
│   │   │                               #   grid geometry be re-chosen on validation, not on test
│   │   └── test_predictions.npz        # mean/lower/upper + y_true, city_id, daylight, window_start
│   │                                   #   (for paired significance tests; gitignored)
│   └── figures/
│       ├── forecast_ci_<city>.png      # one per active city
│       ├── rmse_vs_horizon.png         # all_hours
│       ├── rmse_vs_horizon_daylight.png
│       ├── cp_vs_horizon.png           # all_hours
│       └── cp_vs_horizon_daylight.png
├── experiments_ledger.csv              # ONE ROW PER RUN — compare configs at a glance
└── eda/                                # dataset description, not tied to any run
    ├── README.md                       # what each file is + the analysis caveats
    ├── EDA.md                          # the discussion, written for the manuscript
    ├── tables/                         # descriptive stats, correlations, coverage (CSV/MD/TEX)
    └── figures/                        # each figure as .png (300 dpi) and .pdf (vector)
```

Everything under `outputs/` is tracked in git except the model checkpoints
(`outputs/**/checkpoints/*.pt`) and the prediction dumps
(`outputs/**/metrics/*.npz`), both of which are regenerated from the seeded
config.

`experiments_ledger.csv` is the fastest way to compare many runs: one row per
experiment, its config fields next to its headline metrics. The schema is
declared as `LEDGER_COLUMNS` in `src/merve_solar/experiment.py` and is
asserted against the file on every append, so a row can never silently
misalign against the header. The columns, in order:

- **identity / arm** — `experiment_id`, `model_family`, `training_scope`,
  `excluded_cities` (a `|`-joined string, empty when nothing is excluded)
- **windowing** — `lookback_hours`, `horizon_hours`, `window_stride`,
  `n_features`
- **architecture** — `hidden_sizes`, `dropout_rate`, `city_embedding_dim`
- **splits** — `train_ratio`, `val_ratio`
- **UQ / training budget** — `n_bootstrap`, `bootstrap_block_length`,
  `mc_dropout_passes`, `max_epochs`, `early_stop_patience`
- **optimizer** — `batch_size`, `learning_rate`, `lr_reduce_factor`,
  `lr_reduce_patience` (swept by the `abl_arch_lr3e4*` arms)
- **criterion / post-processing** — `loss_function`, `huber_delta`, `nonneg_penalty_weight`,
  `loss_daylight_only`, `per_city_scaler`, `clamp_night_to_zero`, `conformal_mode`, `seed`,
  `device` (which torch backend actually produced the row — `cpu`/`cuda`/`mps`,
  overridable with the `MERVE_DEVICE` environment variable; interval metrics
  are not comparable across backends, so check it before any arm-to-arm claim)
- **all-hours metrics** — `RMSE`, `MAE`, `R2`, `CP`, `PINW`, `MPIW`,
  `Reliability`, `CWC`, `CRPS`, `n_samples`, `n_elements`
- **daylight metrics** — `RMSE_daylight`, `MAE_daylight`, `R2_daylight`,
  `CP_daylight`, `n_elements_daylight`
- **run stats** — `best_val_loss` (see below), `hit_max_epochs` (how many
  replicas stopped at the epoch cap instead of by early stopping — check this
  before any arm-to-arm claim), `n_models_trained`, `training_time_sec`

Only the aggregate is in the ledger; the per-city and per-horizon breakdowns
live in the two CSVs above. Open it in a spreadsheet/pandas to sort/filter
across runs.

#### `best_val_loss` — the model-selection column

Architecture and hyperparameters must be chosen on **validation** loss, never
on the test metric: picking the best test score folds the test set into model
selection and makes the reported test performance optimistic. This column is
what makes that possible from the ledger alone. Three things to know before
using it:

- **What the number is.** The mean, over the models trained in the run (`B` in
  the global scope, `5B` per-city), of each model's loss at its **best** epoch —
  not its last. `train_model` restores the best epoch's weights before
  returning, so the last epoch's loss describes weights that were discarded;
  with `early_stop_patience=15` the two can be far apart. Per-model values and
  both numbers per replica are in the run's `log.txt`
  (`best_val_loss=… best_epoch=… last_val_loss=… epochs=…`). There is
  deliberately no spread column: the planned sweep runs at `n_bootstrap=1`,
  where a spread is zero or undefined, so it would be empty in exactly the rows
  that would want it.
- **When it is comparable.** It is computed in **scaled** target space, so it
  only compares between runs sharing (a) `loss_function` / `huber_delta`,
  (b) the same pooled provinces — those fix the scaler — and (c)
  `loss_daylight_only`. It is the right instrument for *same data, same
  criterion, different architecture* and the wrong one for anything else. In
  the per-city scope with `per_city_scaler=True` each city's loss is in its own
  scaled space, so the mean summarises that arm and does not compare to a
  global-scope row.
- **Empty, `n/a` and `unknown` mean different things.** Empty = the row was
  written before this column existed (2026-08-29). Those runs are **not**
  backfilled: their `log.txt` recorded the *last* epoch's loss, and filling the
  cells from it would put two different quantities in one column. `n/a` = no
  model was trained at all (the naive baselines). `unknown` = a model was
  trained but its loss was not recorded, i.e. a bug.

### Metrics explained

All metrics are computed three ways: **aggregate** (all cities, all horizon
steps pooled), **per-city** (`results_summary.csv`), and **per-horizon-step**
(`results_by_horizon.csv`, step 1 = 1 hour ahead, step 24 = 24 hours ahead) —
and every one of those, twice, for two **subsets**.

#### The two subsets (`subset` column)

| `subset` | Mask | Share of elements | Role |
|---|---|---|---|
| `all_hours` | none | 100% | completeness only; inflated by night |
| `daylight` | `CLRSKY_SFC_SW_DWN > 0` | ≈51.2% | **the paper's headline numbers** |

Daylight is defined geometrically, from clear-sky irradiance, so the mask never
reads the realised target. Roughly 48.8% of target elements are exactly `0`
because the sun is below the horizon, and they are trivially easy to predict —
so all-hours numbers flatter the model. The daylight share is 0.515 at *every*
one of the 24 horizon steps, so the per-horizon daylight comparison is not
distorted by a shifting day/night mix.

**All-hours R² is the most misleading number in the table.** R² is normalised
by the subset's own variance, and the day/night swing dominates total variance:
on this dataset a plain `(city, month, hour)` climatological lookup table
scores R² = 0.923 over all 24 hours but only 0.856 on daylight hours. An
all-hours R² above 0.9 is therefore not evidence of anything. Quote the
daylight value. The same normalisation argument applies to `PINW`.

`results_summary.csv` also carries an **`Aggregate_excl_Rize`** group row
alongside `Aggregate`. Rize is a separate climatic regime (daily clear-sky
index 0.697 against 0.806–0.840 elsewhere), and the plain aggregate buries it
four-to-one — which is exactly where the city embedding has to do its work, so
cross-city transfer is invisible in the headline number without this row. The
row is omitted when the run already excluded Rize (it would be a byte-for-byte
duplicate of `Aggregate`).

Two columns count different things: **`n_samples`** is the number of *windows*
contributing at least one scored element, while **`n_elements`** is the number
of scored *(window, horizon-step)* pairs — the actual denominator of every
metric. `n_elements` roughly halves in the daylight subset; `n_samples`
usually does not change, because almost every 24-hour window contains some
daylight.

**Point-forecast accuracy** (how good is the predicted mean?):

- **RMSE** (Root Mean Squared Error, W/m²) — average error, penalizing large
  misses more heavily. Lower is better.
- **MAE** (Mean Absolute Error, W/m²) — average error, more robust to
  outliers than RMSE. Lower is better.
- **R²** (coefficient of determination, unitless) — the fraction of the
  subset's own variance the forecast explains. Higher is better; `NaN` when the
  subset's target is constant. Read the caveat above before quoting it.

**Uncertainty quality** (how good is the predicted *confidence interval*,
not just the point forecast?):

- **CP** (Coverage Probability, a.k.a. PICP in the source paper) — the
  fraction of true values that actually fell inside the predicted 95% CI.
  **Target ≈ 0.95.** Much lower than 0.95 means the intervals are
  overconfident (too narrow); at/above 0.95 means they're at least as wide
  as needed (check `PINW`/`MPIW` alongside it — a CP near 1.0 with a huge
  `PINW` means the interval is technically "safe" but uninformatively wide).
- **PINW** (Prediction Interval Normalized Width) — the average interval
  width, normalized by that subset's true-value range (so it's comparable
  across cities/horizons with different irradiance scales). Lower is
  better, but only meaningful *together with* CP.
- **MPIW** (Mean Prediction Interval Width, W/m²) — the same interval
  width as `PINW`, but in physical units instead of normalized (e.g. "the
  95% CI is on average ±80 W/m² wide").
- **Reliability** — `|CP − 0.95|`, a single-number calibration gap. `0` =
  perfectly calibrated coverage.
- **CWC** (Coverage Width Criterion) — a composite score: equals `PINW`
  when `CP ≥ 0.95`, but grows **exponentially** the further `CP` falls
  below `0.95`. A very large `CWC` is a red flag that coverage is badly
  under-target, even if `PINW`/`MPIW` look small. Lower is better.
- **CRPS** (Continuous Ranked Probability Score) — a proper scoring rule
  judging the *entire* predicted distribution against the true value (not
  just whether it falls in the interval). Lower is better; `0` for a
  perfect deterministic forecast.

A well-calibrated, useful model should show CP close to 0.95, Reliability
close to 0, and PINW/MPIW/CWC/CRPS as low as possible without CP dropping
below 0.95.

> **Read interval quality from the `daylight` rows only.** With
> `clamp_night_to_zero` on (the default), every night element gets a degenerate
> `[0, 0]` interval, and the true value there is exactly `0` — so it is covered
> *by definition*. Since ~48.8% of elements are night, the all-hours CP is a
> mixture whose night half is 1.0 by construction, and it comes out far above
> the daylight CP for reasons that have nothing to do with calibration. If an
> all-hours CP is reported at all, it must be reported together with this
> structural inflation. `main_methodology.md` §11.3 and §11.5 give the full
> argument, including a second known limit: the pooled distribution carries no
> aleatoric (observation-noise) term, so the intervals answer "where could the
> model's mean be", not "where could the observation be", and can under-cover
> for that reason alone.

### Figures explained

- **`forecast_ci_<city>.png`** — one representative 24-hour test-window
  forecast for that city: the true irradiance curve (black), the predicted
  mean (blue), and the shaded 95% CI band, plotted against horizon step
  (1–24 hours ahead). A healthy result looks like a diurnal curve — near
  zero at night, a midday peak — with the true curve mostly inside the
  shaded band and the band tightening where the model is more confident.
- **`rmse_vs_horizon.png`** — RMSE at each horizon step. Normally increases
  from left (1h ahead) to right (24h ahead) — forecasting further out is
  harder.
- **`cp_vs_horizon.png`** — Coverage Probability at each horizon step.
  Should stay close to the 0.95 line across the whole horizon; a sharp drop
  at longer lead times means the model's uncertainty estimate isn't keeping
  pace with its growing point-forecast error there.
- **`rmse_vs_horizon_daylight.png` / `cp_vs_horizon_daylight.png`** — the same
  two plots on the `daylight` subset. These are the ones to read: the
  unsuffixed pair is `all_hours` and carries the night inflation described
  above.
