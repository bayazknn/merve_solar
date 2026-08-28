import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "configs"))

import pytest

from experiment_grid import ABLATION_FULL, EXPERIMENT_GROUPS, build_experiment_grid


def test_every_experiment_id_is_unique_across_groups():
    """The ledger appends, so a duplicate id would silently produce two rows for one name."""
    ids = [c.experiment_id for c in build_experiment_grid()]
    assert len(ids) == len(set(ids))


def test_unknown_group_is_rejected():
    with pytest.raises(ValueError, match="unknown group"):
        build_experiment_grid(["not_a_group"])


def test_default_grid_is_every_group_in_declaration_order():
    assert build_experiment_grid() == [c for g in EXPERIMENT_GROUPS.values() for c in g()]


def test_the_smoke_config_is_not_in_the_default_sweep_groups():
    """It used to be, so every sweep appended another duplicate row for the same id."""
    assert [c.experiment_id for c in EXPERIMENT_GROUPS["smoke"]()] == [
        "abl_scope_smoke_global", "abl_scope_smoke_percity"
    ]
    others = [c.experiment_id for g in ("main", "ablation") for c in EXPERIMENT_GROUPS[g]()]
    assert not any(i.endswith("_smoke_global") or i.endswith("_smoke_percity") for i in others)


@pytest.mark.parametrize("seed", [42, 43, 44])
def test_each_ablation_pair_differs_only_in_training_scope(seed):
    """The guarantee the whole comparison rests on, enforced by construction via ABLATION_FULL."""
    configs = {c.experiment_id: c for c in EXPERIMENT_GROUPS["ablation"]()}
    a = configs[f"abl_scope_full_global_s{seed}"].__dict__
    b = configs[f"abl_scope_full_percity_s{seed}"].__dict__
    differing = {k for k in a if a[k] != b[k]}
    assert differing == {"experiment_id", "training_scope"}


def test_sensitivity_runs_change_exactly_one_axis_from_the_percity_arm():
    configs = {c.experiment_id: c for c in EXPERIMENT_GROUPS["ablation"]()}
    reference = configs["abl_scope_full_percity_s42"].__dict__
    for experiment_id, axis in [
        ("abl_sens_percity_small_s42", "hidden_sizes"),
        ("abl_sens_percity_globalscaler_s42", "per_city_scaler"),
    ]:
        candidate = configs[experiment_id].__dict__
        differing = {k for k in reference if reference[k] != candidate[k]}
        assert differing == {"experiment_id", axis}, f"{experiment_id} moved {differing}"


def test_ablation_gives_both_arms_the_same_generous_epoch_budget():
    """A per-province model gets a fifth of the optimizer steps per epoch, so the default
    patience would be five times tighter on it than on the global arm."""
    assert ABLATION_FULL["max_epochs"] == 200
    assert ABLATION_FULL["early_stop_patience"] == 15
