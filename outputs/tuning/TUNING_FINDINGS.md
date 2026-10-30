# Tuning findings

What each tuning stage found and decided. `TUNING_PLAN.md` holds the design (grids, order,
decision rule) and the session status. This file holds the results.

**How to read this file:**
- A stage section is written once, when its decision is recorded in
  `configs/experiment_grid.py::DECISIONS`. After that its numbers and decision are not edited. A
  section marked **provisional** is still waiting for runs. The **Reading the metrics** notes at
  the end of each section were added on 2026-10-30: they explain the tables and change no number
  or decision.
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
  CRPS describe one network's MC-Dropout spread, not the final ensemble's. S4 on trains the
  B=8 moving-block bootstrap ensemble and is judged on val CRPS.

## The metrics

Every table reports the same handful of metrics. Two of them score the **point forecast** (the
mean of all the samples), three score the **predictive distribution** (all the samples together,
which is what the uncertainty layer produces).

**What is being scored.** For every daylight hour the model produces not one forecast but a
cloud of samples: B networks × T MC-Dropout passes (for example 6 × 100 = 600 samples). Their
mean is the point forecast. Their 2.5th and 97.5th percentiles are the lower and upper ends of
the 95% prediction interval. Night hours are left out of every number here.

| Metric | What it measures | Unit | Better | Typical value here (MC-Dropout rows) |
|---|---|---|---|---|
| **RMSE** | Typical size of the point-forecast error; large errors (cloud ramps) weigh more | W/m² | lower | 88 to 115 |
| **MAE** | Average size of the point-forecast error; every error weighs the same | W/m² | lower | 61 to 94 |
| **CRPS** | Quality of the whole predictive distribution: accuracy and spread together | W/m² | lower | 46 to 65 |
| **CP** | Share of observations that fall inside the 95% interval | fraction | close to **0.95** | 0.57 to 0.89 |
| **PINW** | Average width of the 95% interval, divided by the range of the observations | fraction | lower, *but only if CP holds* | 0.10 to 0.40 |

**CRPS (Continuous Ranked Probability Score)** is the main criterion for anything about
uncertainty. It asks how far the forecast distribution is from the observed value, on average:

> CRPS = E|X − y| − ½ E|X − X′|, where X and X′ are two samples from the forecast and y is the
> observation.

- It is in W/m², like MAE, and for a forecast with no spread at all it **equals the MAE**. So
  MAE − CRPS is what the spread adds. At the frozen configuration MAE is about 61 and CRPS about
  46: the distribution is worth about 15 W/m² over its own mean.
- It punishes **both** failure modes. A distribution that is too narrow misses the observation
  (the first term grows); one that is too wide pays for its own spread (only half of it is given
  back by the second term). The best CRPS comes from a distribution that is as narrow as it can
  be while still honest about its errors.
- It is a *proper* score: no forecaster can improve it by reporting something other than what it
  actually believes. That is why it can referee between a sharper and a wider forecast, which CP
  and PINW cannot do on their own.

**CP (Coverage Probability)** is the share of daylight observations inside the 95% interval.
- The target is 0.95. **Below 0.95 means the intervals are too narrow** (the model is
  overconfident); above means too wide.
- Everywhere in these tables CP is below 0.95. That is expected: the samples only describe the
  uncertainty of the *model* (which networks, which dropout masks), not the irreducible
  hour-to-hour variability of clouds around even a perfect mean. The conformal layer is meant to
  correct this after tuning (`TUNING_PLAN.md`), so during tuning CP is reported but not
  optimised.
- CP alone is easy to game: an absurdly wide interval covers everything. Always read it next to
  PINW and CRPS.

**PINW (Prediction Interval Normalised Width)** is the average interval width (MPIW, in W/m²)
divided by the range of the observed values (max − min) in the same subset.
- On the validation daylight subset that range is about 1,040 W/m², so **PINW × 1,040 ≈ the
  average interval width in W/m²**. PINW 0.17 is an interval about 180 W/m² wide; PINW 0.32 is
  about 335 W/m².
- Narrower is better only at the same coverage. A narrower interval with lower CP is not an
  improvement in itself; CRPS decides whether the trade was worth it.

**How the three fit together.** Read a row in this order:
1. **CRPS**: is the forecast distribution better overall?
2. **CP**: are the intervals too narrow or too wide, and by how much?
3. **PINW**: how wide are they?
4. **RMSE / MAE**: is the centre of the distribution more accurate?

