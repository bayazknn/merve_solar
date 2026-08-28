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


def _rize_curve_configs() -> list:
    """The transfer curve, plus a loss-selection stage that must run first.

    Stage 1 fixes pooling at all five provinces and varies the loss, so the headline criterion is
    chosen once on a comparison where nothing else moves. Stage 2 fixes that criterion and varies
    pooling. Running the full cross product would multiply cost for no extra claim.
    """
    configs = []

    # Stage 1 -- loss selection, all five provinces, one axis moving.
    for loss in ("mse", "mae", "huber"):
        configs.append(
            ExperimentConfig(
                experiment_id=f"abl_loss_{loss}_s42", loss_function=loss, seed=42, **ABLATION_FULL
            )
        )

    # Stage 2 -- the curve. Seeds: the two endpoints carry the headline claim and get three each,
    # since a one-seed gap between two arms is not evidence; the intermediate arms are mechanism
    # evidence about the SHAPE of the curve and get one.
    for suffix, kept, scope in RIZE_CURVE_ARMS:
        excluded = [c for c in CITIES if c not in kept]
        seeds = ABLATION_SEEDS if suffix in ("solo", "all5") else (42,)
        for seed in seeds:
            configs.append(
                ExperimentConfig(
                    experiment_id=f"abl_rize_{suffix}_s{seed}",
                    training_scope=scope,
                    excluded_cities=excluded,
                    seed=seed,
                    **ABLATION_FULL,
                )
            )
    return configs


EXPERIMENT_GROUPS = {
    "smoke": _smoke_configs,
    "main": _main_configs,
    "ablation": _ablation_configs,
    "rize_curve": _rize_curve_configs,
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
