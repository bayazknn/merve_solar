# CLAUDE.md

## Project context and working mode

This is **research code for an academic paper in progress**, not a production system. Metrics
tables, figures and model comparisons produced here are candidate artifacts for the manuscript.
**The project restarted from a clean slate on 2026-09-27**: the model, the methodology write-up
and the ablation programme are all being redesigned, so treat everything in the code as the current
best guess, not a settled decision.

- **Act as a senior data scientist collaborator**, not a code executor. When a modeling choice is
  weak (leakage, an unfair baseline comparison, a metric that hides a failure, an underpowered
  sweep, a conclusion the data doesn't support), say so and propose the better design. Give a
  recommendation with reasoning, not a menu of options.
- **Paper-facing output is part of "done."** A modeling change that improves a metric is only
  half-delivered without the table or figure that shows it. Numbers quoted to the user should be
  traceable to a file under `outputs/`.
- **Reproducibility is a publication requirement**: every result comes from a saved
  `ExperimentConfig` with a fixed `seed`, runnable end-to-end from the CLI.
- **The manuscript is in English, and so is every document and artifact produced for it**:
  write-ups, figures, tables, table values and rendered pages.

## The domain

24-hour-ahead hourly solar irradiance forecasting (`ALLSKY_SFC_SW_DWN`, W/m²) for 5 Turkish
provinces (Ankara, Antalya, Konya, Rize, Van, chosen to span different climate zones), using an
LSTM point forecaster wrapped in a **Bootstrap Ensemble × MC-Dropout** uncertainty layer. The
approach is adapted from a reference paper (`main_methodology_paper.pdf`), with an LSTM in place of
its PCNN backbone and irradiance in place of PV power.

The data is NASA POWER hourly, in `SolarData_Merve(140926_V2).xlsx` (one sheet per province), the
repo's only data file. Irradiance arrives in MJ/m²/hour and is converted to W/m² at read time. There
are 13 model features (`config.py::NUMERIC_FEATURE_COLUMNS`) and no clear-sky column, so geometry
comes from `solar.py` instead. `outputs/eda/EDA.md` describes the dataset.

**Legacy material, do not cite or build on it:** everything in `outputs/archive/` (the old
methodology, ablation and TODO documents, and the retired dataset's ledger) is in Turkish and/or
describes experiments on a retired dataset with a different column set. The methodology and
ablation documents will be rewritten from scratch, in English.

## Commands

Dependencies are managed with `uv`; a `.venv/` already exists. There is no linter or formatter.

```bash
uv sync --dev
uv run python -m pytest tests/ -v                          # loads the real xlsx; no GPU needed
uv run python -m pytest tests/test_windows.py::test_no_window_start_predates_its_city_series -v

uv run python scripts/01_prepare_base_data.py              # ONE-TIME: builds outputs/processed/base_features.parquet
uv run python scripts/02_descriptive_analysis.py           # EDA figures/tables -> outputs/eda/
uv run python scripts/03_run_naive_baselines.py            # climatology/persistence floor (seconds)
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json
uv run python scripts/run_all_experiments.py --list        # what a sweep would run, without running it
uv run python scripts/render_pdf.py DATASET_DESCRIPTION.md   # manuscript section -> PDF, figures embedded
```

`run_experiment.py` also takes `--exclude-city NAME`, `--loss {mse,mae,huber}` and
`--experiment-id ID`; any override requires `--experiment-id`, so a changed run never overwrites
the config's own id. `run_all_experiments.py` with no `--group` selects *every* group in
`configs/experiment_grid.py`, which is far more than anyone usually means: always `--list` first.
Full CLI and per-field config reference: `README.md`.

**Before proposing a full run**, sanity-check the code path with a smoke config
(`n_bootstrap=1, max_epochs=5, mc_dropout_passes=10`): a full run is 8 replicas × 100 MC passes,
and a crash at the metrics step after hours of training is the expensive failure. State the
backend (`cpu`/`mps`/`cuda`) with any cost estimate.

## Architecture

**`data.py` is config-independent; everything downstream is per-config.**

1. **Base data (once)**: `data.py` reads the 5 sheets, trims NASA POWER's trailing `-999`
   latency gap at `LAST_VALID_TIMESTAMP`, converts units, computes `solar_elevation` and
   `toa_horizontal` (`MASK_COLUMNS`, never model inputs), adds cyclical hour/day-of-year/wind
   sin-cos features, and caches everything to a parquet.
2. **One experiment**: `experiment.py::run_experiment(config)` is the orchestrator; read it first.
   Chronological split boundaries on the full frame → drop `excluded_cities` → fit scaler on train
   rows only → build windows → per bootstrap replica: moving-block resample, train, MC-Dropout
   predict → pool passes → inverse-transform to W/m² → night clamp → metrics → CSVs,
   `test_predictions.npz`, figures, one ledger row.

`ExperimentConfig` (`config.py`) is the unit of work, serialized to JSON; `experiment_id` names the
output directory `outputs/experiments/<id>/` and the row in `outputs/experiments_ledger.csv`. Every
field is validated in `__post_init__`. Sweeps are named groups in
`configs/experiment_grid.py::EXPERIMENT_GROUPS`.

### Invariants

- **The global model is the default and the headline.** City identity enters only as a learned
  embedding; cross-city transfer is a claim of the paper. `training_scope="per_city"` exists to
  test that claim and is only interpretable as a matched pair against a `global` arm with the same
  seed and fidelity.
- **No BatchNorm, and `dropout_rate > 0`.** MC-Dropout runs the model in `.train()` mode, and
  dropout is its only source of randomness.
- **Windows never cross a city or split boundary.** Splits are chronological and computed once on
  the full five-province frame before any city is excluded, so every arm splits on identical
  dates. `train_ratio=0.74 / val_ratio=0.11` makes the test set cover all four seasons
  (2025-05-16 → 2026-05-30); the validation set has no June or July.
- **Every preprocessing step is fit on train rows only** (`scaling.py`). A step fit on the full
  frame is test leakage that would invalidate published numbers.
- **Moving-block bootstrap, resampled per city** (`bootstrap_block_length`, default 168 windows ≈
  1 week), not i.i.d. resampling, to preserve autocorrelation.
- **Daylight means `solar_elevation > 0`**, computed from site and time alone. A `target > 0`
  threshold would pick the metric's denominator using the answer and cannot be evaluated 24 h
  ahead. The threshold is deliberately untuned.
- **`clamp_night_to_zero` (default on) is physics, not tuning**: elements below the horizon get
  their whole sample set set to zero, applied once in `run_experiment` for every arm.
- **Hours are per-site Local Solar Time**, not a shared time zone: never compare an hour across
  cities, and label hour axes as local solar time.
- **`excluded_cities` never renumbers city ids** (`CITY_TO_ID` is fixed); `config.active_cities`
  is the single source of truth for which provinces a run uses.
- **`hidden_sizes` is overloaded**: `[0]` is the LSTM hidden size, `len()` the number of stacked
  LSTM layers, `[1:]` extra Linear layers in the head.
- **Data-integrity checks in `data.py` raise rather than warn.** If the xlsx is refreshed,
  `LAST_VALID_TIMESTAMP`, `EXPECTED_TRIMMED_ROWS_PER_SHEET` (`config.py`) and
  `FULL_ROWS_PER_SHEET` (`tests/test_data.py`) change together.
- Scripts add `src/` to `sys.path`; keep that prologue in new scripts.

### Comparability rules

The paper's tables come straight out of the ledger, so its rows must be comparable.

- **Give a changed run a new `experiment_id`**: rerunning an id replaces its output directory and
  its ledger row, so the earlier result is gone.
- **Change one axis at a time, and only along ledger columns** (`experiment.py::LEDGER_COLUMNS`).
  A new axis goes into `LEDGER_COLUMNS` and the row dict first;
  `tests/test_ledger.py` fails until it does.
- **Fidelity is an axis**: a `n_bootstrap=1` row's interval metrics are never compared against a
  `B=8` row's, and smoke-fidelity interval metrics never go in the paper. Check `hit_max_epochs`
  before any arm-to-arm claim.
- **Changing an `ExperimentConfig` default orphans every earlier row.** Prefer a new sweep config;
  if a default must change, say so and plan the reruns.
- **Comparison models share the pipeline**: same windows, same splits, same train-only scaler,
  reported through `metrics.py` into the same ledger with `model_family` set. The naive baselines
  (`baselines.py`) use no scaler, fitted on train rows only.

### Metrics

`metrics.py` reports RMSE/MAE/R²/CP/PINW/MPIW/Reliability/CWC/CRPS aggregate, per city and per
horizon step, each for two subsets, `all_hours` and `daylight`. **Headline numbers come from
`daylight`**: about half of all elements are exact night zeros, which pull RMSE/MAE down, push
all-hours R² above 0.9 for even a climatology, and, under the night clamp, make every night
interval cover by construction. Judge a run by daylight CP ≈ 0.95 first, then daylight
PINW/CWC/CRPS, reported alongside daylight RMSE/MAE/R². CP/PINW use the 2.5/97.5 percentiles of the
pooled sample. The pooled distribution has no aleatoric term, so raw intervals under-cover;
`conformal_mode` (`conformal.py`, default `"none"`) is the recalibration layer, and it leaves
RMSE/MAE/R² bit-identical to its uncorrected twin.

**The floor to beat** (current ledger): pooled daylight RMSE **109.86 W/m²** and R² **0.8456**
(climatology), daylight MAE **72.15** (persistence). A model that does not beat both is not a
result.

### Figures, tables and manuscript text

- Experiment figures: `utils.py`, into `outputs/experiments/<id>/figures/` via the `Agg` backend;
  a new plot is a function taking an explicit `save_path` that closes its figure.
- Dataset figures and tables: `eda.py` via `scripts/02_descriptive_analysis.py`, into
  `outputs/eda/`, styled by `paper_style.py` (300 dpi PNG plus vector PDF, white background).
  `paper_style.py` exposes `PAPER_RC` for `plt.rc_context` and never mutates global rcParams.
  Keep `outputs/eda/README.md` and `EDA.md` in step with the numbers.
- Variables are labelled by their raw NASA POWER names (`T2M (°C)`) via
  `paper_style.VARIABLE_LABELS`; everything else, table string values included, is English.
  Those values are join keys, so changing them is a breaking change.
- Manuscript sections are Markdown at the repo root (e.g. `DATASET_DESCRIPTION.md`), rendered by
  `scripts/render_pdf.py`. They contain no internal references (no file paths, config field names
  or pointers to working documents); embedded image `src` paths are the one exception.

## Open work

- Rewrite the methodology document from scratch, in English, from the code as it stands.
- Decide whether to run an ablation programme on the current dataset; nothing but the naive
  baselines has been run on it yet.
- Comparison models (SVM, GRU, Prophet or RF/MLP) through the shared pipeline.
- Feature-set candidates: `log1p(PRECTOTCORR)` plus a rain indicator, and dropping `T2MDEW`
  (reproducible from `T2M` and `RH2M` at r = 0.999).
- Paper figures: a map of the 5 provinces and a paragraph on their climatic differences.

## Paths and git

All paths derive from `PROJECT_ROOT` in `config.py`. `outputs/` is tracked in git except
checkpoints (`*.pt`) and `test_predictions.npz`, which are regenerated from the seeded config, so
a paired significance test has to run where the experiment ran. Long runs may happen on another
machine that syncs through git, so commit and push each coherent change right away (standing
authorization); mention it before running a sweep that rewrites many experiment directories.