Typical patterns in the tables below:

| Pattern | Meaning |
|---|---|
| RMSE ↓, CRPS ↓, CP ≈ same | A genuinely better model. |
| RMSE ↓, CRPS ↓, CP ↓, PINW ↓ | More accurate, and sharper than it has earned; the conformal layer will widen it back. |
| RMSE ≈, CRPS ↑, CP ↓↓ | The spread collapsed: the intervals became overconfident. |
| RMSE ↑, CRPS ↑, CP ↑, PINW ↑ | Coverage bought by blurring the forecast. |

**Other columns.**
- **Δ** and **± sd**: the change against the stage's incumbent on the same seed, averaged over 3
  seeds, and how much that change varied between seeds. A Δ smaller than its sd is noise.
- **Mean best epoch**: the training epoch (counted from 0) whose weights were kept, by
  validation loss.
- **Train min/network**: wall-clock training time per network on the Mac mini (MPS).
- **B** and **T**: number of bootstrap networks and of MC-Dropout passes per network.

**Fidelity matters for comparisons.** S1 to S3 used one network (B=1), so their CP, PINW and
CRPS describe one network's dropout spread. S4 and S5 used ensembles (B=6 to 16), whose spread
is wider. Compare CP and CRPS only within a stage, or across stages of the same B.

## Decisions so far

| Stage | Axis | Incumbent | Decision | Gain over incumbent (val RMSE) | State |
|---|---|---|---|---|---|
| S1 | lookback | 24 h | **24 h** | 0 (incumbent kept) | final |
| S2 | LSTM width × depth | 64 × 2 | **256 × 1** | −9.51 ± 0.71 | final (width compute-bounded) |
| S3 | dropout rate | 0.3 | **0.2** | −1.33 ± 0.36 | final |
| S3 | learning rate | 1e-3 | **5e-4** | −0.99 ± 0.96 | final (marginal pass, accepted as written) |
| — | early-stopping patience, S4 on | 10 | **5** | n/a (no network changes) | final |
| S4 | bootstrap block length | 168 h | **168 h** | 0 (incumbent kept; criterion val CRPS) | final |
| Conformal | recalibration grid | none | **city_horizon** (recommended, awaiting confirmation) | CRPS −1.81 W/m² vs uncorrected, cross-fitted | provisional |
| S5 | ensemble size B × MC passes T | 8 × 100 | **6 × 100** | +0.24 ± 0.20 val CRPS vs the best cell (16 × 150); B cost-driven, T amended | final |

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

**Reading the metrics.** Every lookback lands within about 1 W/m² of the others: RMSE differs by
at most 1.1 (about 1%) and CRPS by 0.3. CP stays between 0.875 and 0.883, so the intervals behave
the same at every lookback. Nothing moves enough to matter, and the decision is "no evidence to
change", not "24 h is clearly best". This stage used one network (B=1), so CP 0.88 describes one
network's dropout spread only.

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

**Reading the metrics.** This is the stage where the metrics pull in different directions.
- **Accuracy:** RMSE falls by 9.5 W/m² (about 10%) and CRPS by 7.3 from 64 × 2 to 256 × 1: a
  genuinely better model.
- **Intervals:** at the same time PINW falls from 0.321 to 0.184, so the interval shrinks from
  about 335 to about 190 W/m² wide (−43%), while the error shrinks by only about 10%. The
  intervals have narrowed much faster than the errors, which is why CP falls from 0.88 to 0.78:
  the wider model is more confident than its accuracy justifies.
- **Verdict:** CRPS still improves, so the net trade is good. The lost coverage is a calibration
  problem for the ensemble and the conformal layer, not a reason to keep the smaller model.
- Small, deep networks (32 × 2, 32 × 3) show the opposite: high CP (0.88 to 0.89) with wide intervals
  (PINW 0.40) and the worst RMSE and CRPS. They are covered by being blurred, not by being right.

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

**Reading the metrics.** Dropout 0.1 is the textbook case of why CRPS is the referee.
- **0.1 against 0.2:** RMSE is essentially the same (89.84 against 89.63), but CRPS is 2 W/m²
  worse, because the interval collapses to about 105 W/m² wide (PINW 0.102) and covers only 57% of
  the observations. On RMSE alone 0.1 looks as good as 0.2; as a forecast distribution it is
  clearly worse.
