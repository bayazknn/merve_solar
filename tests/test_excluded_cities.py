"""The `excluded_cities` axis: a province removed from train, val AND test.

The point of the axis is a four-province run whose Aggregate lines up with the five-province
run's Aggregate_excl_Rize row, so what has to be guaranteed is (a) the excluded province leaves
no trace anywhere, (b) the remaining provinces keep their identity, and (c) the split dates do
not move. (b) and (c) are what make the two runs comparable at all.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

import merve_solar.config as config_module
import merve_solar.experiment as experiment_module
from conftest import make_synthetic_base_df
from merve_solar.config import CITIES, CITY_TO_ID, ExperimentConfig
from merve_solar.experiment import run_experiment
from merve_solar.metrics import compute_metric_subsets, results_summary_dataframe
from merve_solar.windows import build_experiment_windows, compute_split_boundaries

EXCLUDED = "Rize"
HOURS = 900


def _tiny_config(experiment_id: str, **overrides) -> ExperimentConfig:
    """Small enough to train in seconds; the point is the plumbing, not the fit."""
    return ExperimentConfig(
        experiment_id=experiment_id,
        lookback_hours=6,
        horizon_hours=6,
        window_stride=1,
        train_ratio=0.6,
        val_ratio=0.2,
        hidden_sizes=[4, 4],
        n_bootstrap=1,
        mc_dropout_passes=2,
        max_epochs=1,
        batch_size=256,
        **overrides,
    )


@pytest.fixture
def isolated_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "EXPERIMENTS_DIR", tmp_path / "experiments")
    monkeypatch.setattr(experiment_module, "LEDGER_PATH", tmp_path / "ledger.csv")
    return tmp_path


# --------------------------------------------------------------------------- validation


def test_unknown_province_name_is_rejected():
    with pytest.raises(ValueError, match="unknown province"):
        ExperimentConfig(experiment_id="x", excluded_cities=["Rize", "Izmir"])


def test_leaving_fewer_than_two_provinces_is_rejected():
    """A one-province 'global' model is a per-city model under a misleading ledger label."""
    with pytest.raises(ValueError, match="at least 2 are required"):
        ExperimentConfig(experiment_id="x", excluded_cities=[c for c in CITIES if c != "Van"])


def test_active_cities_keeps_canonical_order_and_ledger_key_is_a_stable_string():
    config = ExperimentConfig(experiment_id="x", excluded_cities=["Van", "Rize"])
    assert config.active_cities == ["Ankara", "Antalya", "Konya"]
    assert config.excluded_cities_key == "Rize|Van"
    assert ExperimentConfig(experiment_id="x").excluded_cities_key == ""


def test_config_round_trips_through_json(tmp_path):
    config = _tiny_config("rt", excluded_cities=[EXCLUDED], loss_function="mae")
    path = tmp_path / "config.json"
    config.to_json(path)
    assert ExperimentConfig.from_json(path) == config


# --------------------------------------------------------------------------- windows / ids


def test_excluded_province_appears_in_no_split():
    df = make_synthetic_base_df(HOURS)
    config = _tiny_config("x", excluded_cities=[EXCLUDED])
    train_end, val_end = compute_split_boundaries(df, config)
    windows = build_experiment_windows(df, config, train_end, val_end, include_X=False)

    for split, data in windows.items():
        assert CITY_TO_ID[EXCLUDED] not in set(np.unique(data["city_id"])), f"{EXCLUDED} in {split}"
        assert data["y"].shape[0] > 0


def test_city_ids_of_the_remaining_provinces_are_unchanged():
    """The non-renumbering guarantee.

    Renumbering to a contiguous 0..3 would silently redefine every id: Van's windows would be
    labelled 3, which is Rize, in checkpoints, test_predictions.npz and the metric table alike.
    """
    df = make_synthetic_base_df(HOURS)
    full = _tiny_config("full")
    partial = _tiny_config("partial", excluded_cities=[EXCLUDED])
    train_end, val_end = compute_split_boundaries(df, full)

    w_full = build_experiment_windows(df, full, train_end, val_end, include_X=False)["test"]
    w_part = build_experiment_windows(df, partial, train_end, val_end, include_X=False)["test"]

    for city in partial.active_cities:
        idx = CITY_TO_ID[city]
        assert np.array_equal(
            w_full["window_start"][w_full["city_id"] == idx],
            w_part["window_start"][w_part["city_id"] == idx],
        ), f"{city} (id {idx}) is not the same set of windows under the exclusion"
    assert set(np.unique(w_part["city_id"])) == {CITY_TO_ID[c] for c in partial.active_cities}
    assert CITY_TO_ID["Van"] == 4, "ids must stay non-contiguous after excluding Rize"


def test_split_boundaries_are_identical_with_and_without_an_exclusion():
    """Both arms must split on the same dates, or the comparison measures the calendar."""
    df = make_synthetic_base_df(HOURS)
    full = compute_split_boundaries(df, _tiny_config("full"))
    partial = compute_split_boundaries(df, _tiny_config("p", excluded_cities=[EXCLUDED]))
    assert full == partial


def test_boundaries_still_need_the_full_frame_even_when_a_city_is_excluded():
    """The guard that stops someone filtering the frame before computing boundaries."""
    df = make_synthetic_base_df(HOURS)
    config = _tiny_config("x", excluded_cities=[EXCLUDED])
    filtered = df[df["city"] != EXCLUDED]
    with pytest.raises(ValueError, match="full multi-city frame"):
        compute_split_boundaries(filtered, config)


# --------------------------------------------------------------------------- metric table


def test_metric_table_has_no_row_for_the_excluded_province_and_no_degenerate_aggregate():
    """Aggregate_excl_Rize would be a byte-identical copy of Aggregate once Rize is gone."""
    config = _tiny_config("x", excluded_cities=[EXCLUDED])
    rng = np.random.default_rng(0)
    city_id = np.array([CITY_TO_ID[c] for c in config.active_cities for _ in range(3)])
    y_true = rng.normal(size=(city_id.size, 4)).astype(np.float32)
    preds = rng.normal(size=(5, city_id.size, 4)).astype(np.float32)

    subsets = compute_metric_subsets(preds, y_true, city_id, config.active_cities)
    groups = set(results_summary_dataframe(subsets)["group"])
    assert groups == {"Aggregate", *config.active_cities}
    assert EXCLUDED not in groups
    assert not any(g.startswith("Aggregate_excl") for g in groups)


def test_the_five_province_table_still_reports_the_secondary_aggregate():
    """The other half of the comparison must keep the row the four-province run is compared to."""
    rng = np.random.default_rng(0)
    city_id = np.array([CITY_TO_ID[c] for c in CITIES for _ in range(3)])
    y_true = rng.normal(size=(city_id.size, 4)).astype(np.float32)
    preds = rng.normal(size=(5, city_id.size, 4)).astype(np.float32)

    subsets = compute_metric_subsets(preds, y_true, city_id, CITIES)
    groups = set(results_summary_dataframe(subsets)["group"])
    assert groups == {"Aggregate", "Aggregate_excl_Rize", *CITIES}


def test_per_city_metrics_are_keyed_by_canonical_id_not_by_list_position():
    """Regression guard: enumerate(cities) mislabelled every province after a gap.

    Van (id 4) sitting at position 3 of a Rize-excluded list used to be scored against
    `city_id == 3`, i.e. no windows at all, and dropped from the table.
    """
    subset_cities = ["Konya", "Van"]
    y_true = np.array([[1.0], [2.0]], dtype=np.float32)
    preds = np.stack([y_true, y_true])  # exact forecast -> per-city MAE is 0 iff rows line up
    city_id = np.array([CITY_TO_ID["Konya"], CITY_TO_ID["Van"]])

    per_city = compute_metric_subsets(preds, y_true, city_id, subset_cities)["all_hours"]["per_city"]
    assert set(per_city) == set(subset_cities)


# --------------------------------------------------------------------------- end to end


@pytest.mark.parametrize("scope", ["global", "per_city"])
def test_excluded_run_end_to_end_covers_only_the_remaining_provinces(isolated_outputs, scope):
    df = make_synthetic_base_df(HOURS)
    config = _tiny_config(f"test_excl_{scope}", training_scope=scope, excluded_cities=[EXCLUDED])
    run_experiment(config, base_df=df)

    exp_dir = isolated_outputs / "experiments" / config.experiment_id
    summary = pd.read_csv(exp_dir / "metrics" / "results_summary.csv")
    assert set(summary["group"]) == {"Aggregate", *config.active_cities}

    npz = np.load(exp_dir / "metrics" / "test_predictions.npz")
    assert CITY_TO_ID[EXCLUDED] not in set(np.unique(npz["city_id"]))
    assert set(np.unique(npz["city_id"])) == {CITY_TO_ID[c] for c in config.active_cities}

    assert not (exp_dir / "figures" / f"forecast_ci_{EXCLUDED}.png").exists()
    for city in config.active_cities:
        assert (exp_dir / "figures" / f"forecast_ci_{city}.png").exists()

    row = pd.read_csv(isolated_outputs / "ledger.csv").iloc[-1]
    assert row["excluded_cities"] == EXCLUDED
    assert row["n_models_trained"] == (1 if scope == "global" else len(config.active_cities))


def test_per_city_arm_trains_nothing_for_the_excluded_province(isolated_outputs):
    df = make_synthetic_base_df(HOURS)
    config = _tiny_config("test_excl_percity_ckpts", training_scope="per_city",
                          excluded_cities=[EXCLUDED])
    run_experiment(config, base_df=df)

    checkpoints = isolated_outputs / "experiments" / config.experiment_id / "checkpoints"
    assert not (checkpoints / f"scaler_{EXCLUDED}.joblib").exists()
    assert not (checkpoints / f"bootstrap_model_{EXCLUDED}_0.pt").exists()
    for city in config.active_cities:
        assert (checkpoints / f"bootstrap_model_{city}_0.pt").exists()


def test_excluded_province_does_not_reach_the_scaler(isolated_outputs):
    """'Removed entirely' includes the preprocessing statistics.

    A scaler still fitted on all five provinces would leak the excluded regime's mean and
    variance into the four-province arm, so the run would not be the clean four-province
    comparison the axis claims to be.
    """
    import joblib

    df = make_synthetic_base_df(HOURS)
    config = _tiny_config("test_excl_scaler", excluded_cities=[EXCLUDED])
    run_experiment(config, base_df=df)

    fitted = joblib.load(
        isolated_outputs / "experiments" / config.experiment_id / "checkpoints" / "scaler.joblib"
    )
    train_end, _ = compute_split_boundaries(df, config)
    active_train = df[(df["city"] != EXCLUDED) & (df["datetime"] <= train_end)]
    assert fitted.n_samples_seen_ == len(active_train)
