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

The data is NASA POWER hourly, in `SolarData_Merve(031026_V3).xlsx` (one sheet per province), the
repo's only data file. Irradiance is stored directly in W/m² (the earlier V2 export used MJ/m²/hour). There
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
uv run python scripts/03_run_naive_baselines.py            # naive climatology/persistence rows (descriptive only)
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json
uv run python scripts/run_all_experiments.py --list        # what a sweep would run, without running it
uv run python scripts/run_all_experiments.py --group smoke --ensemble-curves   # real data, minutes
uv run python scripts/check_outputs.py --group tune_s1_lookback   # on the run machine, before committing
uv run python scripts/15_tuning_report.py --stage s1        # validation-only stage summary
uv run python scripts/14_ensemble_curves.py --experiment-id ID   # B x T sub-ensemble curves (needs checkpoints)
uv run python scripts/render_pdf.py DATASET_DESCRIPTION.md   # manuscript section -> PDF, figures embedded
```

`run_experiment.py` also takes `--exclude-city NAME`, `--loss {mse,mae,huber}` and
`--experiment-id ID`; any override requires `--experiment-id`, so a changed run never overwrites
the config's own id. `run_all_experiments.py` with no `--group` selects every group in
`configs/experiment_grid.py` whose prerequisites are decided: always `--list` first.
Full CLI and per-field config reference: `README.md`.

**Before proposing a full run**, sanity-check the code path with the `smoke` group (or a smoke
config: `n_bootstrap=1, max_epochs=5, mc_dropout_passes=10`): a full run is 8 replicas × 100 MC passes,
and a crash at the metrics step after hours of training is the expensive failure. State the
backend (`cpu`/`mps`/`cuda`) with any cost estimate.

## Architecture

**`data.py` is config-independent; everything downstream is per-config.**

1. **Base data (once)**: `data.py` reads the 5 sheets, trims NASA POWER's trailing `-999`
   latency gap at `LAST_VALID_TIMESTAMP`, computes `solar_elevation` and
   `toa_horizontal` (`MASK_COLUMNS`, never model inputs), adds cyclical hour/day-of-year/wind
   sin-cos features, and caches everything to a parquet.
2. **One experiment**: `experiment.py::run_experiment(config)` is the orchestrator; read it first.
   Chronological split boundaries on the full frame → drop `excluded_cities` → fit scaler on train
   rows only → build windows → train every replica (moving-block resample unless
   `bootstrap_resample=False`) → score VALIDATION, then TEST, with `evaluation.evaluate_split`,
   which streams chunks of windows: predict (`inference_mode`), inverse-transform to W/m², night
   clamp, optional conformal rescale, summary + per-element CRPS. The pooled sample is never
   materialised, so B=16 costs no more memory than B=1. Outputs: metrics CSVs (test and
   validation), `daily_scores.csv`, `replicas.csv`, `training_history.csv`,
   `test_predictions.npz`, figures, one ledger row; `experiment.REQUIRED_RUN_OUTPUTS` lists them
   and the run raises if one is missing.

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
  (2025-06-11 → 2026-06-29); the validation set (2024-09-03 → 2025-06-11) has no July and only
  the first 11 days of June.
- **Every preprocessing step is fit on train rows only** (`scaling.py`). A step fit on the full
  frame is test leakage that would invalidate published numbers.
- **Moving-block bootstrap, resampled per city** (`bootstrap_block_length`, default 168 windows ≈
  1 week), not i.i.d. resampling, to preserve autocorrelation.
- **Two subsets, two jobs: the EDA uses `target > 0`, modelling keeps geometric daylight.**
  Every descriptive EDA output (`eda.py`, `scripts/02_descriptive_analysis.py`: statistics,
  correlations, ramps, histograms, the descriptive reference-forecast table) is computed on
  `eda.positive_mask` = `target > 0`, labelled "hours with target > 0" and stored under scope
  `positive`. (NASA's `-999` sentinel is below zero, so it is excluded by the same condition;
  `data.py` raises before one can reach the EDA.) Training, validation, test metrics, the
  conformal layer and the naive baselines keep the geometric `daylight` mask below, which is
  an outlier-removal principle that does not condition on the answer. On this record the two
  differ by 3,030 twilight hours (1.9% of the target > 0 rows, at most 11.68 W/m², sun up to
  2.4° below the horizon), and no daylight hour reads zero (`target_positive_filter_audit.csv`).
  Never mix the two in one table: the manuscript must say which subset each number comes from.
- **Daylight means `solar_elevation > 0`**, computed from site and time alone. A `target > 0`
  threshold would pick the metric's denominator using the answer and cannot be evaluated 24 h
  ahead. The threshold is deliberately untuned.
- **The non-negativity penalty acts at 0 W/m²**, i.e. at `scaling.scaled_target_zero(scaler)`
  on the scaled axis, never at scaled 0 (the training mean). Ledger column
  `nonneg_penalty_floor` records it: `0_wm2` for current runs, `train_mean` for rows trained
  before the 2026-10-29 fix, which are not comparable with anything trained since.
- **`clamp_night_to_zero` (default on) is physics, not tuning**: elements below the horizon get
  their whole sample set set to zero, applied once in `run_experiment` for every arm.
- **Hours are per-site Local Solar Time**, not a shared time zone: never compare an hour across
  cities, and label hour axes as local solar time.
- **`excluded_cities` never renumbers city ids** (`CITY_TO_ID` is fixed); `config.active_cities`
  is the single source of truth for which provinces a run uses.
- **`hidden_sizes` is overloaded**: `[0]` is the LSTM hidden size, `[1:]` extra Linear layers in
  the head, and, while `lstm_layers` is `None`, `len()` the number of stacked LSTM layers
  (`[64, 32]` is a 2-layer LSTM). Read depth through `config.n_lstm_layers`.
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
horizon step, each for two subsets, `all_hours` and `daylight`, for the test split and (in
`val_results_summary.csv` and the `val_*` ledger columns) the validation split. **Every tuning or
design choice is made on the validation columns; test metrics are never used to select
anything** (`scripts/15_tuning_report.py` does not read them). Rows trained before 2026-10-29
have no validation columns. **Headline numbers come from
`daylight`**: about half of all elements are exact night zeros, which pull RMSE/MAE down, push
all-hours R² above 0.9 for even a climatology, and, under the night clamp, make every night
interval cover by construction. Judge a run by daylight CP ≈ 0.95 first, then daylight
PINW/CWC/CRPS, reported alongside daylight RMSE/MAE/R². CP/PINW use the 2.5/97.5 percentiles of the
pooled sample. The pooled distribution has no aleatoric term, so raw intervals under-cover;
`conformal_mode` (`conformal.py`, default `"none"`) is the recalibration layer, and it leaves
RMSE/MAE/R² bit-identical to its uncorrected twin.

**Benchmark: the plain LSTM** (declared by the user, 2026-10-30): one network of the frozen
architecture and training settings, dropout off at prediction, no ensemble, no conformal layer
(arms `*_plain_lstm` in `abl_scope_dropout`), run both global and per province. It has no range,
so it is compared on RMSE/MAE/R² and on CRPS (which equals its MAE). Climatology and persistence
are **not** benchmarks; the naive baseline rows stay in the ledger as descriptive references only.

### Figures, tables and manuscript text

- Experiment figures: `utils.py`, into `outputs/experiments/<id>/figures/` via the `Agg` backend;
  a new plot is a function taking an explicit `save_path` that closes its figure.
- Dataset figures and tables: `eda.py` via `scripts/02_descriptive_analysis.py`, on the
  `target > 0` subset (see the invariant above), into
  `outputs/eda/`, styled by `paper_style.py` (300 dpi PNG plus vector PDF, white background).
  `paper_style.py` exposes `PAPER_RC` for `plt.rc_context` and never mutates global rcParams.
  Keep `outputs/eda/README.md` and `EDA.md` in step with the numbers.
- Variable names are used directly in figures and are never renamed: figure axes and tables both
  show the raw NASA POWER codes with units (`paper_style.AXIS_LABELS` = `VARIABLE_LABELS`, e.g.
  `T2M (°C)`). Everything else, table string values included, is English.
- Figures are sized for pasting into Word: `FULL_WIDTH_IN` = 6.3 in, fonts set in `PAPER_RC`,
  and multi-panel figures built with `layout="constrained"` and x tick labels on every panel.
  Those values are join keys, so changing them is a breaking change.
- Manuscript sections are Markdown at the repo root (e.g. `DATASET_DESCRIPTION.md`), rendered by
  `scripts/render_pdf.py`. They contain no internal references (no file paths, config field names
  or pointers to working documents); embedded image `src` paths are the one exception.

## Open work

- **Tuning complete** (`outputs/tuning/TUNING_PLAN.md`, `TUNING_FINDINGS.md`): stages S1 to S5
  and the conformal mode are recorded in `configs/experiment_grid.py::DECISIONS` /
  `FINAL_CONFORMAL_MODE`. **`final_s42`..`final_s46` (group `final_reference`) are the paper's
  reference row** (summary: `scripts/17_final_reference_report.py` → `outputs/final_reference/`).
  Runs happen on the remote Mac, the analysis here after a pull.
- **Ablation programme drafted** (`outputs/ablation/ABLATION_PLAN.md`, plain English for
  non-specialist readers): one group `abl_scope_dropout`, a 2 x 3 table of training scope
  (global / per province) x predictive layer (MC-Dropout / normal dropout / plain LSTM
  benchmark). 12 new runs: ensemble arms at seeds 42-43 (global MC-Dropout reuses
  `final_s42`, `final_s43`), plain LSTM at 42-44. Plus group `abl_daylight_loss` (2 runs,
  `loss_daylight_only=True`, global MC-Dropout, seeds 42-43; `scripts/run_abl_daylight_loss.sh`),
  kept separate so the running shards were not reshuffled. Further arms are listed there as
  candidates.

- `config_005_default_full` was the pre-tuning reference run; scripts 09 and 12 and the numbers
  in `METHODOLOGY.md` still come from it and must be regenerated on the final reference. `config_000_smoke` and
  `config_002_default_full` are pre-fix rows. Every network stops early (best epoch 0–5); this
  is genuine overfitting after a plateau, not a bug (`outputs/diagnostics/training_dynamics/`),
  so epoch selection is noisy at the ~4 W/m² level and arm comparisons need several seeds.
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
