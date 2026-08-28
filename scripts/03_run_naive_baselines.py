"""Score the naive reference forecasts through the experiment pipeline.

`uv run python scripts/03_run_naive_baselines.py`

These are the floor the LSTM has to clear. They use the same windows, the same chronological
splits and the same metrics.py as every model run, and they write into the same ledger -- the
one documented exception being that no scaler is involved, because none of these rules needs
one. Costs seconds; no training.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from merve_solar.baselines import build_baseline_predictions
from merve_solar.config import BASE_FEATURES_PATH, CITIES, ExperimentConfig
from merve_solar.data import load_base_features
from merve_solar.experiment import _append_ledger_row, _ledger_row, assert_ledger_schema_ok
from merve_solar.metrics import (
    compute_metric_subsets,
    results_by_horizon_dataframe,
    results_summary_dataframe,
)
from merve_solar.windows import compute_split_boundaries

# Interval metrics are degenerate for a point forecast (a zero-width interval makes CP an
# equality test). Blanked rather than reported as a misleading number; CRPS stays, since for a
# point forecast it equals MAE by construction.
DEGENERATE_INTERVAL_METRICS = ("CP", "PINW", "MPIW", "Reliability", "CWC")


def _blank_interval_metrics(subsets: dict) -> None:
    for block in subsets.values():
        groups = [block["aggregate"], block.get("aggregate_excl")]
        groups += list(block["per_city"].values()) + list(block["per_horizon"].values())
        for group in groups:
            if group is not None:
                group.update({k: float("nan") for k in DEGENERATE_INTERVAL_METRICS})


def main() -> None:
    assert_ledger_schema_ok()
    base_df = load_base_features(BASE_FEATURES_PATH)
    config = ExperimentConfig(experiment_id="_layout_probe")
    train_end, val_end = compute_split_boundaries(base_df, config)

    built = build_baseline_predictions(base_df, config, train_end, val_end)
    layout = built["layout"]
    print(f"test windows: {layout['y'].shape[0]}  (dropped {layout['n_dropped']} with no previous day)")
    print(f"daylight elements: {int(layout['daylight'].sum())} of {layout['daylight'].size}")

    for name, preds in built["predictions"].items():
        start = time.time()
        experiment_id = f"baseline_{name}"
        exp_dir = ExperimentConfig(experiment_id=experiment_id).experiment_dir
        (exp_dir / "metrics").mkdir(parents=True, exist_ok=True)

        subsets = compute_metric_subsets(
            preds, layout["y"], layout["city_id"], CITIES, daylight=layout["daylight"]
        )
        _blank_interval_metrics(subsets)

        results_summary_dataframe(subsets).to_csv(exp_dir / "metrics" / "results_summary.csv", index=False)
        results_by_horizon_dataframe(subsets).to_csv(exp_dir / "metrics" / "results_by_horizon.csv", index=False)

        # n_bootstrap/mc_dropout_passes are 1 because there is one deterministic forecast, not
        # an ensemble; recording the family is what makes the row identifiable in the ledger.
        row_config = ExperimentConfig(
            experiment_id=experiment_id, model_family=name, n_bootstrap=1, mc_dropout_passes=1
        )
        row_config.to_json(exp_dir / "config.json")
        _append_ledger_row(
            # device="n/a": these are numpy lookups, no torch backend is selected at all, so
            # "cpu" would misdescribe them as a backend choice that could have gone otherwise.
            _ledger_row(
                row_config, subsets,
                {"hit_max_epochs": 0, "n_models": 0, "device": "n/a"},
                time.time() - start,
            )
        )

        agg = subsets["daylight"]["aggregate"]
        print(f"  {name:20s} daylight  RMSE={agg['RMSE']:7.2f}  MAE={agg['MAE']:6.2f}  R2={agg['R2']:.4f}")

    print("\nall-hours reference (why the daylight breakdown is not optional):")
    for name, preds in built["predictions"].items():
        agg = compute_metric_subsets(preds, layout["y"], layout["city_id"], CITIES)["all_hours"]["aggregate"]
        print(f"  {name:20s} all_hours RMSE={agg['RMSE']:7.2f}  MAE={agg['MAE']:6.2f}  R2={agg['R2']:.4f}")


if __name__ == "__main__":
    main()
