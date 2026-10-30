"""Enumerates the ExperimentConfig sweep, in named groups.

The tuning programme is sequential: each stage starts from the previous stages' decisions,
recorded in DECISIONS below after the stage's validation results are analysed. A stage whose
prerequisites are undecided raises StageNotReady when selected, so it cannot be run (or
listed) on a guessed base. The plan, its rationale and the run commands are in
outputs/tuning/TUNING_PLAN.md.

Rules every stage follows:
- Selection is on the VALIDATION split (ledger columns val_*). Test metrics are recorded but are
  not used for any choice; scripts/15_tuning_report.py does not print them.
- Three seeds per arm (TUNE_SEEDS). FINDINGS on training dynamics put epoch-selection noise near
  4 W/m^2 for one network, so a one-seed difference is not evidence.
- An arm that is identical to an earlier stage's winner is not rerun: stage_arms() lists the
  earlier runs under the new stage's label, and the report reads them from there.
- Grids are centred on the incumbent (the config_005_default_full values) with steps coarse
  enough that a difference can exceed seed noise.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merve_solar.config import ExperimentConfig

TUNE_SEEDS = (42, 43, 44)
FINAL_SEEDS = (42, 43, 44, 45, 46)

# The incumbent, i.e. config_005_default_full, with the LSTM depth written out (hidden_sizes
# [64, 32] has always meant two stacked LSTM layers of 64 plus a 32-unit head).
INCUMBENT = dict(
    lookback_hours=24, hidden_sizes=[64, 32], lstm_layers=2, dropout_rate=0.3,
    learning_rate=1e-3, bootstrap_block_length=168, n_bootstrap=8, mc_dropout_passes=100,
)

# Point-structure stages (S1-S3) run one network, no resampling, and are judged on point
# accuracy; the uncertainty stages (S4-S5) run the full ensemble and are judged on CRPS.
SCREEN_FIDELITY = dict(n_bootstrap=1, mc_dropout_passes=100)
FULL_FIDELITY = dict(n_bootstrap=8, mc_dropout_passes=100)
# Early-stopping patience from S4 on (S1-S3 keep the default 10). No 256-wide network in S2-S3
# (18 of them) would have kept a different epoch at patience 5; the longest wait for a new best
# was 4 epochs. Decided after S3 from <stage>_patience.csv (TUNING_FINDINGS.md).
FROZEN_PATIENCE = 5

STAGE_CRITERION = {
    "s1": "val_RMSE_daylight", "s2": "val_RMSE_daylight", "s3_dropout": "val_RMSE_daylight",
    "s3_lr": "val_RMSE_daylight", "s4": "val_CRPS_daylight", "s5": "val_CRPS_daylight",
}

# Filled in after each stage is analysed, and committed with the analysis.
DECISIONS = {
    "s1": 24,            # lookback_hours; incumbent kept: 48 h and 72 h both worse on val RMSE (+0.9, +1.1 W/m^2)
    "s2": (256, 1),      # (lstm_hidden, lstm_layers); -9.51 W/m^2 vs 64x2, -1.61 +/- 0.59 vs 128x1; width search stopped here on cost (TUNING_FINDINGS.md)
    "s3_dropout": 0.2,   # dropout_rate; -1.33 +/- 0.36 W/m^2 vs 0.3, CRPS unchanged (-0.08); 0.1 is as accurate but CRPS +2.0
    "s3_lr": 5e-4,       # learning_rate; passes the rule marginally (-0.99 +/- 0.96 W/m^2, measured at dropout 0.3); accepted as written, combination untested (TUNING_FINDINGS.md)
    "s4": 168,           # bootstrap_block_length; incumbent kept: all four blocks within 0.15 W/m^2 val CRPS (best 240 h, -0.15 +/- 0.18)
    "s5": (6, 100),      # (n_bootstrap, mc_dropout_passes); B=6 by the rule (cheapest within one seed sd of (16, 150)); T=100 not 50: passes cost inference only, 600 draws steady the 2.5/97.5 percentiles (+0.24 +/- 0.20 W/m^2 vs best)
}

# --- grids ---------------------------------------------------------------------------------------

# Lookback in whole days. Below 24 h a window issued at night contains no daylight at all, and
# 24 h is the incumbent, so the grid can only extend upwards.
LOOKBACK_GRID = (24, 48, 72)
# LSTM width doubles per step around 64; depth around the incumbent's 2 layers. The head is
# always one hidden layer of half the LSTM width, as in the incumbent.
HIDDEN_GRID = (32, 64, 128)
LAYERS_GRID = (1, 2, 3)
# Added after the S2 report: 128 x 1 won at the corner of the grid (widest, shallowest), so one
# more width step at the winning depth checks whether the optimum lies beyond it. Depth is not
# extended: 1 layer was best at every width.
S2_EXTENSION = ((256, 1),)
DROPOUT_GRID = (0.1, 0.2, 0.3, 0.4, 0.5)
# A factor of two either side of 1e-3. A lower rate also spreads the optimum over more epochs,
# which makes the per-epoch early-stopping choice less coarse.
LR_GRID = (5e-4, 1e-3, 2e-3)
# Block length in hours of window starts. Windows whose starts are less than lookback + horizon
# apart share raw hours, and daily cloudiness anomalies stay autocorrelated for about 3 days
# (outputs/tuning/TUNING_PLAN.md), so the shortest block that keeps dependent samples together
# is the window span plus 3 days. The grid adds k whole days to the span, k centred on the
# incumbent's 168 h = 48 h span + 5 days at lookback 24.
BLOCK_EXTRA_DAYS = (3, 5, 8, 12)
HORIZON_HOURS = 24
# Ensemble size and MC passes come from ONE B=16 run per seed (scripts/14_ensemble_curves.py
# scores every sub-ensemble), so these grids cost no extra training.
ENSEMBLE_B_GRID = (4, 6, 8, 10, 12, 14, 16)
ENSEMBLE_T_GRID = (50, 75, 100, 125, 150)


def block_grid(lookback_hours: int) -> tuple:
    return tuple(lookback_hours + HORIZON_HOURS + 24 * k for k in BLOCK_EXTRA_DAYS)


class StageNotReady(RuntimeError):
    pass


def _need(*stages):
    missing = [s for s in stages if DECISIONS[s] is None]
    if missing:
        raise StageNotReady(f"decide {missing} in DECISIONS first (run the report for that stage)")


def _lr_tag(lr: float) -> str:
    return f"{lr:.0e}".replace("e-0", "e-")


def _cfg(experiment_id: str, seed: int, **fields) -> ExperimentConfig:
    return ExperimentConfig(experiment_id=f"{experiment_id}_s{seed}", seed=seed,
                            **{**INCUMBENT, **fields})


def _arm(prefix: str, seeds=TUNE_SEEDS, **fields) -> list:
    return [_cfg(prefix, seed, **fields) for seed in seeds]


def _arch(hidden: int, layers: int) -> dict:
    return dict(hidden_sizes=[hidden, hidden // 2], lstm_layers=layers)


# --- stages: arm label -> configs, including arms reused from an earlier stage --------------------

def _s1() -> dict:
    return {f"lb{L}": _arm(f"tune_s1_lb{L}", lookback_hours=L, **SCREEN_FIDELITY)
            for L in LOOKBACK_GRID}


def _s2() -> dict:
    _need("s1")
    L = DECISIONS["s1"]
    arms = {}
    for h, n in [(h, n) for h in HIDDEN_GRID for n in LAYERS_GRID] + list(S2_EXTENSION):
        label = f"h{h}l{n}"
        if (h, n) == (64, 2):
            arms[label] = _s1()[f"lb{L}"]
        else:
            arms[label] = _arm(f"tune_s2_lb{L}_{label}", lookback_hours=L, **_arch(h, n),
                               **SCREEN_FIDELITY)
    return arms


def _s2_winner() -> tuple[str, dict]:
    _need("s1", "s2")
    h, n = DECISIONS["s2"]
    return f"lb{DECISIONS['s1']}_h{h}l{n}", dict(lookback_hours=DECISIONS["s1"], **_arch(h, n))


def _s3_dropout() -> dict:
    tag, base = _s2_winner()
    winner = _s2()[f"h{DECISIONS['s2'][0]}l{DECISIONS['s2'][1]}"]
    return {f"do{d:.1f}": winner if d == INCUMBENT["dropout_rate"] else
            _arm(f"tune_s3_{tag}_do{int(round(d * 10)):02d}", dropout_rate=d, **base, **SCREEN_FIDELITY)
            for d in DROPOUT_GRID}


def _s3_lr() -> dict:
    tag, base = _s2_winner()
    winner = _s2()[f"h{DECISIONS['s2'][0]}l{DECISIONS['s2'][1]}"]
    return {f"lr{_lr_tag(lr)}": winner if lr == INCUMBENT["learning_rate"] else
            _arm(f"tune_s3_{tag}_lr{_lr_tag(lr)}", learning_rate=lr, **base, **SCREEN_FIDELITY)
            for lr in LR_GRID}


def _s3_winner() -> tuple[str, dict]:
    _need("s3_dropout", "s3_lr")
    tag, base = _s2_winner()
    d, lr = DECISIONS["s3_dropout"], DECISIONS["s3_lr"]
    return (f"{tag}_do{int(round(d * 10)):02d}_lr{_lr_tag(lr)}",
            dict(base, dropout_rate=d, learning_rate=lr, early_stop_patience=FROZEN_PATIENCE))


def _s4() -> dict:
    tag, base = _s3_winner()
    return {f"blk{blk}": _arm(f"tune_s4_{tag}_blk{blk}", bootstrap_block_length=blk, **base,
                              **FULL_FIDELITY)
            for blk in block_grid(base["lookback_hours"])}


def _s4_winner() -> tuple[str, dict]:
    _need("s4")
    tag, base = _s3_winner()
    return f"{tag}_blk{DECISIONS['s4']}", dict(base, bootstrap_block_length=DECISIONS["s4"])


def _s5() -> dict:
    tag, base = _s4_winner()
    return {"b16": _arm(f"tune_s5_{tag}_b16", **base, n_bootstrap=16, mc_dropout_passes=100)}


def _final() -> dict:
    """The frozen configuration at five seeds: the reference row of the paper.

    When the decided ensemble is the stage-4 fidelity (B=8, T=100) the stage-4 winner already
    holds seeds 42-44 of exactly this config, so only the remaining seeds are new runs.
    """
    _need("s5")
    tag, base = _s4_winner()
    b, t = DECISIONS["s5"]
    if (b, t) == (FULL_FIDELITY["n_bootstrap"], FULL_FIDELITY["mc_dropout_passes"]):
        reused = _s4()[f"blk{DECISIONS['s4']}"]
        new = _arm("final", seeds=FINAL_SEEDS[len(reused):], **base, **FULL_FIDELITY)
        return {"final": reused + new}
    return {"final": _arm("final", seeds=FINAL_SEEDS, **base, n_bootstrap=b, mc_dropout_passes=t)}


STAGES = {"s1": _s1, "s2": _s2, "s3_dropout": _s3_dropout, "s3_lr": _s3_lr, "s4": _s4,
          "s5": _s5, "final": _final}


def stage_arms(stage: str) -> dict:
    return STAGES[stage]()


def _new_runs(stage: str, prefix: str):
    """The configs a stage actually has to train: its arms minus those reused from earlier."""
    def build():
        return [c for configs in stage_arms(stage).values() for c in configs
                if c.experiment_id.startswith(prefix)]
    return build


# --- smoke --------------------------------------------------------------------------------------

SMOKE = dict(max_epochs=2, early_stop_patience=2, mc_dropout_passes=5)


def _smoke_configs() -> list:
    """Minutes on the real data. Exercises every code path the tuning and ablation runs use,
    so a crash surfaces before an overnight sweep rather than in it."""
    return [
        ExperimentConfig(experiment_id="smoke_global_b2", n_bootstrap=2, **SMOKE),
        ExperimentConfig(experiment_id="smoke_deterministic_b2", n_bootstrap=2,
                         inference_mode="deterministic", **{**SMOKE, "mc_dropout_passes": 1}),
        ExperimentConfig(experiment_id="smoke_seed_ensemble_b2", n_bootstrap=2,
                         bootstrap_resample=False, **SMOKE),
        ExperimentConfig(experiment_id="smoke_per_city_b1", n_bootstrap=1,
                         training_scope="per_city", **SMOKE),
        ExperimentConfig(experiment_id="smoke_lb48_h32l1", n_bootstrap=1, lookback_hours=48,
                         hidden_sizes=[32, 16], lstm_layers=1, **SMOKE),
    ]


EXPERIMENT_GROUPS = {
    "smoke": _smoke_configs,
    "tune_s1_lookback": _new_runs("s1", "tune_s1_"),
    "tune_s2_arch": _new_runs("s2", "tune_s2_"),
    "tune_s3_dropout": _new_runs("s3_dropout", "tune_s3_"),
    "tune_s3_lr": _new_runs("s3_lr", "tune_s3_"),
    "tune_s4_block": _new_runs("s4", "tune_s4_"),
    "tune_s5_ensemble": _new_runs("s5", "tune_s5_"),
    "final_reference": _new_runs("final", "final_"),
}


def build_experiment_grid(groups: list | None = None) -> list:
    """The named groups in declaration order, or every group that is ready when none is named.

    Naming a group whose prerequisites are undecided raises StageNotReady; with no names, such
    groups are skipped (so `--list` shows what can run now). Raises on a duplicate id.
    """
    names = list(EXPERIMENT_GROUPS) if groups is None else list(groups)
    unknown = [n for n in names if n not in EXPERIMENT_GROUPS]
    if unknown:
        raise ValueError(f"unknown group(s) {unknown}; available: {list(EXPERIMENT_GROUPS)}")

    configs = []
    for name in names:
        try:
            configs += EXPERIMENT_GROUPS[name]()
        except StageNotReady:
            if groups is not None:
                raise
    ids = [c.experiment_id for c in configs]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate experiment_id(s) in the grid: {duplicates}")
    return configs


if __name__ == "__main__":
    for group, builder in EXPERIMENT_GROUPS.items():
        try:
            ids = [c.experiment_id for c in builder()]
        except StageNotReady as exc:
            print(f"[{group}] not ready: {exc}")
            continue
        print(f"[{group}] {len(ids)} runs")
        for i in ids:
            print(f"  {i}")
