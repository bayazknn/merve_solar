"""Reconstruct CLRSKY_SFC_SW_DWN, which the 14-Sep-2026 export no longer contains.

Why this module exists
----------------------
`CLRSKY_SFC_SW_DWN` is not a feature and never will be, but it is load-bearing in four places:

  * it defines the **daylight subset** every headline metric is reported on (`CLRSKY > 0`),
  * it is the instrument behind `clamp_night_to_zero`,
  * it is the denominator of the clearness index `kt = ALLSKY / CLRSKY`, which is both the
    `target_transform="clearsky_index"` arm and most of the EDA's cross-city comparison,
  * it is what the smart-persistence baseline multiplies forward.

The previous export carried it; the 14-Sep-2026 one does not. Removing the column would not
"simplify" anything -- it would delete the daylight subset, i.e. the paper's headline numbers.

The reconstruction, and what it costs
-------------------------------------
Two sources, in order of preference:

1. **Exact.** The two exports are the same NASA POWER record. Joined on (city, datetime) over
   the 59,184 shared hours per province, every meteorological column is bit-identical and the
   irradiance agrees to the unit conversion. So for every hour the old export covers
   (2019-06-30 00:00 -> 2026-03-30 23:00) the clear-sky value is taken from it verbatim. That
   is 59,184 of 60,648 usable hours per province: **97.6%**.

2. **Across-year median.** The remaining 1,464 hours per province (2026-03-31 -> 2026-05-30)
   have no source at all, so they are filled with the median over prior years of the same
   (city, month, day, hour) cell. Solar position at a fixed calendar date and hour repeats to
   within a few tenths of a degree, so this is a near-exact reconstruction of the geometry and
   an average over the atmospheric term.

Accuracy, measured by hold-out (rebuild each year's 31 Mar - 30 May window from the other
years, exactly the operation the tail needs; see the module test):

    sun-up flag wrong on  0.000%-0.082% of hours   <- what the daylight subset depends on
    MAE over lit hours    24.0-30.7 W/m^2  (6.0%-8.1%)   <- what kt depends on

So the daylight mask is effectively exact, and kt in the final two months of the record carries
a few-percent denominator error. Both are stated wherever they matter.

This module is a bridge, not a design. The fix is a re-export including the parameter; when one
arrives, drop `LEGACY_XLSX_PATH`, read the column in `data.py` like any other, and delete this
file.
"""
import numpy as np
import pandas as pd

from merve_solar.config import (
    CITIES,
    CLEARSKY_REFERENCE_PATH,
    LAST_VALID_TIMESTAMP,
    LEGACY_XLSX_PATH,
    MISSING_SENTINEL,
    RAW_XLSX_PATH,
)

CLEARSKY_COLUMN = "CLRSKY_SFC_SW_DWN"
# Provenance of each row: "measured" = verbatim from the previous export, "climatology" =
# across-year median of the same (city, MO, DY, HR) cell. Carried in the cache but NOT merged
# into base_features.parquet -- it is documentation, not data the model may see.
SOURCE_COLUMN = "clrsky_source"


def _legacy_clearsky() -> pd.DataFrame:
    """Every clear-sky hour the superseded export can supply, already sentinel-checked."""
    frames = []
    for city in CITIES:
        raw = pd.read_excel(
            LEGACY_XLSX_PATH, sheet_name=city, engine="openpyxl",
            usecols=["YEAR", "MO", "DY", "HR", CLEARSKY_COLUMN],
        )
        raw["datetime"] = pd.to_datetime(
            {"year": raw["YEAR"], "month": raw["MO"], "day": raw["DY"], "hour": raw["HR"]}
        )
        # The old export's own -999 tail starts at 2026-03-31; trim to what is real. This is
        # deliberately not LAST_VALID_TIMESTAMP (that belongs to the new file, and is later).
        raw = raw[raw[CLEARSKY_COLUMN] != MISSING_SENTINEL].reset_index(drop=True)
        if (raw[CLEARSKY_COLUMN] == MISSING_SENTINEL).any():
            raise ValueError(f"{city}: -999 remains in {CLEARSKY_COLUMN}.")
        raw["city"] = city
        frames.append(raw[["datetime", "city", "MO", "DY", "HR", CLEARSKY_COLUMN]])
    return pd.concat(frames, ignore_index=True)