- **0.4 and 0.5:** the opposite failure. Intervals widen (PINW 0.22 to 0.26) and CP rises to
  0.82 to 0.85, but RMSE and CRPS both get worse. Coverage is bought by blurring the forecast.
- **0.2:** best RMSE, and CRPS no worse than the incumbent's. Its intervals are sharper (about
  150 W/m²) and cover 71%, so it relies even more on the later calibration.

## S3: learning rate (final, decided 2026-10-30)

**Decision: 5e-4, by the decision rule as written.** It passes by 0.03 W/m², and the evidence
behind it is weak (below). All arms are 256 × 1 at dropout 0.3; the 1e-3 arm is the S2 winner,
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

A 3-run combined arm (dropout 0.2 × learning rate 5e-4 at B=1, against dropout 0.2 at 1e-3) was
considered and not run: the pre-registered rule was applied as written. Consequences for the
paper:
- The frozen pair (dropout 0.2, learning rate 5e-4) was never trained against its single-axis
  neighbours at the same fidelity, so the manuscript should describe the two values as chosen
  one axis at a time, not jointly.
- The learning rate is the least supported tuning choice so far. A learning-rate arm (1e-3 on
  the frozen configuration) is a candidate for the ablation programme if a reviewer asks.

**Reading the metrics.** The learning rate leaves the distribution untouched: CP (0.774 to 0.777)
and PINW (0.181 to 0.184) are identical across the three arms, and CRPS differs by at most 0.2,
inside the noise. Only RMSE moves, by 1 W/m², and that difference is carried by one seed and one
province. All of these arms are B=1, at dropout 0.3.

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

## S4: bootstrap block length (final, decided 2026-10-30)

**Decision: keep 168 h.** The four block lengths are indistinguishable: the best arm (240 h)
gains 0.15 ± 0.18 W/m² in CRPS, inside its seed sd, so the decision rule keeps the incumbent.
Every arm is the frozen network (256 × 1, dropout 0.2, learning rate 5e-4, patience 5) at B=8,
T=100, so these are the first ensemble-fidelity tuning numbers.

| Block (h) | Extra days beyond the 48 h window span | val CRPS | Δ CRPS | val RMSE | Δ RMSE | val MAE | val CP | val PINW | Mean best epoch | Min/run |
|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 3 | 46.17 | −0.01 ± 0.37 | 88.41 | +0.03 ± 0.13 | 61.57 | 0.796 | 0.173 | 1.7 | 41.3 |
| **168 (incumbent)** | 5 | 46.18 | 0 | 88.39 | 0 | 61.65 | 0.797 | 0.173 | 1.6 | 41.8 |
| 240 | 8 | **46.03** | −0.15 ± 0.18 | **88.22** | −0.16 ± 0.21 | **61.34** | 0.797 | 0.174 | 1.7 | 41.5 |
| 336 | 12 | 46.08 | −0.10 ± 0.25 | 88.46 | +0.07 ± 0.16 | 61.42 | 0.800 | 0.175 | 1.7 | 41.6 |

Sources: `s4_summary.csv`, `s4_matched_origins.csv`. All arms are scored on the same 1,400
origins. Runs trained two at a time (two shards), so the minutes per run (8 networks) are
inflated and only comparable within S4.

**Per province** (Δ CRPS vs 168 h):

| Province | 120 h | 240 h | 336 h | val CP at 168 h |
|---|---|---|---|---|
| Ankara | −0.00 ± 0.13 | −0.26 ± 0.27 | +0.10 ± 0.31 | 0.780 |
| Antalya | +0.00 ± 0.66 | −0.33 ± 0.20 | −0.26 ± 0.72 | 0.852 |
| Konya | −0.20 ± 0.57 | −0.22 ± 0.40 | −0.17 ± 0.62 | 0.817 |
| Rize | +0.13 ± 0.36 | +0.20 ± 0.34 | +0.04 ± 0.29 | 0.700 |
| Van | +0.01 ± 0.54 | −0.12 ± 0.35 | −0.22 ± 0.10 | 0.838 |

Source: `s4_by_province.csv`.

