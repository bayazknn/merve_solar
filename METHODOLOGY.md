# Methodology

## 1. Overview

The forecasting task is to predict, at every hour, the all-sky surface shortwave downward
irradiance (ALLSKY_SFC_SW_DWN, W/m²) for each of the following 24 hours at five sites in
Türkiye. Point forecasts are produced by a Long Short-Term Memory (LSTM) network, and
predictive uncertainty is quantified by combining a moving-block bootstrap ensemble with Monte
Carlo (MC) Dropout. The combination follows the hybrid ensemble–dropout scheme of Rajaperumal
and Chinnappan, adapted in three respects: an LSTM replaces their physics-constrained
feed-forward backbone, irradiance replaces photovoltaic power as the target, and the bootstrap
resamples contiguous blocks of the training series rather than individual observations.

The procedure consists of the following stages, each described below. The terms *period*,
*window*, *block*, *replicate* and *pass* have precise meanings, defined in Section 2.

1. Split the record chronologically into a training, a validation and a test period, and
   standardise every variable using the training period only.
2. Cut each site's series into overlapping windows of 48 hours: 24 input hours followed by the
   24 hours to be forecast.
3. Build *B* bootstrap replicates of the training windows by drawing blocks of consecutive
   windows with replacement.
4. Train one LSTM on each replicate, with dropout.
5. Run every trained network *M* times on each test window with dropout kept active
   (MC Dropout), giving *B* × *M* forecasts per window.
6. Pool these forecasts into a predictive distribution, from which the point forecast, the
   variance decomposition and the 95% prediction interval are derived.
7. Set forecasts to zero when the sun is below the horizon.
8. Optionally recalibrate the interval width by split-conformal prediction.
9. Evaluate on the test period.

## 2. Terminology: hours, periods, windows, blocks, replicates and passes

The bootstrap and MC Dropout operate on different objects, and the parameters that control
them are easy to confuse. In particular, the 24-hour input length of a window and the
168-window length of a bootstrap block are unrelated settings, and MC Dropout involves
neither blocks nor resampling.

### 2.1 Definitions

**Table 1.** Terms used throughout, from the smallest unit to the largest. Counts are per site
unless stated otherwise.

| Term | Definition | Size in this study | Used by |
|---|---|---|---|
| Hour | One hourly record of one site, in local solar time | 61,368 per site | All stages |
| Period | One of three consecutive, non-overlapping date ranges: training, validation, test | 45,412 / 6,750 / 9,206 hours | All stages |
| Window | 48 consecutive hours of one site: 24 input hours, then 24 target hours | 45,365 / 6,703 / 9,159 windows | Training and prediction |
| Forecast origin | The last input hour of a window, i.e. the hour at which the forecast is issued | One per window | – |
| Horizon step *h* | One of the 24 target hours of a window, *h* = 1 being the hour after the origin | 24 per window | Evaluation |
| Element | One window at one horizon step; the unit every metric is averaged over | 219,816 test elements | Evaluation |
| Block | ℓ consecutive training windows of one site | ℓ = 168 windows | Bootstrap only |
| Replicate | A resampled copy of the training windows, assembled from blocks | *B* = 8 | Bootstrap only |
| Network | One LSTM, trained on one replicate | *B* = 8 | – |
| Pass | One forward run of a network on a window with a fresh random dropout mask | *M* = 100 per network | MC Dropout only |

### 2.2 Periods

Each site's hourly series is cut at two dates that are the same for all sites:

```
 training period (74%)            validation period (11%)      test period (15%)
|-------------------------------|----------------------------|-------------------------|
30 Jun 2019 00:00    3 Sep 2024 03:00             11 Jun 2025 09:00        29 Jun 2026 23:00
      45,412 hours                     6,750 hours                   9,206 hours
```

The training period is used to fit the standardisation, to build the bootstrap replicates and
to train the networks. The validation period is used for early stopping, learning-rate
scheduling and, when used, conformal recalibration. The test period is used only for
evaluation.

### 2.3 Windows

A window is the unit the network sees: the 24 most recent hours as input, and the following
24 hours as the target.

```
hour:     t−23  t−22  ...  t−1   t   | t+1   t+2   ...  t+24
          <------ 24 input hours ----> <---- 24 target hours ---->
                                     ^
                              forecast origin t
```

