import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar import eda
from merve_solar.config import RAW_METEO_COLUMNS, TARGET_COLUMN


def _synthetic(start="2024-01-01", periods=24 * 400, cities=("Ankara", "Rize")):
    """A small two-city hourly frame with a plausible day/night irradiance cycle."""
    idx = pd.date_range(start, periods=periods, freq="h")
    frames = []
    for city in cities:
        hour = idx.hour.to_numpy()
        doy = idx.dayofyear.to_numpy()
        seasonal = 0.5 + 0.5 * np.sin(2 * np.pi * (doy - 80) / 365.25)
        shape = np.clip(np.sin(np.pi * (hour - 6) / 12), 0, None)
        frames.append(
            pd.DataFrame(
                {
                    "datetime": idx,
                    "YEAR": idx.year,
                    "MO": idx.month,
                    "DY": idx.day,
                    "HR": hour,
                    TARGET_COLUMN: 900 * shape * seasonal,
                    # Geometry columns, as data.py attaches them: elevation in degrees and
                    # the top-of-atmosphere horizontal irradiance kt is divided by.
                    "solar_elevation": np.where((hour >= 6) & (hour <= 18), 30.0, -20.0),
                    "toa_horizontal": 1361.0 * shape,
                    "city": city,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_season_mapping_is_meteorological():
    df = _synthetic(periods=24 * 370)
    seasons = eda.add_season(df).groupby("MO", observed=True)["season"].first()
    assert seasons[12] == "Kış" and seasons[1] == "Kış" and seasons[2] == "Kış"
    assert seasons[3] == "İlkbahar"
    assert seasons[7] == "Yaz"
    assert seasons[10] == "Sonbahar"


def test_daylight_mask_is_geometric_not_value_based():
    """The mask must come from the sun's computed position, not from the realised target.

    A fully overcast noon reading of 0.0 is still daylight; the geometry says so regardless
    of the weather. This is the property that keeps the metric subset from being selected
    with the answer -- see solar.py.
    """
    df = _synthetic(periods=24 * 5, cities=("Ankara",))
    df["solar_elevation"] = np.where((df["HR"] >= 6) & (df["HR"] <= 18), 30.0, -20.0)

    noon = df.index[df["HR"] == 12][2]
    df.loc[noon, TARGET_COLUMN] = 0.0
    mask = eda.daylight_mask(df)
    assert mask.loc[noon], "an overcast noon hour was dropped by the daylight filter"
    assert not mask[df["HR"] == 0].any(), "night hours were kept"
    assert mask.sum() == (13 * 5), "daylight span must follow the solar elevation column"


def test_daylight_mask_refuses_a_frame_without_the_geometry_column():
    """A stale parquet is the realistic failure, and it must be loud.

    Without solar_elevation the only thing left to fall back on is the target, which is
    exactly the definition this project rejects -- so there is no fallback.
    """
    df = _synthetic(periods=24 * 3, cities=("Ankara",))
    with pytest.raises(ValueError, match="solar_elevation"):
        eda.daylight_mask(df.drop(columns=["solar_elevation"], errors="ignore"))


def test_last_12_months_is_exactly_twelve_ordered_months():
    df = _synthetic(start="2024-06-01", periods=24 * 670, cities=("Ankara",))
    daily = eda.daily_totals(df)
    out = eda.last_12_months(daily, date_col="date")
    categories = list(out["ym"].cat.categories)
    assert len(categories) == 12
    assert categories[-1] == daily["date"].max().to_period("M")
    assert categories[0] == categories[-1] - 11
    # ordering, not alphabetical/calendar sorting
    assert list(out["ym_label"].cat.categories) == [
        f"{eda.MONTH_ABBR_TR[p.month]} {str(p.year)[2:]}" for p in categories
    ]


def test_daily_totals_are_invariant_to_the_daylight_filter(monkeypatch):
    df = _synthetic(periods=24 * 90)
    df["solar_elevation"] = np.where((df["HR"] >= 6) & (df["HR"] <= 18), 30.0, -20.0)
    full = eda.daily_totals(df).set_index(["city", "date"])["daily_kwh"]
    filtered = eda.daily_totals(df[eda.daylight_mask(df)]).set_index(["city", "date"])["daily_kwh"]
    pd.testing.assert_series_equal(full, filtered, check_names=False)


def test_circular_mean_wraps_around_zero():
    degrees = np.array([350.0, 10.0])
    radians = np.deg2rad(degrees)
    stats = eda.circular_stats(np.sin(radians), np.cos(radians))
    assert stats["mean_deg"] == pytest.approx(0.0, abs=1e-6)
    assert stats["resultant_length"] == pytest.approx(0.985, abs=1e-3)


def test_day_of_year_alignment_across_leap_years():
    dates = pd.Series(pd.to_datetime(["2020-03-01", "2021-03-01", "2020-02-29", "2020-01-15"]))
    aligned = eda.align_day_of_year(dates)
    assert aligned[0] == aligned[1], "1 March must align between leap and non-leap years"
    assert np.isnan(aligned[2]), "29 February must be dropped"
    assert aligned[3] == 15, "dates before 29 February are unchanged"


def test_month_year_grid_raises_on_a_hole():
    df = _synthetic(start="2020-01-01", periods=24 * 366 * 2, cities=("Ankara",))
    daily = eda.daily_totals(df)
    holed = daily[~((daily["YEAR"] == 2020) & (daily["MO"] == 5))]
    with pytest.raises(ValueError, match="empty cells"):
        eda.month_year_grid(holed, "Ankara")


def test_descriptive_table_has_one_row_per_city_and_variable():
    # Columns come from RAW_METEO_COLUMNS rather than a literal list: the export's parameter
    # set has changed once already (17 features -> 16), and a hard-coded fixture turns that
    # into a test failure that says "KeyError: WS2M" instead of anything useful.
    df = _synthetic(periods=24 * 40)
    n_vars = len(RAW_METEO_COLUMNS)
    df = df.assign(**{c: float(i + 1) for i, c in enumerate(RAW_METEO_COLUMNS)
                      if c != TARGET_COLUMN})
    table = eda.descriptive_table(df)
    assert len(table) == 3 * n_vars  # 2 cities + pooled
    assert table.groupby("city")["variable"].nunique().eq(n_vars).all()
    assert table.loc[table["city"] == eda.POOLED_LABEL, "n"].iloc[0] == len(df)


def test_acf_and_pacf_recover_a_known_ar1():
    """An AR(1) with coefficient phi has acf[k] = phi^k and pacf[k] = 0 for k >= 2."""
    rng = np.random.default_rng(0)
    phi = 0.7
    x = np.zeros(20000)
    for t in range(1, len(x)):
        x[t] = phi * x[t - 1] + rng.normal()
    acf = eda._acf(x, 5)
    pacf = eda._pacf_from_acf(acf)
    assert acf[1] == pytest.approx(phi, abs=0.03)
    assert acf[2] == pytest.approx(phi ** 2, abs=0.03)
    assert pacf[1] == pytest.approx(phi, abs=0.03)
    assert abs(pacf[2]) < 0.05
    assert abs(pacf[3]) < 0.05


def test_acf_tolerates_gaps():
    """Night masking leaves NaNs; the pairwise ACF must still recover the AR(1) structure."""
    rng = np.random.default_rng(1)
    x = np.zeros(20000)
    for t in range(1, len(x)):
        x[t] = 0.7 * x[t - 1] + rng.normal()
    gapped = x.copy()
    gapped[::5] = np.nan
    assert eda._acf(gapped, 3)[1] == pytest.approx(0.7, abs=0.05)


def test_daylight_blocks_are_shorter_than_a_lookback_plus_horizon(monkeypatch):
    """The evidence behind TODOs.md item A: no daylight-only run reaches 48 hours."""
    df = _synthetic(periods=24 * 120)
    df["solar_elevation"] = np.where((df["HR"] >= 6) & (df["HR"] <= 18), 30.0, -20.0)
    blocks = eda.daylight_block_table(df)
    assert (blocks["share_blocks_ge_48h"] == 0).all()
    assert (blocks["block_len_max"] < 24).all()
    assert (blocks["n_blocks"] == 120).all()
