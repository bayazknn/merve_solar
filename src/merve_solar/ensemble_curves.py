"""Run-level driver for evaluation.ensemble_curves: reload a finished run and write its curves."""
import pandas as pd
import torch

from merve_solar.config import (
    BASE_FEATURES_PATH,
    CITIES,
    EXPERIMENTS_DIR,
    NUMERIC_FEATURE_COLUMNS,
    ExperimentConfig,
)
from merve_solar.data import load_base_features
from merve_solar.evaluation import CURVE_COLUMNS, ensemble_curves
from merve_solar.model import SolarLSTM
from merve_solar.scaling import apply_scaler, load_scaler
from merve_solar.utils import get_device, set_seed
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

DEFAULT_B_GRID = (4, 6, 8, 10, 12, 14, 16)
DEFAULT_T_GRID = (50, 75, 100, 125, 150)
CURVES_SEED_OFFSET = 1_000_003  # MC-Dropout draws independent of the run's own
CURVES_FILE = "metrics/ensemble_curves.csv"


def write_ensemble_curves(experiment_id: str, b_grid=DEFAULT_B_GRID, t_grid=DEFAULT_T_GRID,
                          base_df: pd.DataFrame | None = None) -> pd.DataFrame:
    exp_dir = EXPERIMENTS_DIR / experiment_id
    config = ExperimentConfig.from_json(exp_dir / "config.json")
    if config.training_scope != "global" or config.inference_mode != "mc_dropout":
        raise ValueError("ensemble curves need a global-scope MC-Dropout run")
    b_grid = [b for b in b_grid if b <= config.n_bootstrap]
    if not b_grid:
        # A run smaller than the grid (the smoke runs): score just the run's own size, which
        # still exercises the whole path at a fraction of the cost.
        b_grid, t_grid = [config.n_bootstrap], [config.mc_dropout_passes]

    if base_df is None:
        base_df = load_base_features(BASE_FEATURES_PATH)
    # Same order as run_experiment: boundaries on the full frame, then the exclusion.
    train_end, val_end = compute_split_boundaries(base_df, config)
    if config.excluded_cities:
        base_df = base_df[base_df["city"].isin(config.active_cities)].reset_index(drop=True)
    layout = build_experiment_windows(base_df, config, train_end, val_end, include_X=False)
    scaler = load_scaler(exp_dir / "checkpoints" / "scaler.joblib")
    splits = build_experiment_windows(apply_scaler(base_df, scaler), config, train_end, val_end)

    device = get_device()
    models = []
    for b in range(max(b_grid)):
        model = SolarLSTM(len(NUMERIC_FEATURE_COLUMNS), len(CITIES), config)
        model.load_state_dict(torch.load(exp_dir / "checkpoints" / f"bootstrap_model_{b}.pt",
                                         map_location="cpu"))
        models.append(model.to(device))

    set_seed(config.seed + CURVES_SEED_OFFSET)
    rows = []
    for split in ("val", "test"):
        print(f"{experiment_id}: ensemble curves on {split} "
              f"({len(splits[split]['X'])} windows, device={device})")
        rows += ensemble_curves(models, splits[split]["X"], splits[split]["city_id"],
                                layout[split]["y"], layout[split]["daylight"], scaler,
                                b_grid, t_grid, device, split)
    out = pd.DataFrame(rows, columns=list(CURVE_COLUMNS))
    out.insert(0, "experiment_id", experiment_id)
    out.insert(1, "seed", config.seed)
    out.insert(2, "device", device)
    out.to_csv(exp_dir / CURVES_FILE, index=False)
    return out