def _target_index() -> pd.DataFrame:
    """(datetime, city) for every row the CURRENT export will keep after trimming."""
    frames = []
    for city in CITIES:
        raw = pd.read_excel(
            RAW_XLSX_PATH, sheet_name=city, engine="openpyxl", usecols=["YEAR", "MO", "DY", "HR"]
        )
        raw["datetime"] = pd.to_datetime(
            {"year": raw["YEAR"], "month": raw["MO"], "day": raw["DY"], "hour": raw["HR"]}
        )
        raw = raw[raw["datetime"] <= pd.Timestamp(LAST_VALID_TIMESTAMP)].reset_index(drop=True)
        raw["city"] = city
        frames.append(raw[["datetime", "city", "MO", "DY", "HR"]])
    return pd.concat(frames, ignore_index=True)


def build_clearsky_reference() -> pd.DataFrame:
    """Build and cache the clear-sky reference for the current export's full index."""
    legacy = _legacy_clearsky()
    index = _target_index()

    out = index.merge(
        legacy[["datetime", "city", CLEARSKY_COLUMN]],
        on=["datetime", "city"], how="left", validate="one_to_one",
    )
    out[SOURCE_COLUMN] = np.where(out[CLEARSKY_COLUMN].notna(), "measured", "climatology")

    # Fill the uncovered tail from the same calendar cell in other years. 29 February has no
    # donor in a run of years that contains only one leap year, so fall back to the (MO, HR)
    # cell for any cell the day-level median cannot reach.
    cell = legacy.groupby(["city", "MO", "DY", "HR"])[CLEARSKY_COLUMN].median().rename("_cell")
    coarse = legacy.groupby(["city", "MO", "HR"])[CLEARSKY_COLUMN].median().rename("_coarse")
    out = out.merge(cell, on=["city", "MO", "DY", "HR"], how="left")
    out = out.merge(coarse, on=["city", "MO", "HR"], how="left")
    out[CLEARSKY_COLUMN] = out[CLEARSKY_COLUMN].fillna(out["_cell"]).fillna(out["_coarse"])
    out = out.drop(columns=["_cell", "_coarse"])

    if out[CLEARSKY_COLUMN].isna().any():
        missing = out.loc[out[CLEARSKY_COLUMN].isna(), ["city", "datetime"]]
        raise ValueError(
            f"clear-sky reconstruction left {len(missing)} hours unfilled, first: "
            f"{missing.iloc[0].to_dict()}"
        )
    if (out[CLEARSKY_COLUMN] < 0).any():
        raise ValueError("clear-sky reconstruction produced negative irradiance.")

    out = out[["datetime", "city", CLEARSKY_COLUMN, SOURCE_COLUMN]].sort_values(
        ["city", "datetime"]
    ).reset_index(drop=True)
    CLEARSKY_REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CLEARSKY_REFERENCE_PATH, index=False)
    return out


_CACHE = None


def load_clearsky_reference() -> pd.DataFrame:
    """Cached clear-sky reference, built on first use.

    Process-local memoisation on top of the parquet: the EDA script asks for this repeatedly
    and the build reads two workbooks.
    """
    global _CACHE
    if _CACHE is None:
        _CACHE = (
            pd.read_parquet(CLEARSKY_REFERENCE_PATH)
            if CLEARSKY_REFERENCE_PATH.exists()
            else build_clearsky_reference()
        )
    return _CACHE


def reconstruction_summary() -> pd.DataFrame:
    """Per-province provenance counts -- what to quote when reporting the daylight subset."""
    ref = load_clearsky_reference()
    rows = []
    for city, sub in ref.groupby("city", observed=True):
        measured = int((sub[SOURCE_COLUMN] == "measured").sum())
        rows.append(
            {
                "city": city,
                "n_hours": len(sub),
                "n_measured": measured,
                "n_climatology": len(sub) - measured,
                "measured_share": measured / len(sub),
                "climatology_first": sub.loc[
                    sub[SOURCE_COLUMN] == "climatology", "datetime"
                ].min(),
                "climatology_last": sub.loc[
                    sub[SOURCE_COLUMN] == "climatology", "datetime"
                ].max(),
            }
        )
    return pd.DataFrame(rows)
