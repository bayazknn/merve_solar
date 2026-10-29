# Tuning plan

Working document for the hyperparameter tuning that precedes the ablation programme. It
records what is tuned, over which grid, in which order and why, and how runs move between the
remote Mac (where they train) and the analysis machine. Results of each stage go in
`<stage>_summary.csv` next to this file; decisions go in `configs/experiment_grid.py::DECISIONS`.

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
git add outputs/ && git commit -m "Tuning S1: lookback runs" && git push
```

- For S5, add `--ensemble-curves` to both the run and the check commands.
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
