"""Five-seed summary of the final reference (the frozen configuration with its conformal layer).

    uv run python scripts/17_final_reference_report.py

Reads the final_reference runs' committed metrics and writes, into outputs/final_reference/:
- final_seeds.csv: one row per seed plus mean and sd rows: test daylight metrics (after the
  conformal layer), test daylight CP/MPIW before it, and the uncorrected validation columns;
- final_by_city.csv: test daylight metrics per province, mean and sd over seeds, with the
  conformal factor and the coverage before correction;
- final_by_horizon.csv: the same per horizon step.
This is the first stage that reads test metrics, and it selects nothing: the configuration was
frozen on validation before any of these runs existed.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "configs"))

import pandas as pd

from experiment_grid import stage_arms

from merve_solar.config import EXPERIMENTS_DIR, LEDGER_PATH, OUTPUTS_DIR

OUT_DIR = OUTPUTS_DIR / "final_reference"
METRICS = ["RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "CRPS"]
VAL_COLUMNS = ["val_RMSE_daylight", "val_MAE_daylight", "val_R2_daylight", "val_CP_daylight",
               "val_PINW_daylight", "val_CRPS_daylight"]


def _mean_sd(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    values = [c for c in frame.columns if c not in keys + ["seed"]]
    grouped = frame.groupby(keys, sort=False)[values]
    return grouped.mean().add_suffix("_mean").join(grouped.std().add_suffix("_sd")).reset_index()


def main():
    (configs,) = stage_arms("final").values()
    ids = {c.experiment_id: c.seed for c in configs}
    ledger = pd.read_csv(LEDGER_PATH).set_index("experiment_id")
    missing = sorted(set(ids) - set(ledger.index))
    if missing:
        raise SystemExit(f"no ledger row yet for {missing}")
    if (ledger.loc[list(ids), "conformal_mode"] == "none").any():
        raise SystemExit("a final_reference row has no conformal layer")

    seeds, cities, steps = [], [], []
    for experiment_id, seed in ids.items():
        metrics = EXPERIMENTS_DIR / experiment_id / "metrics"
        summary = pd.read_csv(metrics / "results_summary.csv").query("subset == 'daylight'")
        effect = pd.read_csv(metrics / "conformal_effect.csv")
        by_step = pd.read_csv(metrics / "results_by_horizon.csv").query("subset == 'daylight'")
        agg_effect = effect.query("group == 'Aggregate' and horizon_step == 'all'").iloc[0]
        agg = summary.set_index("group").loc["Aggregate", METRICS]
        seeds.append({"seed": seed, **{f"test_{m}": agg[m] for m in METRICS},
                      "test_CP_raw": agg_effect["CP_before"], "test_MPIW_raw": agg_effect["MPIW_before"],
                      "k_mean": agg_effect["k_mean"],
                      **ledger.loc[experiment_id, VAL_COLUMNS].to_dict(),
                      "mean_best_epoch": ledger.loc[experiment_id, "mean_best_epoch"]})
        city_effect = effect.query("horizon_step == 'all'").set_index("group")
        for _, row in summary.iterrows():
            extra = city_effect.loc[row["group"]] if row["group"] in city_effect.index else None
            cities.append({"seed": seed, "group": row["group"], **row[METRICS].to_dict(),
                           "CP_raw": extra["CP_before"] if extra is not None else float("nan"),
                           "k_mean": extra["k_mean"] if extra is not None else float("nan")})
        step_effect = effect.query("group == 'Aggregate' and horizon_step != 'all'").copy()
        step_effect["horizon_step"] = step_effect["horizon_step"].astype(int)
        step_effect = step_effect.set_index("horizon_step")
        for _, row in by_step.iterrows():
            s = int(row["horizon_step"])
            steps.append({"seed": seed, "horizon_step": s, **row[METRICS].to_dict(),
                          "CP_raw": step_effect.loc[s, "CP_before"],
                          "MPIW_raw": step_effect.loc[s, "MPIW_before"],
                          "k_mean": step_effect.loc[s, "k_mean"]})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_seed = pd.DataFrame(seeds).sort_values("seed")
    stats = per_seed.drop(columns="seed").agg(["mean", "std"]).rename(index={"std": "sd"})
    table = pd.concat([per_seed.astype({"seed": str}),
                       stats.reset_index().rename(columns={"index": "seed"})], ignore_index=True)
    table.to_csv(OUT_DIR / "final_seeds.csv", index=False)
    _mean_sd(pd.DataFrame(cities), ["group"]).to_csv(OUT_DIR / "final_by_city.csv", index=False)
    _mean_sd(pd.DataFrame(steps), ["horizon_step"]).to_csv(OUT_DIR / "final_by_horizon.csv", index=False)

    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(table.round(4).to_string(index=False))
    print(f"wrote {OUT_DIR.relative_to(ROOT)}/final_{{seeds,by_city,by_horizon}}.csv")


if __name__ == "__main__":
    main()
