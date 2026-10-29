"""Validation-only summary of one tuning stage, from the ledger (and the curves, for s5).

    uv run python scripts/15_tuning_report.py --stage s1
    uv run python scripts/15_tuning_report.py --stage s5

Writes outputs/tuning/<stage>_summary.csv and prints it with a suggested decision. Test
metrics are deliberately never read: every tuning choice is made on the validation split.

Decision rule (s1-s4): the arm with the best mean criterion replaces the incumbent only if its
mean seed-paired improvement exceeds the standard deviation of those paired differences, i.e.
the gain is larger than its own seed-to-seed noise. Otherwise the incumbent stays. For s5 the
suggestion is the cheapest (B, T) cell whose mean validation CRPS is within one seed standard
deviation of the best cell's.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "configs"))

import numpy as np
import pandas as pd

from experiment_grid import DECISIONS, STAGE_CRITERION, block_grid, stage_arms

from merve_solar.config import LEDGER_PATH, OUTPUTS_DIR
from merve_solar.ensemble_curves import CURVES_FILE

TUNING_DIR = OUTPUTS_DIR / "tuning"
VAL_COLUMNS = ("val_RMSE_daylight", "val_MAE_daylight", "val_CRPS_daylight", "val_CP_daylight",
               "val_PINW_daylight")


def _incumbent(stage: str) -> str:
    if stage == "s4":
        return f"blk{block_grid(DECISIONS['s1'])[1]}"
    return {"s1": "lb24", "s2": "h64l2", "s3_dropout": "do0.3", "s3_lr": "lr1e-3"}[stage]


def arm_table(stage: str) -> pd.DataFrame:
    ledger = pd.read_csv(LEDGER_PATH).set_index("experiment_id")
    criterion = STAGE_CRITERION[stage]
    incumbent = _incumbent(stage)
    arms = stage_arms(stage)
    missing = [c.experiment_id for cs in arms.values() for c in cs if c.experiment_id not in ledger.index]
    if missing:
        raise SystemExit(f"{len(missing)} runs of {stage} have no ledger row yet, e.g. {missing[:3]}")

    by_seed = {label: ledger.loc[[c.experiment_id for c in cs]].set_index("seed")
               for label, cs in arms.items()}
    base = by_seed[incumbent][criterion]
    rows = []
    for label, frame in by_seed.items():
        diff = frame[criterion] - base.reindex(frame.index)  # negative = better than incumbent
        row = {"arm": label, "incumbent": label == incumbent, "n_seeds": len(frame),
               f"{criterion}_mean": frame[criterion].mean(), f"{criterion}_sd": frame[criterion].std(),
               "paired_diff_mean": diff.mean(), "paired_diff_sd": diff.std()}
        for col in VAL_COLUMNS:
            row[f"{col}_mean"] = frame[col].mean()
        row["mean_best_epoch"] = frame["mean_best_epoch"].mean()
        row["hit_max_epochs"] = int(frame["hit_max_epochs"].sum())
        row["train_minutes_mean"] = frame["training_time_sec"].mean() / 60
        row["device"] = "|".join(sorted(frame["device"].astype(str).unique()))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(f"{criterion}_mean").reset_index(drop=True)


PATIENCE_PROBES = (3, 5, 7)


def _longest_wait(val_loss: pd.Series) -> int:
    """Most consecutive non-improving epochs that were followed by a new best (0 if none).

    Early stopping with patience p would have missed that later best iff this is >= p, which is
    exactly how train_model counts (improvement = below the running minimum by 1e-6)."""
    best, wait, longest = float("inf"), 0, 0
    for loss in val_loss:
        if loss < best - 1e-6:
            longest, best, wait = max(longest, wait), loss, 0
        else:
            wait += 1
    return longest


def patience_table(stage: str) -> pd.DataFrame:
    """Would a shorter early-stopping patience have changed any network's kept weights?

    Read from every network's full training_history.csv. A probe p counts the networks that
    found a new best only after p or more epochs without one, i.e. whose kept epoch patience p
    would have changed. Zero everywhere is evidence the current patience is wider than needed.
    """
    rows = []
    for label, configs in stage_arms(stage).items():
        waits, best_epochs, epochs = [], [], []
        for c in configs:
            history = pd.read_csv(c.experiment_dir / "metrics" / "training_history.csv")
            for _, net in history.groupby(["city", "replica"]):
                waits.append(_longest_wait(net.sort_values("epoch")["val_loss"]))
                best_epochs.append(int(net.loc[net["val_loss"].idxmin(), "epoch"]))
                epochs.append(len(net))
        row = {"arm": label, "networks": len(waits), "longest_wait_max": max(waits),
               "best_epoch_max": max(best_epochs), "epochs_mean": float(np.mean(epochs))}
        for probe in PATIENCE_PROBES:
            row[f"changed_by_patience_{probe}"] = int(sum(w >= probe for w in waits))
        rows.append(row)
    return pd.DataFrame(rows)


def suggest(table: pd.DataFrame, stage: str) -> str:
    best = table.iloc[0]
    if best["incumbent"]:
        return f"keep the incumbent {best['arm']} (it has the best mean {STAGE_CRITERION[stage]})"
    gain, noise = -best["paired_diff_mean"], best["paired_diff_sd"]
    if gain > noise:
        return (f"switch to {best['arm']}: paired gain {gain:.3f} exceeds its seed sd {noise:.3f}")
    return (f"keep the incumbent: best arm {best['arm']} gains {gain:.3f}, within its seed sd "
            f"{noise:.3f}")


def ensemble_table() -> pd.DataFrame:
    (configs,) = stage_arms("s5").values()
    frames = []
    for c in configs:
        path = c.experiment_dir / CURVES_FILE
        if not path.exists():
            raise SystemExit(f"missing {path}: run scripts/14_ensemble_curves.py where the run ran")
        frames.append(pd.read_csv(path))
    curves = pd.concat(frames)
    val = curves[curves["split"] == "val"]
    table = (val.groupby(["inference_mode", "B", "T"])
             .agg(n_seeds=("seed", "nunique"), CRPS_mean=("CRPS", "mean"), CRPS_sd=("CRPS", "std"),
                  CP_mean=("CP", "mean"), PINW_mean=("PINW", "mean"), RMSE_mean=("RMSE", "mean"))
             .reset_index())
    table["draws"] = table["B"] * table["T"]
    return table


def suggest_ensemble(table: pd.DataFrame) -> str:
    mc = table[table["inference_mode"] == "mc_dropout"]
    best = mc.loc[mc["CRPS_mean"].idxmin()]
    ok = mc[mc["CRPS_mean"] <= best["CRPS_mean"] + best["CRPS_sd"]]
    pick = ok.sort_values(["B", "T"]).iloc[0]  # networks cost training; passes only inference
    return (f"cheapest cell within one seed sd of the best: B={int(pick.B)}, T={int(pick['T'])} "
            f"(CRPS {pick.CRPS_mean:.3f} vs best {best.CRPS_mean:.3f} at "
            f"B={int(best.B)}, T={int(best['T'])}; CP {pick.CP_mean:.3f})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", required=True, choices=list(STAGE_CRITERION))
    stage = parser.parse_args().stage
    TUNING_DIR.mkdir(parents=True, exist_ok=True)
    if stage == "s5":
        table, note = ensemble_table(), None
        note = suggest_ensemble(table)
    else:
        table = arm_table(stage)
        note = suggest(table, stage)
    path = TUNING_DIR / f"{stage}_summary.csv"
    table.to_csv(path, index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(table.round(4).to_string(index=False))
        patience = patience_table(stage)
        patience.to_csv(TUNING_DIR / f"{stage}_patience.csv", index=False)
        print("\nearly-stopping check (networks whose kept epoch a shorter patience would change):")
        print(patience.round(2).to_string(index=False))
    print(f"\nsuggestion: {note}\nwrote {path}")


if __name__ == "__main__":
    main()
