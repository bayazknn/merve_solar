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


# --- The L1 re-run of the curve, and its two controls -------------------------------------

def _by_id(group):
    return {c.experiment_id: c for c in build_experiment_grid([group])}


def test_stage_two_under_l1_actually_carries_l1():
    """The entire reason this group exists.

    The _b1 curve took its loss from the ExperimentConfig default, so stage 2 ran under MSE --
    stage 1's loser -- while the ids said nothing about it. If this assertion ever fails the
    re-run silently repeats the mistake it was created to fix.
    """
    configs = _by_id("rize_curve_l1")
    assert configs, "the group must not be empty"
    assert all(c.loss_function == "mae" for c in configs.values())


def test_the_l1_curve_gives_every_arm_three_seeds():
    """H2 rested on two single-seed arms in the _b1 curve; it is the study's positive result."""
    configs = _by_id("rize_curve_l1")
    for arm in ("solo", "plus_ankara", "plus_antalya", "minus_antalya", "all5"):
        seeds = sorted(c.seed for i, c in configs.items() if i.startswith(f"abl_rize_{arm}_s"))
        assert seeds == [42, 43, 44], f"{arm} has seeds {seeds}"


def test_the_l1_curve_does_not_repeat_stage_one():
    """The criterion is already selected; re-running it would only add duplicate-looking rows."""
    assert not [i for i in _by_id("rize_curve_l1") if i.startswith("abl_loss_")]


def test_the_scaler_control_differs_from_its_arm_on_exactly_one_axis():
    """A control that moved a second field would measure the pair, not the confound."""
    control = _by_id("sens_scaler_l1")["abl_rize_solo_s42_globalscaler_l1"]
    arm = _by_id("rize_curve_l1")["abl_rize_solo_s42_l1"]
    differing = {
        k for k in vars(arm)
        if k != "experiment_id" and vars(arm)[k] != vars(control)[k]
    }
    assert differing == {"per_city_scaler"}, differing
    assert control.per_city_scaler is False and arm.per_city_scaler is True


def test_the_device_parity_pair_is_identical_apart_from_its_ids():
    """Two ids, one config: any metric difference between the runs is the backend and nothing
    else. Seeds included -- a differing seed would make the comparison meaningless."""
    cpu, mps = (_by_id("device_parity")[f"abl_parity_{t}_s42"] for t in ("cpu", "mps"))
    differing = {k for k in vars(cpu) if vars(cpu)[k] != vars(mps)[k]}
    assert differing == {"experiment_id"}, differing


def test_the_new_groups_do_not_collide_with_the_runs_already_in_the_ledger():
    """Reusing an id appends a second row under it, which _append_ledger_row cannot detect."""
    existing = {c.experiment_id for c in build_experiment_grid(
        ["smoke", "main", "ablation", "rize_curve", "rize_curve_b1", "rize_curve_smoke"])}
    new = {c.experiment_id for c in build_experiment_grid(
        ["rize_curve_l1", "sens_scaler_l1", "device_parity"])}
    assert not (existing & new)


def test_the_full_fidelity_curve_is_the_declared_method_under_the_selected_criterion():
    """This is the group the paper's interval table comes from, so both halves matter.

    B=8 x T=100 is what the methodology describes (|P| = 800); every arm run so far is B=1 and
    its interval metrics are MC-Dropout only. And the criterion must be the one stage 1 chose --
    repeating the _b1 curve's mistake at eight times the cost would be the expensive version of
    the same bug.
    """
    configs = build_experiment_grid(["rize_curve_full_l1"])
    assert len(configs) == 15
    for c in configs:
        assert c.n_bootstrap == 8 and c.mc_dropout_passes == 100, c.experiment_id
        assert c.loss_function == "mae", c.experiment_id


def test_the_full_curve_differs_from_the_b1_curve_only_in_fidelity():
    """Same study, more compute -- not a different study that happens to share a name."""
    full = {c.experiment_id: c for c in build_experiment_grid(["rize_curve_full_l1"])}
    b1 = {c.experiment_id: c for c in build_experiment_grid(["rize_curve_l1"])}
    for arm in ("solo", "plus_ankara", "plus_antalya", "minus_antalya", "all5"):
        a, b = full[f"abl_rize_{arm}_s42_full"], b1[f"abl_rize_{arm}_s42_l1"]
        differing = {k for k in vars(a) if vars(a)[k] != vars(b)[k]}
        assert differing == {"experiment_id", "n_bootstrap", "max_epochs"}, (arm, differing)
