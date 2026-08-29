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

The methodology is adapted from a reference paper (`main_methodology_paper.pdf`), substituting
the paper's PCNN backbone with an LSTM and PV power output with irradiance.
**`main_methodology.md` (Turkish) is this project's own Method source of truth** — it describes
what the code actually does, section by section, with a document↔code map in its §17. When
implementing anything UQ-related, check it for the formula actually specified before reaching for
a textbook default; when it and the code disagree, the code wins and the doc is the thing to fix.

`README.md` is the user-facing manual and holds the full per-field config table and metric
definitions — consult it before re-deriving config semantics or metric interpretation, and update
it when either changes.

## Commands

Dependencies are managed with `uv` (`pyproject.toml` + `uv.lock`); a `.venv/` already exists.

```bash
uv sync --dev                                              # install
uv run python -m pytest tests/ -v                          # all tests (loads the real xlsx; slow-ish, no GPU needed)
uv run python -m pytest tests/test_windows.py -v           # one test file
uv run python -m pytest tests/test_windows.py::test_no_window_start_predates_its_city_series -v   # one test

uv run python scripts/01_prepare_base_data.py              # ONE-TIME: build outputs/processed/base_features.parquet
uv run python scripts/03_run_naive_baselines.py            # climatology/persistence/smart-persistence floor (seconds)
uv run python scripts/run_experiment.py --config configs/config_000_smoke.json   # one run (smoke ≈ minutes)
uv run python scripts/run_all_experiments.py --list        # what the whole sweep would run, without running it
uv run python scripts/run_all_experiments.py --group smoke # one named group of configs/experiment_grid.py
```

`run_experiment.py` also takes `--exclude-city NAME` (repeatable), `--loss {mse,mae,huber}` and
`--experiment-id ID`; any override requires `--experiment-id` or the script refuses, because
reusing the config's id would overwrite that run and leave a misdescribing ledger row.
`run_all_experiments.py` takes `--group` (repeatable), `--only ID ...`, `--list`,
`--skip-existing` and `--continue-on-error`. Full CLI reference in `README.md`.

`01_prepare_base_data.py` must have been run before any experiment. There is no linter/formatter
configured in this repo.

**Before proposing a full run**, sanity-check the code path with a smoke config
(`n_bootstrap=1, max_epochs=5, mc_dropout_passes=10`). A full-fidelity run is 8 replicas × 100
MC passes; a crash at the metrics step after two hours of training is the expensive failure mode
here. Cost is measured, not guessed: on this CPU-only host (12 cores, torch on 6 threads) the
pooled five-province split runs 25.7 s/epoch and 1.83 s/MC-pass, which puts a twelve-arm study
at B=8×T=100 between 22 h (early stopping at epoch 40) and 96 h (every replica to the cap) —
days, not hours. That is why `ABLATION_B1` exists. `run_all_experiments.py` with no `--group`
selects *every* group, which is far more than anyone usually means; always `--list` first.

## Architecture

Two-stage design, and the split matters: **`data.py` is config-independent, everything downstream
is per-config.**

1. **Base data (once)** — `data.py` reads the 5 sheets, trims NASA POWER's trailing `-999` latency
   gap at `LAST_VALID_TIMESTAMP`, drops the `DROPPED_COLUMNS` (`ALLSKY_KT` only, ~50% `-999`
   at night) at read time so the xlsx stays untouched, keeps `CLRSKY_SFC_SW_DWN` as a
   `MASK_COLUMNS` entry that is never a model input, adds cyclical
   hour/day-of-year/wind-direction sin-cos features, and caches all cities concatenated to a
   parquet. Every experiment reuses this cache.
