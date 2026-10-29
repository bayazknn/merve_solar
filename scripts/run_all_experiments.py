"""Run a selection of the sweep in configs/experiment_grid.py, appending to the ledger.

    uv run python scripts/run_all_experiments.py --list
    uv run python scripts/run_all_experiments.py --group smoke --ensemble-curves
    uv run python scripts/run_all_experiments.py --group tune_s1_lookback --skip-existing --continue-on-error
    uv run python scripts/run_all_experiments.py --group tune_s2_arch --shard 0/2 --skip-existing  # terminal 1
    uv run python scripts/run_all_experiments.py --group tune_s2_arch --shard 1/2 --skip-existing  # terminal 2

After a sweep, scripts/check_outputs.py --group <same groups> verifies that every run left all
its files and its ledger row before anything is committed.
"""
import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "configs"))

from experiment_grid import EXPERIMENT_GROUPS, StageNotReady, build_experiment_grid

from merve_solar.config import BASE_FEATURES_PATH
from merve_solar.data import load_base_features
from merve_solar.ensemble_curves import CURVES_FILE, write_ensemble_curves
from merve_solar.experiment import assert_ledger_schema_ok, missing_run_outputs, run_experiment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", action="append", choices=list(EXPERIMENT_GROUPS),
                        help="repeatable; default is every group")
    parser.add_argument("--only", nargs="+", metavar="ID",
                        help="run exactly these experiment_ids (intersected with --group if both given)")
    parser.add_argument("--ensemble-curves", action="store_true",
                        help="after each global MC-Dropout run, write metrics/ensemble_curves.csv "
                             "(scripts/14_ensemble_curves.py); needed by tune_s5_ensemble")
    parser.add_argument("--shard", metavar="I/N",
                        help="run only every N-th selected config starting at I (0-based), e.g. "
                             "0/2 and 1/2 in two terminals: disjoint halves of the same sweep")
    parser.add_argument("--list", action="store_true", help="print the selected ids and exit")
    parser.add_argument("--skip-existing", action="store_true",
                        help="skip configs that already have metrics/results_summary.csv, so an "
                             "interrupted sweep resumes instead of restarting")
    parser.add_argument("--continue-on-error", action="store_true",
                        help="keep going if one config raises, and report the failures at the end")
    return parser.parse_args()


def select_configs(args) -> list:
    try:
        configs = build_experiment_grid(args.group)
    except StageNotReady as exc:
        raise SystemExit(f"stage not ready: {exc}")
    if args.only:
        wanted = set(args.only)
        found = {c.experiment_id for c in configs}
        missing = sorted(wanted - found)
        if missing:
            raise SystemExit(f"--only ids not in the selected group(s): {missing}")
        configs = [c for c in configs if c.experiment_id in wanted]
    if args.shard:
        try:
            index, count = (int(x) for x in args.shard.split("/"))
        except ValueError:
            raise SystemExit(f"--shard must look like 0/2, got {args.shard!r}")
        if not 0 <= index < count:
            raise SystemExit(f"--shard index must be in [0, {count}), got {index}")
        # Sharded on the full selection, BEFORE --skip-existing, so each process keeps the same
        # half on a resume and two processes never pick the same config.
        configs = configs[index::count]
    return configs


def _wants_curves(config) -> bool:
    return config.training_scope == "global" and config.inference_mode == "mc_dropout"


def _write_curves(configs, base_df, failures, continue_on_error) -> None:
    """Curves for every finished run that lacks them, after the training loop."""
    for config in configs:
        if not _wants_curves(config) or config.experiment_id in failures:
            continue
        if (config.experiment_dir / CURVES_FILE).exists() or missing_run_outputs(config):
            continue
        try:
            write_ensemble_curves(config.experiment_id, base_df=base_df)
        except Exception:
            if not continue_on_error:
                raise
            failures.append(config.experiment_id)
            traceback.print_exc()


def main() -> None:
    args = parse_args()
    configs = select_configs(args)
    all_configs = list(configs)

    if args.skip_existing:
        # Keyed on the full output list, not config.json: config.json is written BEFORE training
        # and the ledger row last, so a run that crashed mid-way reruns while a completed one is
        # skipped. That also enforces "never reuse an experiment_id" on its own. A finished run
        # whose curves are missing only reruns the curves.
        pending = [c for c in configs if missing_run_outputs(c)]
        for config in configs:
            if config not in pending:
                print(f"skipping {config.experiment_id} (already has results)")
        configs = pending

    if args.list:
        for config in configs:
            print(config.experiment_id)
        return

    curve_targets = [c for c in all_configs if args.ensemble_curves and _wants_curves(c)
                     and not (c.experiment_dir / CURVES_FILE).exists()]
    if not configs and not curve_targets:
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

    if args.ensemble_curves:
        _write_curves(all_configs, base_df, failures, args.continue_on_error)

    if failures:
        print(f"\n{len(failures)} of {len(configs)} failed: {failures}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