- **The result is insensitive to block length over 120 to 336 h.** The largest mean difference
  is 0.15 W/m² in CRPS (0.3%) and 0.16 in RMSE; CP and PINW move by under 0.004. With seed sds of
  0.2 to 0.4, an effect larger than about 0.4 W/m² would have been visible, so the paper can state
  that the block length within the dependence-respecting range does not matter, rather than claim
  an optimum.
- **No province prefers a different block.** Every per-province difference is within its seed sd.
- **A plausible reason** (an interpretation, not tested): with about 130 to 375 distinct blocks per
  province (roughly 45,000 training windows over 336 to 120 h), every block length yields equally diverse resamples, and each
  network trains for under 2 epochs before its best, so most of the between-replica spread comes
  from initialisation and data order, not from how the resample is cut. S5 and the
  seed-ensemble ablation (`bootstrap_resample=False`) measure how much the resampling itself adds.

**What the ensemble adds over one network.** The nearest B=1 arm is S3's dropout 0.2 at learning
rate 1e-3 (the combination 0.2 / 5e-4 was never trained at B=1, so this is indicative only):

| | val CRPS | val RMSE | val CP | val PINW |
|---|---|---|---|---|
| B=1, dropout 0.2, lr 1e-3 (S3) | 47.80 | 89.63 | 0.710 | 0.146 |
| B=8, dropout 0.2, lr 5e-4, 168 h (S4) | 46.18 | 88.39 | 0.797 | 0.173 |

- The ensemble raises CP by about 0.09 and widens PINW by about 18%, but daylight coverage at
  B=8 is still 0.80, against a nominal 0.95. Rize is at 0.70.
- **Raw intervals will not reach nominal coverage through B alone.** The pooled distribution has
  no aleatoric term, and the spread that bootstrap plus MC-Dropout adds is much smaller than the
  error. Calibration has to come from the conformal layer. This matters for the paper: the
  conformal layer should be presented as a necessary part of the method, not an optional extra,
  and the ablation should show raw against recalibrated coverage.

**Early stopping at patience 5 is safe for the ensemble.** All 96 networks (8 per run, 12 runs)
kept their best epoch at 1 to 3 (mean 1.7) and stopped after 7 to 9 epochs. The longest wait for
a new best was 2 epochs, and patience 3 would have changed none of them. Source:
`s4_patience.csv`. Bootstrap replicas peak no later than single networks.

**The optimum keeps moving earlier.** Mean best epoch was 3.7 at 256 × 1 / dropout 0.3 / lr 1e-3
(S2), 2.3 at dropout 0.2 (S3), and is 1.7 here. Each choice that improved validation accuracy
also brought the peak forward. With about 1,700 steps per epoch, the selected network is
effectively chosen from 2 or 3 checkpoints. This is the epoch-selection coarseness noted in the
training-dynamics findings; the ensemble averages over it, which is consistent with the smaller
seed sd at B=8: val CRPS sd averages 0.15 over the S4 arms, against 0.40 over the seven 256 × 1
arms at B=1 (S2, S3).

**Reading the metrics.** Block length changes nothing measurable. CRPS differs by at most
0.15 W/m² (0.3%), RMSE by 0.2, and CP (0.796 to 0.800) and PINW (0.173 to 0.175) agree to two
decimals: the intervals are about 180 W/m² wide in every arm. These are the first ensemble (B=8)
numbers, so they are not comparable with the B=1 rows of S1 to S3. The comparison table above
shows what the ensemble adds: CP rises from 0.71 to 0.80 and CRPS improves by about 1.6 W/m²,
while the interval widens only from about 150 to about 180 W/m².

## S5: ensemble size and MC passes (final, decided 2026-10-30)

**Decision: B = 6 networks, T = 100 MC-Dropout passes.** B is the pre-registered rule's choice:
the cheapest cell whose mean val CRPS is within one seed sd of the best cell (B=16, T=150)
(`TUNING_PLAN.md`, Grids). The rule's own pick was 6 × 50; T was raised to 100 on 2026-10-30
(see the T bullet below), a documented departure from the rule's tie-break, not from its
tolerance. Every cell is read off one 16-network run per seed (seeds 42 to 44),
using its first B networks and first T passes, so all cells share their networks and are
compared seed by seed. Configuration: 256 × 1, dropout 0.2, learning rate 5e-4, block 168 h,
patience 5.

**Selected cells**, MC-Dropout inference (val, daylight):

