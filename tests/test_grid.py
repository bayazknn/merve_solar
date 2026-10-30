import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "configs"))

import pytest

import experiment_grid as grid
from experiment_grid import (
    DECISIONS,
    EXPERIMENT_GROUPS,
    INCUMBENT,
    S2_EXTENSION,
    StageNotReady,
    TUNE_SEEDS,
    block_grid,
    build_experiment_grid,
    stage_arms,
)

ALL_DECIDED = {"s1": 48, "s2": (128, 1), "s3_dropout": 0.2, "s3_lr": 5e-4, "s4": 192,
               "s5": (12, 75)}


@pytest.fixture
def decided(monkeypatch):
    """Every stage decided, on values that differ from the incumbent, so reuse is visible."""
    def _set(**overrides):
        for key, value in {**ALL_DECIDED, **overrides}.items():
            monkeypatch.setitem(DECISIONS, key, value)
    return _set


def _diff(a, b):
    a, b = a.__dict__, b.__dict__
    return {k for k in a if a[k] != b[k]}


def test_the_committed_decisions_start_undecided_or_are_complete_prefixes():
    """A later stage decided while an earlier one is not would build on a guess."""
    order = ["s1", "s2", "s3_dropout", "s3_lr", "s4", "s5"]
    decided = [DECISIONS[k] is not None for k in order]
    assert decided == sorted(decided, reverse=True)


def test_unknown_group_is_rejected():
    with pytest.raises(ValueError, match="unknown group"):
        build_experiment_grid(["not_a_group"])


def test_listing_everything_skips_stages_that_are_not_ready(monkeypatch):
    for key in DECISIONS:
        monkeypatch.setitem(DECISIONS, key, None)
    ids = [c.experiment_id for c in build_experiment_grid()]
    assert ids and all(i.startswith(("smoke_", "tune_s1_")) for i in ids)
    with pytest.raises(StageNotReady):
        build_experiment_grid(["tune_s2_arch"])


def test_every_id_is_unique_once_everything_is_decided(decided):
    decided()
    ids = [c.experiment_id for c in build_experiment_grid()]
    assert len(ids) == len(set(ids))


def test_stage_one_moves_only_the_lookback():
    arms = stage_arms("s1")
    assert set(arms) == {"lb24", "lb48", "lb72"}
    reference = arms["lb24"][0]
    assert reference.hidden_sizes == INCUMBENT["hidden_sizes"] and reference.n_lstm_layers == 2
    assert reference.n_bootstrap == 1 and reference.mc_dropout_passes == 100
    for label, configs in arms.items():
        assert [c.seed for c in configs] == list(TUNE_SEEDS)
        assert _diff(reference, configs[0]) <= {"experiment_id", "lookback_hours"}


def test_stage_two_is_the_full_width_by_depth_grid_and_reuses_the_stage_one_winner(decided):
    decided(s1=48)
    arms = stage_arms("s2")
    assert len(arms) == 9 + len(S2_EXTENSION)
    assert arms["h64l2"] == stage_arms("s1")["lb48"]
    new = build_experiment_grid(["tune_s2_arch"])
    assert len(new) == (8 + len(S2_EXTENSION)) * len(TUNE_SEEDS)
    for c in new:
        assert c.lookback_hours == 48
        assert c.hidden_sizes[1] == c.hidden_sizes[0] // 2
        assert _diff(arms["h64l2"][0], c) <= {"experiment_id", "seed", "hidden_sizes", "lstm_layers"}


def test_stage_three_moves_one_axis_from_the_stage_two_winner(decided):
    decided(s2=(128, 1))
    winner = stage_arms("s2")["h128l1"]
    dropout, lr = stage_arms("s3_dropout"), stage_arms("s3_lr")
    assert dropout["do0.3"] == winner and lr["lr1e-3"] == winner
    for arms, axis in ((dropout, "dropout_rate"), (lr, "learning_rate")):
        for configs in arms.values():
            assert _diff(winner[0], configs[0]) <= {"experiment_id", axis}
    assert len(build_experiment_grid(["tune_s3_dropout"])) == 4 * len(TUNE_SEEDS)
    assert len(build_experiment_grid(["tune_s3_lr"])) == 2 * len(TUNE_SEEDS)


@pytest.mark.parametrize("lookback", [24, 48, 72])
def test_every_block_holds_a_window_span_plus_the_weather_memory(lookback):
    blocks = block_grid(lookback)
    assert min(blocks) == lookback + 24 + 72
    assert list(blocks) == sorted(blocks)
    if lookback == 24:
        assert INCUMBENT["bootstrap_block_length"] in blocks


def test_stage_four_runs_the_full_ensemble_and_moves_only_the_block(decided):
    decided()
    arms = stage_arms("s4")
    assert set(arms) == {f"blk{b}" for b in block_grid(48)}
    first = next(iter(arms.values()))[0]
    assert (first.n_bootstrap, first.mc_dropout_passes) == (8, 100)
    assert (first.lookback_hours, first.hidden_sizes, first.lstm_layers) == (48, [128, 64], 1)
    assert (first.dropout_rate, first.learning_rate) == (0.2, 5e-4)
    assert first.early_stop_patience == grid.FROZEN_PATIENCE
    for configs in arms.values():
        assert _diff(first, configs[0]) <= {"experiment_id", "bootstrap_block_length"}


def test_stage_five_is_one_sixteen_network_run_per_seed(decided):
    decided()
    (configs,) = stage_arms("s5").values()
    assert [c.n_bootstrap for c in configs] == [16] * len(TUNE_SEEDS)
    assert all(c.bootstrap_block_length == 192 for c in configs)


