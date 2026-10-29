# Tuning findings

What each tuning stage found and decided. `TUNING_PLAN.md` holds the design (grids, order,
decision rule) and the session status. This file holds the results.

**How to read this file:**
- A stage section is written once, when its decision is recorded in
  `configs/experiment_grid.py::DECISIONS`. After that it is not edited. A section marked
  **provisional** is still waiting for runs.
- Every number comes from a CSV in this directory, written by
  `scripts/15_tuning_report.py --stage <stage>`. The source file is named under each table.
- All numbers are from the **validation** split, **daylight** subset (`solar_elevation > 0`),
  in W/m². No test metric is read for any decision.
- "Δ" is the seed-paired difference from the stage's incumbent: arm minus incumbent on the same
  seed, mean ± sd over the 3 seeds (42, 43, 44). A negative Δ means a lower value than the
  incumbent's (better for RMSE and CRPS).
- **Decision rule:** the best arm replaces the incumbent only if its mean paired gain exceeds the
  sd of those paired gains.
- S1 to S3 train one network without resampling (B=1, T=100 MC-Dropout passes). Their CP and
  CRPS describe one network's MC-Dropout spread, not the final ensemble's.

## Decisions so far

| Stage | Axis | Incumbent | Decision | Gain over incumbent (val RMSE) | State |
|---|---|---|---|---|---|
| S1 | lookback | 24 h | **24 h** | 0 (incumbent kept) | final |
| S2 | LSTM width × depth | 64 × 2 | **256 × 1** | −9.51 ± 0.71 | final (width compute-bounded) |

## S1: lookback (final, decided 2026-10-29)

**Decision: keep 24 h.** A longer history makes the model slightly worse on every seed, so the
decision rule never comes into play.

| Lookback | val RMSE | Δ RMSE | val MAE | val CRPS | Δ CRPS | val CP | Mean best epoch | Train min/network |
|---|---|---|---|---|---|---|---|---|
| **24 h** | **100.47** | 0 | **78.03** | **55.14** | 0 | 0.879 | 5.3 | 4.1 |
| 48 h | 101.41 | +0.94 ± 0.63 | 78.70 | 55.44 | +0.29 ± 0.46 | 0.875 | 5.0 | 7.0 |
| 72 h | 101.59 | +1.12 ± 0.12 | 78.75 | 55.47 | +0.33 ± 0.29 | 0.883 | 4.7 | 9.3 |

Source: `s1_summary.csv`.

**Same days for every arm.** A window may not cross the split boundary, so a 48 h or 72 h
lookback loses the first 1 or 2 validation days. The arms were therefore scored on 1,400, 1,395
and 1,390 (province, day) origins. Re-scored on the 1,390 origins all runs share, the result is
unchanged: Δ RMSE +0.86 ± 0.63 (48 h) and +0.97 ± 0.13 (72 h). Source: `s1_matched_origins.csv`.

**Per province** (Δ RMSE vs 24 h):

| Province | 48 h | 72 h |
|---|---|---|
| Ankara | −0.04 ± 1.63 | +1.56 ± 1.87 |
| Antalya | +1.20 ± 0.87 | +0.20 ± 0.52 |
| Konya | +0.27 ± 0.39 | −0.05 ± 0.98 |
| Rize | +2.30 ± 2.02 | +1.49 ± 2.62 |
| Van | +0.86 ± 0.42 | +2.29 ± 1.10 |

Source: `s1_by_province.csv`.

- No province gains from longer history. The only negative values (Ankara 48 h, Konya 72 h) are
  under 0.1 W/m², far inside seed noise.
- This agrees with the training-dynamics diagnosis that more history adds little at this
  horizon. Day-to-day cloudiness memory is about 3 days (`TUNING_PLAN.md`), but a 24 h window
  apparently already holds what the network can use of it.

**Early stopping.** With patience 5 or 7, none of the 9 networks would have kept a different
epoch. With patience 3, one would (24 h, seed 42, whose best epoch was 10). Source:
`s1_patience.csv`.

## S2: LSTM width × depth (final, decided 2026-10-30)

