import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from merve_solar.config import CITIES, EXPECTED_TRIMMED_ROWS_PER_SHEET
from merve_solar.data import load_city_sheet

FULL_ROWS_PER_SHEET = 61392


@pytest.fixture(scope="module", params=CITIES)
def city_df(request):
    return request.param, load_city_sheet(request.param)


def test_trim_removes_exact_row_count(city_df):
    _, df = city_df
    assert len(df) == FULL_ROWS_PER_SHEET - EXPECTED_TRIMMED_ROWS_PER_SHEET


def test_no_sentinel_or_nan_remains(city_df):
    _, df = city_df
    numeric_cols = df.select_dtypes(include="number").columns
    assert not (df[numeric_cols] == -999).any().any()
    assert not df.isnull().any().any()


def test_allsky_kt_dropped(city_df):
    _, df = city_df
    assert "ALLSKY_KT" not in df.columns
