"""The clear-sky reconstruction is the one place this project invents data, so it is tested.

CLRSKY_SFC_SW_DWN left the export on 14-Sep-2026 and is rebuilt in clearsky.py. It defines the
daylight subset every headline metric is reported on, so a silent regression here would not
crash anything -- it would quietly move the paper's numbers. These tests pin the two properties
that matter: complete coverage of the record, and a day/night flag that agrees with physics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar import clearsky
from merve_solar.config import BASE_FEATURES_PATH, CITIES, TARGET_COLUMN
from merve_solar.data import load_base_features


@pytest.fixture(scope="module")
def reference():
    return clearsky.load_clearsky_reference()


def test_reference_covers_every_city_hour_exactly_once(reference):
    assert not reference.duplicated(["city", "datetime"]).any()
    assert sorted(reference["city"].unique()) == sorted(CITIES)
    per_city = reference.groupby("city").size()
    assert per_city.nunique() == 1, f"provinces have different lengths: {per_city.to_dict()}"


def test_reference_is_physically_admissible(reference):
    values = reference[clearsky.CLEARSKY_COLUMN]
    assert values.notna().all()
    assert (values >= 0).all()
    # Clear-sky GHI cannot exceed the solar constant at these latitudes; anything near it
    # means the unit handling has drifted.
    assert values.max() < 1367.0


def test_only_the_uncovered_tail_is_reconstructed(reference):
    """Everything the previous export reaches must be verbatim, not climatology."""
    measured = reference[reference[clearsky.SOURCE_COLUMN] == "measured"]
    filled = reference[reference[clearsky.SOURCE_COLUMN] == "climatology"]
    assert len(filled) > 0, "nothing was reconstructed -- has the export changed?"
    # The reconstructed part is the tail, and it is small: a fifth of the record being
    # invented would change how the daylight subset should be reported.
    assert len(filled) / len(reference) < 0.05
    assert filled["datetime"].min() > measured["datetime"].max()


def test_daylight_flag_matches_the_target_being_positive():
    """The geometric mask and a `target > 0` reading must agree except at the rounding grid.

    They are not the same definition and only the geometric one is admissible (a target
    threshold conditions on the outcome), but they describe the same physical event, so a
    large disagreement means the reconstruction has slipped against the record. The tolerated
    residual is the export's 2.78 W/m^2 quantisation: a handful of true twilight hours store
    as exactly 0.00.
    """
    df = load_base_features(BASE_FEATURES_PATH)
    geometric = df["CLRSKY_SFC_SW_DWN"] > 0
    positive = df[TARGET_COLUMN] > 0
    disagreement = (geometric != positive).mean()
    assert disagreement < 1e-3, f"masks disagree on {disagreement:.2%} of rows"
    # Every disagreement must be in the harmless direction: the sun is up but the reading
    # quantised to zero. A night hour with positive irradiance would be a real defect.
    assert not (positive & ~geometric).any()


def test_daylight_share_is_physically_plausible():
    df = load_base_features(BASE_FEATURES_PATH)
    share = (df["CLRSKY_SFC_SW_DWN"] > 0).mean()
    # Roughly half a year-round record at these latitudes; the observed value is 0.514.
    assert 0.48 < share < 0.55


def test_climatological_fill_reproduces_a_held_out_window():
    """The accuracy claim in clearsky.py's docstring, checked rather than asserted in prose.

    Rebuild one year's 31 Mar - 30 May window from the other years -- exactly the operation
    the 2026 tail needs -- and require the sun-up flag to survive it.
    """
    legacy = clearsky._legacy_clearsky()
    window = legacy[((legacy["MO"] == 3) & (legacy["DY"] == 31)) | legacy["MO"].isin([4, 5])]
    window = window[~((window["MO"] == 5) & (window["DY"] > 30))]
    year = window["datetime"].dt.year
    held_out = year.max() - 1  # a complete year, not the ragged edge of the record

    train = window[year != held_out]
    test = window[year == held_out]
    cell = (
        train.groupby(["city", "MO", "DY", "HR"])[clearsky.CLEARSKY_COLUMN]
        .median().rename("pred")
    )
    joined = test.merge(cell, on=["city", "MO", "DY", "HR"], how="left")
    assert joined["pred"].notna().all()

    truth = joined[clearsky.CLEARSKY_COLUMN]
    flag_error = ((joined["pred"] > 0) != (truth > 0)).mean()
    assert flag_error < 0.002, f"sun-up flag wrong on {flag_error:.4%} of held-out hours"

    lit = truth > 20
    mape = ((joined.loc[lit, "pred"] - truth[lit]).abs() / truth[lit]).mean()
    assert mape < 0.10, f"clear-sky magnitude MAPE {mape:.3%} over lit hours"
    assert np.isfinite(mape)
