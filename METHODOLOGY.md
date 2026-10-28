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

The procedure consists of the following stages, each described below:

1. chronological partitioning of the record and standardisation fitted on the training period;
2. construction of input–output windows (24 h of history in, the next 24 h out);
3. generation of *B* moving-block bootstrap replicates of the training windows;
4. training of one LSTM per replicate, with dropout;
5. *M* stochastic forward passes per trained network with dropout kept active (MC Dropout),
   giving *B* × *M* forecasts for every input window;
6. pooling of these forecasts into a predictive distribution, from which the point forecast,
   the variance decomposition and the 95% prediction interval are derived;
7. a physical constraint that sets forecasts to zero when the sun is below the horizon;
8. optional split-conformal recalibration of the interval width;
9. evaluation on the held-out test period.

## 2. Problem formulation

Let *s* ∈ {1, …, 5} index the site and *t* the hour, expressed in each site's local solar time.
Let **x**<sub>*s*,*t*</sub> ∈ ℝ<sup>13</sup> be the standardised feature vector of site *s* at
hour *t* (Section 3) and *y*<sub>*s*,*t*</sub> the observed irradiance. An input window is the
sequence of the 24 most recent feature vectors,

<p class="eq">X<sub>s,t</sub> = (<b>x</b><sub>s,t−23</sub>, …, <b>x</b><sub>s,t</sub>),</p>

and the corresponding target is the irradiance over the following 24 hours,

<p class="eq">y<sub>s,t</sub> = (y<sub>s,t+1</sub>, …, y<sub>s,t+24</sub>).</p>

The model maps the window and the site identity to all 24 values at once
(direct multi-output forecasting):

<p class="eq">ŷ<sub>s,t</sub> = f<sub>θ</sub>(X<sub>s,t</sub>, s) ∈ ℝ<sup>24</sup>.<span class="eqn">(1)</span></p>

Each horizon step *h* = 1, …, 24 is therefore a separate output of the same network rather
than the result of feeding earlier predictions back as inputs. Only observed quantities enter
the window; no numerical weather prediction or other forecast of the meteorological variables
is used, so the inputs are all available at the time the forecast is issued.

A single model is trained on all five sites jointly. Site identity enters only through a
learned embedding (Section 5), so information can be shared across climates while the
network can still represent site-specific behaviour.

## 3. Input variables

Table 1 lists the 13 model inputs. The target's own history is included as an input, so the
model is autoregressive in irradiance. Wind direction is encoded by its sine and cosine to
remove the discontinuity at 0°/360°, and the hour of day and day of year are encoded the same
way. Solar geometry (solar elevation and top-of-atmosphere irradiance) is computed from the
site coordinates and the timestamp but is used only to define daylight (Section 8); it is not a
model input, because the cyclical time encodings already carry that information.

**Table 1.** Model inputs.

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

## 4. Data partitioning, standardisation and windowing

The record (30 June 2019 00:00 – 29 June 2026 23:00, 61,368 hours per site) is divided
chronologically into training (74%), validation (11%) and test (15%) periods. The boundaries are
computed once and fall on identical dates at every site: training ends on 3 September 2024
03:00 and validation on 11 June 2025 09:00. The test period therefore spans 384 days and covers
all four seasons.

Every variable is standardised to zero mean and unit variance, with means and standard
deviations estimated from the training period only and then applied unchanged to the
validation and test periods. Forecasts are transformed back to W/m² before evaluation.

Windows are built separately for each site with a stride of one hour. A window, comprising its
24 input hours and 24 target hours, is assigned to a period only if all 48 hours fall inside
that period; windows that straddle a period boundary are discarded. Windows never span two
sites. This gives 226,825 training, 33,515 validation and 45,795 test windows
(9,159 test windows per site, i.e. 219,816 forecast–observation pairs per site).

## 5. Network architecture

The network has three parts.

- **Site embedding.** Each site is mapped to a learned 4-dimensional vector, which is
  concatenated to the feature vector at every time step of the window, giving 17 inputs per
  step.
- **Recurrent encoder.** Two stacked LSTM layers with 64 hidden units each. Dropout
  (rate *p* = 0.3) is applied between the two layers, and again to the hidden state of the
  second layer at the final time step, which summarises the window.
- **Output head.** A fully connected layer with 32 units and ReLU activation, followed by
  dropout (*p* = 0.3) and a linear layer with 24 outputs, one per horizon step.

