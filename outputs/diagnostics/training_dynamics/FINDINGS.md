# Why every network stops within the first few epochs

Diagnostic run: `scripts/13_training_dynamics.py --epochs 40`. One network, using the reference
config (`config_005_default_full`, seed 42, MPS), trained on the unresampled training windows
with early stopping disabled and the same LR schedule. After each epoch it is evaluated with
dropout off on all training and validation windows. Numbers come from `history.csv` and
`loss_and_lr.csv`; the figure is `training_dynamics.png`. The test period was not used.

## Findings

1. **This is ordinary overfitting, not a validation-period artefact.** Training daylight RMSE falls
   steadily, from 99.3 W/m² after epoch 1 to 81.1 W/m² after epoch 39. Validation daylight RMSE
   is lowest at 100.6 W/m² (epoch 5, which is also the epoch with the lowest validation loss) and
   then drifts up to about 106 W/m². Everything the network learns after the first few epochs is
   specific to the training years.
2. **The network is not overfitting at the epoch early stopping picks.** At epoch 5 the gap
   between training and validation RMSE is about 5 W/m² (95.6 against 100.6). The ~100 W/m²
   error is a limit of what can be learned, not overfitting: once the first ~2 epochs (about 3,500
   Adam steps) have passed, a 24-hour history without weather-forecast inputs carries no further
   information that generalises. Regularisation (more dropout, weight decay, a smaller network)
   can make the drift after the optimum slower, but it should not be expected to lower the
   optimum itself.
3. **The choice of epoch is close to arbitrary.** Over epochs 1–12, validation daylight RMSE stays
   between 100.6 and 104.5 W/m², and the validation loss moves between 0.0666 and 0.0709 from
   epoch to epoch without a trend. Early stopping is picking a noisy minimum on a plateau.
   Consequence for ablations: differences of a few W/m² between arms are within this selection
   noise, so they need several seeds before they can be claimed.
4. **The drift after the optimum is uneven.** Up to epoch 39, validation error grows most for
   spring targets (+9.5 W/m²; spring is the largest validation season, with 144,696 daylight
   elements) and for Ankara, Konya and Rize (+6.7 to +7.5 W/m²). It grows least for Antalya and Van
   (+2.6 and +3.1 W/m²) and for autumn and winter. Summer covers only 1–11 June in the validation period
   (17,274 elements) and is too noisy to read. The validation mix may affect where the drift
   shows up, but it does not create it.
5. **A side observation:** on daylight hours, forecasts are biased low on average (validation mean
   error −13 W/m² at epoch 4), and before the night clamp, night forecasts have an RMSE of about
   25 W/m². The network spends part of its fit on night hours, which the clamp later sets to zero
   anyway. That is a possible reason to test `loss_daylight_only`.

## Implications

- Early stopping at epochs 0–5 is correct behaviour and needs no fix.
- Arm-to-arm comparisons need several seeds.
- Gains are more likely from more informative inputs than from more regularisation.

Caveats: this is one network and one seed, trained without bootstrap resampling.
