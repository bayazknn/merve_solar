# Tuning plan

Working document for the hyperparameter tuning that precedes the ablation programme. It
records what is tuned, over which grid, in which order and why, and how runs move between the
remote Mac (where they train) and the analysis machine. **Results and their interpretation are
in `TUNING_FINDINGS.md`**, backed by the `<stage>_*.csv` tables next to this file. Decisions go in
`configs/experiment_grid.py::DECISIONS`.

## Status (update at the end of every session)

**As of 2026-10-30 (after the S5 pull): tuning is complete. The frozen configuration is lookback
24 h, 256 × 1, dropout 0.2, learning rate 5e-4, patience 5, block 168 h, B = 6, T = 100
(`TUNING_FINDINGS.md`, Frozen configuration). `final_reference` is unlocked (5 new runs), but one
setting is open: the conformal mode, which is `"none"` in every tuning run and in the final
configs as they stand. Decide it before running the final reference.**

| Stage | Group | State | Decision |
|---|---|---|---|
| Smoke | `smoke` | Done on the analysis Mac (MPS, 3.6 min), all outputs present | n/a |
| S1 lookback | `tune_s1_lookback` | Done (9 runs, MPS); findings final | **24 h** (incumbent kept) |
| S2 architecture | `tune_s2_arch` | Done (24 grid runs + 3 extension runs, MPS); findings final | **256 × 1** (width compute-bounded) |
| S3 dropout | `tune_s3_dropout` | Done (12 runs, MPS); findings final | **0.2** |
| S3 learning rate | `tune_s3_lr` | Done (6 runs, MPS); findings final | **5e-4** (marginal pass, rule applied as written) |
| Patience | | Decided from S1 to S3 patience tables | **5** from S4 on (`FROZEN_PATIENCE`) |
| S4 block length | `tune_s4_block` | Done (12 runs at B=8, MPS, 2 shards); findings final | **168 h** (incumbent kept; all blocks within 0.15 W/m² CRPS) |
| S5 ensemble size, MC passes | `tune_s5_ensemble` | Done (3 runs at B=16, curves, MPS, 3 shards); findings final | **B = 6, T = 100** (B by the rule; T raised from the rule's 50 for stable interval endpoints) |
| Conformal mode | | Open: needed for the headline row | pending (the user's call) |
| Final | `final_reference` | Unlocked: 5 runs at B=6, T=100, seeds 42 to 46 | wait for the conformal decision |

Findings for every stage, with per-province tables and robustness checks: `TUNING_FINDINGS.md`.

**Machines:**
- **Remote Mac:** the Mac mini, user `merveer`, clone at `merve_solar/`. All tuning runs train
  here, on MPS.
  - It pulls and pushes over HTTPS (`https://github.com/bayazknn/merve_solar.git`).
  - Never edit tracked files there. If both machines committed, `git pull --rebase` and then
    `git push` (S2 was pushed this way).
- **Analysis Mac:** this machine. Pull, report, decide, commit `DECISIONS`.

**Remote commit convention.** After `check_outputs.py` passes, commit only the result paths
(`git add outputs/experiments outputs/experiments_ledger.csv`), never all of `outputs/`, so
`.DS_Store` files stay out. Messages read like `Tuning S1 (lookback): 9 runs on Mac mini,
check_outputs passed`. They start with "partial" and name the failed id if a run failed, and
they copy any WARNING lines from the check.

**Next session, in order:**
1. **Decide the conformal mode for the frozen configuration** (being decided with the user).
   Raw daylight CP is 0.79 at the chosen cell, so the paper's headline row needs the conformal
   layer. Agreed so far:
   - **The city axis is required**: the cross-province claim needs coverage per province.
   - **No season axis**: validation (2024-09-03 → 2025-06-11) has no July or August and only
     11 days of June. A summer cell would be fitted on those 11 days and applied to two test
     summers.
   - **Candidates: `per_city` (5 factors) and `city_horizon` (120 factors).** The question is
     whether coverage varies with the lead time enough to need a factor per step, at the price of
     about 130 effective observations per cell.
   - **Not by test, not by in-sample validation.** `08_conformal_mode_selection.py` scores on
     the test split and must not be used to choose. Post-correction validation CP is fitted by
     construction.
   - **The check (validation only): `scripts/16_conformal_check.py`.** It reloads the first 6
     networks of each S5 run (seeds 42 to 44), predicts validation at T=100 and never touches
     test. Each mode (global, per_city, per_horizon, city_horizon) is fitted on some months and
     scored on the others: alternating months for the geometry, and leave-one-season-out for
     the seasonal-transfer risk. It reports aggregate |CP − 0.95|, worst province, worst horizon
     step, the CP spread across steps, MPIW, PINW and the rescaled CRPS. It also refits k month
     by month (overall and per province) to show how seasonal it is. The `in_sample` rows are
     there only to show how optimistic a fitted coverage is.
   - **On the Mac mini** (estimated 10 to 20 min in all, about 1 GB of memory per run; the
     smoke run took 4 s):
     ```bash
     git pull && uv sync --dev
     uv run python scripts/16_conformal_check.py
     git add outputs/experiments outputs/tuning/conformal_check_*.csv && git commit -m "Conformal check on the S5 runs (B=6, T=100), validation only" && git push
     ```
   - **Then here:** pull, read `outputs/tuning/conformal_check_scores.csv` (and the groups,
     folds and month_k tables), decide the mode with the user, and write a conformal section in
     `TUNING_FINDINGS.md`.
2. Set `conformal_mode` on the final configs in `configs/experiment_grid.py` (the ids stay
   `final_s42` to `final_s46`; the mode is a ledger column), check `final_reference --list`,
   run the grid tests, commit and push.
3. Give the user the final-reference commands: 5 runs × 6 networks, about 2.5 to 3 h
   single-process, or about 1.5 h with three shards:
   ```bash
   uv run python scripts/run_all_experiments.py --group final_reference --skip-existing --continue-on-error --shard 0/3
   ```
   (and `--shard 1/3`, `--shard 2/3` in two more terminals), then
   `check_outputs.py --group final_reference` and the usual result-path commit.
4. After the pull: report the five-seed mean ± sd of the validation and test rows. This is the
   first time a test metric of the frozen configuration is read. Then start the ablation
   programme (After tuning).

**Open observations to carry forward:**
- **Resolved by S5:** the smoke run's 6 W/m² RMSE gap between MC-averaged and dropout-off
  predictions does not hold on trained weights (+0.05 W/m²). MC-Dropout supplies most of the
  spread: dropout-off CP is 0.28 at B=6, against 0.79 with MC-Dropout.
- Patience is 5 from S4 on, for the 256 × 1 architecture only (see Early stopping). An
  ablation that narrows the network must restore 10: S2 shows 5 is not safe for 32- or 64-wide
  networks.
- The benchmark methodology is still undeclared (CLAUDE.md). Nothing in tuning depends on it.

## Principles

1. **Tune, freeze, then ablate.** Ablations are run on the frozen configuration. An ablation
   of a configuration that is later changed describes a model that is not the paper's.
2. **Select on validation only.** Every choice uses the ledger's `val_*` columns (validation
   split, daylight subset). Test metrics are written but never read for a decision.
   `scripts/15_tuning_report.py` does not load them.
3. **Three seeds per arm.** Choosing a different stopping epoch alone moves daylight RMSE by
   about 4 W/m² for one network (`outputs/diagnostics/training_dynamics/FINDINGS.md`), so a
   one-seed difference is not evidence.
4. **Decision rule.** The best arm replaces the incumbent only if its mean seed-paired gain
   is larger than the standard deviation of those paired gains. Otherwise the incumbent stays.
   This keeps the reported configuration from tracking noise.
5. **One criterion per stage.**
   - Point-structure stages (S1 to S3: window, architecture, dropout, learning rate) train one
     network without resampling (`n_bootstrap=1`, T=100) and are judged on
     `val_RMSE_daylight`.
   - Uncertainty stages (S4 to S5) train the full ensemble and are judged on
     `val_CRPS_daylight`, a proper score that rewards accuracy and calibration together.
     `val_CP_daylight` is reported beside it.
6. **No unnecessary runs.**
   - An arm identical to an earlier winner is reused, not rerun.
   - The ensemble-size and MC-pass grids are read off one 16-network run per seed instead of
     being trained separately. The first k networks of a run are exactly the networks of a
     k-network run with the same seed (tested bitwise on CPU).
7. **One device.** All tuning runs train on the remote Mac (MPS). MPS, CPU and CUDA do not
   agree bitwise, so a mean over seeds must not mix backends. `check_outputs.py` flags a
   CPU row.

## Grids

Every grid is centred on the incumbent (`config_005_default_full`), with steps coarse enough
that a difference can exceed seed noise.

| Stage | Parameter | Grid | Incumbent | Step | Arms | New runs |
|---|---|---|---|---|---|---|
| S1 | lookback (h) | 24, 48, 72 | 24 | 1 day | 3 | 9 |
| S2 | LSTM width × depth | {32, 64, 128} × {1, 2, 3}, + 256 × 1 | 64 × 2 | ×2 width, +1 layer | 10 | 27 |
| S3 | dropout rate | 0.1, 0.2, 0.3, 0.4, 0.5 | 0.3 | 0.1 | 5 | 12 |
| S3 | learning rate | 5e-4, 1e-3, 2e-3 | 1e-3 | ×2 | 3 | 6 |
| S4 | block length (h) | L + 24 + 24k, k ∈ {3, 5, 8, 12} | 168 | days | 4 | 12 (B=8) |
| S5 | ensemble size B | 4, 6, 8, 10, 12, 14, 16 | 8 | 2 | 7 | 3 (B=16) |
| S5 | MC passes T | 50, 75, 100, 125, 150 | 100 | 25 | 5 | 0 |
| Final | frozen configuration | 5 seeds | | | 1 | 5 (B=6 is not the S4 fidelity, so no run is reused) |

Notes on the grids:

- **Lookback cannot go below 24 h.** A window issued at night would then contain no daylight
  hour at all, and 24 h is the incumbent. So the grid only extends upwards. The
  training-dynamics findings suggest more history adds little, which is what S1 tests.
- **Architecture.** The head is always one hidden layer of half the LSTM width, as in the
  incumbent. Width and depth are crossed because they trade off against each other: a deeper,
  narrower network can match a wider, shallower one.
- **Dropout and learning rate** are each moved one at a time from the S2 winner. S4 trains
  every arm with both chosen values, but it has no arm without them, so it cannot detect an
  interaction. After S3 the combination (0.2, 5e-4) was accepted untested. A lower
  learning rate also spreads the optimum over more epochs. FINDINGS observed the best epoch
  at 0 to 5 with ~1,700 steps per epoch, so a slower rate also makes the per-epoch
  early-stopping choice less coarse.
- **Ensemble size and MC passes are not trained per cell.** Each S5 seed trains 16 networks
  once. `scripts/14_ensemble_curves.py` then scores every (first B networks, first T passes)
  cell and the dropout-off ensemble of each B. That gives the B × T surface and the
  MC-Dropout-vs-normal-dropout contrast on identical weights.
  - Selection: the cheapest cell whose mean validation CRPS is within one seed standard
    deviation of the best cell. Networks cost training time; passes cost only inference.

## Block length and window size

**A block must be longer than the window, not shorter.**

- The bootstrap resamples windows, and windows whose starts are less than the window span
  (lookback + horizon = L + 24 h) apart share raw hours. A block shorter than that span cuts
  through samples that are dependent by construction. The replicas then look more independent
  than they are, and the bootstrap under-states the spread.
- Weather persistence adds to that. Daily cloudiness anomalies (the daily clear-sky index minus
  its day-of-year mean, training period) are autocorrelated as follows:

| Lag (days) | Ankara | Antalya | Konya | Rize | Van |
|---|---|---|---|---|---|
| 1 | 0.43 | 0.38 | 0.45 | 0.37 | 0.45 |
| 2 | 0.18 | 0.13 | 0.18 | 0.11 | 0.19 |
| 3 | 0.10 | 0.04 | 0.08 | 0.05 | 0.13 |
| 4 | 0.08 | −0.01 | 0.07 | 0.04 | 0.11 |
| 5 | 0.05 | 0.00 | 0.05 | 0.05 | 0.07 |

With 1,892 days the noise band is ±0.046. The memory is therefore about 3 days (up to 4 to
5 in Van).

The rule is therefore **block ≥ L + 24 h + 3 days**: proportional to the window, plus the
weather memory, which does not scale with the window. The grid adds k whole days to the span,
k ∈ {3, 5, 8, 12}. At L = 24 this is 120, 168, 240 and 336 h, and the incumbent's 168 h is
k = 5.

- The upper end is bounded by block diversity. Roughly 45,000 training windows per province
  over 336 h still give about 130 distinct blocks per province.
- Because the grid is defined relative to the chosen lookback, S4 runs after S1 and never on
  a lookback the model does not use.

## Early stopping

Early stopping is on in every run (`early_stop_patience=10`, `max_epochs=100`): training stops
after 10 epochs without a new best validation loss, and the best epoch's weights are kept.

The evidence says 10 is already wide enough:
- In the 40-epoch diagnostic run without early stopping, the best epoch was 5. It was never
  beaten in the following 34 epochs, through three learning-rate halvings. The longest wait
  before any new best was 3 epochs.
- The reference run's networks stopped after 11 to 16 epochs, with best epochs 0 to 5.
- No network has reached the 100-epoch cap.

The cost is that about 10 of every 11 to 16 epochs only confirm a stop that has already
happened. A patience of 5 would cut roughly a third of the training time.

**The patience is not shortened during S1 to S3**, for two reasons:
- The arms most likely to peak later are exactly the ones being tested: a lower learning rate,
  a wider network, a longer lookback. A tight patience could truncate them and bias the
  comparison against them.
- Patience is a training setting, so changing it mid-stage would mix two settings in one
  comparison.

Instead, every stage report measures it. `15_tuning_report.py` reads each network's full
validation-loss history and writes `<stage>_patience.csv`: for patience 3, 5 and 7, how many
networks would have kept a different epoch. If S1 to S3 (about 50 networks) show zero at
patience 5 or 7, the patience is lowered before S4. S4 and S5 are the expensive stages (about
10 h of the total), and the frozen configuration and every ablation would use the lower value.

**Outcome (after S3): patience 5 from S4 on.** None of the 18 networks at the chosen 256 × 1
width (S2 and S3, every dropout rate and learning rate) would have kept a different epoch at
patience 5 or 7; the longest wait for a new best was 4 epochs. For 32- and 64-wide networks it
is not safe (8 of 18 changed at patience 5), so the value is tied to the architecture. It is
`FROZEN_PATIENCE` in `configs/experiment_grid.py`, applied to S4, S5 and the final reference.

## Interactions and how the order handles them

| Interaction | Handling |
|---|---|
| lookback ↔ block length | Block grid is a function of the chosen lookback (above). |
| lookback ↔ capacity | Lookback first at the incumbent architecture, then architecture at the chosen lookback. |
| width ↔ depth | Crossed grid in S2. |
| dropout ↔ MC-Dropout spread | Dropout is chosen for accuracy at B=1. Its effect on the intervals is measured in S4/S5, and T is chosen at the chosen dropout. Choosing dropout on CRPS at B=1 would favour too much dropout, because a single network's MC spread has to stand in for the bootstrap spread it lacks at B=8. |
| dropout ↔ learning rate | Each moved one at a time. S4 carries both chosen values but cannot detect an interaction; the combination was not tested separately (S3 findings). |
| block length ↔ ensemble size | B is chosen at the chosen block length. |
| ensemble size ↔ MC passes | Crossed B × T surface in S5, at no training cost. |

A full factorial of these grids would be 3 × 9 × 5 × 3 × 4 × 7 × 5 ≈ 57,000 cells. The staged
design trains 66 runs (9 + 24 + 18 + 12 + 3) plus 2 to 5 for the final reference.

## Cost (remote Mac, MPS)

Measured anchors:

- The incumbent full run (`config_005_default_full`, B=8, T=100) took 27.7 min, about
  3.5 min per network.
- The smoke group took 3.6 min on this Mac, ensemble curves included. Validation is now scored in every run,
  which adds roughly 10 to 15% wall clock.

Estimates per stage (lookback 24; longer lookbacks scale roughly linearly):

| Stage | Estimate |
|---|---|
| S1 | ~1 h |
| S2 | 2 to 3 h |
| S3 | 1 to 1.5 h at 64 × 2; done in 18 runs at 256 × 1 (6 to 8 min per network) |
| S4 | done: 12 runs at about 41.5 min each with 2 shards (5.2 min per network) |
| S5 | done: 3 runs at about 1.9 h each with 3 shards (7.2 to 7.5 min per network), curves included |
| Final | ~2.5 to 3 h single-process at B=6 (5 new runs, 30 networks); ~1.5 h with 3 shards |
| **Total** | **about 3 h** left (final reference) |

S2 chose a network that trains in about 7.6 min (6.5 min at dropout 0.2) instead of 3.5 to
4 min. Patience 5 cuts a dropout-0.2 network from about 13 epochs to about 8, which takes back
most of that. These are single-process figures; sharding shortens the wall clock.

## Runbook

On the remote Mac, once per stage:

```bash
git pull
uv sync --dev
uv run python scripts/run_all_experiments.py --group smoke --ensemble-curves   # first time only
uv run python scripts/check_outputs.py --group smoke --ensemble-curves         # first time only
uv run python scripts/run_all_experiments.py --group tune_s1_lookback --list
uv run python scripts/run_all_experiments.py --group tune_s1_lookback --skip-existing --continue-on-error
uv run python scripts/check_outputs.py --group tune_s1_lookback
git add outputs/experiments outputs/experiments_ledger.csv && git commit -m "Tuning S1 (lookback): ..." && git push
```

- For S5, add `--ensemble-curves` to both the run and the check commands.
- **Parallel runs.** Add `--shard 0/2` in one terminal and `--shard 1/2` in another, with the same
  group and flags. The shards are disjoint, and ledger writes are locked.
  - The networks are small, so one process leaves MPS mostly idle. Two or three shards should
    finish a stage in close to half or a third of the time. Check this on the first stage
    before relying on it.
  - Shards share the GPU, so `training_time_sec` is inflated and stops being a clean cost
    measure. The metrics are unaffected.
  - Run `check_outputs.py` once, after every shard has finished, and commit once.
  - Never start the same group twice without `--shard`: two processes would train the same
    configs and overwrite each other's output folders.
- `--skip-existing` makes an interrupted sweep resume where it stopped.
- `check_outputs.py` must pass before committing. A missing file cannot be recovered from the
  analysis machine, because checkpoints and `test_predictions.npz` are gitignored.
- Everything the analysis needs is a committed CSV:
  - the ledger
  - `results_summary.csv` and `val_results_summary.csv`
  - `daily_scores.csv` (for paired tests)
  - `replicas.csv` and `training_history.csv`
  - `ensemble_curves.csv`

On the analysis machine, after `git pull`:

```bash
uv run python scripts/15_tuning_report.py --stage s1
```

It writes `<stage>_summary.csv`, `_patience.csv`, `_by_province.csv` and `_matched_origins.csv`.
Add `--allow-missing` for a provisional report while some arms are still training. The stage's
choice is then written into `DECISIONS`, its section into `TUNING_FINDINGS.md`, and both are
committed with the tables. That
unlocks the next group. S3 has two groups, `tune_s3_dropout` and `tune_s3_lr`, which can run in
one sweep.

## What each stage also checks from FINDINGS.md

- Every run now writes `replicas.csv` (best epoch per network) and `training_history.csv`
  (per-epoch losses). Each stage therefore shows whether "the optimum is at epoch 0 to 5" holds
  across lookbacks, architectures and learning rates, or is specific to the incumbent.
- FINDINGS expects regularisation not to lower the optimum. S2 and S3 test that directly; if
  they confirm it, the paper can say so with numbers.
- The daylight-only loss (FINDINGS point 5) and the other design choices are ablations, not
  tuning axes. They run on the frozen configuration.

## After tuning

1. `final_reference`: the frozen configuration at seeds 42 to 46. This is the paper's
   reference row.
2. Ablation programme on the frozen configuration, 3 seeds per arm, paired tests from
   `daily_scores.csv`:
   - **Uncertainty layer:** plain LSTM / one network / seed ensemble (`bootstrap_resample=False`) /
     bootstrap ensemble, each with normal and MC-Dropout inference (`inference_mode`).
   - **Transfer:**
     - global versus per-province
     - leave-one-province-out, giving a contribution matrix of which province helps which
     - city embedding removed
   - **Training choices:** daylight-only loss, no non-negativity penalty, conformal on/off.
   - **Inputs:** feature groups.
