"""Emit results_by_city_horizon.csv for finished runs, from their saved predictions.

The pipeline reports per city (pooled over the horizon) and per horizon step (pooled over the
cities) but never the cross of the two, which is what the paper needs: how each province's
error and coverage grow with lead time, and the grid a per-(city, horizon) conformal factor
would be fitted on. Nothing is retrained -- this reads test_predictions.npz, which every run
already wrote.

Because that file is gitignored, this must run on the machine the experiment ran on.

    uv run python scripts/06_city_horizon_metrics.py --experiment-id abl_rize_all5_s42_full
    uv run python scripts/06_city_horizon_metrics.py --all --skip-missing
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from merve_solar.config import PROJECT_ROOT
from merve_solar.postprocess import CITY_HORIZON_FILENAME, prediction_path, write_city_horizon_table

LEDGER_PATH = PROJECT_ROOT / "outputs" / "experiments_ledger.csv"


def ledger_ids() -> list[str]:
    if not LEDGER_PATH.exists():
        raise SystemExit(f"no ledger at {LEDGER_PATH}")
    d = pd.read_csv(LEDGER_PATH)
    # The naive baselines have a single deterministic forecast and no npz; excluding them by
    # model_family rather than by "file missing" keeps a genuinely missing npz an error.
    return d.loc[d["model_family"] == "lstm", "experiment_id"].tolist()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--experiment-id", action="append", default=[], help="repeatable")
    p.add_argument("--all", action="store_true", help="every lstm row in the ledger")
    p.add_argument("--skip-missing", action="store_true",
                   help="skip runs whose npz is absent instead of failing (it is gitignored)")
    p.add_argument("--no-check", action="store_true",
                   help="skip the cross-check against results_summary.csv / results_by_horizon.csv")
    args = p.parse_args()

    ids = args.experiment_id or (ledger_ids() if args.all else [])
    if not ids:
        p.error("give --experiment-id or --all")

    failures, written, skipped = [], 0, 0
    for eid in ids:
        if args.skip_missing and not prediction_path(eid).exists():
            skipped += 1
            continue
        try:
            table, problems = write_city_horizon_table(eid, check=not args.no_check)
        except Exception as exc:                                  # noqa: BLE001 -- reported below
            failures.append(f"{eid}: {type(exc).__name__}: {exc}")
            continue
        written += 1
        status = "ok" if not problems else f"{len(problems)} MISMATCH"
        print(f"{eid:34s} {len(table):5d} satır  {status}")
        for line in problems:
            print(f"    ! {line}")
            failures.append(f"{eid}: {line}")

    print(f"\n{written} yazıldı, {skipped} atlandı, {len(failures)} sorun "
          f"-> metrics/{CITY_HORIZON_FILENAME}")
    for line in failures:
        print(f"  ! {line}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
