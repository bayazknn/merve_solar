"""Loops configs/experiment_grid.py, runs every config, appends to the ledger."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "configs"))

from experiment_grid import build_experiment_grid

from merve_solar.config import BASE_FEATURES_PATH
from merve_solar.data import load_base_features
from merve_solar.experiment import run_experiment


def main():
    base_df = load_base_features(BASE_FEATURES_PATH)
    for config in build_experiment_grid():
        print(f"Running {config.experiment_id}...")
        subsets = run_experiment(config, base_df=base_df)
        for subset, block in subsets.items():
            agg = block["aggregate"]
            print(f"  [{subset:9s}] RMSE={agg['RMSE']:.2f}  MAE={agg['MAE']:.2f}  "
                  f"R2={agg['R2']:.3f}  CP={agg['CP']:.3f}")


if __name__ == "__main__":
    main()
