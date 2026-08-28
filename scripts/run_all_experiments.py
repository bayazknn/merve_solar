"""Run a selection of the sweep in configs/experiment_grid.py, appending to the ledger.

    uv run python scripts/run_all_experiments.py --list
    uv run python scripts/run_all_experiments.py --group smoke
    uv run python scripts/run_all_experiments.py --group ablation --skip-existing --continue-on-error
"""
import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "configs"))

from experiment_grid import EXPERIMENT_GROUPS, build_experiment_grid

from merve_solar.config import BASE_FEATURES_PATH
from merve_solar.data import load_base_features
from merve_solar.experiment import assert_ledger_schema_ok, run_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", action="append", choices=list(EXPERIMENT_GROUPS),
                        help="repeatable; default is every group")
    parser.add_argument("--only", nargs="+", metavar="ID",
                        help="run exactly these experiment_ids (intersected with --group if both given)")
    parser.add_argument("--list", action="store_true", help="print the selected ids and exit")
    parser.add_argument("--skip-existing", action="store_true",
                        help="skip configs that already have metrics/results_summary.csv, so an "
                             "interrupted sweep resumes instead of restarting")
    parser.add_argument("--continue-on-error", action="store_true",
                        help="keep going if one config raises, and report the failures at the end")
    return parser.parse_args()


def select_configs(args) -> list:
    configs = build_experiment_grid(args.group)
    if args.only:
        wanted = set(args.only)
        found = {c.experiment_id for c in configs}
        missing = sorted(wanted - found)
        if missing:
            raise SystemExit(f"--only ids not in the selected group(s): {missing}")
        configs = [c for c in configs if c.experiment_id in wanted]
    return configs


def main() -> None:
    args = parse_args()
    configs = select_configs(args)

    if args.skip_existing:
        # Keyed on results_summary.csv, not config.json: config.json is written BEFORE training
        # and the ledger row last, so a run that crashed mid-training reruns while a completed
        # one is skipped. That also enforces "never reuse an experiment_id" on its own.
        pending = [c for c in configs
                   if not (c.experiment_dir / "metrics" / "results_summary.csv").exists()]
        for config in configs:
            if config not in pending:
                print(f"skipping {config.experiment_id} (already has results)")
        configs = pending

    if args.list:
        for config in configs:
            print(config.experiment_id)
        return

    if not configs:
        print("nothing to run")
        return

    assert_ledger_schema_ok()  # once up front, before loading anything
    base_df = load_base_features(BASE_FEATURES_PATH)
    failures = []

    for i, config in enumerate(configs, start=1):
        excluded = config.excluded_cities_key or "none"
        print(f"\n[{i}/{len(configs)}] {config.experiment_id} "
              f"(scope={config.training_scope}, loss={config.loss_function}, "
              f"excluded={excluded}, seed={config.seed})")
        try:
            subsets = run_experiment(config, base_df=base_df)
        except Exception:
            if not args.continue_on_error:
                raise
            failures.append(config.experiment_id)
            print(f"  FAILED: {config.experiment_id}")
            traceback.print_exc()
            continue
        for subset, block in subsets.items():
            agg = block["aggregate"]
            print(f"  [{subset:9s}] RMSE={agg['RMSE']:.2f}  MAE={agg['MAE']:.2f}  "
                  f"R2={agg['R2']:.3f}  CP={agg['CP']:.3f}")

    if failures:
        print(f"\n{len(failures)} of {len(configs)} failed: {failures}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