| B × T | Draws | val CRPS | Δ CRPS vs 16 × 150 (paired) | val RMSE | val CP | val PINW |
|---|---|---|---|---|---|---|
| 4 × 50 | 200 | 46.36 | +0.48 ± 0.54 | 88.43 | 0.779 | 0.168 |
| 6 × 50 (the rule's pick) | 300 | 46.16 | +0.27 ± 0.20 | 88.37 | 0.790 | 0.171 |
| **6 × 100 (decided)** | 600 | 46.12 | **+0.24 ± 0.20** | 88.35 | 0.794 | 0.172 |
| 8 × 100 (incumbent, = S4) | 800 | 46.17 | +0.28 ± 0.20 | 88.38 | 0.798 | 0.173 |
| 12 × 100 | 1,200 | 45.99 | +0.11 ± 0.17 | 88.23 | 0.804 | 0.175 |
| 16 × 100 | 1,600 | 45.89 | +0.01 ± 0.00 | 88.17 | 0.808 | 0.177 |
| 16 × 150 (best) | 2,400 | 45.89 | 0 | 88.17 | 0.809 | 0.177 |

Source: `s5_summary.csv` (every cell, both inference modes). The paired differences are
computed from the three runs' `ensemble_curves.csv`.

**Per seed, val CRPS at T = 100:**

| Seed | B=4 | 6 | 8 | 10 | 12 | 14 | 16 |
|---|---|---|---|---|---|---|---|
| 42 | 45.78 | 45.99 | 46.11 | 46.02 | 46.05 | 46.11 | 45.97 |
| 43 | 46.74 | 46.40 | 46.34 | 46.36 | 46.08 | 46.21 | 46.14 |
| 44 | 46.40 | 45.98 | 46.07 | 46.07 | 45.85 | 45.67 | 45.56 |

What the surface shows:
- **B matters little and T barely at all.** From B=4 to B=16 val CRPS improves by about
  0.4 W/m² (1%). From T=50 to T=150 it improves by 0.02 to 0.08, depending on B, on every seed
  (paired sd ≤ 0.004). RMSE moves by under 0.3 over the whole grid.
- **B=6 and B=8 are indistinguishable.** Seed-paired, both cost about 0.27 W/m² against the
  best cell, and B=8 is not better than B=6 on the mean. Below B=12 the curve is not monotone,
  because each seed adds networks in a fixed order and one weak network shows up at every
  larger B. Only from B=12 on is a gain (about 0.15 to 0.25 W/m²) consistent across seeds.
- **The rule trades 0.6% of CRPS for cost.** The selected cell is worse than the best on all
  three seeds (+0.46, +0.30, +0.06), so the cost is real, but at 0.27 W/m² it is small next to the
  between-seed sd of a single run's CRPS (0.15 to 0.30). It also costs 0.019 in raw CP, which the
  conformal layer absorbs.
- **What the rule buys.** Six networks instead of eight cut every remaining training run by a
  quarter: the final reference and every ablation arm. That is why a cost rule was chosen for
  this stage, and why B is not pushed to 16 for a 0.27 W/m² gain.
- **T = 100, not the rule's 50.** The rule sorts cells by B and then T, so within B=6 it took the
  fewest passes. But passes cost only inference, never training, so the cost argument behind the
  rule does not apply to T. The reason for 100 is Monte Carlo stability, not the CRPS gain: 600
  draws per element put about 15 samples beyond each 2.5% interval endpoint instead of about 7,
  so the interval endpoints are estimated more stably. The CRPS gain (0.04 W/m², 46.16 → 46.12)
  is consistent on every seed but too small to justify the change by itself. Inference stays
  cheaper than the previous 8 × 100.
- **The block length was not reopened.** 240 h failed the S4 rule (−0.15 ± 0.18 W/m²), and a
  noise-level gain does not become real by being combined with another change. The 168 h
  block stays.

**MC-Dropout against dropout-off, on identical weights** (val, daylight; MC at T=100 minus the
deterministic ensemble of the same B networks, mean over seeds):

| B | Δ RMSE | Δ bias | Δ CRPS | CP (dropout-off) | CP (MC) | Δ PINW |
|---|---|---|---|---|---|---|
| 4 | +0.06 | +0.46 | −7.14 | 0.229 | 0.784 | +0.125 |
| 6 | +0.06 | +0.48 | −6.48 | 0.276 | 0.794 | +0.119 |
| 8 | +0.06 | +0.49 | −6.21 | 0.302 | 0.798 | +0.114 |
| 16 | +0.05 | +0.51 | −5.52 | 0.373 | 0.808 | +0.104 |

Source: `s5_summary.csv` (rows with `inference_mode` = `deterministic` and `mc_dropout`).

- **The smoke-run concern does not hold.** The 2-epoch smoke run showed the MC average about
  6 W/m² worse in RMSE than dropout-off. On fully trained weights the difference is +0.05 to
  +0.06 W/m² (paired sd ≤ 0.02): real but negligible. MC-Dropout does not cost point accuracy.
- **MC-Dropout supplies most of the predictive spread.** Without it, the bootstrap ensemble alone
  covers 23% to 37% of daylight observations at the nominal 95% level; with it, 78% to 81%. Its
  CRPS is 5.5 to 7.1 W/m² better. The bootstrap still adds spread (dropout-off CP rises from 0.23
  to 0.37 as B grows from 4 to 16), but at this configuration the dropout term is the larger
  of the two. This is the direct measurement the paper's Bootstrap × MC-Dropout claim needs.
- **Neither closes the coverage gap.** The best raw CP anywhere on the grid is 0.81. The pooled
  sample contains epistemic spread only, so the conformal layer is what brings coverage to the
  nominal level. That makes the conformal mode a decision for the frozen configuration, not
  only an ablation (`TUNING_PLAN.md`, Status).

**Early stopping.** All 48 networks kept their best epoch at 1 to 3 and stopped after 7 to 9
epochs. The longest wait for a new best was 1 epoch, and patience 3 would have changed none.
Source: `s5_patience.csv`.

**Cost.** With three runs sharing the GPU, a network took 7.2 to 7.5 min (about 1.9 h per
16-network run), the curves included in the process time.

**Reading the metrics.**
- **Along B and T** every metric moves by very little: CRPS by 0.5 W/m² over the whole grid, CP
  from 0.78 to 0.81, PINW from 0.168 to 0.177 (about 175 to 185 W/m²). Adding networks or passes
  mostly makes the forecast distribution a little smoother, not different.
- **MC-Dropout against dropout-off** is where the numbers move. With dropout switched off, the 6
  networks still agree closely with each other: their interval is only about 60 W/m² wide
  (PINW 0.054) and covers 28% of observations. Switching MC-Dropout on widens it to about
  180 W/m², raises CP to 0.79 and improves CRPS by 6.5 W/m² (about 12%), while the point forecast
  (RMSE) changes by 0.06 W/m². In plain terms: almost all of the forecast's uncertainty comes from
  MC-Dropout, and it costs nothing in accuracy.
- **What is still missing:** at CP 0.79, about one daylight observation in five falls outside a
  95% interval, against one in twenty. That remaining gap is what the conformal layer has to
  close.

## Conformal mode (validation-only check, 2026-10-30; provisional)

**Recommendation: `city_horizon`**, one factor k per province × lead-time step (120 factors).
On held-out validation months it is the best of the four candidates on every criterion: it
corrects coverage per province **and** per step, gives the narrowest intervals of the corrected
modes, and the best CRPS on every seed. Awaiting the user's confirmation before it is set on the
final reference.

**How it was measured.** `scripts/16_conformal_check.py` reloaded the first 6 networks of each S5
run (seeds 42 to 44) and predicted the validation split at T=100, which is exactly the frozen
ensemble. Test windows were never predicted. Each mode was fitted on some validation months and
scored on the others, so every number below is out-of-sample:
- **Alternating months**: fit on odd months, score on even, and the reverse. Both halves contain
  every season, so this measures whether a grid's shape is right.
- **Leave one season out**: fit on three seasons, score on the fourth. This imitates what the test
  year demands (factors applied to a season they were not fitted on), so it measures the
  seasonal-transfer error.

All numbers are daylight, mean over the 3 seeds; seed sds are in the source files and are small
(CP sd ≤ 0.003).

**Alternating months** (the geometry check):

| Mode | Factors | CP | Worst province, \|CP − 0.95\| | Worst step, \|CP − 0.95\| | CP spread across steps | MPIW (W/m²) | CRPS |
|---|---|---|---|---|---|---|---|
| none (uncorrected) | — | 0.794 | 0.256 (Rize) | 0.222 | 0.217 | 180 | 46.12 |
| global | 1 | 0.948 | 0.043 (Rize) | 0.042 | 0.076 | 332 | 44.89 |
| per_horizon | 24 | 0.948 | 0.041 (Rize) | 0.004 | 0.004 | 326 | 44.52 |
| per_city | 5 | 0.948 | 0.007 | 0.041 | 0.076 | 323 | 44.64 |
| **city_horizon** | 120 | **0.948** | **0.006** | **0.004** | **0.004** | **318** | **44.32** |

**Leave one season out** (the seasonal-transfer check):

| Mode | CP | Worst province | Worst step | CRPS |
|---|---|---|---|---|
| global | 0.944 | 0.048 | 0.041 | 45.02 |
| per_horizon | 0.944 | 0.047 | 0.011 | 44.66 |
| per_city | 0.941 | 0.016 | 0.044 | 44.80 |
| **city_horizon** | **0.942** | **0.015** | **0.012** | **44.47** |

Sources: `conformal_check_scores.csv`, `conformal_check_groups.csv`.

**What the two axes fix.**
- **The lead time is the largest miscalibration, and only the horizon axis sees it.** Raw
  coverage falls steadily from 0.945 at step 1 to 0.73 at step 24: the model's spread does not
  grow as fast as its error does along the day. A per-province factor is an average over steps,
  so it over-covers the early steps and under-covers the late ones:

| Step | Raw CP | per_city CP | per_city MPIW | city_horizon CP | city_horizon MPIW |
|---|---|---|---|---|---|
| 1 | 0.945 | 0.991 | 315 | 0.950 | 180 |
| 6 | 0.830 | 0.957 | 327 | 0.947 | 307 |
| 12 | 0.782 | 0.946 | 331 | 0.948 | 338 |
| 18 | 0.751 | 0.939 | 322 | 0.949 | 341 |
| 24 | 0.733 | 0.916 | 310 | 0.948 | 368 |

  (alternating months; MPIW in W/m²). city_horizon gives the next hours a narrow interval and
  the following day a wide one, which is what an honest forecast should do.
- **The province axis fixes the cross-site differences.** Without it Rize, the cloudiest site,
  stays at 0.907 and Antalya over-covers at 0.969 (global). With city_horizon every province is
  between 0.944 and 0.951, with intervals of 279 W/m² (Antalya) to 369 W/m² (Rize).
- **The two axes do not substitute for each other.** per_city fixes provinces and leaves the step
  error at 0.041; per_horizon does the reverse. Only the crossed grid fixes both.
- **The finer grid does not overfit.** With 120 factors, each fitted on about 1,460 to 1,750
  daylight elements per fold, city_horizon's out-of-sample errors are as small as the 5- or
  24-factor grids' on the axis those grids target. Its CRPS beats per_city on every seed (−0.31,
  −0.36, −0.29 W/m²) and per_horizon on every seed (−0.23, −0.20, −0.20).

