"""Verify that every run of a sweep left all its files and a complete ledger row.

    uv run python scripts/check_outputs.py --group tune_s1_lookback
    uv run python scripts/check_outputs.py --group tune_s5_ensemble --ensemble-curves

Run it on the machine that ran the sweep, BEFORE committing: a run that is missing a file
there cannot be repaired from the analysis machine, because the checkpoints do not sync. Exits
non-zero and lists every problem if anything is missing. Also lists which outputs are
committed (small CSVs) and which stay local (checkpoints, npz).
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "configs"))

import numpy as np
import pandas as pd

from experiment_grid import EXPERIMENT_GROUPS, StageNotReady, build_experiment_grid

from merve_solar.config import LEDGER_PATH
from merve_solar.ensemble_curves import CURVES_FILE
from merve_solar.experiment import LEDGER_COLUMNS, REQUIRED_RUN_OUTPUTS, missing_run_outputs

# Must be finite in every row a tuning stage reads. Interval columns are exempt for one-draw
# runs (deterministic inference at B=1), where they are NaN by design.
REQUIRED_FINITE = ("RMSE_daylight", "MAE_daylight", "CRPS_daylight", "val_RMSE_daylight",
                   "val_MAE_daylight", "val_CRPS_daylight", "mean_best_epoch", "training_time_sec")
INTERVAL_FINITE = ("CP_daylight", "PINW_daylight", "val_CP_daylight", "val_PINW_daylight")
LOCAL_ONLY = ("metrics/test_predictions.npz",)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", action="append", choices=list(EXPERIMENT_GROUPS), required=True)
    parser.add_argument("--ensemble-curves", action="store_true",
                        help="also require metrics/ensemble_curves.csv of every global MC-Dropout run")
    args = parser.parse_args()
    try:
        configs = build_experiment_grid(args.group)
    except StageNotReady as exc:
        raise SystemExit(f"stage not ready: {exc}")

    ledger = pd.read_csv(LEDGER_PATH).set_index("experiment_id")
    if tuple(["experiment_id", *ledger.columns]) != LEDGER_COLUMNS:
        raise SystemExit("ledger schema differs from LEDGER_COLUMNS")
    problems = []
    for config in configs:
        eid = config.experiment_id
        problems += [f"{eid}: missing {rel}" for rel in missing_run_outputs(config)]
        wants_curves = config.training_scope == "global" and config.inference_mode == "mc_dropout"
        if args.ensemble_curves and wants_curves and not (config.experiment_dir / CURVES_FILE).exists():
            problems.append(f"{eid}: missing {CURVES_FILE}")
        if eid not in ledger.index:
            problems.append(f"{eid}: no ledger row")
            continue
        row = ledger.loc[eid]
        one_draw = config.n_bootstrap * (1 if config.inference_mode == "deterministic"
                                         else config.mc_dropout_passes) == 1
        for col in REQUIRED_FINITE + (() if one_draw else INTERVAL_FINITE):
            if not np.isfinite(pd.to_numeric(row[col], errors="coerce")):
                problems.append(f"{eid}: ledger {col} is not a number ({row[col]!r})")
        if int(row["hit_max_epochs"]) > 0:
            problems.append(f"{eid}: WARNING {row['hit_max_epochs']} network(s) hit max_epochs")
        if str(row["device"]) == "cpu":
            problems.append(f"{eid}: WARNING trained on cpu; its seed siblings may be on mps")

    devices = sorted({str(ledger.loc[c.experiment_id, "device"]) for c in configs
                      if c.experiment_id in ledger.index})
    print(f"{len(configs)} runs checked; devices: {devices or ['none']}")
    committed = [r for r in REQUIRED_RUN_OUTPUTS if r not in LOCAL_ONLY]
    print(f"committed per run: {committed + ([CURVES_FILE] if args.ensemble_curves else [])}")
    print(f"local only (gitignored): checkpoints/*.pt, {list(LOCAL_ONLY)}")
    ignored = subprocess.run(["git", "check-ignore", "-q", str(LEDGER_PATH)], cwd=ROOT).returncode == 0
    if ignored:
        problems.append("the ledger is gitignored")

    if problems:
        print("\n".join(problems))
        if any("WARNING" not in p for p in problems):
            raise SystemExit(1)
    else:
        print("all outputs present")


if __name__ == "__main__":
    main()