Windows are taken at every hour (stride 1), so consecutive windows overlap by 47 of their 48
hours:

```
window k      [ 24 in  | 24 out ]
window k+1     [ 24 in  | 24 out ]
window k+2      [ 24 in  | 24 out ]
                 ...
```

A window is kept only if all 48 of its hours lie inside one period; the 47 windows per site
that would straddle each period boundary are discarded. This is why a period of *H* hours
yields *H* − 47 windows (for example 45,412 − 47 = 45,365 training windows per site). Windows
never mix two sites. The temporal order of the 48 hours inside a window is always preserved, by
construction, whatever happens to the window afterwards.

### 2.4 Blocks and replicates (bootstrap only)

The bootstrap does not cut the series again and does not create new windows. It takes the
45,365 training windows of one site, in time order, and draws *blocks* of ℓ = 168 consecutive
windows from them:

```
training windows of one site, in time order:   w1  w2  w3  ...  w45365

one block starting at w_j:   w_j, w_j+1, ..., w_j+167
   = 168 forecast origins spanning 7 days (215 hours of data, inputs and targets included)

one replicate for this site: [block at w_9120][block at w_301][block at w_40007] ...
   = 271 randomly placed blocks, joined and cut to exactly 45,365 windows
```

The same is done independently for the other four sites, and the five resampled sets are
pooled into one replicate. Repeating this *B* = 8 times gives eight replicates, and one network
is trained on each.

What the blocks accomplish needs stating precisely. Windows inside a replicate are shuffled
into mini-batches during training, and the network carries no state from one window to the
next, so the order in which blocks are joined plays no role. What the blocks control is
*which* windows enter a replicate, and how often: neighbouring windows, which share most of
their hours and the same weather, are included or left out together, a week at a time. A
replicate is therefore a resampling of weeks of weather rather than of isolated hours, which is
the dependence an independent (window-by-window) bootstrap would ignore. A replicate contains
about 61–65% of the distinct training windows, some of them several times over.

### 2.5 Passes (MC Dropout only)

MC Dropout acts after training, on one window at a time. A trained network is run *M* = 100
times on the same test window, each time with a new random dropout mask, giving 100 slightly
different 24-hour forecasts. No periods, blocks or replicates are involved at this step: the
windows are the ordinary test windows, used once each and in no particular order. With
*B* = 8 networks, every test window receives 8 × 100 = 800 forecasts.

### 2.6 How the pieces combine

```
training windows (5 sites)
   |-- bootstrap with blocks --> replicate 1 --> train --> network 1 --+
   |-- bootstrap with blocks --> replicate 2 --> train --> network 2 --+
   |   ...                                                             |
   '-- bootstrap with blocks --> replicate 8 --> train --> network 8 --+
                                                                       |
test window --> 100 dropout passes through each of the 8 networks <----+
           --> 800 forecasts of the next 24 hours
           --> mean, variance decomposition, 95% interval
```

## 3. Problem formulation

Let *s* ∈ {1, …, 5} index the site and *t* the hour, expressed in each site's local solar time.
Let **x**<sub>*s*,*t*</sub> ∈ ℝ<sup>13</sup> be the standardised feature vector of site *s* at
hour *t* (Section 4) and *y*<sub>*s*,*t*</sub> the observed irradiance. The input of the window
with origin *t* is

<p class="eq">X<sub>s,t</sub> = (<b>x</b><sub>s,t−23</sub>, …, <b>x</b><sub>s,t</sub>),</p>

and its target is the irradiance over the following 24 hours,

<p class="eq">y<sub>s,t</sub> = (y<sub>s,t+1</sub>, …, y<sub>s,t+24</sub>).</p>

The model maps the window and the site identity to all 24 values at once
(direct multi-output forecasting):

<p class="eq">ŷ<sub>s,t</sub> = f<sub>θ</sub>(X<sub>s,t</sub>, s) ∈ ℝ<sup>24</sup>.<span class="eqn">(1)</span></p>

Each horizon step *h* = 1, …, 24 is therefore a separate output of the same network rather
than the result of feeding earlier predictions back as inputs. Only observed quantities enter
the window; no numerical weather prediction or other forecast of the meteorological variables
is used, so the inputs are all available at the time the forecast is issued.

A single model is trained on all five sites jointly. Site identity enters only through a
learned embedding (Section 6), so information can be shared across climates while the
network can still represent site-specific behaviour.

