"""Ablation summary: arm tables and paired day-level comparisons on the test year.

    uv run python scripts/18_ablation_report.py

Reads the committed metrics of the three ablation groups (abl_scope_dropout, abl_daylight_loss,
abl_no_city_embedding) and of the final reference, and writes into outputs/ablation/:
- ablation_runs.csv: one row per run: test daylight metrics (after the conformal layer where
  there is one), mean error (bias, forecast minus observed), coverage/width/factor before it, validation columns, best epoch, training time;
- ablation_arms.csv: the same, mean and sd over each arm's seeds;
- ablation_by_city.csv: test daylight metrics per arm and province, mean and sd over seeds;
- ablation_paired.csv: every planned comparison (arm minus reference, positive = the arm is
  worse for an error metric), per seed and pooled, with a 95% interval from a paired moving-block
  bootstrap over forecast-origin days, for the aggregate and for each province;
- figures/ablation_paired_differences.{png,pdf}: the aggregate differences with their intervals.

Ablations explain the frozen method, they select nothing, so they read test metrics. The paired
test uses metrics/daily_scores.csv (daylight sums per province and origin day): both arms forecast
the same days, so whole days are resampled together, in circular blocks of BLOCK_DAYS to keep
weather autocorrelation, and the same resampled days are used for every seed of a comparison.
A difference is called real when it has the same sign on every seed, its pooled size exceeds
MIN_EFFECT and the bootstrap interval excludes zero (outputs/ablation/ABLATION_PLAN.md, Section 4).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "configs"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiment_grid import stage_arms

from merve_solar.config import CITIES, EXPERIMENTS_DIR, LEDGER_PATH, OUTPUTS_DIR
from merve_solar.paper_style import ACCENT, DPI, FULL_WIDTH_IN, INK_MUTED, PAPER_RC

OUT_DIR = OUTPUTS_DIR / "ablation"
GROUPS = ("abl_scope_dropout", "abl_daylight_loss", "abl_no_city_embedding")
METRICS = ["RMSE", "MAE", "R2", "CP", "PINW", "MPIW", "CRPS"]
VAL_COLUMNS = ["val_RMSE_daylight", "val_MAE_daylight", "val_CP_daylight", "val_CRPS_daylight"]
PAIRED_METRICS = ("RMSE", "MAE", "CRPS")
BLOCK_DAYS = 7
N_BOOT = 2000
BOOT_SEED = 20261030
MIN_EFFECT = 0.3  # W/m^2: three times the final reference's seed sd in RMSE and CRPS

# (label, question, arm, reference). Each pair uses the seeds both arms have; the reference
# global_mc_dropout is the final run of the same seed, so the benchmark pairs on 42-44.
COMPARISONS = [
    ("A: per province vs shared, MC-Dropout", "A", "per_city_mc_dropout", "global_mc_dropout"),
    ("A: per province vs shared, normal dropout", "A", "per_city_normal_dropout", "global_normal_dropout"),
    ("A: per province vs shared, plain LSTM", "A", "per_city_plain_lstm", "global_plain_lstm"),
    ("B: normal vs MC-Dropout, shared", "B", "global_normal_dropout", "global_mc_dropout"),
    ("B: normal vs MC-Dropout, per province", "B", "per_city_normal_dropout", "per_city_mc_dropout"),
    ("C: plain LSTM vs method, shared", "C", "global_plain_lstm", "global_mc_dropout"),
    ("C: plain LSTM vs method, per province", "C", "per_city_plain_lstm", "per_city_mc_dropout"),
    ("D: daylight-only loss vs method", "D", "global_daylight_loss", "global_mc_dropout"),
    ("E: no province code vs method", "E", "global_no_city_embedding", "global_mc_dropout"),
    ("E: per province vs shared without code", "E", "per_city_mc_dropout", "global_no_city_embedding"),
]


def _arm_runs() -> dict:
    """arm -> {seed: experiment_id}; global_mc_dropout gets every final seed, for pairing."""
    arms = {}
    for group in GROUPS:
        for arm, configs in stage_arms(group).items():
            arms[arm] = {c.seed: c.experiment_id for c in configs}
    (final,) = stage_arms("final").values()
    arms["global_mc_dropout_all"] = {c.seed: c.experiment_id for c in final}
    return arms


def _run_rows(experiment_id: str, ledger: pd.DataFrame) -> tuple[dict, list[dict]]:
    metrics = EXPERIMENTS_DIR / experiment_id / "metrics"
    summary = pd.read_csv(metrics / "results_summary.csv").query("subset == 'daylight'")
    summary = summary.set_index("group")
    effect_path = metrics / "conformal_effect.csv"
    effect = (pd.read_csv(effect_path).query("horizon_step == 'all'").set_index("group")
              if effect_path.exists() else None)
    row = ledger.loc[experiment_id]

    def extra(group):
        if effect is None or group not in effect.index:
            return {"CP_raw": np.nan, "MPIW_raw": np.nan, "k_mean": np.nan}
        e = effect.loc[group]
        return {"CP_raw": e["CP_before"], "MPIW_raw": e["MPIW_before"], "k_mean": e["k_mean"]}

    daily = _daily(experiment_id).groupby(level="city")[["sum_error", "n_daylight"]].sum()
    bias = daily["sum_error"] / daily["n_daylight"]
    total_bias = daily["sum_error"].sum() / daily["n_daylight"].sum()
    run = {**summary.loc["Aggregate", METRICS].to_dict(), "bias": total_bias, **extra("Aggregate"),
           **row[VAL_COLUMNS].to_dict(), "mean_best_epoch": row["mean_best_epoch"],
           "hit_max_epochs": row["hit_max_epochs"],
           "training_time_min": row["training_time_sec"] / 60}
    cities = [{"group": c, **summary.loc[c, METRICS].to_dict(), "bias": bias[c], **extra(c)}
              for c in CITIES]
    return run, cities


def _daily(experiment_id: str) -> pd.DataFrame:
    frame = pd.read_csv(EXPERIMENTS_DIR / experiment_id / "metrics" / "daily_scores.csv")
    return frame.query("split == 'test'").set_index(["origin_date", "city"]).sort_index()


def _score(n, sse, sae, scrps) -> dict:
    return {"RMSE": np.sqrt(sse / n), "MAE": sae / n, "CRPS": scrps / n}


def _sums(daily: pd.DataFrame, cities) -> np.ndarray:
    """(days, 4) daylight sums n, sse, sae, scrps, summed over `cities`."""
    sub = daily[daily.index.get_level_values("city").isin(cities)]
    cols = ["n_daylight", "sum_sq_error", "sum_abs_error", "sum_crps"]
    return sub.groupby(level="origin_date")[cols].sum().to_numpy(dtype=np.float64)


def _block_indices(n_days: int, rng: np.random.Generator) -> np.ndarray:
    """(N_BOOT, n_days) day indices from circular blocks of BLOCK_DAYS consecutive days."""
    n_blocks = -(-n_days // BLOCK_DAYS)
    starts = rng.integers(0, n_days, size=(N_BOOT, n_blocks))
    idx = (starts[:, :, None] + np.arange(BLOCK_DAYS)) % n_days
    return idx.reshape(N_BOOT, -1)[:, :n_days]


def _paired(arm_runs: dict, ref_runs: dict, boot_idx: np.ndarray, label, question, arm, ref):
    seeds = sorted(set(arm_runs) & set(ref_runs))
    dailies = {s: (_daily(arm_runs[s]), _daily(ref_runs[s])) for s in seeds}
    rows = []
    for scope in ["Aggregate", *CITIES]:
        cities = CITIES if scope == "Aggregate" else [scope]
        per_seed, boot = {m: [] for m in PAIRED_METRICS}, {m: [] for m in PAIRED_METRICS}
        for s in seeds:
            a, r = (_sums(d, cities) for d in dailies[s])
            if not np.array_equal(a[:, 0], r[:, 0]):
                raise SystemExit(f"{label}: seed {s} arms do not cover the same daylight elements")
            full_a, full_r = _score(*a.sum(axis=0)), _score(*r.sum(axis=0))
            ba, br = a[boot_idx].sum(axis=1), r[boot_idx].sum(axis=1)  # (N_BOOT, 4)
            boot_a, boot_r = _score(*ba.T), _score(*br.T)
            for m in PAIRED_METRICS:
                per_seed[m].append(full_a[m] - full_r[m])
                boot[m].append(boot_a[m] - boot_r[m])
        for m in PAIRED_METRICS:
            diffs = np.array(per_seed[m])
            dist = np.mean(boot[m], axis=0)  # pooled over seeds, same resampled days
            lo, hi = np.percentile(dist, [2.5, 97.5])
            same_sign = bool(np.all(diffs > 0) or np.all(diffs < 0))
            real = same_sign and abs(diffs.mean()) > MIN_EFFECT and (lo > 0 or hi < 0)
            rows.append({"comparison": label, "question": question, "arm": arm, "reference": ref,
                         "group": scope, "metric": m, "seeds": " ".join(map(str, seeds)),
                         "diff_mean": diffs.mean(),
                         "diff_per_seed": " ".join(f"{d:+.3f}" for d in diffs),
                         "ci_low": lo, "ci_high": hi, "same_sign": same_sign, "real": real})
    return rows


def _mean_sd(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    values = [c for c in frame.columns if c not in keys + ["seed", "experiment_id"]]
    grouped = frame.groupby(keys, sort=False)[values]
    out = grouped.mean().add_suffix("_mean").join(grouped.std().add_suffix("_sd"))
    out.insert(0, "n_seeds", grouped.size())
    return out.reset_index()


def _plot(paired: pd.DataFrame, save_path: Path) -> None:
    agg = paired.query("group == 'Aggregate'")
    labels = list(dict.fromkeys(agg["comparison"]))
    with plt.rc_context(PAPER_RC):
        fig, axes = plt.subplots(1, 2, figsize=(FULL_WIDTH_IN, 3.6), sharey=True,
                                 layout="constrained")
        y = np.arange(len(labels))[::-1]
        for ax, metric in zip(axes, ("RMSE", "CRPS")):
            block = agg.query("metric == @metric").set_index("comparison").loc[labels]
            for yi, (_, r) in zip(y, block.iterrows()):
                color = ACCENT if r["real"] else INK_MUTED
                ax.errorbar(r["diff_mean"], yi, fmt="o", markersize=3.5, color=color,
                            xerr=[[r["diff_mean"] - r["ci_low"]], [r["ci_high"] - r["diff_mean"]]],
                            elinewidth=1.2, capsize=2)
            ax.axvline(0, color="black", linewidth=0.8)
            ax.set_xlabel(f"Δ {metric}, arm − reference (W/m²)")
            ax.set_title(f"Test daylight {metric}")
        axes[0].set_yticks(y, labels)
        fig.savefig(save_path.with_suffix(".png"), dpi=DPI, facecolor="white")
        fig.savefig(save_path.with_suffix(".pdf"), facecolor="white")
        plt.close(fig)


def main():
    arms = _arm_runs()
    ledger = pd.read_csv(LEDGER_PATH).set_index("experiment_id")
    needed = {e for runs in arms.values() for e in runs.values()}
    missing = sorted(needed - set(ledger.index))
    if missing:
        raise SystemExit(f"no ledger row yet for {missing}")

    runs, cities = [], []
    for arm, by_seed in arms.items():
        if arm == "global_mc_dropout_all":
            continue
        for seed, experiment_id in sorted(by_seed.items()):
            run, city_rows = _run_rows(experiment_id, ledger)
            runs.append({"arm": arm, "seed": seed, "experiment_id": experiment_id, **run})
            cities.extend({"arm": arm, "seed": seed, **c} for c in city_rows)
    runs = pd.DataFrame(runs)
    cities = pd.DataFrame(cities)

    rng = np.random.default_rng(BOOT_SEED)
    n_days = _daily(arms["global_mc_dropout"][42]).index.get_level_values("origin_date").nunique()
    boot_idx = _block_indices(n_days, rng)
    paired = []
    for label, question, arm, ref in COMPARISONS:
        ref_runs = arms["global_mc_dropout_all"] if ref == "global_mc_dropout" else arms[ref]
        paired.extend(_paired(arms[arm], ref_runs, boot_idx, label, question, arm, ref))
    paired = pd.DataFrame(paired)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "figures").mkdir(exist_ok=True)
    runs.to_csv(OUT_DIR / "ablation_runs.csv", index=False)
    _mean_sd(runs, ["arm"]).to_csv(OUT_DIR / "ablation_arms.csv", index=False)
    _mean_sd(cities, ["arm", "group"]).to_csv(OUT_DIR / "ablation_by_city.csv", index=False)
    paired.to_csv(OUT_DIR / "ablation_paired.csv", index=False)
    _plot(paired, OUT_DIR / "figures" / "ablation_paired_differences")

    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(_mean_sd(runs, ["arm"])[["arm", "n_seeds", "RMSE_mean", "MAE_mean", "CRPS_mean",
                                       "CP_mean", "MPIW_mean", "CP_raw_mean", "k_mean_mean"]]
              .round(3).to_string(index=False))
        print(paired.query("group == 'Aggregate'")[["comparison", "metric", "diff_mean",
                                                     "diff_per_seed", "ci_low", "ci_high", "real"]]
              .round(3).to_string(index=False))
    print(f"wrote {OUT_DIR.relative_to(ROOT)}/ablation_{{runs,arms,by_city,paired}}.csv and a figure")


if __name__ == "__main__":
    main()