def test_the_final_reference_is_five_new_conformal_runs_of_the_frozen_configuration(decided):
    # Even at the stage-4 fidelity nothing is reused: no tuning run carries the conformal layer.
    for s5 in ((8, 100), (12, 75)):
        decided(s5=s5)
        final = build_experiment_grid(["final_reference"])
        assert [c.seed for c in final] == [42, 43, 44, 45, 46]
        assert all(c.experiment_id.startswith("final_") for c in final)
        assert all((c.n_bootstrap, c.mc_dropout_passes) == s5 for c in final)
        assert all(c.conformal_mode == grid.FINAL_CONFORMAL_MODE for c in final)
        assert all(c.bootstrap_block_length == 192 for c in final)
        assert all(c.early_stop_patience == grid.FROZEN_PATIENCE for c in final)


def test_the_smoke_group_covers_every_new_code_path():
    smoke = {c.experiment_id: c for c in EXPERIMENT_GROUPS["smoke"]()}
    assert any(c.inference_mode == "deterministic" for c in smoke.values())
    assert any(not c.bootstrap_resample and c.n_bootstrap > 1 for c in smoke.values())
    assert any(c.training_scope == "per_city" for c in smoke.values())
    assert any(c.conformal_mode == grid.FINAL_CONFORMAL_MODE for c in smoke.values())
    assert any(c.lstm_layers == 1 for c in smoke.values())
    assert all(c.max_epochs <= 2 for c in smoke.values())



ABLATION_CHANGES = {
    "per_city_mc_dropout": {"training_scope"},
    "global_normal_dropout": {"inference_mode", "mc_dropout_passes"},
    "per_city_normal_dropout": {"training_scope", "inference_mode", "mc_dropout_passes"},
    "global_plain_lstm": {"n_bootstrap", "inference_mode", "mc_dropout_passes", "conformal_mode"},
    "per_city_plain_lstm": {"training_scope", "n_bootstrap", "inference_mode", "mc_dropout_passes",
                            "conformal_mode"},
}


def test_every_ablation_arm_changes_only_its_own_axes_from_the_reference(decided):
    decided()
    arms = stage_arms("abl_scope_dropout")
    reference = arms.pop("global_mc_dropout")
    assert [c.experiment_id for c in reference] == [f"final_s{s}" for s in grid.ABLATION_SEEDS]
    assert set(arms) == set(ABLATION_CHANGES)
    by_seed = {c.seed: c for c in grid._final()["final"]}
    for label, configs in arms.items():
        expected_seeds = grid.BENCHMARK_SEEDS if "plain" in label else grid.ABLATION_SEEDS
        assert [c.seed for c in configs] == list(expected_seeds)
        for arm in configs:
            assert arm.experiment_id.startswith("abl_")
            assert _diff(by_seed[arm.seed], arm) == {"experiment_id"} | ABLATION_CHANGES[label], label


def test_the_ablation_group_trains_only_new_runs(decided):
    decided(s5=(6, 100))
    configs = build_experiment_grid(["abl_scope_dropout"])
    assert len(configs) == 12 and all(c.experiment_id.startswith("abl_") for c in configs)
    plain = [c for c in configs if "plain" in c.experiment_id]
    assert all(c.n_bootstrap == 1 and c.conformal_mode == "none" for c in plain)


def test_the_smoke_group_covers_the_ablation_code_paths():
    smoke = EXPERIMENT_GROUPS["smoke"]()
    assert any(c.training_scope == "per_city" and c.conformal_mode != "none" for c in smoke)
    assert any(c.training_scope == "per_city" and c.inference_mode == "deterministic"
               and c.conformal_mode != "none" for c in smoke)
    assert any(c.city_embedding_dim == 0 for c in smoke)


def test_the_daylight_loss_arm_changes_only_the_loss_mask(decided):
    decided()
    arms = stage_arms("abl_daylight_loss")
    reference = arms.pop("global_mc_dropout")
    assert [c.experiment_id for c in reference] == [f"final_s{s}" for s in grid.ABLATION_SEEDS]
    (configs,) = arms.values()
    assert [c.seed for c in configs] == list(grid.ABLATION_SEEDS)
    for ref, arm in zip(reference, configs):
        assert _diff(ref, arm) == {"experiment_id", "loss_daylight_only"}
        assert arm.loss_daylight_only


def test_adding_the_daylight_loss_group_leaves_the_running_shards_unchanged(decided):
    decided(s5=(6, 100))
    scope = [c.experiment_id for c in build_experiment_grid(["abl_scope_dropout"])]
    assert len(scope) == 12 and not any("daylight" in i for i in scope)
    assert len(build_experiment_grid(["abl_daylight_loss"])) == 2


def test_the_no_city_embedding_arm_changes_only_the_embedding(decided):
    decided()
    arms = stage_arms("abl_no_city_embedding")
    reference = arms.pop("global_mc_dropout")
    (configs,) = arms.values()
    assert [c.seed for c in configs] == list(grid.ABLATION_SEEDS)
    for ref, arm in zip(reference, configs):
        assert _diff(ref, arm) == {"experiment_id", "city_embedding_dim"}
        assert arm.city_embedding_dim == 0 and arm.training_scope == "global"
    decided(s5=(6, 100))
    assert [c.experiment_id for c in build_experiment_grid(["abl_no_city_embedding"])] == [
        "abl_global_no_city_embedding_s42", "abl_global_no_city_embedding_s43"]
