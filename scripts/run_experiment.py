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
    all_metrics = run_experiment(config)
    print(f"experiment_id={config.experiment_id}")
    for key, value in all_metrics["aggregate"].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
