"""Sub-ensemble curves of finished global-scope runs: daylight metrics for B x T.

    uv run python scripts/14_ensemble_curves.py --experiment-id tune_s5_..._s42 [...]
    uv run python scripts/14_ensemble_curves.py --experiment-id X --b-grid 4 6 8 --t-grid 50 100

Reloads each run's saved networks and scaler, predicts validation and test once at the largest
T, and scores every (first B networks, first T passes) cell plus the deterministic (dropout-off)
ensemble of each B. Must run where the experiment ran, because the .pt checkpoints are not in
git. The output, metrics/ensemble_curves.csv, is small and is committed. Tuning reads its
validation rows only. run_all_experiments.py --ensemble-curves runs this after each run.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merve_solar.ensemble_curves import DEFAULT_B_GRID, DEFAULT_T_GRID, write_ensemble_curves


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment-id", required=True, nargs="+")
    parser.add_argument("--b-grid", type=int, nargs="+", default=list(DEFAULT_B_GRID))
    parser.add_argument("--t-grid", type=int, nargs="+", default=list(DEFAULT_T_GRID))
    args = parser.parse_args()
    for experiment_id in args.experiment_id:
        out = write_ensemble_curves(experiment_id, args.b_grid, args.t_grid)
        print(f"{experiment_id}: wrote {len(out)} rows")


if __name__ == "__main__":
    main()
