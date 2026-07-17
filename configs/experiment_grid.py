"""Enumerates the ExperimentConfig sweep — mirrors the source paper's Table 6/7
one-row-per-config sweep, plus the sequence-specific axes (lookback/horizon)
the paper's PCNN never had.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merve_solar.config import ExperimentConfig


def build_experiment_grid() -> list:
    configs = []

    # Fast sanity-check config: n_bootstrap=1 unifies "baseline" and "full ensemble"
    # into one code path (no resampling, still MC-Dropout-scored).
    configs.append(
        ExperimentConfig(
            experiment_id="config_000_smoke",
            n_bootstrap=1,
            max_epochs=5,
            mc_dropout_passes=10,
            early_stop_patience=3,
        )
    )

    # Architecture sweep (paper's Table 6 hidden-layer options: [32,16]/[64,32]/[128,64]).
    for i, hidden_sizes in enumerate([[32, 16], [64, 32], [128, 64]], start=1):
        configs.append(
            ExperimentConfig(
                experiment_id=f"config_{i:03d}_hidden_{'-'.join(map(str, hidden_sizes))}",
                hidden_sizes=hidden_sizes,
            )
        )

    # Lookback sweep — no precedent in PCNN, our own sequence-design axis.
    for lookback in [12, 24, 48]:
        configs.append(
            ExperimentConfig(experiment_id=f"config_lookback_{lookback}h", lookback_hours=lookback)
        )

    # Dropout sweep (paper's Table 6 dropout options).
    for dropout in [0.1, 0.2, 0.3]:
        configs.append(
            ExperimentConfig(experiment_id=f"config_dropout_{dropout}", dropout_rate=dropout)
        )

    # Split-ratio comparison: our default (full-seasonal-year test) vs. the paper's own 64/16/20.
    configs.append(
        ExperimentConfig(experiment_id="config_split_paper_64_16_20", train_ratio=0.64, val_ratio=0.16)
    )

    return configs


if __name__ == "__main__":
    for config in build_experiment_grid():
        print(config.experiment_id)
