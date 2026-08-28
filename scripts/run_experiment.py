"""Run ONE experiment end-to-end.

    uv run python scripts/run_experiment.py --config configs/config_003.json

Axis overrides let a saved config be reused for one arm of a comparison without hand-editing a
second JSON file:

    uv run python scripts/run_experiment.py --config configs/config_000_smoke.json \
        --exclude-city Rize --experiment-id smoke_excl_rize
    uv run python scripts/run_experiment.py --config configs/config_000_smoke.json \
        --loss mae --experiment-id smoke_loss_mae

Any override requires --experiment-id: reusing the config's own id would overwrite that run's
output directory and leave a stale, now-misdescribed ledger row behind (see the comparability
rules in CLAUDE.md). Overrides are applied BEFORE run_experiment, so the config.json written
into the experiment directory is the effective one and the run stays reproducible from it alone.
"""
import argparse
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merve_solar.config import LOSS_FUNCTIONS, ExperimentConfig
from merve_solar.experiment import run_experiment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", required=True, help="Path to an ExperimentConfig JSON file")
    parser.add_argument("--exclude-city", action="append", metavar="NAME", dest="exclude_city",
                        help="repeatable; drop this province from train, val AND test")
    parser.add_argument("--loss", choices=list(LOSS_FUNCTIONS),
                        help="training criterion (default: whatever the config says)")
    parser.add_argument("--experiment-id", metavar="ID",
                        help="rename the run; REQUIRED whenever another override is given")
    return parser


def apply_overrides(config: ExperimentConfig, args: argparse.Namespace) -> ExperimentConfig:
    """A new config with the CLI overrides applied, or a clear refusal.

    dataclasses.replace re-runs __post_init__, so an unknown province name or a one-province
    exclusion is rejected here rather than after the run has started.
    """
    overrides = {}
    if args.exclude_city:
        overrides["excluded_cities"] = list(args.exclude_city)
    if args.loss:
        overrides["loss_function"] = args.loss

    if overrides and not args.experiment_id:
        raise SystemExit(
            f"refusing to run: {sorted(overrides)} overridden but no --experiment-id given.\n"
            f"  The run would be written to outputs/experiments/{config.experiment_id}/ and "
            f"appended to the ledger as {config.experiment_id!r}, overwriting that run's outputs "
            "and leaving a stale row that describes a different configuration.\n"
            "  Pass --experiment-id with a new, unused name."
        )
    if args.experiment_id:
        overrides["experiment_id"] = args.experiment_id
    return dataclasses.replace(config, **overrides) if overrides else config


def main():
    args = build_parser().parse_args()

    config = apply_overrides(ExperimentConfig.from_json(Path(args.config)), args)
    subsets = run_experiment(config)
    print(f"experiment_id={config.experiment_id}")
    if config.excluded_cities:
        print(f"  excluded: {config.excluded_cities_key}  active: {config.active_cities}")
    for subset, block in subsets.items():
        summary = "  ".join(
            f"{k}={block['aggregate'][k]:.4g}" for k in ("RMSE", "MAE", "R2", "CP")
        )
        print(f"  [{subset:9s}] {summary}")


if __name__ == "__main__":
    main()
