# Tuning plan

Working document for the hyperparameter tuning that precedes the ablation programme. It
records what is tuned, over which grid, in which order and why, and how runs move between the
remote Mac (where they train) and the analysis machine. Results of each stage go in
`<stage>_summary.csv` next to this file; decisions go in `configs/experiment_grid.py::DECISIONS`.

## Status (update at the end of every session)

**As of 2026-10-30: S1 is decided (lookback 24 h). S2's 3 × 3 grid is done; its winner sat at
the grid edge, so a 3-run extension (256 × 1) must run on the remote Mac before S2 is decided.**

| Stage | Group | State | Decision |
|---|---|---|---|
| Smoke | `smoke` | Done on the analysis Mac (MPS, 3.6 min), all outputs present | n/a |
| S1 lookback | `tune_s1_lookback` | Done on the remote Mac (9 runs, MPS), report in `s1_summary.csv`, `s1_patience.csv` | **24 h** (incumbent kept) |
| S2 architecture | `tune_s2_arch` | 24 grid runs done (MPS). Extension `h256l1` (3 runs) pending on the remote Mac | pending; 128 × 1 leads |
| S3 to S5, final | | Locked until the previous decision is in `DECISIONS` | |

**S2 interim result (validation, daylight, 3 seeds, B=1; paired Δ vs the incumbent 64 × 2):**

| Width × depth | val RMSE | Paired Δ RMSE (mean ± sd) | val CRPS | val CP | Mean best epoch |
|---|---|---|---|---|---|
| **128 × 1** | **92.57** | **−7.89 ± 0.13** | **49.55** | 0.809 | 5.7 |
| 64 × 1 | 95.10 | −5.37 ± 1.04 | 51.50 | 0.875 | 13.7 |
| 128 × 2 | 96.05 | −4.42 ± 1.02 | 51.57 | 0.836 | 3.0 |
| 128 × 3 | 96.58 | −3.88 ± 0.35 | 51.84 | 0.849 | 1.7 |
| 64 × 2 (incumbent) | 100.47 | 0 | 55.14 | 0.879 | 5.3 |
| 64 × 3 | 101.54 | +1.07 ± 0.59 | 55.97 | 0.871 | 3.7 |
| 32 × 1 | 105.19 | +4.73 ± 0.40 | 58.36 | 0.893 | 29.3 |
| 32 × 2 | 112.45 | +11.98 ± 1.24 | 63.21 | 0.887 | 10.7 |
| 32 × 3 | 114.92 | +14.45 ± 1.72 | 64.52 | 0.877 | 8.3 |

- 128 × 1 passes the decision rule by a wide margin (gain 7.9, paired sd 0.13). It wins in every
  province (−6.5 Rize to −9.3 Antalya), and CRPS agrees (−5.6).
- **It won at the corner of the grid** (widest, shallowest), so the grid did not bracket the
  optimum. `S2_EXTENSION` adds 256 × 1 (3 seeds). The decision is taken after it: 256 × 1 replaces
  128 × 1 only under the same rule. Depth is not extended, since 1 layer is best at every width.
- **Depth is confounded with dropout.** `nn.LSTM` applies dropout between stacked layers only
  when there are 2 or more, so a 1-layer model has dropout only in the head. "Deeper is worse"
  here means "deeper with 0.3 inter-layer dropout is worse". The paper must say this, not that
  depth hurts. For S3 it means the dropout sweep at 1 layer tunes head dropout only.
- **CP falls as the model gets better** (0.879 → 0.809). In a 1-layer network the MC-Dropout spread
  comes only from the head. A sharper, more accurate network with a thin stochastic layer
  under-covers at B=1. This is the job of the bootstrap (S4/S5) and the conformal layer, and it
  is selected on CRPS there. Carry it forward: it bears directly on the paper's MC-Dropout claim.
- **Patience:** small networks peak late (32 × 1 up to epoch 33, 64 × 1 at 13.7 on average), and
  patience 5 would have changed 8 of the 27 S2 networks. Every 128-wide network would be unchanged.
  Lowering the patience is therefore justified only for the chosen architecture, and only if
  S3's lower learning rate does not push its best epoch later.

**S1 result (validation, daylight, 3 seeds, B=1):**

| Lookback | val RMSE | Paired Δ vs 24 h (mean ± sd) | val CRPS | val CP | Best epochs | Train min/network |
|---|---|---|---|---|---|---|
| 24 h | 100.47 | 0 | 55.14 | 0.879 | 10, 4, 2 | 4.1 |
| 48 h | 101.41 | +0.94 ± 0.63 | 55.44 | 0.875 | 7, 4, 4 | 7.0 |
| 72 h | 101.59 | +1.12 ± 0.12 | 55.47 | 0.883 | 4, 4, 6 | 9.3 |

