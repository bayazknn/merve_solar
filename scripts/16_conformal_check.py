"""Validation-only choice of the conformal mode, cross-fitted inside the validation split.

    uv run python scripts/16_conformal_check.py                      # the S5 runs at the S5 decision
    uv run python scripts/16_conformal_check.py --experiment-id smoke_global_b2 --b 2 --t 5

For each run: reload its first B networks, predict the VALIDATION windows at T MC-Dropout passes
(the decided ensemble), keep the daylight sample in memory (~0.9 GB at B=6, T=100), and score
every candidate mode under alternating-month and leave-one-season-out cross-fitting
(src/merve_solar/conformal_check.py). Test windows are never predicted.

Must run where the experiment ran: the .pt checkpoints are not in git. Writes per run
metrics/conformal_check_{scores,groups,folds,month_k}.csv. For the default S5 set it also
concatenates them into outputs/tuning/conformal_check_*.csv. Commit both.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "configs"))

import numpy as np
import pandas as pd
import torch

from experiment_grid import DECISIONS, stage_arms

from merve_solar.config import (BASE_FEATURES_PATH, CITIES, EXPERIMENTS_DIR,
                                NUMERIC_FEATURE_COLUMNS, OUTPUTS_DIR, ExperimentConfig)
from merve_solar.conformal_check import check_run
from merve_solar.data import load_base_features
from merve_solar.mc_dropout import mc_dropout_predict
from merve_solar.model import SolarLSTM
from merve_solar.scaling import apply_scaler, inverse_transform_target, load_scaler
from merve_solar.utils import get_device, set_seed
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

TABLES = ("scores", "groups", "folds", "month_k")
CHECK_SEED_OFFSET = 2_000_003  # MC-Dropout draws independent of the run's and of the curves'
CHUNK_WINDOWS = 500


def validation_sample(experiment_id: str, b: int, t: int, base_df: pd.DataFrame):
    """(daylight sample (B*T, n_daylight) in W/m^2, val layout) for the first b networks."""
    exp_dir = EXPERIMENTS_DIR / experiment_id
    config = ExperimentConfig.from_json(exp_dir / "config.json")
    if config.training_scope != "global" or config.inference_mode != "mc_dropout":
        raise SystemExit(f"{experiment_id}: needs a global-scope MC-Dropout run")
    if b > config.n_bootstrap:
        raise SystemExit(f"{experiment_id}: has {config.n_bootstrap} networks, asked for {b}")
    # Same order as run_experiment: boundaries on the full frame, then the exclusion.
    train_end, val_end = compute_split_boundaries(base_df, config)
    if config.excluded_cities:
        base_df = base_df[base_df["city"].isin(config.active_cities)].reset_index(drop=True)
    val = build_experiment_windows(base_df, config, train_end, val_end, include_X=False)["val"]
    scaler = load_scaler(exp_dir / "checkpoints" / "scaler.joblib")
    X = build_experiment_windows(apply_scaler(base_df, scaler), config, train_end, val_end)["val"]

    device = get_device()
    models = []
    for i in range(b):
        model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), len(CITIES), config)
        model.load_state_dict(torch.load(exp_dir / "checkpoints" / f"bootstrap_model_{i}.pt",
                                         map_location="cpu"))
        models.append(model.to(device))

    set_seed(config.seed + CHECK_SEED_OFFSET)
    daylight = val["daylight"]
    samples = np.empty((b * t, int(daylight.sum())), dtype=np.float32)
    offset = 0
    print(f"{experiment_id}: {len(X['X'])} validation windows, B={b}, T={t}, device={device}")
    for start in range(0, len(X["X"]), CHUNK_WINDOWS):
        stop = min(start + CHUNK_WINDOWS, len(X["X"]))
        mask = daylight[start:stop]
        if not mask.any():
            continue
        scaled = np.concatenate([mc_dropout_predict(m, X["X"][start:stop], X["city_id"][start:stop],
                                                    t, device=device) for m in models])
        block = inverse_transform_target(scaler, scaled)[:, mask]
        samples[:, offset:offset + block.shape[1]] = block
        offset += block.shape[1]
    assert offset == samples.shape[1]
    return samples, val, config


def combine(experiment_ids: list[str]) -> None:
    out_dir = OUTPUTS_DIR / "tuning"
    for table in TABLES:
        paths = [EXPERIMENTS_DIR / i / "metrics" / f"conformal_check_{table}.csv" for i in experiment_ids]
        frames = [pd.read_csv(p) for p in paths if p.exists()]
        if frames:
            pd.concat(frames).to_csv(out_dir / f"conformal_check_{table}.csv", index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--experiment-id", nargs="+",
                        help="default: the S5 runs (tune_s5_ensemble)")
    parser.add_argument("--b", type=int, help="networks; default DECISIONS['s5'][0]")
    parser.add_argument("--t", type=int, help="MC-Dropout passes; default DECISIONS['s5'][1]")
    args = parser.parse_args()
    (configs,) = stage_arms("s5").values()
    s5_ids = [c.experiment_id for c in configs]
    default_set = args.experiment_id is None
    if default_set:
        args.experiment_id = s5_ids
    b = args.b or DECISIONS["s5"][0]
    t = args.t or DECISIONS["s5"][1]

    base_df = load_base_features(BASE_FEATURES_PATH)
    for experiment_id in args.experiment_id:
        started = time.time()
        samples, val, config = validation_sample(experiment_id, b, t, base_df)
        print(f"  predicted in {time.time() - started:.0f} s; scoring modes")
        tables = check_run(samples, val["y"], val["daylight"], val["city_id"], val["window_start"])
        del samples
        for name, frame in tables.items():
            frame.insert(0, "experiment_id", experiment_id)
            frame.insert(1, "seed", config.seed)
            frame.insert(2, "B", b)
            frame.insert(3, "T", t)
            frame.to_csv(EXPERIMENTS_DIR / experiment_id / "metrics" / f"conformal_check_{name}.csv",
                         index=False)
        scores = tables["scores"]
        print(scores[["mode", "scheme", "CP", "dev_worst_province", "dev_worst_step", "CRPS"]]
              .round(4).to_string(index=False))
        print(f"  done in {time.time() - started:.0f} s")
    if default_set:
        # Only the S5 runs feed the tuning tables, so a check on any other run (a smoke run, a
        # different B or T) can never mix into them.
        combine(s5_ids)
        print("wrote outputs/tuning/conformal_check_*.csv")
    else:
        print("per-run tables only; outputs/tuning/ is written for the default S5 set")


if __name__ == "__main__":
    main()