**The correction nearly doubles the interval.** The fitted factor is about 1.86 overall (cells
from 0.9 to 2.9; `conformal_check_folds.csv`), so the 95% interval grows from about 180 to about
318 W/m² on average. This is the size of the aleatoric term the pooled sample lacks.

**Conformal recalibration improves CRPS, not only coverage.** CRPS falls from 46.12 to 44.32
(−1.81 W/m², −3.9%) with city_horizon, on every seed. So the uncorrected distribution was too
narrow as a whole, not just in its tails. (In the 2-epoch smoke run the correction made CRPS
worse; on trained networks it does not.)

**Seasonal transfer is the remaining calibration error, and the grid cannot fix it.**

| Season (validation) | Daylight elements | Raw CP | city_horizon CP, alternating months | city_horizon CP, season held out |
|---|---|---|---|---|
| DJF | 108,287 | 0.797 | 0.962 | 0.961 |
| MAM | 145,204 | 0.734 | 0.923 | 0.901 |
| JJA (1 to 11 June only) | 14,718 | 0.954 | 0.994 | 0.994 |
| SON | 117,826 | 0.844 | 0.961 | 0.967 |

The factor k refitted month by month (all provinces pooled, and per province):

| | Jan | Feb | Mar | Apr | May | Jun (1–11) | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|
| All | 1.64 | 1.84 | 2.21 | 2.15 | 2.03 | 0.97 | 1.66 | 1.42 | 1.86 | 1.70 |
| Ankara | 1.64 | 1.82 | 2.20 | 2.28 | 2.04 | 0.86 | 1.84 | 1.01 | 1.88 | 1.66 |
| Antalya | 1.31 | 1.65 | 2.12 | 1.61 | 1.82 | 0.60 | 1.08 | 0.86 | 1.70 | 1.84 |
| Konya | 1.72 | 1.84 | 2.33 | 1.52 | 1.72 | 0.73 | 1.31 | 1.07 | 1.74 | 1.91 |
| Rize | 2.12 | 2.26 | 2.41 | 2.38 | 2.34 | 1.47 | 2.29 | 2.34 | 2.16 | 1.86 |
| Van | 1.12 | 1.64 | 1.87 | 2.56 | 1.94 | 1.05 | 1.54 | 1.61 | 1.43 | 1.17 |