2. **One experiment (per config)** — `experiment.py::run_experiment(config)` is the single
   orchestrator; read it first to understand the flow. Order is deliberate:
   chronological split boundaries on the FULL frame (`windows.py`) → drop `excluded_cities` →
   unscaled "layout" pass for the canonical W/m² truth, city ids, daylight mask and window
   timestamps → fit scaler on train rows only (`scaling.py`, leakage-safe) → build windows
   (`windows.py`) → for each bootstrap replica: moving-block resample (`bootstrap.py`) → train
   (`train.py`) → MC-Dropout predict (`mc_dropout.py`) → pool all replicas' passes →
   inverse-transform to W/m² → clamp night elements to zero if `clamp_night_to_zero` → metrics
   over both subsets (`metrics.py`) → CSVs, `test_predictions.npz`, figures (`utils.py`), and one
   ledger row. `SCOPE_RUNNERS` dispatches the middle of that on `training_scope`.

**A "config" (facet) is the unit of work.** `ExperimentConfig` (`config.py`) is a dataclass
serialized to/from JSON; `experiment_id` names both the output directory
(`outputs/experiments/<id>/`) and the row in the shared `outputs/experiments_ledger.csv`.
`configs/experiment_grid.py` groups the sweep by name in `EXPERIMENT_GROUPS` (`smoke`, `main`,
`ablation`, `rize_curve`, `rize_curve_b1`, `rize_curve_smoke`); add sweep entries to a group
builder there, and `build_experiment_grid(groups)` assembles them and rejects duplicate ids.

Besides the windowing/architecture/UQ knobs, `ExperimentConfig` now carries the **arm-selection
and criterion axes**: `training_scope` (`global` | `per_city`), `model_family`,
`excluded_cities`, `loss_function` (`mse` | `mae` | `huber`) + `huber_delta`,
`target_transform` (`raw` | `clearsky_index`), `loss_daylight_only`, `per_city_scaler` and
`clamp_night_to_zero`. All of them are validated in
`__post_init__` (so a typo fails at config load, not three hours into a sweep) and all of them
are ledger columns. `README.md` has the per-field table.

**`baselines.py` + `scripts/03_run_naive_baselines.py`** are the reference floor: climatology,
persistence and smart persistence, fitted on training rows only and gathered into windows by
`build_experiment_windows(..., extra_target_columns=...)` so they are aligned by exactly the
indexing the model's targets are. They report through `metrics.py` into the same ledger with
`model_family` set, and blank the interval metrics (a point forecast's zero-width interval makes
CP an equality test). A model that does not beat these is not a result.

### Invariants worth preserving

- **The global model is the headline configuration and the default.** City identity enters only
  as a learned embedding (`SolarLSTM.city_embedding`) broadcast to every timestep. Cross-city
  transfer is a deliberate claim of the paper, not an implementation shortcut, so `global` stays
  the default and every headline number comes from it. **Per-city training is not a bug — it is
  the `training_scope="per_city"` ablation arm** (`experiment.py::_run_per_city_scope`) that
  tests that claim by removing the transfer; do not "fix" it away. Rules for it: it is never the
  default, and it is only interpretable as a *matched pair* against a `global` arm on the same
  seed and the same fidelity (see `configs/experiment_grid.py::ABLATION_FULL`, which builds both
  arms from one dict so they provably differ in `training_scope` alone). A per-city arm reported
  on its own is not evidence of anything.
- **No BatchNorm in the model.** MC-Dropout inference keeps the model in `.train()` mode
  (deliberately not `.eval()`), which would corrupt BatchNorm running stats.
- **`dropout_rate` must stay > 0** — it is the *only* source of MC-Dropout randomness.
- **Windows never cross a city boundary or a split boundary.** A window is assigned to a split
  only if its entire lookback+horizon span falls inside that split's date range; straddlers are
  dropped. Split boundaries are chronological (train → val → test, oldest first), computed once
  on the FULL five-province frame *before* any `excluded_cities` filter, so every arm of every
  comparison splits on identical dates. The default `train_ratio=0.74 / val_ratio=0.11` is tuned
  so the test set spans all four seasons: measured, it is 8,878 hours = 369 days 22 hours ≈ 370
  days (2025-03-26 02:00 → 2026-03-30 23:00), i.e. slightly over a full year — not exactly one.
  Changing those ratios breaks the four-season property and makes the score season-biased.
