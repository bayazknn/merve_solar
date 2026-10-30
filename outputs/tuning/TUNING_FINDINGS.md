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
| S3 | dropout rate | 0.3 | **0.2** | −1.33 ± 0.36 | final |
| S3 | learning rate | 1e-3 | 5e-4 passes the rule marginally | −0.99 ± 0.96 | **provisional** (see below) |
| — | early-stopping patience, S4 on | 10 | **5** | n/a (no network changes) | final |

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

## S3: dropout rate (final, decided 2026-10-30)

**Decision: dropout 0.2.** It beats the 0.3 incumbent by 1.33 ± 0.36 W/m² on every seed (−1.68,
−1.33, −0.97), which passes the decision rule. All arms are 256 × 1 at learning rate 1e-3; the 0.3
arm is the S2 winner, reused. At 1 layer the rate applies to the head only (see S2).

| Dropout | val RMSE | Δ RMSE | val MAE | val CRPS | Δ CRPS | val CP | val PINW | Mean best epoch | Train min/network |
|---|---|---|---|---|---|---|---|---|---|
| 0.1 | 89.84 | −1.12 ± 0.37 | **61.04** | 49.85 | +1.98 ± 1.06 | 0.565 | 0.102 | 1.3 | 6.0 |
| **0.2** | **89.63** | **−1.33 ± 0.36** | 61.54 | **47.80** | −0.08 ± 0.68 | 0.710 | 0.146 | 2.3 | 6.5 |
| 0.3 (incumbent) | 90.96 | 0 | 63.49 | 47.88 | 0 | 0.777 | 0.184 | 3.7 | 7.6 |
| 0.4 | 91.61 | +0.65 ± 0.89 | 64.94 | 48.23 | +0.36 ± 0.21 | 0.822 | 0.218 | 7.7 | 7.7 |
| 0.5 | 92.74 | +1.78 ± 1.61 | 67.64 | 49.64 | +1.76 ± 0.09 | 0.846 | 0.255 | 8.0 | 8.0 |

Sources: `s3_dropout_summary.csv`, `s3_dropout_matched_origins.csv` (Δ CRPS). All arms share the
lookback, so all are scored on the same 1,400 origins.

**Per province** (Δ RMSE vs 0.3):

| Province | 0.1 | 0.2 | 0.4 | 0.5 |
|---|---|---|---|---|
| Ankara | −1.93 ± 1.25 | −1.80 ± 1.56 | +0.45 ± 1.98 | +2.12 ± 2.83 |
| Antalya | −0.94 ± 0.39 | −0.80 ± 0.52 | +1.06 ± 0.50 | +2.73 ± 0.07 |
| Konya | −0.64 ± 0.12 | −1.49 ± 0.91 | +1.47 ± 1.93 | +2.16 ± 0.84 |
| Rize | −1.55 ± 0.95 | −1.50 ± 0.66 | −0.42 ± 1.07 | +0.06 ± 4.31 |
| Van | −0.44 ± 0.86 | −1.00 ± 0.46 | +0.90 ± 1.77 | +2.16 ± 1.69 |

Source: `s3_dropout_by_province.csv`.

- **The gain is broad.** 0.2 is better than 0.3 in every province, by 0.8 to 1.8 W/m².
- **The optimum is inside the grid.** 0.1 and 0.2 are tied on RMSE (0.2 − 0.1 = −0.21 ± 0.56,
  seed-paired), so the grid does not need extending downwards.
- **0.2 costs nothing in CRPS; 0.1 does.** At 0.2, CRPS is unchanged (−0.08 ± 0.68). At 0.1 it is
  2.0 W/m² worse, because the MC-Dropout spread collapses (CP 0.57, PINW 0.10). Between the two
  RMSE-tied arms, the proper score separates them, and it agrees with the RMSE ranking. The concern
  in `TUNING_PLAN.md` (Interactions) that a B=1 CRPS choice would favour too much dropout does not
  bite here: CRPS is flat from 0.2 to 0.4.
- **Rize is the exception at high dropout.** It is the only province where 0.4 and 0.5 do not
  lose RMSE, and its CRPS improves there (−1.34 and −0.92). The cloudiest site benefits from a
  wider spread; elsewhere the extra spread is paid for in accuracy.

**Regularisation delays the optimum but does not improve it.** The mean best epoch rises with
dropout (1.3 → 2.3 → 3.7 → 7.7 → 8.0), while val RMSE gets steadily worse above 0.2. This is the
prediction of the training-dynamics diagnosis: the early peak is not overfitting that more
dropout would cure. The paper can state it with these numbers.

**Coverage keeps falling.** At B=1, val CP drops from 0.777 to 0.710 and PINW from 0.184 to
0.146. Rize falls to 0.59. A lower dropout rate shrinks the only source of MC-Dropout randomness
at 1 layer, so in the final model the bootstrap ensemble (S4, S5) and the conformal layer carry
even more of the calibration. How much of the final spread is dropout's is measured in S5.

## S3: learning rate (provisional)

**Status: 5e-4 passes the decision rule by 0.03 W/m², and the evidence behind it is weak. Not yet
recorded in `DECISIONS`.** All arms are 256 × 1 at dropout 0.3; the 1e-3 arm is the S2 winner,
reused.

