# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context and working mode

This is **research code for an academic paper in progress**, not a production system. Everything
produced here — metrics tables, figures, model comparisons — is a candidate artifact for the
manuscript.

- **Act as a senior data scientist collaborator**, not a code executor. When a modeling choice is
  weak (leakage, an unfair baseline comparison, a metric that hides a failure, an underpowered
  sweep, a conclusion the data doesn't support), say so and propose the better design. Give a
  recommendation with reasoning, not a menu of options.
- **The model is not finalized.** Architecture, feature set, horizon, and the UQ layer are all
  still open and expected to change. Treat existing choices as the current best guess, not as
  settled constraints — but never silently change a default that existing ledger rows were
  produced under (see *Comparability rules*).
- **Paper-facing output is part of "done."** A modeling change that improves a metric is only
  half-delivered without the table/figure that shows it. Numbers quoted to the user should be
  traceable to a file under `outputs/`.
- Reproducibility is a publication requirement here: every result must come from a saved
  `ExperimentConfig` with a fixed `seed`, runnable end-to-end from the CLI.

## The domain

24-hour-ahead hourly solar irradiance forecasting (`ALLSKY_SFC_SW_DWN`, W/m²) for 5 Turkish
provinces (Ankara, Antalya, Konya, Rize, Van — deliberately spanning different climate zones),
using an LSTM point forecaster wrapped in a **Bootstrap Ensemble × MC-Dropout** uncertainty layer.
Source data is NASA POWER hourly, in `SolarData_Merve_All(16July).xlsx` (one sheet per province).

The methodology is adapted from a reference paper (`main_methodology.md` — Turkish — and
`main_methodology_paper.pdf`), substituting the paper's PCNN backbone with an LSTM and PV power
output with irradiance. When implementing anything UQ-related, check `main_methodology.md` for the
formula the paper actually specifies before reaching for a textbook default.

`README.md` is the user-facing manual and holds the full per-field config table and metric
definitions — consult it before re-deriving config semantics or metric interpretation, and update
it when either changes.

## Commands

Dependencies are managed with `uv` (`pyproject.toml` + `uv.lock`); a `.venv/` already exists.

```bash
uv sync --dev                                              # install
uv run pytest tests/ -v                                    # all tests (loads the real xlsx; slow-ish, no GPU needed)
uv run pytest tests/test_windows.py -v                     # one test file
uv run pytest tests/test_windows.py::test_no_window_start_predates_its_city_series -v   # one test

uv run python scripts/01_prepare_base_data.py              # ONE-TIME: build outputs/processed/base_features.parquet
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json   # one run (smoke ≈ minutes)
uv run python scripts/run_all_experiments.py               # the whole sweep in configs/experiment_grid.py
```

`01_prepare_base_data.py` must have been run before any experiment. There is no linter/formatter
configured in this repo.

**Before proposing a full run**, sanity-check the code path with a smoke config
(`n_bootstrap=1, max_epochs=5, mc_dropout_passes=10`). A full-fidelity run is 8 replicas × 100
MC passes and can take hours; a crash at the metrics step after two hours of training is the
expensive failure mode here.

## Architecture

Two-stage design, and the split matters: **`data.py` is config-independent, everything downstream
is per-config.**

1. **Base data (once)** — `data.py` reads the 5 sheets, trims NASA POWER's trailing `-999` latency
   gap at `LAST_VALID_TIMESTAMP`, drops the `DROPPED_COLUMNS` (`ALLSKY_KT`, ~50% `-999` at
   night, and `CLRSKY_SFC_SW_DWN`) at read time so the xlsx stays untouched, adds cyclical
   hour/day-of-year/wind-direction sin-cos features, and caches all cities concatenated to a
   parquet. Every experiment reuses this cache.
2. **One experiment (per config)** — `experiment.py::run_experiment(config)` is the single
   orchestrator; read it first to understand the flow. Order is deliberate:
   chronological split boundaries (`windows.py`) → fit scaler on train rows only
   (`scaling.py`, leakage-safe) → build windows (`windows.py`) → for each bootstrap replica:
   moving-block resample (`bootstrap.py`) → train (`train.py`) → MC-Dropout predict
   (`mc_dropout.py`) → pool all replicas' passes → inverse-transform to W/m² → metrics
   (`metrics.py`) → CSVs, figures (`utils.py`), and one ledger row.

**A "config" (facet) is the unit of work.** `ExperimentConfig` (`config.py`) is a dataclass
serialized to/from JSON; `experiment_id` names both the output directory
(`outputs/experiments/<id>/`) and the row in the shared `outputs/experiments_ledger.csv`.
Add sweep entries to `build_experiment_grid()` in `configs/experiment_grid.py`.

### Invariants worth preserving

- **One global model across all cities.** City identity enters only as a learned embedding
  (`SolarLSTM.city_embedding`) broadcast to every timestep — never train per-city models. This is
  a deliberate claim of the paper (cross-city transfer), not an implementation shortcut.
- **No BatchNorm in the model.** MC-Dropout inference keeps the model in `.train()` mode
  (deliberately not `.eval()`), which would corrupt BatchNorm running stats.
- **`dropout_rate` must stay > 0** — it is the *only* source of MC-Dropout randomness.
- **Windows never cross a city boundary or a split boundary.** A window is assigned to a split
  only if its entire lookback+horizon span falls inside that split's date range; straddlers are
  dropped. Split boundaries are chronological (train → val → test, oldest first), and the default
  `train_ratio=0.74 / val_ratio=0.11` is tuned so the test set lands on exactly one full seasonal
  year — changing those ratios breaks that property and makes the score season-biased.
- **Scaler is fit on train rows only** (`scaling.py`). Any new preprocessing step must be fit
  inside the same train-only boundary; a scaler fit on the full frame is silent test leakage that
  would invalidate published numbers.
- **Moving-block bootstrap, not i.i.d. resampling** (`bootstrap_block_length`, default 168h ≈ 1
  week), resampled per city, to preserve temporal autocorrelation.
- **`hidden_sizes` is overloaded**: `hidden_sizes[0]` is the LSTM hidden size, `len(hidden_sizes)`
  is the number of stacked LSTM layers, and `hidden_sizes[1:]` become extra Linear layers in the
  head. Changing its interpretation invalidates every existing ledger row.
- **`n_bootstrap=1` is the fast path**, not a separate code path: no resampling, a single LSTM,
  still scored via MC-Dropout alone.
- **Scripts add `src/` to `sys.path`** rather than relying on the editable install; keep that
  prologue when adding a script under `scripts/`.
- **Data-integrity checks in `data.py` raise rather than warn** (exact trimmed row count,
  no residual `-999`, no NaN). If the source xlsx is ever refreshed, `LAST_VALID_TIMESTAMP`,
  `EXPECTED_TRIMMED_ROWS_PER_SHEET`, and `FULL_ROWS_PER_SHEET` in `tests/test_data.py` all need
  updating together.

### Comparability rules

The ledger is only useful if rows are comparable, and the paper's tables come straight out of it.

- **Never reuse an `experiment_id`.** `_append_ledger_row` always appends, so a rerun overwrites
  the output directory but leaves a stale duplicate row behind. Give a changed run a new id.
- **Change one axis at a time.** Ledger rows carry only a subset of the config
  (`hidden_sizes`, `lookback_hours`, `dropout_rate`, ratios, `n_bootstrap`, `mc_dropout_passes`);
  a run that also changed something *not* in those columns is indistinguishable in the table.
  If a new axis matters, add it to the ledger row dict in `experiment.py` first.
- **Changing a default in `ExperimentConfig` orphans every prior row**, which were produced under
  the old default and don't record it. Prefer adding an explicit sweep config over editing a
  default; if a default genuinely must change, say so and plan the reruns.
- **Baselines must share the pipeline.** Any comparison model (GRU, SVM, RF, MLP, …) must use the
  same windows, the same chronological splits, and the same train-only scaler, and must report
  through `metrics.py` into the same ledger — otherwise the comparison isn't publishable. Add it
  as a model variant behind the existing `run_experiment` flow rather than as a parallel script.

### Metrics

`metrics.py` reports every metric three ways: aggregate, per-city (`results_summary.csv`), and
per-horizon-step (`results_by_horizon.csv`). CP/PINW follow the methodology doc's percentile-based
CI (2.5/97.5 of the pooled sample — *not* mean ± 1.96·std); MPIW/CWC/Reliability/CRPS use standard
literature definitions to match the source paper's reporting table.

Judge a run by **CP ≈ 0.95 first**, then PINW/CWC/CRPS. A low PINW with CP far below 0.95 is an
overconfident model, not a good one, and a huge CWC is the flag for exactly that. Report point
accuracy (RMSE/MAE) and interval quality together — neither alone is a result.

Caveat worth remembering when writing up numbers: night-time hours are ~zero irradiance and are
included in every split, which flatters MAE/RMSE and inflates CP. A daylight-only breakdown is
usually the more honest comparison against literature.

### Figures and tables

`utils.py` holds the plotting helpers; all figures go to `outputs/experiments/<id>/figures/` at
120 dpi via the `Agg` backend (no interactive display available). New plots should follow the same
pattern: a function taking an explicit `save_path`, creating parent dirs, closing the figure.

For anything destined for the manuscript, prefer vector output (`.pdf`/`.svg`) alongside the PNG,
readable axis labels with units (W/m²), and a caption-ready title. EDA figures that describe the
dataset rather than a single run belong in a dedicated `scripts/` entry point writing to
`outputs/figures/`, not inside `run_experiment`.

## Open work (from `TODOs.md`, Turkish)

Roughly translated, still outstanding:

- **Dataset decisions: DONE (2026-08-28).** `CLRSKY_SFC_SW_DWN` and `ALLSKY_KT` are now dropped
  at read time via `DROPPED_COLUMNS` (`config.py`), the feature set is 17 columns, and
  `ALLSKY_SFC_SW_DWN` is confirmed as `TARGET_COLUMN`. Ledger rows written before this change ran
  with 18 features and are **not comparable** — the sweep needs rerunning under new ids.
- **Model configuration:** settle layer count / neuron sizes and the lookback lag; build an
  "optimal LSTM config" from the reference papers.
- **Baselines for comparison:** SVM, Prophet, GRU (Random Forest or MLP if Prophet is unworkable
  on this framing) — see *Comparability rules* before adding any.
- **Metrics table:** MAE, RMSE, **R²** — R² is not implemented anywhere yet; it needs adding to
  `metrics.py` and to the ledger row.
- **Paper figures not yet built:** map of the 5 provinces; per-variable scatter vs. solar
  radiation; correlation matrix; monthly boxplots of irradiance per city; 3D month × year ×
  irradiance surface per city; seasonal day-vs-radiation plot. Plus a written paragraph on the
  climatic/geographic differences between the 5 provinces.

### Paths

All paths derive from `PROJECT_ROOT` in `config.py`; nothing takes a path argument on the CLI
except `run_experiment.py --config`.

`outputs/` is tracked in git **except model checkpoints** (`.gitignore` ignores
`outputs/**/checkpoints/*.pt`): configs, logs, metrics CSVs, figures, `scaler.joblib`, and the
ledger all sync; the `.pt` weights stay local and are regenerated from the seeded config. This
matters because long experiments are run on a remote server that syncs through git — results
produced there only reach the paper if they are committed and pushed.

Commit and push each coherent change immediately rather than batching at the end of a session
(the user has given standing authorization for this); the remote otherwise runs stale code. Note
that a sweep produces a large, reviewable diff — mention it before running one that rewrites many
experiment directories.