- **Scaler is fit on train rows only** (`scaling.py`). Any new preprocessing step must be fit
  inside the same train-only boundary; a scaler fit on the full frame is silent test leakage that
  would invalidate published numbers. This holds in every arm: the `per_city` arm fits *per
  province* (`per_city_scaler=True`) but still only on that province's train rows.
- **Moving-block bootstrap, not i.i.d. resampling** (`bootstrap_block_length`, default 168
  windows ≈ 1 week at `window_stride=1`), resampled per city, to preserve temporal
  autocorrelation.
- **`clamp_night_to_zero` (default ON) is a physics constraint, not post-hoc tuning.** After the
  inverse transform, every element with `CLRSKY = 0` has its whole pooled sample set to zero —
  below the horizon the target is exactly 0 and that is known from geometry alone, without
  reading the target. It is applied once in `run_experiment`, not inside a scope runner, so every
  arm gets it identically. Consequence to carry into every write-up: it makes the all-hours CP
  structurally inflated (see *Metrics*).
- **`excluded_cities` never renumbers city ids.** `CITY_TO_ID` is fixed, ids come from the frame,
  and the model keeps a full `len(CITIES)` embedding table so an excluded province's row simply
  gets no gradient. Renumbering would silently change what every id in every saved checkpoint and
  `test_predictions.npz` means. `config.active_cities` is the single source of truth for "which
  provinces" — windows, scaler, training loop, figures and the metric table all route through it.
- **`hidden_sizes` is overloaded**: `hidden_sizes[0]` is the LSTM hidden size, `len(hidden_sizes)`
  is the number of stacked LSTM layers, and `hidden_sizes[1:]` become extra Linear layers in the
  head. Changing its interpretation invalidates every existing ledger row.
- **`n_bootstrap=1` is the fast path**, not a separate code path: no resampling, a single LSTM,
  still scored via MC-Dropout alone.
- **Scripts add `src/` to `sys.path`** rather than relying on the editable install; keep that
  prologue when adding a script under `scripts/`.
- **Daylight means `CLRSKY_SFC_SW_DWN > 0`, everywhere in the project.** Clear-sky irradiance is
  pure solar geometry with no weather term, so the boolean is an exact "is the sun above the
  horizon" indicator that never reads the realised target — which is why it is not leakage even
  though the column itself must never be a feature. Two alternatives were tried and are wrong:
  a `target > 0` threshold looks like conditioning on the outcome (it happens to select the
  identical 151,643 rows here, but only by coincidence), and a climatological `(city, month,
  hour)` cell mean is too coarse — sunrise shifts 30-60 minutes within a month, so it admitted
  5,266 rows whose clear-sky value is exactly 0, i.e. night. See `outputs/eda/README.md`,
  *Düzeltme kaydı*.
- **The hourly clock is per-site Local Solar Time, not a shared time zone.** Verified from the
  data: mean-irradiance peak hour runs Konya 11.25 < Ankara 11.26 < Antalya 11.41 < Van 11.56 <
  Rize 11.89, which is the *reverse* of what a common clock would give and matches
  `UTC + round(lon/15)` to within 0.1 h. So `HR=11` is a different physical instant in Rize than
  in Ankara — never compare hours across cities, and label hour axes "yerel saat (LST)". Hour
  labels are interval *starts*. This makes `hour_sin`/`hour_cos` a better encoding than it looks
  (each city is encoded in its own solar time) and is worth a sentence in the paper's methods.
- **Data-integrity checks in `data.py` raise rather than warn** (exact trimmed row count,
  no residual `-999`, no NaN). If the source xlsx is ever refreshed, `LAST_VALID_TIMESTAMP` and
  `EXPECTED_TRIMMED_ROWS_PER_SHEET` (both in `config.py`) and `FULL_ROWS_PER_SHEET`
  (`tests/test_data.py`) all need updating together.

