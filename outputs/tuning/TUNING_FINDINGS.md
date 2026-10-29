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
| S2 | LSTM width × depth | 64 × 2 | 128 × 1 leads | −7.89 ± 0.13 | provisional: 256 × 1 pending |

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

## S2: LSTM width × depth (provisional)

**Provisional.** 128 × 1 passes the decision rule by a wide margin. It sits at the widest,
shallowest corner of the grid, so one more width (256 × 1, 3 seeds) is being trained before
the decision. Depth is not extended, since 1 layer is best at every width. The head is always
one hidden layer of half the LSTM width.

| Width × depth | val RMSE | Δ RMSE | val MAE | val CRPS | Δ CRPS | val CP | val PINW | Mean best epoch |
|---|---|---|---|---|---|---|---|---|
| **128 × 1** | **92.57** | **−7.89 ± 0.13** | **67.58** | **49.55** | −5.59 ± 0.38 | 0.809 | 0.236 | 5.7 |
| 64 × 1 | 95.10 | −5.37 ± 1.04 | 72.71 | 51.50 | −3.64 ± 0.57 | 0.875 | 0.306 | 13.7 |
| 128 × 2 | 96.05 | −4.42 ± 1.02 | 70.68 | 51.57 | −3.58 ± 0.30 | 0.836 | 0.248 | 3.0 |
| 128 × 3 | 96.58 | −3.88 ± 0.35 | 71.39 | 51.84 | −3.31 ± 0.43 | 0.849 | 0.251 | 1.7 |
| 64 × 2 (incumbent) | 100.47 | 0 | 78.03 | 55.14 | 0 | 0.879 | 0.321 | 5.3 |
| 64 × 3 | 101.54 | +1.07 ± 0.59 | 79.03 | 55.97 | +0.83 ± 0.46 | 0.871 | 0.322 | 3.7 |
| 32 × 1 | 105.19 | +4.73 ± 0.40 | 84.42 | 58.36 | +3.21 ± 0.72 | 0.893 | 0.380 | 29.3 |
| 32 × 2 | 112.45 | +11.98 ± 1.24 | 91.52 | 63.21 | +8.06 ± 0.68 | 0.887 | 0.400 | 10.7 |
| 32 × 3 | 114.92 | +14.45 ± 1.72 | 93.44 | 64.52 | +9.38 ± 1.42 | 0.877 | 0.397 | 8.3 |

Sources: `s2_summary.csv`, `s2_matched_origins.csv` (Δ CRPS). Every arm has the same lookback, so
all are scored on the same 1,400 origins, and the matched table equals the summary.

**Per province** (Δ RMSE vs 64 × 2, the three leading arms):

| Province | 128 × 1 | 64 × 1 | 128 × 2 |
|---|---|---|---|
| Ankara | −7.37 ± 1.47 | −5.68 ± 2.12 | −4.25 ± 0.42 |
| Antalya | −9.29 ± 0.73 | −5.58 ± 0.81 | −5.92 ± 1.79 |
| Konya | −9.16 ± 0.27 | −5.11 ± 1.40 | −5.60 ± 1.09 |
| Rize | −6.45 ± 1.14 | −5.66 ± 0.41 | −2.39 ± 4.59 |
| Van | −7.55 ± 1.58 | −4.80 ± 1.19 | −4.38 ± 1.48 |

Source: `s2_by_province.csv`.

- **The gain is general.** 128 × 1 improves every province by 6.5 to 9.3 W/m², each well beyond
  its seed sd. CRPS improves in every province too.
- **Rize gains least from width.** Its gain at 128 × 1 is −6.45, against −5.66 already at
  64 × 1, and its coverage is the lowest of any province (0.72 at 128 × 1). It remains the hardest
  site.
- **Width helps at every depth, and 1 layer is best at every width.** That includes 32, where
  3 layers cost 9.7 W/m² over 1 layer.

**Depth is confounded with dropout.** PyTorch's `nn.LSTM` applies dropout between stacked layers
only when there are at least 2 (`model.py`). At `dropout_rate = 0.3`:
- a 1-layer model has dropout only in the head;
- 2 and 3 layers add 1 and 2 dropout masks inside the recurrent stack.

So the S2 depth result reads "deeper, with 0.3 dropout between the layers, is worse", not "depth
is worse". The paper should state it that way. A consequence for S3: at 1 layer the dropout-rate
sweep tunes the head's dropout only.

**Coverage falls as the model improves.** CP drops from 0.879 (64 × 2) to 0.809 (128 × 1) while
PINW narrows from 0.321 to 0.236.
- At 1 layer, the head is the only source of MC-Dropout randomness, so a more accurate network
  also has a thinner stochastic layer.
- CRPS still improves by 5.6 W/m², so as a forecast distribution the wider model is better
  overall. It is too sharp for its accuracy.
- Restoring coverage is the job of the bootstrap ensemble (S4, S5) and the conformal layer, which
  are selected on CRPS.
- This bears directly on the paper's MC-Dropout claim: how much of the final spread comes from
  dropout versus the bootstrap is measured in S5.

**Early stopping.** Small networks peak late (32 × 1: best epoch up to 33; 64 × 1: 13.7 on
average). With patience 5, 8 of the 27 S2 networks would have kept a different epoch, all of
them 32- or 64-wide. No 128-wide network would. Source: `s2_patience.csv`.

## Carried forward

- **Patience** (decided before S4): a patience of 5 is not safe in general (S2), only for wide
  networks. It may be lowered for the frozen architecture only if the S3 arms (especially the
  lower learning rate, which may peak later) also show no change at patience 5.
- **MC-Dropout spread at 1 layer** (S2) and the smoke-run gap between MC-averaged and
  dropout-off predictions (`TUNING_PLAN.md`) are both measured on fully trained weights by the
  S5 ensemble curves.
