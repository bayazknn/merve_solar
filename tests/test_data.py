import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from merve_solar.config import (
    CITIES,
    DROPPED_COLUMNS,
    EXPECTED_TRIMMED_ROWS_PER_SHEET,
    TARGET_COLUMN,
)
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


def test_dropped_columns_removed(city_df):
    _, df = city_df
    assert not set(DROPPED_COLUMNS) & set(df.columns)


def test_target_column_present(city_df):
    _, df = city_df
    assert TARGET_COLUMN in df.columns
    assert TARGET_COLUMN not in DROPPED_COLUMNS
    assert (df[TARGET_COLUMN] >= 0).all()