### Comparability rules

The ledger is only useful if rows are comparable, and the paper's tables come straight out of it.

- **Never reuse an `experiment_id`.** `_append_ledger_row` always appends, so a rerun overwrites
  the output directory but leaves a stale duplicate row behind. Give a changed run a new id.
- **Change one axis at a time.** Ledger rows carry only a subset of the config — the authoritative
  list is `LEDGER_COLUMNS` in `experiment.py`, currently `model_family`, `training_scope`,
  `excluded_cities`, `lookback_hours`/`horizon_hours`/`window_stride`, `n_features`,
  `hidden_sizes`, `dropout_rate`, `city_embedding_dim`, the ratios, `n_bootstrap`,
  `bootstrap_block_length`, `mc_dropout_passes`, the optimizer knobs (`batch_size`,
  `learning_rate`, `lr_reduce_factor`, `lr_reduce_patience`), `max_epochs`,
  `early_stop_patience`, `loss_function`, `huber_delta`, `nonneg_penalty_weight`,
  `target_transform`, `loss_daylight_only`, `per_city_scaler`, `clamp_night_to_zero`, `seed`
  and `device`. A run
  that changed something *not* in those columns is indistinguishable in the table. If a new axis
  matters, add it to `LEDGER_COLUMNS` and the row dict first — `assert_ledger_schema_ok()` then
  fails loudly in milliseconds instead of misaligning every column of the appended row, and
  `tests/test_ledger.py::test_every_config_field_that_changes_a_result_is_a_ledger_column`
  fails in the test suite until you do. This has already happened once: `abl_arch_lr3e4_*` swept
  `learning_rate` while the ledger had no column for it, so three rows sat in the file
  indistinguishable from the arm they were supposed to be contrasted against.
- **Fidelity is an axis too.** `n_bootstrap` and `mc_dropout_passes` change what the interval
  metrics *are*: a `B=1` row is MC-Dropout-only and its CP/PINW/MPIW/CWC must never be compared
  against a `B=8` row. Smoke-fidelity interval metrics never go in the paper. Likewise check
  `hit_max_epochs` before any arm-to-arm claim: arms that differ in how much training they
  actually got are not comparable.
- **Changing a default in `ExperimentConfig` orphans every prior row**, which were produced under
  the old default and don't record it. Prefer adding an explicit sweep config over editing a
  default; if a default genuinely must change, say so and plan the reruns.
- **Baselines must share the pipeline.** Any comparison model (GRU, SVM, RF, MLP, …) must use the
  same windows, the same chronological splits, and must report through `metrics.py` into the same
  ledger — otherwise the comparison isn't publishable. Add it as a model variant behind the
  existing `run_experiment` flow rather than as a parallel script. Two documented exceptions
  exist on the *scaler* clause only, and neither weakens the train-only leakage invariant:
  the `per_city` arm gives each province its own scaler when `per_city_scaler=True` (fit on that
  province's train rows only; set `per_city_scaler=False` to run the matched arm that isolates
  the normalisation effect from the training effect), and the naive baselines in `baselines.py`
  use no scaler at all because none of those rules needs one — they are fitted on
  `datetime <= train_end` rows exactly like the scaler would be. Anything else must share the
  pooled train-only scaler.

### Metrics

`metrics.py` reports RMSE/MAE/**R²**/CP/PINW/MPIW/Reliability/CWC/CRPS three ways — aggregate,
per-city (`results_summary.csv`, which also carries an `Aggregate_excl_Rize` group row), and
per-horizon-step (`results_by_horizon.csv`) — and each of those **twice**, once per subset:
`all_hours` and `daylight` (`CLRSKY_SFC_SW_DWN > 0`, ≈51.2% of elements). The subset is a
`subset` column in both CSVs; the ledger carries the all-hours aggregate plus
`RMSE_daylight`/`MAE_daylight`/`R2_daylight`/`CP_daylight`/`n_elements_daylight`. CP/PINW follow
the methodology doc's percentile-based CI (2.5/97.5 of the pooled sample — *not* mean ± 1.96·std);
MPIW/CWC/Reliability/CRPS use standard literature definitions to match the source paper's
reporting table. `n_samples` counts windows, `n_elements` counts scored (window, horizon-step)
pairs — the actual denominator.

