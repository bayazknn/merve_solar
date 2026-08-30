"""Enumerates the ExperimentConfig sweep, in named groups.

Groups exist so an hours-long run can be selected precisely rather than by running everything:
`smoke` is minutes and proves the code path, `main` is the hyperparameter sweep, `ablation` is
the global-vs-per-province comparison that tests the paper's cross-city transfer claim.

Keeping the smoke config in its own group also fixes a real hazard: it used to sit in the
default sweep, so every run of run_all_experiments.py appended another duplicate row for the
same experiment_id, which the comparability rules forbid.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dataclasses import fields

from merve_solar.config import CITIES, ExperimentConfig

# The ablation pair's shared settings. Both arms are constructed from this one dict so the pair
# provably differs only in training_scope (and seed) -- far safer than two hand-written blocks
# that can silently drift apart.
#
# max_epochs/early_stop_patience are raised above the ExperimentConfig defaults on purpose: a
# per-province model sees a fifth of the windows per epoch at the same batch size, so it gets a
# fifth of the optimizer steps and the default patience is effectively five times tighter. Both
# arms get the same generous budget so neither is judged on truncated training.
ABLATION_FULL = dict(
    lookback_hours=24,
    horizon_hours=24,
    window_stride=1,
    train_ratio=0.74,
    val_ratio=0.11,
    hidden_sizes=[64, 32],
    dropout_rate=0.3,
    city_embedding_dim=4,
    learning_rate=1e-3,
    batch_size=128,
    max_epochs=200,
    early_stop_patience=15,
    n_bootstrap=8,
    mc_dropout_passes=100,
    bootstrap_block_length=168,
)

ABLATION_SMOKE = dict(n_bootstrap=1, mc_dropout_passes=10, max_epochs=5, early_stop_patience=3)

ABLATION_SEEDS = (42, 43, 44)


def _smoke_configs() -> list:
    """Minutes, on CPU. Exercises both scope arms end to end before anything expensive."""
    return [
        ExperimentConfig(experiment_id="abl_scope_smoke_global", training_scope="global", **ABLATION_SMOKE),
        ExperimentConfig(experiment_id="abl_scope_smoke_percity", training_scope="per_city", **ABLATION_SMOKE),
    ]


def _main_configs() -> list:
    configs = []
    # Architecture sweep (the source paper's Table 6 hidden-layer options).
    for i, hidden_sizes in enumerate([[32, 16], [64, 32], [128, 64]], start=1):
        configs.append(
            ExperimentConfig(
                experiment_id=f"config_{i:03d}_hidden_{'-'.join(map(str, hidden_sizes))}",
                hidden_sizes=hidden_sizes,
            )
        )
    # Lookback sweep -- no precedent in the source paper's PCNN, our own sequence-design axis.
    for lookback in [12, 24, 48]:
        configs.append(
            ExperimentConfig(experiment_id=f"config_lookback_{lookback}h", lookback_hours=lookback)
        )
    for dropout in [0.1, 0.2, 0.3]:
        configs.append(
            ExperimentConfig(experiment_id=f"config_dropout_{dropout}", dropout_rate=dropout)
        )
    # Our default split (test lands on a full seasonal year) against the source paper's 64/16/20.
    configs.append(
        ExperimentConfig(experiment_id="config_split_paper_64_16_20", train_ratio=0.64, val_ratio=0.16)
    )
    return configs


def _ablation_configs() -> list:
    """Global vs per-province, three seeds, plus two sensitivity runs.

    Three seeds because a single-seed comparison of two arms is not publishable evidence: a seed
    changes both the weight init and the bootstrap draw, so it is the right unit of variability.
    If the gap between arms is smaller than the spread across seeds, the honest conclusion is
    that there is no detectable difference.
    """
    configs = []
    for seed in ABLATION_SEEDS:
        for scope, tag in (("global", "global"), ("per_city", "percity")):
            configs.append(
                ExperimentConfig(
                    experiment_id=f"abl_scope_full_{tag}_s{seed}",
                    training_scope=scope,
                    seed=seed,
                    **ABLATION_FULL,
                )
            )

    # Sensitivity 1: the hyperparameters above were chosen for the pooled regime (218,745
    # windows). On 43,749 the same model may simply overfit, which would show up as a per-province
    # loss that reflects capacity mismatch rather than absence of transfer. This confound points
    # the opposite way to the scaler one below; they compound rather than cancel.
    small = {**ABLATION_FULL, "hidden_sizes": [32, 16]}
    configs.append(
        ExperimentConfig(
            experiment_id="abl_sens_percity_small_s42", training_scope="per_city", seed=42, **small
        )
    )

    # Sensitivity 2: per-province training with the pooled scaler, isolating the normalisation
    # effect from the training effect.
    configs.append(
        ExperimentConfig(
            experiment_id="abl_sens_percity_globalscaler_s42",
            training_scope="per_city",
            per_city_scaler=False,
            seed=42,
            **ABLATION_FULL,
        )
    )
    return configs


# ---------------------------------------------------------------------------------------------
# Rize transfer curve: the paper's cross-province claim, tested in the direction it is made.
#
# The claim is that pooling improves EACH province's forecast versus a province-specific model --
# transfer *into* a province. Rize is the sharpest place to test it: the EDA puts it in a separate
# climatic regime (daily clear-sky index 0.697 against 0.806-0.840, overcast-day share 8.0%
# against 1.0-2.8%, its best season near the others' winter), and it is where the model currently
# earns its keep -- the global smoke run beats climatology by 14.1% on Rize against 0.2-3.0%
# elsewhere. If pooling buys anything, it should show up there.
#
# So instead of removing Rize, we remove the OTHERS and watch Rize degrade. Every arm is scored on
# Rize's own test windows, which are identical across arms because the split boundaries come from
# the full frame before any exclusion.
#
# The confound is that adding provinces also adds data, so a monotone curve alone cannot separate
# "more data" from "more diverse data". The pair arms are the control: Rize+Ankara and
# Rize+Antalya train on exactly the same number of windows, and differ only in WHICH province is
# added -- Ankara being the cloudiest of the other four (kt 0.806) and Antalya the sunniest
# (0.840). If transfer is about information rather than volume, those two should not be equal.
RIZE = "Rize"
_OTHERS = [c for c in CITIES if c != RIZE]

RIZE_CURVE_ARMS = [
    # (id suffix,        provinces kept,                      scope,       what it isolates)
    ("solo",             [RIZE],                              "per_city"),   # zero transfer
    ("plus_ankara",      [RIZE, "Ankara"],                    "global"),     # +1, cloudiest partner
    ("plus_antalya",     [RIZE, "Antalya"],                   "global"),     # +1, sunniest partner
    ("minus_antalya",    [RIZE, "Ankara", "Konya", "Van"],    "global"),     # 4 of 5
    ("all5",             [RIZE] + _OTHERS,                    "global"),     # full pooling
]


# Reduced-fidelity variant of ABLATION_FULL, used because the full setting does not fit the
# available compute. MEASURED on this CPU-only host (12 cores, torch using 6 threads) with a
# timing probe over the real windows: 25.7 s/epoch and 1.83 s/MC-pass on the pooled five-province
# split (218,745 train windows), 9.9 s / 0.72 s on a two-province split, 5.0 s / 0.37 s on Rize
# alone. At B=8 x T=100 the twelve-arm study costs 22 h if early stopping bites at epoch 40 and
# 96 h if every replica runs to the 200-epoch cap -- days, not hours.
#
# What is given up, and why it is the right thing to give up:
#   n_bootstrap 8 -> 1  is the sanctioned fast path, not a separate code path (experiment.py):
#       no moving-block resampling, one LSTM, still scored by MC-Dropout alone. It removes the
#       data/sampling component of the UQ layer, so the interval metrics of a B=1 arm are
#       MC-Dropout-only and must not be compared against a B=8 row. The point metrics are the
#       mean over T=100 stochastic passes, which is what this study reads.
#   max_epochs 200 -> 100 with early_stop_patience kept at 15: the minimum setting at which
#       early stopping, rather than the cap, is expected to decide when training ends. Whether
#       it actually did is recorded per arm in the ledger's hit_max_epochs column and MUST be
#       checked before any arm-to-arm claim -- arms that differ in training amount are not
#       comparable.
# T=100 MC passes is unchanged, so the percentile CI is estimated from the same sample size.
#
# The two dicts are deliberately built from one another rather than written out twice: the
# reduced arms must differ from the full ones in exactly these three fields and nothing else.
ABLATION_B1 = {**ABLATION_FULL, "n_bootstrap": 1, "max_epochs": 100}

# Smoke fidelity for the curve's two structurally new code paths (a per_city arm with four
# provinces excluded, and a global arm with three excluded). Minutes, and it is what stops a
# multi-hour sweep from dying at the metrics step.
RIZE_SMOKE_ARMS = ("solo", "plus_ankara")


def _rize_curve_configs(fidelity: dict = ABLATION_FULL, suffix: str = "",
                        arms=None, seeds_override=None, loss: str | None = None,
                        include_stage1: bool = True, **extra) -> list:
    """The transfer curve, plus a loss-selection stage that must run first.

    SUPERSEDED AS A GROUP TO RUN. Called with no arguments -- which is what the `rize_curve`
    group does -- this builds twelve arms at B=8 under the ExperimentConfig default loss, i.e.
    MSE. Stage 1 has since measured MSE to be the worst of the three criteria, and section 2 of
    ABLATION.md shows the criterion changes the curve's conclusion, not just its level. Running
    `--group rize_curve` would therefore spend ~15 h reproducing a curve we already know is
    measured with the wrong instrument. Use `rize_curve_full_l1` instead. The group is kept
    because its ids appear in the plan and in ABLATION.md's threat list, and because deleting a
    declared group silently changes what `build_experiment_grid(None)` returns.


    Stage 1 fixes pooling at all five provinces and varies the loss, so the headline criterion is
    chosen once on a comparison where nothing else moves. Stage 2 fixes that criterion and varies
    pooling. Running the full cross product would multiply cost for no extra claim.

