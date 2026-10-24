"""Score a finished global-scope run on its train, validation AND test splits.

The pipeline scores the test split only; train and validation appear in log.txt as a scaled
loss. This reloads the run's saved scaler and replica checkpoints, predicts every split by the
same pooled MC-Dropout procedure the test path uses, applies the same night clamp and writes
one table in W/m^2: metrics/split_metrics.csv (subset x split x group).

What the train row means: each replica was fitted on a moving-block RESAMPLE of the train
windows, so the train row scores the ensemble on the original train windows -- an in-sample
diagnostic for over/under-fitting, never a result. CRPS is NaN throughout because the full
sample is never materialised (see metrics.compute_metrics_for_subset).

The train split is ~5x the test split, so by default it is scored with fewer MC passes per
replica (--train-passes); point metrics are stable at that size, the 2.5/97.5 percentiles less
so, which is why the pooled sample size is a column of the table. Checkpoints are gitignored,
so this must run on the machine the experiment ran on.

    uv run python scripts/04_split_metrics.py --experiment-id config_002_default_full
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import torch

from merve_solar.config import (
    BASE_FEATURES_PATH,
    CITIES,
    CITY_TO_ID,
    EXPERIMENTS_DIR,
    NUMERIC_FEATURE_COLUMNS,
    ExperimentConfig,
)
from merve_solar.data import load_base_features
from merve_solar.mc_dropout import pooled_summary
from merve_solar.metrics import compute_metrics_for_subset
from merve_solar.model import SolarLSTM
from merve_solar.scaling import apply_scaler, inverse_transform_target, load_scaler
from merve_solar.utils import get_device, set_seed
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

SPLITS = ("train", "val", "test")
METRIC_COLUMNS = ("RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "Reliability", "CWC")


def load_replicas(exp_dir: Path, config) -> list:
    paths = sorted((exp_dir / "checkpoints").glob("bootstrap_model_*.pt"))
    if len(paths) != config.n_bootstrap:
        raise SystemExit(f"expected {config.n_bootstrap} checkpoints in {exp_dir}, found {len(paths)}")
    models = []
    for path in paths:
        model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), len(CITIES), config)
        model.load_state_dict(torch.load(path, map_location="cpu"))
        models.append(model)
    return models


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--train-passes", type=int, default=10,
                        help="MC passes per replica on the train split (default 10)")
    args = parser.parse_args()

    exp_dir = EXPERIMENTS_DIR / args.experiment_id
    config = ExperimentConfig.from_json(exp_dir / "config.json")
    if config.training_scope != "global" or config.model_family != "lstm":
        raise SystemExit("only global-scope LSTM runs are supported")
    set_seed(config.seed)
    device = get_device()

    base_df = load_base_features(BASE_FEATURES_PATH)
    train_end, val_end = compute_split_boundaries(base_df, config)
    if config.excluded_cities:
        base_df = base_df[base_df["city"].isin(config.active_cities)].reset_index(drop=True)

    # Ground truth from the unscaled frame, exactly as run_experiment takes it.
    layout = build_experiment_windows(base_df, config, train_end, val_end, include_X=False)
    scaler = load_scaler(exp_dir / "checkpoints" / "scaler.joblib")
    splits = build_experiment_windows(apply_scaler(base_df, scaler), config, train_end, val_end)
    models = load_replicas(exp_dir, config)

    rows = []
    for split in SPLITS:
        passes = args.train_passes if split == "train" else config.mc_dropout_passes
        scaled = pooled_summary(models, splits[split]["X"], splits[split]["city_id"], passes,
                                config.horizon_hours, device=device)
        dist = {k: inverse_transform_target(scaler, scaled[k]) for k in ("mean", "lower", "upper")}
        y, daylight, city_id = (layout[split][k] for k in ("y", "daylight", "city_id"))
        if config.clamp_night_to_zero:
            for value in dist.values():
                value[~daylight] = 0.0

        groups = [("Aggregate", slice(None))] + [
            (city, city_id == CITY_TO_ID[city]) for city in config.active_cities
        ]
        for subset, mask in (("all_hours", None), ("daylight", daylight)):
            for group, sel in groups:
                m = compute_metrics_for_subset(
                    None, y[sel], None if mask is None else mask[sel],
                    {k: v[sel] for k, v in dist.items()},
                )
                rows.append({
                    "subset": subset, "split": split, "group": group,
                    **{k: m[k] for k in METRIC_COLUMNS},
                    "n_windows": int(y[sel].shape[0]), "n_elements": m["n_elements"],
                    "pooled_samples": passes * len(models),
                })
        print(f"{split}: {y.shape[0]} windows scored with {passes * len(models)} pooled samples")

    table = pd.DataFrame(rows)
    out = exp_dir / "metrics" / "split_metrics.csv"
    table.to_csv(out, index=False)
    print(table[table["group"] == "Aggregate"].round(4).to_string(index=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