**Decision: 256 × 1** (one LSTM layer of width 256, head of width 128). It beats the 64 × 2
incumbent by 9.51 ± 0.71 W/m² and the runner-up 128 × 1 by 1.61 ± 0.59 W/m², the latter on every
seed. Both gains pass the decision rule. The grid was 3 widths × 3 depths. Because 128 × 1 won at
its widest, shallowest corner, one more width (256 × 1) was added at the winning depth. Depth was
not extended: 1 layer is best at every width. The head is always one hidden layer of half the
LSTM width.

| Width × depth | val RMSE | Δ RMSE | val MAE | val CRPS | Δ CRPS | val CP | val PINW | Mean best epoch | Train min/network |
|---|---|---|---|---|---|---|---|---|---|
| **256 × 1** | **90.96** | **−9.51 ± 0.71** | **63.49** | **47.88** | −7.27 ± 0.60 | 0.777 | 0.184 | 3.7 | 7.6 |
| 128 × 1 | 92.57 | −7.89 ± 0.13 | 67.58 | 49.55 | −5.59 ± 0.38 | 0.809 | 0.236 | 5.7 | 3.7 |
| 64 × 1 | 95.10 | −5.37 ± 1.04 | 72.71 | 51.50 | −3.64 ± 0.57 | 0.875 | 0.306 | 13.7 | 3.7 |
| 128 × 2 | 96.05 | −4.42 ± 1.02 | 70.68 | 51.57 | −3.58 ± 0.30 | 0.836 | 0.248 | 3.0 | 6.0 |
| 128 × 3 | 96.58 | −3.88 ± 0.35 | 71.39 | 51.84 | −3.31 ± 0.43 | 0.849 | 0.251 | 1.7 | 8.2 |
| 64 × 2 (incumbent) | 100.47 | 0 | 78.03 | 55.14 | 0 | 0.879 | 0.321 | 5.3 | 4.1 |
| 64 × 3 | 101.54 | +1.07 ± 0.59 | 79.03 | 55.97 | +0.83 ± 0.46 | 0.871 | 0.322 | 3.7 | 4.7 |
| 32 × 1 | 105.19 | +4.73 ± 0.40 | 84.42 | 58.36 | +3.21 ± 0.72 | 0.893 | 0.380 | 29.3 | 4.8 |
| 32 × 2 | 112.45 | +11.98 ± 1.24 | 91.52 | 63.21 | +8.06 ± 0.68 | 0.887 | 0.400 | 10.7 | 3.7 |
| 32 × 3 | 114.92 | +14.45 ± 1.72 | 93.44 | 64.52 | +9.38 ± 1.42 | 0.877 | 0.397 | 8.3 | 4.3 |

Sources: `s2_summary.csv`, `s2_matched_origins.csv` (Δ CRPS). Every arm has the same lookback, so
all are scored on the same 1,400 origins, and the matched table equals the summary. The 256 × 1
runs trained alone, the others possibly two at a time (sharded), so training times are only
roughly comparable.

**256 × 1 against 128 × 1, seed by seed** (from the ledger rows behind `s2_summary.csv`):

| Seed | Δ val RMSE | Δ val CRPS | Δ val CP |
|---|---|---|---|
| 42 | −0.94 | −2.48 | −0.013 |
| 43 | −1.86 | −0.81 | −0.057 |
| 44 | −2.04 | −1.74 | −0.026 |
| mean ± sd | −1.61 ± 0.59 | −1.67 ± 0.84 | −0.032 ± 0.023 |

**Per province** (Δ RMSE vs 64 × 2):

| Province | 256 × 1 | 128 × 1 | 64 × 1 | 128 × 2 |
|---|---|---|---|---|
| Ankara | −9.15 ± 2.17 | −7.37 ± 1.47 | −5.68 ± 2.12 | −4.25 ± 0.42 |
| Antalya | −11.95 ± 0.97 | −9.29 ± 0.73 | −5.58 ± 0.81 | −5.92 ± 1.79 |
| Konya | −11.28 ± 0.68 | −9.16 ± 0.27 | −5.11 ± 1.40 | −5.60 ± 1.09 |
| Rize | −6.83 ± 0.46 | −6.45 ± 1.14 | −5.66 ± 0.41 | −2.39 ± 4.59 |
| Van | −8.98 ± 1.39 | −7.55 ± 1.58 | −4.80 ± 1.19 | −4.38 ± 1.48 |