Source: `conformal_check_month_k.csv`.

- **k is strongly seasonal**: about 2.2 in spring, about 1.0 in early June. Spring's convective
  cloudiness makes errors large relative to the model's spread; early summer is mostly clear and
  the raw spread is already about right (raw CP 0.954).
- So even after correction, spring is under-covered (0.92, or 0.90 when spring is held out) and
  early June over-covered (0.99). Rize is the exception: k stays near 2.1 to 2.4 all year.
- **Consequence for the test year.** The test year contains two full summers' worth of June to
  August that the calibration set never saw, apart from 11 days. If summer behaves like early
  June, summer intervals will be too wide (coverage near 0.99, wider than needed) and spring
  ones slightly too narrow. The aggregate test CP may still land near 0.95 while the seasonal
  conditional coverage does not. The paper should report test coverage per season and state
  this as a limitation.
- **Why the season axis is still not the fix.** A season factor needs every season in the
  calibration set; validation has 11 summer days. The clean fix is a calibration set that spans a
  full year inside the training period, for example out-of-bag (jackknife+-after-bootstrap)
  calibration, which the bootstrap already makes possible. That is separate work, logged in
  `TUNING_PLAN.md`.

**This revises an earlier claim.** The `conformal.py` module comments, written on the retired
dataset, say the horizon axis is null. On the current data and model it is the single largest
conditional error (raw CP from 0.945 to 0.73 across steps). Those comments should not be cited.