**The paper's headline numbers come from the `daylight` subset.** ~48.8% of elements are exact
night zeros that are trivially easy to predict, so all-hours numbers flatter the model in three
distinct ways, and each has to be handled separately:

- **RMSE/MAE** are simply pulled down by the easy half.
- **All-hours R² is the trap.** R² is normalised by the subset's own variance and the day/night
  swing dominates it: a plain `(city, month, hour)` climatology scores R² = 0.923 all-hours
  against 0.856 daylight. An all-hours R² above 0.9 is evidence of nothing. The same
  normalisation argument applies to PINW.
- **All-hours CP is inflated by construction, not by calibration.** With `clamp_night_to_zero`
  on (the default) every night element gets a degenerate `[0, 0]` interval around a true value of
  exactly 0, so it is covered by definition — roughly half the mixture is 1.0 before the model
  contributes anything. Measured on smoke runs: all-hours CP ≈ 0.80 against daylight CP ≈
  0.62–0.67.

So judge a run by **daylight CP ≈ 0.95 first**, then daylight PINW/CWC/CRPS, and report daylight
point accuracy (RMSE/MAE/R²) alongside — neither alone is a result. A low PINW with CP far below
0.95 is an overconfident model, and a huge CWC is the flag for exactly that. Note that the
current under-coverage is partly structural and expected: the pooled distribution contains no
aleatoric term (`main_methodology.md` §11.5), so the intervals answer "where could the model's
mean be", not "where could the observation be" — a residual-variance add-on or a conformal layer
is a precondition for a fair comparison against the source paper's PICP = 0.9472, not an optional
extra.

Interval metrics are `NaN` for the naive baselines by design (a single deterministic forecast has
a zero-width interval); CRPS is kept because it reduces exactly to MAE there.

### Figures and tables

`utils.py` holds the plotting helpers for **experiment** figures; those go to
`outputs/experiments/<id>/figures/` at 120 dpi via the `Agg` backend (no interactive display
available). New plots should follow the same pattern: a function taking an explicit `save_path`,
creating parent dirs, closing the figure. The per-horizon plots are emitted once per metric
subset — unsuffixed is `all_hours`, `_daylight` is the one to read.

`ABLATION.md` (Turkish) is the hand-written home for ablation write-ups: one `## N. …` section
per axis, appended rather than rewritten, with every number traced to a
`results_summary.csv` / ledger row. Keep it in step with the runs it describes.

EDA figures and tables that describe the dataset rather than a single run live in `eda.py` and
are driven by `scripts/02_descriptive_analysis.py`, writing to `outputs/eda/{figures,tables}/` —
never inside `run_experiment`. Two hand-written documents sit beside them and must be kept in
step with the numbers: `outputs/eda/README.md` (how each output was produced, its span and its
caveats, plus a correction log) and `outputs/eda/EDA.md` (the manuscript-facing discussion, with
a claim-to-file mapping). They share a separate style contract in `paper_style.py` (Turkish labels, always
a white background, PNG at 300 dpi + vector PDF with Type 42 fonts, validated season palette with
linestyle as a second channel). `paper_style.py` deliberately never mutates global rcParams — it
exposes `PAPER_RC` for `plt.rc_context`, because a `sns.set_theme()` at import would silently
restyle the `utils.py` experiment figures whenever both modules load in one process.

For anything destined for the manuscript, prefer vector output (`.pdf`/`.svg`) alongside the PNG,
readable axis labels with units (W/m²), and a caption-ready title.

