import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
import pytest

from merve_solar import eda
from merve_solar.config import TARGET_COLUMN


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


def test_daylight_mask_keeps_overcast_daylight_hours():
    """A realised zero inside a climatologically-lit cell must survive the filter.

    This is the whole point of the climatological mask: `target > 0` would delete exactly
    the overcast hours the correlation analysis needs.
    """
    df = _synthetic(periods=24 * 60, cities=("Ankara",))
    noon = df.index[(df["HR"] == 12)][5]
    df.loc[noon, TARGET_COLUMN] = 0.0
    mask = eda.daylight_mask(df)
    assert mask.loc[noon], "overcast noon hour was dropped by the daylight filter"
    assert not mask[df["HR"] == 0].any(), "true night hours were kept"


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


def test_daily_totals_are_invariant_to_the_daylight_filter():
    df = _synthetic(periods=24 * 90)
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
    df = _synthetic(periods=24 * 40)
    df = df.assign(T2M=1.0, RH2M=2.0, QV2M=3.0, T2MDEW=4.0, PS=5.0,
                   WS10M=6.0, WS50M=7.0, PRECTOTCORR=8.0)
    table = eda.descriptive_table(df)
    assert len(table) == 3 * 9  # 2 cities + pooled, 9 variables
    assert table.groupby("city")["variable"].nunique().eq(9).all()
    assert table.loc[table["city"] == eda.POOLED_LABEL, "n"].iloc[0] == len(df)