The `loss` argument is what connects the two stages. Left None, stage 2 runs at the
    ExperimentConfig default ("mse") -- which is what the `_b1` group did, before stage 1 had
    been run and therefore before its answer was known. Stage 1 selected `mae`, so the
    `rize_curve_l1` group passes it explicitly and is the version of the curve that actually
    follows its own two-stage design. The `_b1` curve is kept as-is: it is a real measurement
    under a different criterion, and deleting it would discard the only evidence about how much
    the criterion moves the curve.

    `fidelity` and `suffix` exist so a reduced-cost replica of the whole study is provably the
    same study: the arms, provinces, scopes and seeds come from the same code, and only the
    fidelity dict and the id suffix differ.
    """
    configs = []

    # Stage 1 -- loss selection, all five provinces, one axis moving. Skipped when the criterion
    # has already been selected and only the curve is being re-run.
    if include_stage1:
        for stage1_loss in ("mse", "mae", "huber"):
            configs.append(
                ExperimentConfig(
                    experiment_id=f"abl_loss_{stage1_loss}_s42{suffix}",
                    loss_function=stage1_loss, seed=42, **fidelity,
                )
            )

    # Stage 2 -- the curve. Seeds: the two endpoints carry the headline claim and get three each,
    # since a one-seed gap between two arms is not evidence; the intermediate arms are mechanism
    # evidence about the SHAPE of the curve and get one.
    for suffix_arm, kept, scope in (arms if arms is not None else RIZE_CURVE_ARMS):
        excluded = [c for c in CITIES if c not in kept]
        if seeds_override is not None:
            seeds = seeds_override
        else:
            seeds = ABLATION_SEEDS if suffix_arm in ("solo", "all5") else (42,)
        for seed in seeds:
            configs.append(
                ExperimentConfig(
                    experiment_id=f"abl_rize_{suffix_arm}_s{seed}{suffix}",
                    training_scope=scope,
                    excluded_cities=excluded,
                    seed=seed,
                    **({"loss_function": loss} if loss else {}),
                    **extra,
                    **fidelity,
                )
            )
    return configs


def _rize_curve_b1_configs() -> list:
    """The same twelve arms at the reduced fidelity that fits this host. See ABLATION_B1."""
    return _rize_curve_configs(ABLATION_B1, suffix="_b1")


def _rize_curve_l1_configs() -> list:
    """Stage 2 re-run under L1 -- the criterion stage 1 actually selected -- with three seeds
    on every arm.

    Two reasons this supersedes the `_b1` curve rather than merely extending it.

    The criterion moves Rize further than pooling does. Stage 1 measured, on the same five
    provinces, Rize daylight RMSE 112.88 under MSE against 109.56 under L1 -- 3.3 W/m2. The
    pooling effect the curve exists to measure is 1.5 W/m2. Reading a 1.5 W/m2 effect through an
    instrument that a criterion change moves by 3.3 is measuring with the wrong instrument, and
    the criterion is a free choice while the pooling effect is the finding.

    Every arm gets three seeds, not just the endpoints. In the `_b1` curve H2 -- the claim that
    WHICH province is added matters, which is the study's actual positive result -- rested on two
    single-seed arms (plus_ankara 109.80 vs plus_antalya 119.66). A 9.86 W/m2 gap against a
    seed spread of 2.15 is suggestive, but the finding the paper leans on should not be the one
    with no replication. The intermediate arms are no longer only shape evidence.
    """
    return _rize_curve_configs(
        ABLATION_B1, suffix="_l1", loss="mae",
        seeds_override=ABLATION_SEEDS, include_stage1=False,
    )


def _rize_curve_full_l1_configs() -> list:
    """The curve at full fidelity (B=8, T=100) under L1. The run the paper's table comes from.

    Everything measured so far is B=1, which is the sanctioned fast path but removes the
    bootstrap component of the UQ layer entirely: those arms' CP/PINW/MPIW/CWC are MC-Dropout
    only. This group is the first time the interval metrics are produced by the method the
    methodology actually describes -- Bootstrap Ensemble x MC-Dropout, |P| = B*T = 800 -- so
    it is the first run whose interval numbers may be quoted.

    It also strengthens H1. The B=1 curve puts the solo-vs-all5 gap at -5.11 W/m2, p = 0.037 on
    three seeds; a claim resting on three single-replica runs is thinner than the compute now
    available justifies.

    Cost, from the unit costs in ABLATION_B1's comment and the 18-39 epochs early stopping
    actually used (so ~25 epochs), at B=8 both training and the 800 MC passes scale:

        arm             per arm      x3 seeds
        solo             ~22 min      ~66 min
        plus_ankara      ~43 min     ~129 min
        plus_antalya     ~43 min     ~129 min
        minus_antalya    ~88 min     ~264 min
        all5            ~110 min     ~330 min
                                    ~15.3 h   on the CPU host; ~7 h at the 2.17x MPS speedup
                                              measured in ABLATION.md 1.11

    MEMORY IS THE REAL RISK, not time. At B=8 x T=100 the pooled prediction array for a
    five-province arm is 800 x 44,155 x 24 float32 = 3.4 GB, and this is precisely what killed
    `config_002_default_full` before metrics.py was chunked. Peak is ~4 GB now, but on a 16 GB
    Mac that pool shares unified memory with the MPS backend. Run ONE all5 arm first: it is the
    largest and the only one that can fail this way, so it is the correct canary even though it
    is not the cheapest. `--skip-existing` means a successful canary is not repeated work.

    Not repeated at this fidelity: stage 1. The criterion is settled (10.1.1) and re-running it
    at B=8 would cost 5.5 h to re-answer a question already answered on a clean one-axis
    comparison.
    """
    return _rize_curve_configs(
        ABLATION_FULL, suffix="_full", loss="mae",
        seeds_override=ABLATION_SEEDS, include_stage1=False,
    )


# Three more seeds for the full-fidelity curve. Same ids scheme and same `_full` suffix as
# rize_curve_full_l1, so the two groups' arms pool directly into one n=6 sample.
EXTRA_SEEDS = (45, 46, 47)


def _rize_curve_full_seeds_configs() -> list:
    """Seeds 45-47 of the full-fidelity curve. Power, not a new question.

    At n = 3 the paired t-test has two degrees of freedom, and that -- not the effect size --
    is what stops H1. The paired differences are [-1.98, -3.65, -0.51], mean -2.05, sd 1.57:

        n = 3   SE 0.907   t = -2.26   p = 0.153
        n = 6   SE 0.641   t = -3.19   p = 0.024
        n = 9   SE 0.524   t = -3.91   p = 0.0045

    So n = 6 is the point where H1 clears 0.05 as a single test, assuming the spread holds.

    It does NOT clear Benjamini-Hochberg over the four contrasts of ABLATION.md 3.3, which
    would need n = 9. The answer to that is not three times the compute -- it is that those
    four are not co-primary. H1 is the paper's claim; minus_antalya-vs-all5 and the rest are
    exploratory observations that came out of looking at the curve. Pre-specifying H1 as the
    primary endpoint and reporting the others as exploratory, without significance claims, is
    both standard and the honest description of how they arose. The four-way correction in 3.3
    was over-conservative for treating them as equals.

    All five arms are declared so the choice of how far to go is operational. Priority order,
    with measured per-arm costs on the Mac at B=8:

        solo (~9 min) + all5 (~42 min), 3 seeds each   ~2.5 h   <- the H1 contrast, run this
        minus_antalya (~33 min), 3 seeds               +1.7 h      the strongest exploratory one
        the two pair arms (~16 min each), 3 seeds      +1.6 h      H2, currently 2/3 and p=0.30
    """
    return _rize_curve_configs(
        ABLATION_FULL, suffix="_full", loss="mae",
        seeds_override=EXTRA_SEEDS, include_stage1=False,
    )


# --- Architecture sweep -------------------------------------------------------------------
#
# Nothing in the ledger has ever varied the architecture: every LSTM row is hidden_sizes=[64,32],
# lookback_hours=24, dropout_rate=0.3. These are first guesses inherited from the plan, not
# measurements.
#
# One axis at a time from the current default, never a cross product: 3 x 3 x 3 would be 27
# configs x 3 seeds for a question that does not need interaction terms answered.
#
# The incumbent is NOT re-run. abl_rize_all5_s{42,43,44}_l1 already is [64,32] / 24 / 0.3 at this
# exact fidelity, criterion and province set, so it is the baseline these are compared against --
# which is also why early_stop_patience stays at 15 despite ABLATION.md T-14 showing that best
# epochs land at 3-9 and the patience wastes most of the wall clock. Lowering it here would make
# the sweep incomparable with the baseline it is measured against. Lower it AFTER the winner is
# chosen, as its own one-axis change.
ARCH_SWEEP_AXES = [
    # (id fragment,      overrides)
    ("h32x16",           {"hidden_sizes": [32, 16]}),
    ("h128x64",          {"hidden_sizes": [128, 64]}),
    ("h64x64x32",        {"hidden_sizes": [64, 64, 32]}),
    ("lookback48",       {"lookback_hours": 48}),
    ("lookback72",       {"lookback_hours": 72}),
    ("dropout02",        {"dropout_rate": 0.2}),
    ("dropout04",        {"dropout_rate": 0.4}),
]


def _arch_sweep_configs() -> list:
    """Seven one-axis departures from the default, three seeds each, on the all5 arm.

    SELECT ON `best_val_loss`, NOT ON THE TEST METRIC. Choosing an architecture by its test
    score folds the test set into model selection and makes the reported test performance
    optimistic -- the same class of error as scaler leakage, and easier to miss because nothing
    crashes. The ledger carries best_val_loss for exactly this. Test rows for the losing
    configurations exist but must not be read as results.

    Two axes need reading with care, and neither is a reason not to sweep them:

    `lookback_hours` changes the windows themselves. A 48- or 72-hour lookback needs a longer
    contiguous span, so more windows straddle a split boundary and are dropped, and the
    validation set is a slightly smaller subset. best_val_loss is a per-element mean so the
    comparison is still meaningful, but it is not scored on an identical set the way the other
    two axes are. Check n_samples alongside it.

    `dropout_rate` is not only a regulariser here: it is the ONLY source of MC-Dropout
    randomness (a project invariant), so changing it changes the width of every predictive
    interval. Selecting it on validation loss optimises point accuracy alone. Whatever value
    wins, its CP must be checked before it is adopted -- ABLATION.md 3.5 has four provinces
    already over-covering at 0.981-0.984, so a larger dropout would push them further out.

    Cost: 7 configs x 3 seeds at B=1 on the all5 split, ~400 s each on the Mac, ~2.3 h.
    B=1 rather than B=8 because selection reads best_val_loss, which is per model and needs no
    ensemble; three seeds give the spread that tells a real difference from init noise.
    """
    configs = []
    for fragment, overrides in ARCH_SWEEP_AXES:
        for seed in ABLATION_SEEDS:
            configs.append(
                ExperimentConfig(
                    experiment_id=f"abl_arch_{fragment}_s{seed}",
                    loss_function="mae",
                    seed=seed,
                    **{**ABLATION_B1, **overrides},
                )
            )
    return configs


# Completing the sweep. Restructured after ABLATION_REVIEW.md, which found that the capacity
# ladder is confounded with the learning-rate schedule.
#
# THE CONFOUND. `best_epoch` falls monotonically as capacity rises: [32,16] -> 12,
# [64,64,32] -> 10, dropout0.2 -> 8, [128,64] -> 3. With `lr_reduce_patience=7`, the learning
# rate never dropped before the winner reached its own optimum -- so no arm on the ladder ever
# entered a refinement phase, and [256,128] at lr=1e-3 would very likely peak at epoch 1-2.
# Run that way, the ladder measures "which model gets furthest before overfitting at 1e-3",
# not capacity. A [256,128] arm at the default lr could therefore come back WORSE and we would
# wrongly conclude the ladder had turned over.
#
# So the extension is staged: settle whether the learning rate matters first, cheaply, then
# extend the ladder at whichever rate wins.
ARCH_SWEEP_X_AXES = [
    # The incumbent, re-run under its own id. abl_rize_all5_s*_l1 IS this configuration and is
    # already comparable on the TEST metrics -- all thirteen config fields match -- but those
    # rows predate the best_val_loss column and their logs recorded the last epoch's loss
    # rather than the best. This buys the missing selection statistic, nothing else. It doubles
    # as a determinism check: its test metrics must reproduce the _l1 arms'.
    ("base",            {}),
    # One axis from the incumbent: does a lower rate help at all, given nothing ever refined?
    ("lr3e4",           {"learning_rate": 3e-4}),
    # Deliberately TWO axes from the incumbent, and not part of the one-axis screen: the
    # question is an interaction. Testing the rate only at [64,32] cannot say whether the
    # ladder's leader improves when it is allowed to refine, and that is what decides how the
    # ladder is extended.
    ("h128x64_lr3e4",   {"hidden_sizes": [128, 64], "learning_rate": 3e-4}),
]

# Conditional on the stage above; declared now so the ids are fixed and reviewable.
ARCH_FRONTIER_AXES = [
    ("h256x128",        {"hidden_sizes": [256, 128]}),
    ("h256x128_lr3e4",  {"hidden_sizes": [256, 128], "learning_rate": 3e-4}),
    # The accuracy-vs-coverage frontier probe. Every one-axis departure so far lands on a single
    # CP-vs-log(MPIW) curve per province: coverage is a pure function of interval width, and
    # nothing has moved the frontier itself. This cell asks whether the extra capacity plus more
    # dropout can buy back the coverage that capacity alone gives up -- i.e. whether the frontier
    # moves at all, or whether only the bootstrap component can move it.
    ("h128x64_do04",    {"hidden_sizes": [128, 64], "dropout_rate": 0.4}),
]


def _arch_configs(axes: list) -> list:
    """Shared builder: same fidelity, criterion, province set and patience as `arch_sweep`, so
    every configuration lands in one comparable table. Selection is on `best_val_loss`."""
    return [
        ExperimentConfig(
            experiment_id=f"abl_arch_{fragment}_s{seed}",
            loss_function="mae",
            seed=seed,
            **{**ABLATION_B1, **overrides},
        )
        for fragment, overrides in axes
        for seed in ABLATION_SEEDS
    ]


def _arch_sweep_x_configs() -> list:
    """Stage 1 of the extension: the missing baseline plus the learning-rate question. ~55 min."""
    return _arch_configs(ARCH_SWEEP_X_AXES)


def _arch_frontier_configs() -> list:
    """Stage 2: extend the ladder at the winning rate, and probe the coverage frontier. ~85 min.

    Run AFTER arch_sweep_x. If the rate turns out not to matter, only the `h256x128` arm is
    needed and `h256x128_lr3e4` is redundant; if it does matter, the reverse. Both are declared
    so the choice is a `--only` away rather than an edit.

    ANSWERED, 2026-08-29 (ABLATION.md 4.5, B-3): the rate does not matter. 1e-3 -> 3e-4 moves
    best_epoch 4.3 -> 14.0 at [128,64] -- so the mechanism is real, the model genuinely trains
    past the point the default rate stopped at -- and lands in the same place (val_loss
    -0.0016, p = 0.175; test RMSE +0.62, p = 0.338). At [64,32] likewise (p = 0.33 / 0.81).
    The "the ladder only looks monotone because no arm reached its refinement stage" confound
    is therefore measured and dead, and [256,128] can be read at the default rate.

    So run six of the nine, and hold the other three:

        --group arch_frontier --only \
            abl_arch_h256x128_s42 abl_arch_h256x128_s43 abl_arch_h256x128_s44 \
            abl_arch_h128x64_do04_s42 abl_arch_h128x64_do04_s43 abl_arch_h128x64_do04_s44

    Run `h256x128_lr3e4` only if `h256x128` LOSES to `[128,64]` on best_val_loss. A win needs
    no explanation; a loss is the one result the optimizer could still be faking, because
    [256,128] is another doubling past the capacity where best_epoch was already 4.
    """
    return _arch_configs(ARCH_FRONTIER_AXES)


# The transfer curve has one endpoint. The paper claims pooling helps every province and has
# tested the one where it was most likely to work -- Rize, the cloudiest and least predictable.
# ABLATION_REVIEW.md makes the risk concrete: the [64,32] -> [128,64] capacity gain is
# -3.5 to -6.3 W/m2 in the four Anatolian provinces and -0.40 (p = 0.88) in Rize, so nearly all
# the learnable signal lives in the four, and pooling may well cost them what it buys Rize.
#
# RUN, 2026-08-29 (ABLATION.md 5): it does not cost them. Pooling wins in all five provinces
# and in 15 of 15 seed-arms; the redistribution scenario below did not happen. Kept as the
# definition of record -- the arms are what the paper's "every province" sentence rests on.
PERCITY_ENDPOINT_CITIES = [c for c in CITIES if c != RIZE]


def _percity_endpoints_configs() -> list:
    """A `solo` arm for each of the other four provinces, at full fidelity. ~1.8 h.

    Each is that province trained alone, scored on its own test windows, against the same
    province's row in the existing all5 arms -- the identical contrast H1 uses for Rize. Both
    outcomes are publishable and the negative one is the more interesting paper: if the four
    lose what Rize gains, the finding is that the global model REDISTRIBUTES accuracy toward
    the data-poor regime rather than improving everything, which is a sharper claim than
    "pooling helps" and one the referee cannot get to first.
    """
    return [
        ExperimentConfig(
            experiment_id=f"abl_percity_{city.lower()}_s{seed}_full",
            training_scope="per_city",
            excluded_cities=[c for c in CITIES if c != city],
            loss_function="mae",
            seed=seed,
            **ABLATION_FULL,
        )
        for city in PERCITY_ENDPOINT_CITIES
        for seed in ABLATION_SEEDS
    ]


def _target_transform_configs() -> list:
    """Regress the clearness index instead of the irradiance. 3 arms, ~2.0 h.

    ABLATION.md 3.6 measured the gap this asks about: the LSTM wins daylight RMSE in all five
    provinces and LOSES daylight MAE in four of them, to smart persistence. The mechanism is
    that the naive rules are handed the target hour's clear-sky envelope for free -- smart
    persistence multiplies the carried-forward kt by CLRSKY(t+h), the climatology cell memorises
    the same geometry -- while the model has to infer the geometry from hour_sin/cos and the
    day-of-year encoding. This arm hands the model the same thing without making CLRSKY a
    feature: it regresses kt = ALLSKY / CLRSKY and the transform multiplies the envelope back.

    CLRSKY is pure astronomy with no weather term, computable from latitude, longitude and time,
    so admitting it through the transform is not leakage. Measured before implementing: daylight
    CLRSKY has a floor of 2.40 W/m^2 so the division never blows up, and kt has median 0.885 and
    p99 = 1.000 with exactly one value above 1.5 (the documented Van back-fill artefact). No
    clipping is applied.

    THE MATCHED RAW ARM ALREADY EXISTS and is not rebuilt here: abl_rize_all5_s{42,43,44}_full
    is this same dict with target_transform="raw", which was the only behaviour available when
    it ran. The assertion below proves the pair differs in that one field and nothing else,
    which is what the comparability rules actually require -- rerunning an identical config
    under a new id to satisfy the letter of "build both from one dict" would cost two hours and
    add a duplicate row.

    Two effects travel together on this axis and cannot be separated by adding an arm, because
    they are the same change: the target definition, and the loss weighting it implies (in kt
    space a cloudy noon hour and a clear morning hour carry comparable weight, where in W/m^2
    the high-irradiance hours dominate). State it; do not pretend the arm isolates one of them.
    """
    return _target_kt_pooled(ABLATION_SEEDS)


TARGET_KT_BASE = {**ABLATION_FULL, "loss_function": "mae", "target_transform": "clearsky_index"}


def _target_kt_pooled(seeds) -> list:
    """The pooled (all5) kt arms, at the given seeds. Split out so stage 2 can extend the seed
    axis under the same ids rather than duplicating the definition."""
    base = {**ABLATION_FULL, "loss_function": "mae"}
    configs = [
        ExperimentConfig(
            experiment_id=f"abl_target_kt_s{seed}_full",
            target_transform="clearsky_index",
            seed=seed,
            **base,
        )
        for seed in seeds
    ]
    for cfg, seed in zip(configs, seeds):
        raw = ExperimentConfig(experiment_id=f"abl_rize_all5_s{seed}_full", seed=seed, **base)
        differing = {
            f.name for f in fields(ExperimentConfig)
            if f.name != "experiment_id" and getattr(cfg, f.name) != getattr(raw, f.name)
        }
        assert differing == {"target_transform"}, differing
    return configs


def _target_kt_h1_configs() -> list:
    """Stage 1: does the pooling result survive the target transform? 3 arms, ~0.7 h.

    MEASURED (target_transform group, ABLATION.md 6): regressing kt beats raw at full fidelity
    in every province, aggregate daylight RMSE -9.2% and MAE -12.9%, p <= 0.008 throughout. That
    makes it a candidate for the headline configuration -- and the entire transfer result
    (sections 1-5, H1 and the endpoint ablation) was measured under target_transform="raw".

    It cannot be assumed to carry over, and the direction of the doubt is specific: a large part
    of what a "raw" model must learn is the solar-geometry envelope, which is the structure most
    obviously SHARED across the five provinces -- i.e. plausibly the very thing pooling was
    helping with. Handing that envelope to the model for free could shrink the transfer gain, or
    remove it. That would be a genuine threat to the paper's headline claim, so it gets measured
    before anything is rewritten, not after.

    Only the solo arm is built: abl_target_kt_s{42,43,44}_full is already the matched pooled arm
    at the same seeds. Three seeds is enough to see whether the effect survives; extending to the
    six the primary endpoint uses is stage 2, and only worth paying for if it does.
    """
    return [
        ExperimentConfig(
            experiment_id=f"abl_target_kt_solo_s{seed}_full",
            training_scope="per_city",
            excluded_cities=[c for c in CITIES if c != RIZE],
            seed=seed,
            **TARGET_KT_BASE,
        )
        for seed in ABLATION_SEEDS
    ]


def _target_kt_full_configs() -> list:
    """Stage 2: the whole transfer result re-established under kt. 18 arms, ~6 h.

    Run ONLY if stage 1 shows the pooling gain surviving. Brings H1 to the same six seeds as the
    raw primary endpoint (sections 3.2) and repeats the five-province endpoint ablation
    (section 5), so every claim the paper makes about transfer is available under whichever
    target transform ends up being the headline.

    Costed from the measured stage-0 arms: a pooled kt run took 3508-3945 s against raw's 2337 s,
    because the kt model early-stops later (best_epoch 21-28 against raw's single digits) rather
    than because a step is slower. Solo arms are roughly a fifth of that.
    """
    configs = _target_kt_pooled(EXTRA_SEEDS)
    configs += [
        ExperimentConfig(
            experiment_id=f"abl_target_kt_solo_s{seed}_full",
            training_scope="per_city",
            excluded_cities=[c for c in CITIES if c != RIZE],
            seed=seed,
            **TARGET_KT_BASE,
        )
        for seed in EXTRA_SEEDS
    ]
    configs += [
        ExperimentConfig(
            experiment_id=f"abl_target_kt_percity_{city.lower()}_s{seed}_full",
            training_scope="per_city",
            excluded_cities=[c for c in CITIES if c != city],
            seed=seed,
            **TARGET_KT_BASE,
        )
        for city in PERCITY_ENDPOINT_CITIES
        for seed in ABLATION_SEEDS
    ]
    return configs


def _sens_scaler_l1_configs() -> list:
    """The control for the confound most likely to be producing H1's null result.

    The `solo` arm trains on Rize alone with its own target scaler (per_city_scaler defaults to
    True), so its loss is normalised to Rize's own variance. The pooled arms fit one scaler over
    all five provinces -- and Rize is the LOW-variance province (sigma 231.5 against the pooled
    ~280), so in scaled space its targets carry roughly a third less weight than Van's. Under any
    mean-seeking loss the pooled model therefore under-weights exactly the province the curve is
    scored on. The comparison is built against the pooled arm, which is the direction that
    manufactures a null.

    This arm is `solo` with per_city_scaler=False: Rize alone, but scaled by the pooled scaler.
    If the solo advantage shrinks here, part of H1's null was a scaling artefact rather than an
    absence of transfer. Three seeds, because a one-seed control cannot rule anything out. Same
    L1 criterion and fidelity as the curve it controls, so it differs on one axis only.
    """
    arms = [a for a in RIZE_CURVE_ARMS if a[0] == "solo"]
    configs = _rize_curve_configs(
        ABLATION_B1, suffix="_globalscaler_l1", loss="mae", arms=arms,
        seeds_override=ABLATION_SEEDS, include_stage1=False, per_city_scaler=False,
    )
    assert all(c.per_city_scaler is False for c in configs)
    return configs


def _device_parity_configs() -> list:
    """Two byte-identical configs under two ids, to be run on two backends.

    An audit raised an unverified claim that nn.LSTM's inter-layer dropout diverges between MPS
    and CPU. Unverified is not the same as false, and the exposure is real: hidden_sizes=[64, 32]
    builds nn.LSTM(num_layers=2, dropout=0.3), and that dropout is one of the MC-Dropout noise
    sources at inference -- so the metrics most exposed would be the interval ones the paper is
    about. Failure here does not crash, it returns different numbers.

    Rather than trusting or dismissing the claim, measure it. Run `abl_parity_cpu_s42` with
    MERVE_DEVICE=cpu and `abl_parity_mps_s42` with MERVE_DEVICE=mps; identical configs and
    identical seeds mean any metric difference is the backend. The ids state the intent and the
    ledger's `device` column records what actually happened, so running both on one device makes
    the check visibly void instead of silently meaningless.

    Rize alone at T=100: the cheapest arm that still exercises the two-layer LSTM and the full
    MC-Dropout pass count.
    """
    arms = [a for a in RIZE_CURVE_ARMS if a[0] == "solo"]
    configs = []
    for tag in ("cpu", "mps"):
        [config] = _rize_curve_configs(
            ABLATION_B1, suffix=f"_PARITY_{tag}", loss="mae", arms=arms,
            seeds_override=(42,), include_stage1=False,
        )
        config.experiment_id = f"abl_parity_{tag}_s42"
        configs.append(config)
    return configs


def _rize_curve_smoke_configs() -> list:
    """Two arms, smoke fidelity, only to prove the exclusion code paths before the real sweep."""
    arms = [a for a in RIZE_CURVE_ARMS if a[0] in RIZE_SMOKE_ARMS]
    configs = _rize_curve_configs(
        {**ABLATION_FULL, **ABLATION_SMOKE}, suffix="_smoke", arms=arms, seeds_override=(42,)
    )
    # Stage 1 needs no smoke: the pooled five-province path is already exercised by the
    # `smoke` group. Keep only the curve arms.
    return [c for c in configs if c.experiment_id.startswith("abl_rize_")]


EXPERIMENT_GROUPS = {
    "smoke": _smoke_configs,
    "main": _main_configs,
    "ablation": _ablation_configs,
    "rize_curve": _rize_curve_configs,
    "rize_curve_b1": _rize_curve_b1_configs,
    "rize_curve_l1": _rize_curve_l1_configs,
    "rize_curve_full_l1": _rize_curve_full_l1_configs,
    "rize_curve_full_seeds": _rize_curve_full_seeds_configs,
    "arch_sweep": _arch_sweep_configs,
    "arch_sweep_x": _arch_sweep_x_configs,
    "arch_frontier": _arch_frontier_configs,
    "percity_endpoints": _percity_endpoints_configs,
    "target_transform": _target_transform_configs,
    "target_kt_h1": _target_kt_h1_configs,
    "target_kt_full": _target_kt_full_configs,
    "sens_scaler_l1": _sens_scaler_l1_configs,
    "device_parity": _device_parity_configs,
    "rize_curve_smoke": _rize_curve_smoke_configs,
}


def build_experiment_grid(groups: list | None = None) -> list:
    """All groups in declaration order, or just the named ones. Raises on a duplicate id."""
    names = list(EXPERIMENT_GROUPS) if groups is None else list(groups)
    unknown = [n for n in names if n not in EXPERIMENT_GROUPS]
    if unknown:
        raise ValueError(f"unknown group(s) {unknown}; available: {list(EXPERIMENT_GROUPS)}")

    configs = [c for name in names for c in EXPERIMENT_GROUPS[name]()]
    ids = [c.experiment_id for c in configs]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate experiment_id(s) in the grid: {duplicates}")
    return configs


if __name__ == "__main__":
    for group, builder in EXPERIMENT_GROUPS.items():
        print(f"[{group}]")
        for config in builder():
            print(f"  {config.experiment_id}")