## Open work (from `TODOs.md`, Turkish)

Roughly translated, still outstanding:

- **Dataset decisions: DONE (2026-08-28).** `ALLSKY_KT` is dropped at read time via
  `DROPPED_COLUMNS`; `CLRSKY_SFC_SW_DWN` is retained in the frame as a `MASK_COLUMNS` entry but
  is **never a model input** (it defines the daylight subset — see the *Daylight* invariant
  above, and it is also the instrument behind `clamp_night_to_zero`). The
  feature set is 17 columns and `ALLSKY_SFC_SW_DWN` is confirmed as `TARGET_COLUMN`. Ledger rows
  written before this change ran with 18 features and are **not comparable** — the sweep needs
  rerunning under new ids.
- **Model configuration:** the lookback lag is settled at 24 h on EDA evidence (clearness-index
  PACF is ~0.006–0.12 at day 2), with a single `lookback_hours=48` config left as empirical
  confirmation; layer count / neuron sizes are still open, as is the "optimal LSTM config" built
  from the reference papers.
- **Naive reference floor: DONE (2026-08-28)** — `baselines.py` + `scripts/03_run_naive_baselines.py`
  score climatology / persistence / smart persistence through the pipeline into the ledger. The
  LSTM has to beat daylight RMSE 106.8 W/m² and R² 0.856 (climatology) *and* daylight MAE 60.4
  (smart persistence) to be a result.
- **Baselines for comparison: still outstanding.** SVM, Prophet, GRU (Random Forest or MLP if
  Prophet is unworkable on this framing) — see *Comparability rules* before adding any.
  `model_family` already exists as a ledger column, so no header migration is needed.
- **Ablations: the arms exist, the write-up does not.** `training_scope="per_city"` (the
  cross-city transfer test) and `excluded_cities` (the Rize transfer curve, plus the loss-function
  selection stage) are implemented and grouped in `configs/experiment_grid.py`; `ABLATION.md` is
  still a template awaiting the finished runs.
- **Metrics table: R² DONE (2026-08-28)** — `metrics.py::r2` feeds the summary, per-horizon and
  ledger outputs alongside MAE/RMSE, for both subsets.
- **Feature-set work queued from the EDA** (`TODOs.md` §B/§C): `log1p(PRECTOTCORR)` plus a
  rain/no-rain binary indicator, and dropping `T2MDEW` and `WS50M` as near-deterministic
  duplicates (17 → 15). Both invalidate existing ledger rows and both need a new ledger column or
  a new id; neither is done.
- **Paper figures: DONE (2026-08-28) except the map.** Per-variable scatter, correlation
  matrices, monthly boxplots, the 3D month × year × irradiance surface (plus a 2-D anomaly
  companion) and both seasonal views are built by `scripts/02_descriptive_analysis.py` into
  `outputs/eda/`. Still outstanding: the map of the 5 provinces and the written paragraph on
  their climatic/geographic differences (both need external geodata).

### Paths

All paths derive from `PROJECT_ROOT` in `config.py`; nothing takes a path argument on the CLI
except `run_experiment.py --config`.

`outputs/` is tracked in git **except model checkpoints and prediction dumps** (`.gitignore`
ignores `outputs/**/checkpoints/*.pt` and `outputs/**/metrics/*.npz`): configs, logs, metrics
CSVs, figures, `scaler*.joblib`, and the ledger all sync; the `.pt` weights and
`test_predictions.npz` stay local and are regenerated from the seeded config. This matters
because long experiments are run on a remote server that syncs through git — results produced
there only reach the paper if they are committed and pushed. Corollary: a paired significance
test needs `test_predictions.npz`, so it has to run where the experiment ran.

Commit and push each coherent change immediately rather than batching at the end of a session
(the user has given standing authorization for this); the remote otherwise runs stale code. Note
that a sweep produces a large, reviewable diff — mention it before running one that rewrites many
experiment directories.