The network has 57,420 trainable parameters. It contains no batch normalisation, because MC
Dropout runs the network in training mode at prediction time, where batch normalisation would
use the statistics of the prediction batch rather than fixed ones. Dropout is therefore the only
source of randomness at prediction time.

## 6. Training

Each network is trained on standardised targets by minimising the mean squared error over all
24 horizon steps, plus a soft penalty on negative irradiance forecasts:

<p class="eq">𝓛(θ) = (1/24N) Σ<sub>i</sub> Σ<sub>h</sub> (ŷ<sub>i,h</sub> − y<sub>i,h</sub>)<sup>2</sup> + λ (1/24N) Σ<sub>i</sub> Σ<sub>h</sub> max(0, −ŷ<sub>i,h</sub>)<sup>2</sup>,<span class="eqn">(2)</span></p>

with λ = 0.1, where the penalty is evaluated on the irradiance scale so that it acts only on
physically impossible negative values. The mean squared error targets the conditional mean, so
the point forecast is an estimate of expected irradiance.

Optimisation uses Adam with an initial learning rate of 10<sup>−3</sup> and mini-batches of 128
windows, shuffled every epoch. The learning rate is halved when the validation loss has not
improved for 7 epochs. Training stops when the validation loss has not improved for 10 epochs,
or after 100 epochs, and the weights from the epoch with the lowest validation loss are kept.
The validation loss is computed with dropout disabled.

## 7. Uncertainty quantification

### 7.1 Moving-block bootstrap

Meteorological and irradiance series are strongly autocorrelated, and resampling individual
observations independently would destroy that dependence. A moving-block bootstrap is used
instead. For site *s* with *n*<sub>*s*</sub> chronologically ordered training windows and block
length ℓ, ⌈*n*<sub>*s*</sub>/ℓ⌉ block start positions are drawn uniformly and with replacement from
{1, …, *n*<sub>*s*</sub> − ℓ + 1}. The blocks of ℓ consecutive windows are concatenated and
truncated to exactly *n*<sub>*s*</sub> windows. This is repeated for every site, and the five
resampled sets are pooled into one bootstrap replicate:

<p class="eq">𝒟<sup>(1)</sup>, 𝒟<sup>(2)</sup>, …, 𝒟<sup>(B)</sup>.<span class="eqn">(3)</span></p>

Resampling site by site keeps the number of windows per site identical in every replicate, so
no replicate is dominated by one climate. Each window carries its own inputs and targets, so
resampling cannot pair an input with the wrong target. Block length ℓ = 168 windows (one week of
forecast origins) is used, chosen to cover the diurnal cycle and multi-day synoptic weather
systems.

Only the training windows are resampled. The validation set is the same for every replicate
and is used only for early stopping and learning-rate scheduling, and the test set takes no part
in training or resampling.

**[To be decided: whether to run the block-length sensitivity analysis (ℓ = 24, 72 and
168 windows); it has not been run.]**

### 7.2 Monte Carlo Dropout

One network *f*<sub>θ<sub>b</sub></sub> is trained on each replicate 𝒟<sup>(*b*)</sup>, with a
different random initialisation. At prediction time dropout is kept active, so each forward
pass applies a fresh random dropout mask **z**<sub>*b*,*m*</sub>. With *M* passes per network,
every input window receives *B* × *M* stochastic forecasts:

<p class="eq">ŷ<sup>(b,m)</sup> = f<sub>θ<sub>b</sub></sub>(X, s; <b>z</b><sub>b,m</sub>),&nbsp;&nbsp; b = 1, …, B,&nbsp; m = 1, …, M.<span class="eqn">(4)</span></p>

This study uses *B* = 8 and *M* = 100, giving 800 forecasts for every window and horizon step.
All quantities below are computed separately for each window and horizon step.

### 7.3 Predictive mean and variance decomposition

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
contributes.

### 7.4 Prediction interval

The nominal 95% prediction interval is given by the empirical 2.5th and 97.5th percentiles of
the *B* × *M* pooled forecasts:

<p class="eq">PI<sub>95</sub> = [Q<sub>0.025</sub>({ŷ<sup>(b,m)</sup>}), Q<sub>0.975</sub>({ŷ<sup>(b,m)</sup>})].<span class="eqn">(10)</span></p>

Because the interval is taken from the pooled sample rather than from a Gaussian assumption, it
can be asymmetric, which arises naturally when the networks disagree in one direction.

### 7.5 Aleatoric uncertainty and interval recalibration

