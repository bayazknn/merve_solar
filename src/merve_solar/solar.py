"""Solar geometry: where the sun is, for each province and hour.

This module replaces the project's dependence on NASA POWER's `CLRSKY_SFC_SW_DWN` column,
which the 14-Sep-2026 export no longer contains. It supplies the one thing that column was
load-bearing for and that nothing else can provide: **an "is the sun above the horizon"
indicator that is a pure function of (site, timestamp) and never reads the realised target.**

Why not just test `target > 0`
------------------------------
It is tempting, and on this dataset it agrees with the geometry on 303,204 of 303,240 rows.
It is still wrong, for two reasons, and the second one is decisive:

1. **It selects the evaluation set using the answer.** The daylight subset is the denominator
   of every headline metric. If membership depends on the realised target, a heavily overcast
   twilight hour reads 0 and silently leaves the subset -- i.e. the hours where the model is
   worst are the ones that get dropped. Here that is 36 rows (the export's 2.78 W/m^2
   quantisation makes real daylight hours store as 0.00), so the bias is tiny; the mechanism
   is not bounded by anything, which is the problem.
2. **It cannot be evaluated at prediction time.** `clamp_night_to_zero` has to decide, for an
   hour 24 h in the future, whether the sun will be up. `y` is not available then. A clamp that
   used it would report skill that is unattainable operationally. So geometry is required
   regardless -- and once it exists, using a *different* definition for the metric subset
   would make the two incoherent.

Conventions, all verified against this record
---------------------------------------------
* **Timestamps are per-site local solar time**, specifically `UTC + round(lon/15)`. Confirmed
  from the data: the irradiance-weighted peak hour runs Konya 11.24 ~ Ankara 11.24 <
  Antalya 11.41 < Van 11.58 < Rize 11.91, which is the *reverse* of what a shared clock would
  give and matches this rule to within 0.11 h. The offset is derived from the longitude rather
  than stored, so the two can never disagree.
* **Hour labels are interval starts**, so hour `h` covers `[h, h+1)` and the sun's position is
  evaluated at its **midpoint**. Measured on the record, the midpoint is the rule that best
  separates lit hours from dark ones; testing the interval's edges instead admits ~8,600 hours
  whose irradiance is exactly zero, which is precisely the night inflation the daylight subset
  exists to remove.
* **Daylight means apparent elevation > 0** -- refraction included, the standard visible-sunrise
  definition. It is deliberately NOT a tuned threshold: sweeping the cut-off does find a
  slightly better fit to the realised target (-2.0 deg minimises disagreement at 587 rows
  against 3,034), but tuning a geometric mask against the target reintroduces exactly the
  conditioning this module exists to avoid. What the untuned choice costs is measured: the
  climatology floor's daylight RMSE moves 108.78 -> 109.86 W/m^2 and R^2 0.8514 -> 0.8460
  against the old `CLRSKY > 0` mask.

Site altitude enters only through the refraction correction and moves sunrise by under a
minute, so published province elevations are used rather than the MERRA-2 cell's model terrain.
"""
import numpy as np
import pandas as pd

from merve_solar.config import PROVINCE_SITES

# The quantity every caller actually wants; kept here so the definition lives in one place.
DAYLIGHT_ELEVATION_THRESHOLD_DEG = 0.0


def utc_offset_hours(longitude: float) -> int:
    """The whole-hour zone NASA POWER stamped this site's rows in."""
    return int(round(longitude / 15.0))


def apparent_elevation(city: str, local_datetimes) -> np.ndarray:
    """Apparent solar elevation in degrees at the MIDPOINT of each labelled hour.

    `local_datetimes` are the record's own timestamps, i.e. already in the site's
    `UTC + round(lon/15)` zone and labelled by interval start.
    """
    import pvlib  # local: heavy import, and only the geometry path needs it

    if city not in PROVINCE_SITES:
        raise ValueError(f"no site definition for {city!r}; known: {sorted(PROVINCE_SITES)}")
    site = PROVINCE_SITES[city]
    offset = utc_offset_hours(site["longitude"])

    midpoint_utc = (
        pd.DatetimeIndex(pd.to_datetime(local_datetimes))
        - pd.Timedelta(hours=offset)
        + pd.Timedelta(minutes=30)
    ).tz_localize("UTC")

    location = pvlib.location.Location(
        site["latitude"], site["longitude"], altitude=site["altitude_m"]
    )
    return location.get_solarposition(midpoint_utc)["apparent_elevation"].to_numpy()


def is_daylight(elevation_deg) -> np.ndarray:
    """The project's daylight predicate, in one place so it cannot drift between callers."""
    return np.asarray(elevation_deg) > DAYLIGHT_ELEVATION_THRESHOLD_DEG


def extraterrestrial_horizontal(city: str, local_datetimes) -> np.ndarray:
    """Top-of-atmosphere irradiance on a horizontal surface, W/m^2, at the hour midpoint.

    `I0 * sin(elevation)`, with `I0` the extraterrestrial normal irradiance including the
    Earth-Sun distance correction. Pure astronomy: no atmosphere, no aerosol, no turbidity,
    nothing fitted. Zero below the horizon.

    This is the denominator of the CLEARNESS INDEX as the solar literature defines it,

        kt = GHI / (I0 * cos(theta_z)),

    which is what this project now uses everywhere it used to divide by NASA POWER's
    `CLRSKY_SFC_SW_DWN`. The substitution is an improvement, not a fallback:

      * it is computable from the site and the timestamp alone, so it survives any export;
      * it is the standard definition, so the numbers are comparable to the literature rather
        than to one provider's clear-sky product;
      * it is better behaved. Measured on this record, kt has median 0.555 and p99 0.801, with
        2 hours of 150,746 above 1.0 -- against the clear-sky-index form's 2.9% above 1.0, an
        artefact of the export's 2.78 W/m^2 quantisation landing on a near-unity denominator.

    The scale differs and must not be mixed with the old numbers: a cloudless hour reads
    kt ~ 0.75-0.80 here (atmospheric transmittance) where the clear-sky index read ~1.0.
    """
    import pvlib  # local: see apparent_elevation

    site = PROVINCE_SITES[city]
    offset = utc_offset_hours(site["longitude"])
    midpoint_utc = (
        pd.DatetimeIndex(pd.to_datetime(local_datetimes))
        - pd.Timedelta(hours=offset)
        + pd.Timedelta(minutes=30)
    ).tz_localize("UTC")

    elevation = apparent_elevation(city, local_datetimes)
    normal = pvlib.irradiance.get_extra_radiation(midpoint_utc).to_numpy()
    return np.maximum(normal * np.sin(np.deg2rad(np.maximum(elevation, 0.0))), 0.0)
