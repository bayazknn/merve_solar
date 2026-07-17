# Solar Irradiance Forecasting: LSTM + Bootstrap-Ensemble / MC-Dropout UQ

Forecasts hourly solar irradiance (`ALLSKY_SFC_SW_DWN`, W/m²) 24 hours ahead
for 5 Turkish cities (Ankara, Antalya, Konya, Rize, Van) using an LSTM, with
uncertainty quantification via a **Bootstrap Ensemble × Monte Carlo Dropout**
hybrid — adapted from the reference paper's PCNN + UQ methodology
(`main_methodology.md`, `main_methodology_paper.pdf`), substituting the PCNN
backbone with an LSTM and the target from PV power output to solar
irradiance.

One global model is trained across all 5 cities (city is a learned
embedding). Every training+evaluation run is a **configuration** (a
"facet") that gets its own persisted directory and a row in a shared
comparison ledger — see [Interpreting results](#interpreting-results) below.

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
uv run pytest tests/ -v
```

All tests should pass (they load the real dataset and check the cleaning/
windowing logic — no network or GPU required).

## Running an experiment

### 1. One-time data preparation

Before any experiment, build the cleaned/feature-engineered cache (loads all
5 city sheets from `SolarData_Merve_All(16July).xlsx`, trims the trailing
NASA POWER data-latency gap, drops the unusable `ALLSKY_KT` column, adds
cyclical time/wind-direction features). Only needs to be run once — every
experiment reuses the cached file:

```bash
uv run python scripts/01_prepare_base_data.py
```

This writes `outputs/processed/base_features.parquet` and prints a
per-city row count / date-range sanity check.

### 2. Run a single experiment

```bash
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json
```

`--config` points at a JSON file describing one **`ExperimentConfig`** (see
[Configuration reference](#configuration-reference) below). A few example
configs already exist in `configs/` — `config_000_smoke.json` is a fast
(~a few minutes) sanity-check config, `config_002_default_full.json` is the
full-fidelity default (8 bootstrap replicas × 100 MC-Dropout passes,
expect anywhere from ~30 minutes to a few hours depending on your machine
and how many epochs early stopping actually runs).

Results print to the console and are persisted under
`outputs/experiments/<experiment_id>/` — see
[Interpreting results](#interpreting-results).

### 3. Run a sweep of experiments

`configs/experiment_grid.py` enumerates a list of `ExperimentConfig`s (a
hidden-layer-size sweep, a lookback-window sweep, a dropout sweep, etc. —
edit this file to add your own). Run the whole sweep with:

```bash
uv run python scripts/run_all_experiments.py
```

Every config in the sweep runs one after another, each writing to its own
`outputs/experiments/<experiment_id>/` and appending one row to
`outputs/experiments_ledger.csv`.

### 4. Creating your own config

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
list returned by `build_experiment_grid()` in `configs/experiment_grid.py`,
then run `run_all_experiments.py`.

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
| `val_ratio` | `0.11` | Fraction used for validation/early-stopping (immediately after the training range). The remainder (`1 - train_ratio - val_ratio`, ≈`0.15` by default) is the held-out test set (the most recent data — by default this lands on exactly one full seasonal year, important for solar irradiance so the test score isn't biased toward one season). |
| `hidden_sizes` | `[64, 32]` | Model size/depth. The first number is the LSTM's hidden size, and `len(hidden_sizes)` is the number of stacked LSTM layers. Any additional numbers become extra `Linear` layers in the output head (e.g. `[64, 32]` → a 1-layer-hidden LSTM(64) feeding a Linear(64→32)→Linear(32→horizon_hours) head; `[128, 64, 32]` → a 2-layer LSTM(128) feeding a deeper head). |
| `dropout_rate` | `0.3` | Dropout probability, used both for regularization during training *and* as the source of randomness for Monte Carlo Dropout at inference — don't set this to `0`, or MC-Dropout will produce identical predictions every pass (no epistemic uncertainty). |
| `city_embedding_dim` | `4` | Size of the learned vector representing which city a window belongs to. |
| `learning_rate` | `1e-3` | Adam optimizer's initial learning rate. |
| `batch_size` | `128` | Training/validation batch size. |
| `max_epochs` | `100` | Hard cap on training epochs per model (early stopping usually kicks in well before this). |
| `early_stop_patience` | `10` | Stop training if validation loss hasn't improved for this many consecutive epochs. |
| `lr_reduce_factor` / `lr_reduce_patience` | `0.5` / `7` | Learning-rate is multiplied by `lr_reduce_factor` if validation loss plateaus for `lr_reduce_patience` epochs. |
| `nonneg_penalty_weight` | `0.1` | Weight of a soft penalty discouraging negative irradiance predictions (irradiance can't physically be negative). `0` disables it. |
| `n_bootstrap` | `8` | Number of bootstrap-resampled model replicas trained for the ensemble (the paper recommends 5–10). **Set to `1` for a fast sanity-check run** — with only one replica there's no resampling, just a single trained LSTM, still scored via MC-Dropout alone. |
| `mc_dropout_passes` | `100` | Number of stochastic forward passes per replica at inference time (the paper recommends 50–100). Total predictions pooled per test point = `n_bootstrap × mc_dropout_passes` (e.g. 8×100=800 by default). |
| `bootstrap_block_length` | `168` | Block length (in windows) for the moving-block bootstrap resampling — resampling in contiguous blocks (default ≈1 week) rather than individually preserves the data's temporal autocorrelation. Only relevant when `n_bootstrap > 1`. |
| `seed` | `42` | Random seed (each bootstrap replica additionally offsets this so replicas aren't identical). |

## Interpreting results

### Where things are written

```
outputs/
├── experiments/<experiment_id>/
│   ├── config.json                    # the exact config used for this run
│   ├── log.txt                        # device used, split dates, per-replica val loss, total time
│   ├── checkpoints/
│   │   ├── bootstrap_model_<i>.pt      # trained weights for each replica
│   │   └── scaler.joblib               # the fitted feature scaler (needed to interpret raw model outputs)
│   ├── metrics/
│   │   ├── results_summary.csv         # one row per {Aggregate, Ankara, Antalya, Konya, Rize, Van}
│   │   └── results_by_horizon.csv      # one row per horizon step (1h-ahead .. 24h-ahead)
│   └── figures/
│       ├── forecast_ci_<city>.png      # one per city
│       ├── rmse_vs_horizon.png
│       └── cp_vs_horizon.png
└── experiments_ledger.csv              # ONE ROW PER RUN — compare configs at a glance
```

`experiments_ledger.csv` is the fastest way to compare many runs: it has one
row per experiment with its key config fields (`hidden_sizes`,
`lookback_hours`, `n_bootstrap`, ...) alongside its headline metrics
(aggregate, across all cities and horizon steps). Open it in a
spreadsheet/pandas to sort/filter across runs.

### Metrics explained

All metrics are computed three ways: **aggregate** (all cities, all horizon
steps pooled), **per-city** (`results_summary.csv`), and **per-horizon-step**
(`results_by_horizon.csv`, step 1 = 1 hour ahead, step 24 = 24 hours ahead).

**Point-forecast accuracy** (how good is the predicted mean?):

- **RMSE** (Root Mean Squared Error, W/m²) — average error, penalizing large
  misses more heavily. Lower is better.
- **MAE** (Mean Absolute Error, W/m²) — average error, more robust to
  outliers than RMSE. Lower is better.

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
