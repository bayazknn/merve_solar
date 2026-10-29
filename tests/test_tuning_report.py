import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import pytest

from merve_solar.config import OUTPUTS_DIR


def _load_report():
    spec = importlib.util.spec_from_file_location(
        "tuning_report", ROOT / "scripts" / "15_tuning_report.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = _load_report()


def test_paired_differences_are_taken_seed_by_seed_within_each_group():
    values = pd.DataFrame({
        "group": ["A"] * 4 + ["B"] * 4,
        "arm": ["inc", "inc", "new", "new"] * 2,
        "seed": [1, 2, 1, 2] * 2,
        "RMSE": [10.0, 12.0, 9.0, 10.0, 5.0, 5.0, 6.0, 8.0],
    })
    table = report.paired(values, "inc", "RMSE").set_index(["group", "arm"])
    assert table.loc[("A", "inc"), "RMSE_diff_mean"] == 0
    assert table.loc[("A", "new"), "RMSE_diff_mean"] == pytest.approx(-1.5)  # -1 and -2
    assert table.loc[("A", "new"), "RMSE_diff_sd"] == pytest.approx(0.7071, abs=1e-4)
    assert table.loc[("B", "new"), "RMSE_diff_mean"] == pytest.approx(2.0)   # +1 and +3
    assert table.loc[("B", "new"), "RMSE_mean"] == pytest.approx(7.0)


RUN = OUTPUTS_DIR / "experiments" / "tune_s1_lb24_s42" / "metrics"


@pytest.mark.skipif(not (RUN / "daily_scores.csv").exists(), reason="needs a committed tuning run")
@pytest.mark.parametrize("city", [None, "Rize"])
def test_daily_scores_over_all_origins_reproduce_the_validation_summary(city):
    """The matched-origin table is only trustworthy if, before any origin is dropped, it gives
    back exactly the numbers the run reported."""
    daily = pd.read_csv(RUN / "daily_scores.csv")
    daily = daily[daily["split"] == "val"]
    summary = pd.read_csv(RUN / "val_results_summary.csv")
    row = summary[(summary["subset"] == "daylight")
                  & (summary["group"] == (city or "Aggregate"))].iloc[0]
    scores = report.scores_from_daily(daily if city is None else daily[daily["city"] == city])
    for metric in ("RMSE", "MAE", "CRPS", "CP", "MPIW"):
        assert scores[metric] == pytest.approx(row[metric], rel=1e-5), metric