- Longer history makes the model slightly worse, not better. Every seed is worse at 48 h and at 72 h,
  and CRPS agrees with RMSE. The decision rule is not even triggered, because neither challenger
  has a positive gain. This confirms the training-dynamics expectation that more history adds
  little.
- Longer lookbacks lose the first 1 to 2 validation days (no window may cross the split). Re-scored
  from `daily_scores.csv` on the 1,390 origins all arms share, the paired gaps are +0.86 ± 0.63
  (48 h) and +0.97 ± 0.13 (72 h), so the conclusion does not depend on the target set.
- Per province the gaps are mixed and within seed noise, except Van at 72 h (+2.3 ± 1.1). No
  province shows a clear gain from longer history.
- Best epoch: one network (24 h, seed 42) peaked at epoch 10. "Best epoch 0 to 5" is therefore
  typical, not universal.
- Patience: at patience 5 or 7, 0 of 9 networks would keep a different epoch. At patience 3, 1 of 9
  would. Seven more patience checks come from S2 and S3 before the patience decision before S4.

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

**Next session, in order** (after the S2 extension finishes on the remote Mac):
1. `git pull`, then `uv run python scripts/check_outputs.py --group tune_s2_arch` (27 runs, all
   mps; only the gitignored `test_predictions.npz` reported missing).
2. Run `uv run python scripts/15_tuning_report.py --stage s2`. Apply the rule between 256 × 1
   and 128 × 1. If 256 × 1 also wins clearly, it is again at the grid edge: consider 512 × 1, but
   weigh it against the cost per network and the risk of a model too large for 5 provinces.
3. Write `DECISIONS["s2"]`, commit it with `s2_summary.csv` and `s2_patience.csv`, then confirm
   `tune_s3_dropout` and `tune_s3_lr` list (12 + 6 runs).
4. Give the user the S3 commands. Update this Status section.

**Open observations to carry forward:**
- In the 2-epoch smoke run, the average of the MC-Dropout passes was about 6 W/m² worse in
  RMSE than the same networks with dropout off (106.1 vs 99.8 on test). The bias was also
  more negative: −15.8 vs −14.4 W/m².
  - The smoke models were barely trained, so this proves nothing yet.
  - The S5 curves measure exactly this contrast on identical, fully trained weights. If it
    holds, it matters for the paper's MC-Dropout claim.
- Patience stays at 10 through S3. The decision to lower it before S4 comes from the
  `<stage>_patience.csv` files (see Early stopping). S2 already shows it is not safe for small
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
| S2 | LSTM width × depth | {32, 64, 128} × {1, 2, 3} | 64 × 2 | ×2 width, +1 layer | 9 | 24 |
| S3 | dropout rate | 0.1, 0.2, 0.3, 0.4, 0.5 | 0.3 | 0.1 | 5 | 12 |
| S3 | learning rate | 5e-4, 1e-3, 2e-3 | 1e-3 | ×2 | 3 | 6 |
| S4 | block length (h) | L + 24 + 24k, k ∈ {3, 5, 8, 12} | 168 | days | 4 | 12 (B=8) |
| S5 | ensemble size B | 4, 6, 8, 10, 12, 14, 16 | 8 | 2 | 7 | 3 (B=16) |
| S5 | MC passes T | 50, 75, 100, 125, 150 | 100 | 25 | 5 | 0 |
| Final | frozen configuration | 5 seeds | | | 1 | 2 to 5 |

Notes on the grids:

- **Lookback cannot go below 24 h.** A window issued at night would then contain no daylight
  hour at all, and 24 h is the incumbent. So the grid only extends upwards. The
  training-dynamics findings suggest more history adds little, which is what S1 tests.
- **Architecture.** The head is always one hidden layer of half the LSTM width, as in the
  incumbent. Width and depth are crossed because they trade off against each other: a deeper,
  narrower network can match a wider, shallower one.
- **Dropout and learning rate** are each moved one at a time from the S2 winner. Their
  combination is checked in S4, which trains every arm with both chosen values. A lower
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

## Interactions and how the order handles them

| Interaction | Handling |
|---|---|
| lookback ↔ block length | Block grid is a function of the chosen lookback (above). |
| lookback ↔ capacity | Lookback first at the incumbent architecture, then architecture at the chosen lookback. |
| width ↔ depth | Crossed grid in S2. |
| dropout ↔ MC-Dropout spread | Dropout is chosen for accuracy at B=1. Its effect on the intervals is measured in S4/S5, and T is chosen at the chosen dropout. Choosing dropout on CRPS at B=1 would favour too much dropout, because a single network's MC spread has to stand in for the bootstrap spread it lacks at B=8. |
| dropout ↔ learning rate | Each moved one at a time; the combination is checked in S4. |
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
| S3 | 1 to 1.5 h |
| S4 | ~6 h |
| S5 | ~4 h, curves included |
| Final | 1 to 2.5 h |
| **Total** | **15 to 18 h** |

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

The stage's choice is then written into `DECISIONS`, with the report committed beside it. That
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