## 4. Input variables

Table 2 lists the 13 model inputs. The target's own history is included as an input, so the
model is autoregressive in irradiance. Wind direction is encoded by its sine and cosine to
remove the discontinuity at 0°/360°, and the hour of day and day of year are encoded the same
way. Solar geometry (solar elevation and top-of-atmosphere irradiance) is computed from the
site coordinates and the timestamp but is used only to define daylight (Section 9); it is not a
model input, because the cyclical time encodings already carry that information.

**Table 2.** Model inputs.

| Variable | Description | Unit |
|---|---|---|
| ALLSKY_SFC_SW_DWN | All-sky surface shortwave downward irradiance (lagged target) | W/m² |
| T2M | Air temperature at 2 m | °C |
| RH2M | Relative humidity at 2 m | % |
| T2MDEW | Dew/frost point at 2 m | °C |
| PS | Surface pressure | kPa |
| WS2M | Wind speed at 2 m | m/s |
| PRECTOTCORR | Bias-corrected precipitation | mm/h |
| WD2M (sin, cos) | Wind direction at 2 m, sine and cosine | – |
| Hour of day (sin, cos) | 2π · hour / 24 | – |
| Day of year (sin, cos) | 2π · day of year / 365.25 | – |

## 5. Data partitioning, standardisation and windowing

The record (30 June 2019 00:00 – 29 June 2026 23:00, 61,368 hours per site) is divided into the
three periods of Section 2.2, in proportions 74% / 11% / 15%. The boundaries are computed once
and are identical at every site. The test period spans 384 days and covers all four seasons;
the validation period contains no July or August and only the first eleven days of June.

Every variable, the target included, is standardised to zero mean and unit variance, with means
and standard deviations estimated from the training period only and then applied unchanged to
the validation and test periods. For the target these are ȳ = 198.5 W/m² and
*s*<sub>*y*</sub> = 279.7 W/m². Networks are trained on the standardised target, and their
forecasts are transformed back to W/m² before evaluation.

Windows are built as described in Section 2.3. Across the five sites this gives 226,825
training, 33,515 validation and 45,795 test windows.

## 6. Network architecture

The network has three parts.

- **Site embedding.** Each site is mapped to a learned 4-dimensional vector, which is
  concatenated to the feature vector at every hour of the window, giving 17 inputs per hour.
- **Recurrent encoder.** Two stacked LSTM layers with 64 hidden units each read the 24 input
  hours in order. Dropout (rate *p* = 0.3) is applied between the two layers, and again to the
  hidden state of the second layer at the last input hour, which summarises the window.
- **Output head.** A fully connected layer with 32 units and ReLU activation, followed by
  dropout (*p* = 0.3) and a linear layer with 24 outputs, one per horizon step.

The network has 57,420 trainable parameters. It contains no batch normalisation, because MC
Dropout runs the network in training mode at prediction time, where batch normalisation would
use the statistics of the prediction batch rather than fixed ones. Dropout is therefore the only
source of randomness at prediction time.

## 7. Training

Each network is trained on its replicate by minimising, over mini-batches of *N* windows, the
mean squared error on the standardised target plus a penalty on negative standardised
forecasts:

<p class="eq">𝓛(θ) = (1/24N) Σ<sub>i</sub> Σ<sub>h</sub> (z̃<sub>i,h</sub> − z<sub>i,h</sub>)<sup>2</sup> + λ (1/24N) Σ<sub>i</sub> Σ<sub>h</sub> max(0, −z̃<sub>i,h</sub>)<sup>2</sup>,<span class="eqn">(2)</span></p>