Source: `s2_by_province.csv`.

- **Width helps every province, but not equally.** From 128 to 256, Antalya and Konya gain a
  further 2.1 to 2.7 W/m², and Ankara and Van 1.4 to 1.8. Rize gains 0.4 in RMSE and its CRPS gets
  slightly worse (57.56 → 57.77).
- Rize, the cloudiest and hardest site, has nearly stopped improving with capacity: its gain at
  64 × 1 is already −5.66. Extra width mostly sharpens the forecast where the sky is more often
  predictable. For the paper's cross-province claim this is a per-site pattern worth reporting.
- **Width helps at every depth, and 1 layer is best at every width.** That includes 32, where
  3 layers cost 9.7 W/m² over 1 layer.

**Why the width search stops at 256, although 256 is again the edge of the grid.**
- The returns are diminishing: each doubling gained 10.1, then 2.5, then 1.6 W/m² (32 → 64 →
  128 → 256, at 1 layer).
- The cost is not: each doubling of width doubles the time per network (3.7 → 7.6 min). The
  remaining stages and the ablations all train ensembles of 8 to 16 networks per run, so 512
  would roughly double the entire remaining programme again for an expected gain of about
  1 W/m² or less.
- The paper should therefore state the width as **compute-bounded**: the best of the widths
  tried, with a possible small further gain beyond it. It should not claim an optimum.

**Depth is confounded with dropout.** PyTorch's `nn.LSTM` applies dropout between stacked layers
only when there are at least 2 (`model.py`). At `dropout_rate = 0.3`:
- a 1-layer model has dropout only in the head;
- 2 and 3 layers add 1 and 2 dropout masks inside the recurrent stack.

So the S2 depth result reads "deeper, with 0.3 dropout between the layers, is worse", not "depth
is worse". The paper should state it that way. A consequence for S3: at 1 layer the dropout-rate
sweep tunes the head's dropout only.

**Coverage falls as the model improves.** From 64 × 2 to 256 × 1, CP drops from 0.879 to 0.777
and PINW narrows from 0.321 to 0.184. Rize falls to 0.67.
- At 1 layer, the head is the only source of MC-Dropout randomness. The network gets more
  accurate, but its stochastic layer does not grow with it.
- CRPS still improves by 7.3 W/m², so as a forecast distribution the wider model is better
  overall. It is too sharp for its accuracy.
- Restoring coverage is the job of the bootstrap ensemble (S4, S5) and the conformal layer, which
  are selected on CRPS.
- This bears directly on the paper's MC-Dropout claim: how much of the final spread comes from
  dropout versus the bootstrap is measured in S5.

**Early stopping.** The chosen width peaks early (best epochs 7, 2 and 2), and with patience 3,
5 or 7 none of the 256-wide or 128-wide networks would have kept a different epoch. Small
networks peak late (32 × 1: best epoch up to 33; 64 × 1: 13.7 on average). Across S2, patience 5
would have changed 8 of 30 networks, all of them 32- or 64-wide. Source: `s2_patience.csv`.

## Carried forward

- **Patience** (decided before S4): a patience of 5 is not safe in general (S2), only for wide
  networks. At 256 × 1 no network has changed yet. It may be lowered for the frozen architecture
  only if the S3 arms (especially the lower learning rate, which may peak later) also show no
  change at patience 5.
- **Cost.** At 256 × 1 a network takes about 7.6 min on MPS, twice the 128 × 1 time on which the
  remaining-stage estimates in `TUNING_PLAN.md` were based.
- **MC-Dropout spread at 1 layer** (S2) and the smoke-run gap between MC-averaged and
  dropout-off predictions (`TUNING_PLAN.md`) are both measured on fully trained weights by the
  S5 ensemble curves.
