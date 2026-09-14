"""The solar geometry that replaced NASA POWER's clear-sky column.

`solar.py` now decides which hours are daylight, which is the denominator of every headline
metric and the condition `clamp_night_to_zero` acts on. A regression here would not crash
anything -- it would quietly move the paper's numbers -- so the properties are pinned.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar import solar
from merve_solar.config import BASE_FEATURES_PATH, CITIES, PROVINCE_SITES, TARGET_COLUMN
from merve_solar.data import load_base_features


@pytest.fixture(scope="module")
def frame():
    return load_base_features(BASE_FEATURES_PATH)


def test_every_province_has_a_site():
    assert sorted(PROVINCE_SITES) == sorted(CITIES)
    for city, site in PROVINCE_SITES.items():
        assert 35.0 < site["latitude"] < 43.0, city   # Türkiye
        assert 25.0 < site["longitude"] < 45.0, city
        assert 0 <= site["altitude_m"] < 3000, city


def test_utc_offset_matches_the_records_own_clock():
    """The timestamps are UTC + round(lon/15); the data has to agree.

    Checked the way the convention was discovered: solar noon in record time should land at
    12 - lon/15 + offset, and the observed irradiance-weighted peak hour (interval start, so
    +0.5 for the centre) should match it.
    """
    expected = {"Ankara": 11.81, "Antalya": 11.95, "Konya": 11.83, "Rize": 12.30, "Van": 12.11}
    for city, site in PROVINCE_SITES.items():
        offset = solar.utc_offset_hours(site["longitude"])
        noon = 12.0 - site["longitude"] / 15.0 + offset
        assert abs(noon - expected[city]) < 0.02, city


def test_observed_peak_hour_matches_the_computed_solar_noon(frame):
    day = frame["solar_elevation"] > 0
    lit = frame[day]
    for city, site in PROVINCE_SITES.items():
        sub = lit[lit["city"] == city]
        profile = sub.groupby("HR")[TARGET_COLUMN].mean()
        observed = float(np.average(profile.index, weights=profile.to_numpy())) + 0.5
        computed = 12.0 - site["longitude"] / 15.0 + solar.utc_offset_hours(site["longitude"])
        assert abs(observed - computed) < 0.2, (city, observed, computed)


def test_elevation_is_bounded_and_seasonal(frame):
    elevation = frame["solar_elevation"].to_numpy()
    assert np.isfinite(elevation).all()
    assert elevation.min() > -90.0 and elevation.max() < 90.0
    # The sun cannot reach the zenith at these latitudes (all above the Tropic of Cancer).
    assert elevation.max() < 78.0


def test_the_mask_never_calls_a_lit_hour_night_in_the_dangerous_direction(frame):
    """Night must mean dark, and the disagreements must be the harmless kind.

    The geometric mask and the realised target are different definitions and do not have to
    agree exactly -- an hour whose sunrise falls inside it is "night" here while carrying a
    little energy. What must not happen is the reverse of the project's intent: the mask must
    not be inflating the daylight subset with hours that are really dark.
    """
    day = (frame["solar_elevation"] > 0).to_numpy()
    positive = (frame[TARGET_COLUMN] > 0).to_numpy()
    # Hours called daylight that read exactly zero: these would be free wins in the metric.
    assert int((day & ~positive).sum()) < 100
    # Hours called night that carry energy: allowed (sunrise inside the interval), but they
    # are twilight, so their share of total daylight energy must be negligible.
    dropped = frame.loc[~day & positive, TARGET_COLUMN].sum()
    kept = frame.loc[day, TARGET_COLUMN].sum()
    assert dropped / kept < 0.005


def test_clearness_index_is_physically_admissible(frame):
    """kt = GHI / TOA cannot exceed ~1 by more than measurement noise."""
    toa = frame["toa_horizontal"].to_numpy()
    lit = toa > 20.0
    kt = frame[TARGET_COLUMN].to_numpy()[lit] / toa[lit]
    assert np.isfinite(kt).all()
    assert np.median(kt) < 0.75          # atmospheric transmittance, not a clear-sky ratio
    assert np.percentile(kt, 99) < 0.90
    assert (kt > 1.0).mean() < 1e-4


def test_toa_is_zero_exactly_where_the_sun_is_down(frame):
    down = frame["solar_elevation"].to_numpy() <= 0
    assert (frame["toa_horizontal"].to_numpy()[down] == 0).all()
    assert (frame["toa_horizontal"].to_numpy()[~down] > 0).all()


def test_geometry_does_not_depend_on_the_frames_other_columns():
    """The mask is a function of (site, timestamp) and nothing else -- that is the whole point."""
    stamps = pd.date_range("2025-06-21", periods=48, freq="h")
    first = solar.apparent_elevation("Ankara", stamps)
    second = solar.apparent_elevation("Ankara", pd.Series(stamps))
    np.testing.assert_allclose(first, second)
    assert solar.apparent_elevation("Rize", stamps).max() != pytest.approx(first.max())


def test_unknown_city_is_refused():
    with pytest.raises(ValueError, match="no site definition"):
        solar.apparent_elevation("Bursa", pd.date_range("2025-01-01", periods=3, freq="h"))