Every network outputs a single value per horizon step, so the pooled forecasts describe
uncertainty about the conditional mean only. They contain no term for the variability of the
observation around that mean (aleatoric uncertainty), which in irradiance is dominated by cloud
processes that a 24-hour history cannot resolve. The pooled interval is therefore expected to
cover fewer than 95% of observations.

This is corrected, where stated, by split-conformal recalibration on the validation period.
The pooled forecasts for each element are rescaled about their own mean,

<p class="eq">ŷ<sup>(b,m)</sup> → μ̂ + k (ŷ<sup>(b,m)</sup> − μ̂),<span class="eqn">(11)</span></p>

so the point forecast, and hence every point-accuracy metric, is unchanged, while the interval
endpoints and the whole predictive distribution scale together. For each validation element
with observation *y* and interval [*L*, *U*], the conformity score is the smallest factor that
would have covered it:

<p class="eq">r = (y − μ̂) / (U − μ̂) if y ≥ μ̂,&nbsp;&nbsp; r = (μ̂ − y) / (μ̂ − L) otherwise.<span class="eqn">(12)</span></p>

Given *n* scores, *k* is the ⌈(*n* + 1)(1 − α)⌉-th smallest, with α = 0.05. Factors are
estimated separately for each cell of a grid defined by **[to be decided: the grid, e.g. site
× season]**; cells with fewer than 200 usable scores fall back to the pooled factor. Night-time
elements, where forecast and observation are both zero, carry no information about the interval
width and are excluded from calibration.

Two limitations follow from the data. First, the validation period also serves for early
stopping, so the calibration data are not entirely independent of training decisions; the
dependence is weak, because early stopping selects only the epoch. Second, the validation period
contains no July or August and only the first eleven days of June, so the summer factors are
extrapolated from the other months.

## 8. Physical constraint at night

Daylight is defined geometrically: an hour is a daylight hour if the apparent solar elevation at
the midpoint of the hour, computed from the site coordinates and the timestamp, is above zero.
When the sun is below the horizon, irradiance is physically zero. For every such element, all
*B* × *M* forecasts are set to zero, so the point forecast and both interval endpoints are zero.
The constraint uses only site and time, so it is available when the forecast is issued, and it
is applied identically to every model.

## 9. Evaluation

### 9.1 Evaluation subsets

All metrics are computed on the test period, over every window and all 24 horizon steps, and
reported for two subsets: all hours, and daylight hours only (solar elevation > 0). About half of
all elements are night hours whose observation and (constrained) forecast are both exactly zero.
These lower RMSE and MAE, inflate R² because the day–night cycle dominates the total variance,
and are covered by every interval by construction. **Daylight metrics are therefore the headline
results**; all-hours metrics are given for completeness.

Results are reported pooled over the five sites, for each site, pooled over the four sites other
than Rize (which forms a distinct radiative regime), and for each horizon step.

### 9.2 Point-forecast metrics

With μ̂<sub>*i*</sub> the point forecast and *y*<sub>*i*</sub> the observation over the *N*
elements of a subset:

<p class="eq">RMSE = √[(1/N) Σ<sub>i</sub> (μ̂<sub>i</sub> − y<sub>i</sub>)<sup>2</sup>],&nbsp;&nbsp; MAE = (1/N) Σ<sub>i</sub> |μ̂<sub>i</sub> − y<sub>i</sub>|,&nbsp;&nbsp; R<sup>2</sup> = 1 − Σ<sub>i</sub>(y<sub>i</sub> − μ̂<sub>i</sub>)<sup>2</sup> / Σ<sub>i</sub>(y<sub>i</sub> − ȳ)<sup>2</sup>,<span class="eqn">(13)</span></p>

where ȳ is the mean observation of the subset.

### 9.3 Probabilistic metrics

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

### 9.4 Reference forecasts

Two reference forecasts are evaluated on exactly the same test windows and subsets:

- **Climatology**: the mean irradiance of the same site, calendar month and hour of day over the
  training period;
- **Persistence**: the observed irradiance at the same site and hour on the previous day.

A model is considered informative only if it beats both on daylight RMSE and MAE.

## 10. Reproducibility

Each experiment is fully specified by a configuration file and a master random seed. The
resampling generator is seeded from the master seed, and network *b* is initialised from
seed + *b*, so the replicates and their initialisations are reproducible. Results are
reproducible on the same hardware backend; GPU and CPU backends do not agree bit for bit. Models
were trained in PyTorch on **[to be decided: hardware backend]**.