| Learning rate | val RMSE | Δ RMSE | val MAE | val CRPS | Δ CRPS | val CP | val PINW | Mean best epoch | Train min/network |
|---|---|---|---|---|---|---|---|---|---|
| **5e-4** | **89.97** | −0.99 ± 0.96 | 63.87 | 47.93 | +0.05 ± 0.17 | 0.775 | 0.181 | 4.0 | 7.0 |
| 1e-3 (incumbent) | 90.96 | 0 | **63.49** | **47.88** | 0 | 0.777 | 0.184 | 3.7 | 7.6 |
| 2e-3 | 90.91 | −0.05 ± 0.34 | 63.77 | 48.09 | +0.21 ± 0.33 | 0.774 | 0.181 | 3.7 | 6.7 |

Sources: `s3_lr_summary.csv`, `s3_lr_matched_origins.csv` (Δ CRPS).

**Per province** (Δ RMSE vs 1e-3):

| Province | 5e-4 | 2e-3 |
|---|---|---|
| Ankara | −1.44 ± 2.12 | +0.05 ± 1.05 |
| Antalya | +0.00 ± 0.40 | +0.18 ± 0.58 |
| Konya | −0.38 ± 0.99 | −0.21 ± 0.97 |
| Rize | −2.44 ± 1.61 | −0.54 ± 0.97 |
| Van | −0.41 ± 0.31 | +0.36 ± 0.50 |
| All but Rize | −0.57 ± 0.78 | +0.10 ± 0.72 |

Source: `s3_lr_by_province.csv`.

Why the marginal pass is not convincing:
- **One seed carries it.** The paired gains are −2.06, −0.17 and −0.75 W/m². The largest comes
  from seed 42, which is the incumbent's worst seed (91.75, against 90.32 and 90.81).
- **One province carries it.** Without Rize the gain is −0.57 ± 0.78, which fails the rule.
- **No gain as a distribution.** Val MAE is slightly worse (+0.39) and CRPS is unchanged
  (+0.05 ± 0.17).
- **It was measured at dropout 0.3, not at the chosen 0.2.** The two axes were moved one at a
  time, and the plan relied on S4 to check the combination. S4 cannot do that: every S4 arm
  carries both values, so there is no arm to compare against.
- 5e-4 does not peak later (mean best epoch 4.0, max 5), so the hoped-for finer early-stopping
  resolution did not materialise either.

**Recommendation: settle it with one combined arm before S4.** Train dropout 0.2 with learning
rate 5e-4 at the S3 fidelity (B=1, patience 10, seeds 42 to 44; 3 runs, about 20 min on MPS) and
compare it, seed-paired, with the existing dropout-0.2 arm at 1e-3 under the same decision rule.
This tests the configuration that would actually be frozen, and costs about 3% of S4. If the
user prefers to apply the rule as written, 5e-4 is recorded and S4 runs on (0.2, 5e-4).

## Early-stopping patience (decided 2026-10-30)

**Decision: patience 5 from S4 on**, for the frozen 256 × 1 architecture. S1 to S3 keep 10.

| Stage | Networks | Changed at patience 3 | Changed at 5 | Changed at 7 |
|---|---|---|---|---|
| S1 (64 × 2, three lookbacks) | 9 | 1 | 0 | 0 |
| S2, 32 and 64 wide (64 × 2 reused from S1) | 18 | 10 | 8 | 5 |
| S2, 128 and 256 wide | 12 | 0 | 0 | 0 |
| S3 (all 256 × 1) | 15 new | 3 (dropout 0.4, 0.5; lr 2e-3) | 0 | 0 |
| **256 × 1 in S2 and S3** | **18** | **3** | **0** | **0** |

Sources: `s1_patience.csv`, `s2_patience.csv`, `s3_dropout_patience.csv`, `s3_lr_patience.csv`.

- At the chosen width no network, at any dropout rate or learning rate tried, would have kept a
  different epoch at patience 5. The longest wait for a new best was 4 epochs (lr 2e-3); in the
  arms that can still be chosen (dropout 0.2, lr 5e-4 or 1e-3) it was 1.
- The rule in `TUNING_PLAN.md` asked for zero changes "at patience 5 or 7"; for 256-wide networks
  that holds. For narrow networks it does not, so the lower patience is tied to this architecture
  and an ablation that changes width must restore 10.
- Effect: a dropout-0.2 network trained 13.3 epochs on average at patience 10. At patience 5 that
  is about 8, so S4 and later stages cost roughly 40% less.
- What it gives up: S4 onward train bootstrap replicas, whose validation curves have not been
  observed. A later stage can still detect a too-short patience only down to 3 (its report
  re-evaluates the history it has), not whether 10 would have found a later epoch.

## Carried forward

- **Patience** is 5 from S4 on (above). Ablations that change the architecture's width restore 10.
- **Cost.** At 256 × 1 a network takes about 6.5 min on MPS at dropout 0.2, at patience 10.
- **MC-Dropout spread at 1 layer** (S2) and the smoke-run gap between MC-averaged and
  dropout-off predictions (`TUNING_PLAN.md`) are both measured on fully trained weights by the
  S5 ensemble curves.