where *z* = (*y* − ȳ)/*s*<sub>*y*</sub> is the standardised observation, z̃ the standardised
forecast, and λ = 0.1. The squared error targets the conditional mean, so the point forecast is
an estimate of expected irradiance.

The penalty is intended to discourage physically impossible negative irradiance. Because it is
evaluated on the standardised scale, however, it acts on forecasts below the training-period
mean, ŷ < ȳ = 198.5 W/m², rather than below 0 W/m². This covers about 66% of training hours,
including every night hour, so the penalty pulls low forecasts upward, towards the mean. At
night the resulting bias is removed by the constraint of Section 9; on low-irradiance daylight
hours (early morning, late afternoon, overcast conditions) it is not. The physically intended
form would be max(0, −(z̃ + ȳ/*s*<sub>*y*</sub>))<sup>2</sup>, which is zero for every
non-negative forecast. **[Known issue: the implemented form is the one in Eq. 2; correcting it
requires retraining every network.]**

Optimisation uses Adam with an initial learning rate of 10<sup>−3</sup> and mini-batches of 128
windows, reshuffled every epoch. After each epoch the loss of Eq. 2, penalty included, is
computed on the validation windows with dropout disabled. The learning rate is halved when this
validation loss has not improved for 7 epochs. Training stops when it has not improved for 10
epochs, or after 100 epochs, and the weights from the epoch with the lowest validation loss are
kept. Every network uses the same, unresampled validation windows.

## 8. Uncertainty quantification

### 8.1 Moving-block bootstrap

Meteorological and irradiance series are strongly autocorrelated, so resampling windows
independently would treat near-identical neighbouring windows as independent evidence. A
moving-block bootstrap is used instead (Section 2.4). For site *s* with *n*<sub>*s*</sub>
chronologically ordered training windows and block length ℓ, ⌈*n*<sub>*s*</sub>/ℓ⌉ block start
positions are drawn uniformly and with replacement from {1, …, *n*<sub>*s*</sub> − ℓ + 1}. The
blocks of ℓ consecutive windows are joined and cut to exactly *n*<sub>*s*</sub> windows. This
is repeated for every site, and the five resampled sets are pooled into one replicate:

<p class="eq">𝒟<sup>(1)</sup>, 𝒟<sup>(2)</sup>, …, 𝒟<sup>(B)</sup>.<span class="eqn">(3)</span></p>

With *n*<sub>*s*</sub> = 45,365 and ℓ = 168, each site contributes 271 blocks per replicate.
Resampling site by site keeps the number of windows per site identical in every replicate, so
no replicate is dominated by one climate. Each window carries its own inputs and targets, so
resampling cannot pair an input with the wrong target. The block length of 168 windows (one
week of forecast origins) is chosen to span the diurnal cycle and the multi-day lifetime of
synoptic weather systems. As in any moving-block bootstrap, windows within ℓ − 1 of either end
of a site's training series can be drawn by fewer block positions and so appear less often.

Only training windows are resampled. Validation windows are the same for every replicate and are
used only for early stopping and learning-rate scheduling; test windows take no part in training
or resampling.

**[To be decided: whether to run a block-length sensitivity analysis (ℓ = 24, 72 and
168 windows); it has not been run.]**

### 8.2 Monte Carlo Dropout

One network *f*<sub>θ<sub>b</sub></sub> is trained on each replicate 𝒟<sup>(*b*)</sup>, starting
from a different random initialisation. During training, dropout acts as a regulariser. At
prediction time it is kept active, so each forward pass applies a fresh random dropout mask
**z**<sub>*b*,*m*</sub>, drawn independently for every window. With *M* passes per network,
every input window receives *B* × *M* stochastic forecasts (Section 2.5):

<p class="eq">ŷ<sup>(b,m)</sup> = f<sub>θ<sub>b</sub></sub>(X, s; <b>z</b><sub>b,m</sub>),&nbsp;&nbsp; b = 1, …, B,&nbsp; m = 1, …, M.<span class="eqn">(4)</span></p>

This study uses *B* = 8 and *M* = 100, giving 800 forecasts for every window and horizon step.
All quantities below are computed separately for each element, i.e. for each window and horizon
step.

### 8.3 Predictive mean and variance decomposition

The point forecast is the mean over all *B* × *M* forecasts:

<p class="eq">μ̂ = (1/BM) Σ<sub>b=1</sub><sup>B</sup> Σ<sub>m=1</sub><sup>M</sup> ŷ<sup>(b,m)</sup>.<span class="eqn">(5)</span></p>

The spread of the pooled forecasts has two sources. Writing the mean of network *b* as

<p class="eq">μ̂<sub>b</sub> = (1/M) Σ<sub>m=1</sub><sup>M</sup> ŷ<sup>(b,m)</sup>,<span class="eqn">(6)</span></p>

the variability within each network due to dropout is

<p class="eq">σ<sup>2</sup><sub>MC</sub> = (1/B) Σ<sub>b=1</sub><sup>B</sup> (1/M) Σ<sub>m=1</sub><sup>M</sup> (ŷ<sup>(b,m)</sup> − μ̂<sub>b</sub>)<sup>2</sup>,<span class="eqn">(7)</span></p>

and the variability between networks due to the bootstrap replicates is

<p class="eq">σ<sup>2</sup><sub>boot</sub> = (1/B) Σ<sub>b=1</sub><sup>B</sup> (μ̂<sub>b</sub> − μ̂)<sup>2</sup>.<span class="eqn">(8)</span></p>

By the law of total variance, their sum is exactly the variance of the pooled forecasts:

<p class="eq">σ<sup>2</sup><sub>epi</sub> = σ<sup>2</sup><sub>MC</sub> + σ<sup>2</sup><sub>boot</sub> = (1/BM) Σ<sub>b</sub> Σ<sub>m</sub> (ŷ<sup>(b,m)</sup> − μ̂)<sup>2</sup>.<span class="eqn">(9)</span></p>

Both components describe uncertainty about the model, that is, epistemic uncertainty: how much
the conditional-mean forecast would change with different training data (σ²<sub>boot</sub>) and
under the approximate posterior over network weights that MC Dropout represents
(σ²<sub>MC</sub>). Reporting the two separately shows how much each part of the ensemble
contributes. **[Known issue: the pipeline currently stores only the total, σ<sub>epi</sub>; the
two components require a small change to be reported.]**

### 8.4 Prediction interval

The nominal 95% prediction interval is given by the empirical 2.5th and 97.5th percentiles of
the *B* × *M* pooled forecasts:

<p class="eq">PI<sub>95</sub> = [Q<sub>0.025</sub>({ŷ<sup>(b,m)</sup>}), Q<sub>0.975</sub>({ŷ<sup>(b,m)</sup>})].<span class="eqn">(10)</span></p>

Because the interval is taken from the pooled sample rather than from a Gaussian assumption, it
can be asymmetric, which arises naturally when the networks disagree in one direction.

### 8.5 Aleatoric uncertainty and interval recalibration

Every network outputs a single value per horizon step, so the pooled forecasts describe
uncertainty about the conditional mean only. They contain no term for the variability of the
observation around that mean (aleatoric uncertainty), which in irradiance is dominated by cloud
processes that a 24-hour history cannot resolve. The pooled interval is therefore expected to
cover fewer than 95% of observations.

This can be corrected by split-conformal recalibration on the validation period. The pooled
forecasts for each element are rescaled about their own mean,

<p class="eq">ŷ<sup>(b,m)</sup> → μ̂ + k (ŷ<sup>(b,m)</sup> − μ̂),<span class="eqn">(11)</span></p>

so the point forecast, and hence every point-accuracy metric, is unchanged, while the interval
endpoints and the whole predictive distribution scale together. To estimate *k*, every network
is also run *M* times on each validation window, exactly as on the test windows. For each
validation element with observation *y* and interval [*L*, *U*], the conformity score is the
smallest factor that would have covered it:

<p class="eq">r = (y − μ̂) / (U − μ̂) if y ≥ μ̂,&nbsp;&nbsp; r = (μ̂ − y) / (μ̂ − L) otherwise.<span class="eqn">(12)</span></p>

Given *n* scores, *k* is the ⌈(*n* + 1)(1 − α)⌉-th smallest, with α = 0.05. Factors are
estimated separately for each cell of a grid defined by **[to be decided: the grid, e.g. site
× season]**; cells with fewer than 200 usable scores fall back to the pooled factor. Night-time
elements, where forecast and observation are both zero, carry no information about the interval
width and are excluded from calibration. The reference run reported here uses no recalibration.

Two limitations follow from the data. First, the validation period also serves for early
stopping, so the calibration data are not entirely independent of training decisions; the
dependence is weak, because early stopping selects only the epoch. Second, the validation period
contains no July or August and only the first eleven days of June, so the summer factors are
extrapolated from the other months.

## 9. Physical constraint at night

Daylight is defined geometrically: an hour is a daylight hour if the apparent solar elevation at
the midpoint of the hour, computed from the site coordinates and the timestamp, is above zero.
When the sun is below the horizon, irradiance is physically zero. For every such element, all
*B* × *M* forecasts are set to zero, so the point forecast and both interval endpoints are zero.
The constraint uses only site and time, so it is available when the forecast is issued, and it
is applied identically to every model.

## 10. Evaluation

### 10.1 Evaluation subsets

All metrics are computed on the test period, over every test window and all 24 horizon steps,
and reported for two subsets: all hours, and daylight hours only (solar elevation > 0). About
half of all elements are night hours whose observation and (constrained) forecast are both
exactly zero. These lower RMSE and MAE, inflate R² because the day–night cycle dominates the
total variance, and are covered by every interval by construction. **Daylight metrics are
therefore the headline results**; all-hours metrics are given for completeness.

Because test windows overlap, each test hour appears as a target in up to 24 windows, once at
each horizon step. Metrics are averages over elements, so every hour is counted once per horizon
step at which it is forecast.

Results are reported pooled over the five sites, for each site, pooled over the four sites other
than Rize (which forms a distinct radiative regime), and for each horizon step.

### 10.2 Point-forecast metrics

With μ̂<sub>*i*</sub> the point forecast and *y*<sub>*i*</sub> the observation over the *N*
elements of a subset:

<p class="eq">RMSE = √[(1/N) Σ<sub>i</sub> (μ̂<sub>i</sub> − y<sub>i</sub>)<sup>2</sup>],&nbsp;&nbsp; MAE = (1/N) Σ<sub>i</sub> |μ̂<sub>i</sub> − y<sub>i</sub>|,&nbsp;&nbsp; R<sup>2</sup> = 1 − Σ<sub>i</sub>(y<sub>i</sub> − μ̂<sub>i</sub>)<sup>2</sup> / Σ<sub>i</sub>(y<sub>i</sub> − ȳ<sub>sub</sub>)<sup>2</sup>,<span class="eqn">(13)</span></p>

where ȳ<sub>sub</sub> is the mean observation of the subset.

### 10.3 Probabilistic metrics

With [*L*<sub>*i*</sub>, *U*<sub>*i*</sub>] the 95% interval and μ = 0.95 the nominal coverage:

- **Coverage probability**, CP = (1/N) Σ<sub>*i*</sub> 𝟙(*L*<sub>*i*</sub> ≤ *y*<sub>*i*</sub> ≤ *U*<sub>*i*</sub>);
- **Reliability**, |CP − μ|;
- **Mean prediction interval width**, MPIW = (1/N) Σ<sub>*i*</sub> (*U*<sub>*i*</sub> − *L*<sub>*i*</sub>), in W/m²;
- **Prediction interval normalised width**, PINW = MPIW / (max *y* − min *y*), with the range taken over the subset;
- **Coverage width-based criterion**, CWC = PINW · [1 + γ exp(−η (CP − μ))], with γ = 1 if CP < μ and 0 otherwise, and η = 50;
- **Continuous ranked probability score**, estimated from the *S* = *B* × *M* pooled forecasts as

<p class="eq">CRPS = (1/N) Σ<sub>i</sub> [ (1/S) Σ<sub>j</sub> |ŷ<sub>i</sub><sup>(j)</sup> − y<sub>i</sub>| − (1/2S<sup>2</sup>) Σ<sub>j</sub> Σ<sub>j′</sub> |ŷ<sub>i</sub><sup>(j)</sup> − ŷ<sub>i</sub><sup>(j′)</sup>| ],<span class="eqn">(14)</span></p>

in W/m². CRPS rewards calibration and sharpness together and reduces to MAE for a
deterministic forecast, which makes it directly comparable with the reference forecasts below.

A run is judged first on whether daylight CP is close to 0.95, then on interval sharpness
(PINW, CWC) and CRPS, alongside the point metrics.

### 10.4 Reference forecasts

Two reference forecasts are evaluated on exactly the same test windows and subsets:

- **Climatology**: the mean irradiance of the same site, calendar month and hour of day over the
  training period;
- **Persistence**: the observed irradiance at the same site and hour on the previous day.

A model is considered informative only if it beats climatology on daylight RMSE and R² and
persistence on daylight MAE, the strongest reference on each measure.

## 11. Reproducibility

Each experiment is fully specified by a configuration file and a master random seed. The
resampling generator is seeded from the master seed, and network *b* is initialised from
seed + *b*, so the replicates and their initialisations are reproducible. Results are
reproducible on the same hardware backend; different backends do not agree bit for bit. The
reference run was trained in PyTorch on an Apple-silicon GPU (MPS backend).