**Reading the metrics.**
- Read the first table across: every corrected mode brings the aggregate CP to 0.948, so
  aggregate coverage cannot choose between them. The choice is made by the conditional
  columns (worst province, worst step) and by CRPS, which also rewards narrower honest intervals.
- MPIW is the interval width in W/m². city_horizon is the narrowest corrected mode because it
  spends width where the errors are (late steps, Rize) and saves it where they are not (step 1,
  Antalya).
- The season tables are the honest caveat: aggregate coverage hides a spring/summer imbalance
  that no grid fitted on this validation split can remove.

## Frozen configuration

| Setting | Value | Stage |
|---|---|---|
| Lookback | 24 h | S1 |
| LSTM | 1 layer of width 256, head width 128 | S2 |
| Dropout rate | 0.2 (head only, at 1 layer) | S3 |
| Learning rate | 5e-4 | S3 |
| Early-stopping patience | 5 | after S3 |
| Bootstrap block length | 168 h | S4 |
| Ensemble size B | 6 | S5 |
| MC-Dropout passes T | 100 | S5 (rule pick 50, amended) |
| Conformal mode | `city_horizon` (recommended, awaiting confirmation) | conformal check |

## Carried forward

- **Patience** is 5 from S4 on (above). Ablations that change the architecture's width restore 10.
- **Cost.** At 256 × 1 a network takes about 6.5 min on MPS at dropout 0.2 and patience 10
  (alone), and about 5.2 min at patience 5 with two shards sharing the GPU (S4).
- **Coverage.** Raw ensemble CP at B=8 is 0.80 (Rize 0.70). The conformal layer is required to
  reach nominal coverage; S5 measures how far B and T move it.
- **MC-Dropout spread at 1 layer** (S2) and the smoke-run gap between MC-averaged and
  dropout-off predictions are both resolved by S5: dropout is the larger source of spread, and
  it costs no point accuracy.
