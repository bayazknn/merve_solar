"""Run ONE experiment end-to-end: `python run_experiment.py --config configs/config_003.json`."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merve_solar.config import ExperimentConfig
from merve_solar.experiment import run_experiment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to an ExperimentConfig JSON file")
    args = parser.parse_args()

    config = ExperimentConfig.from_json(Path(args.config))
    subsets = run_experiment(config)
    print(f"experiment_id={config.experiment_id}")
    for subset, block in subsets.items():
        summary = "  ".join(
            f"{k}={block['aggregate'][k]:.4g}" for k in ("RMSE", "MAE", "R2", "CP")
        )
        print(f"  [{subset:9s}] {summary}")


if __name__ == "__main__":
    main()
