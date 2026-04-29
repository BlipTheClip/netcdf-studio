"""
Climate indices — ENSO, NAO, and ETCCDI precipitation extremes.

All functions are pure: they return lazy xr.DataArray objects backed by dask.
No disk I/O; computation is deferred until the caller calls .compute() or
passes the result to save_dataarray().

Scientific references
---------------------
ENSO:  Trenberth (1997), https://doi.org/10.1175/1520-0477(1997)078<2771:TDOSO>2.0.CO;2
NAO:   Hurrell (1995), https://doi.org/10.1126/science.269.5224.676
ETCCDI: Zhang et al. (2011), https://doi.org/10.1002/wcc.147
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import xarray as xr

from ._coords import _LAT_ALIASES, _LON_ALIASES, _TIME_ALIASES, detect_coord

logger = logging.getLogger(__name__)

# Niño box definitions [lat_min, lat_max, lon_min, lon_max] in -180..180 convention
_NINO_BOXES: dict[str, tuple[float, float, float, float]] = {
    "1+2": (-10.0, 0.0, -90.0, -80.0),
    "3":   (-5.0,  5.0, -150.0, -90.0),
    "3.4": (-5.0,  5.0, -170.0, -120.0),
    "4":   (-5.0,  5.0, 160.0, -150.0),   # wraps antimeridian
}

# NAO box centres (Hurrell station-based, approximated as 2° boxes)
_NAO_AZORES_BOX  = (36.8, 38.8, -26.5, -24.5)   # Ponta Delgada area
_NAO_ICELAND_BOX = (63.1, 65.1, -23.9, -21.9)   # Reykjavik area


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_var(ds: xr.Dataset, variable: str) -> xr.DataArray:
    if variable not in ds:
        raise KeyError(
            f"Variable '{variable}' not found. Available: {list(ds.data_vars)}"
        )
    return ds[variable]


def _require_coords(da: xr.DataArray, *alias_sets) -> list[str | None]:
    return [detect_coord(da, aliases) for aliases in alias_sets]


def _select_latlon_box(
    da: xr.DataArray,
    lat_c: str,
    lon_c: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> xr.DataArray:
    """
    Select a lat/lon bounding box, handling both 0-360 and -180-180 lon conventions
    and antimeridian-crossing boxes (e.g. Niño 4: 160°E to 150°W).
    """
    lon_vals = da[lon_c].values
    uses_0_360 = float(lon_vals.max()) > 180.0

    # Convert box bounds to match the dataset's convention
    if uses_0_360:
        lon_min = lon_min % 360.0
        lon_max = lon_max % 360.0

    # Select latitude first
    da = da.sel({lat_c: slice(lat_min, lat_max)})

    # Handle antimeridian crossing (lon_min > lon_max after normalisation)
    if lon_min > lon_max:
        east = da.sel({lon_c: slice(lon_min, None)})
        west = da.sel({lon_c: slice(None, lon_max)})
        da = xr.concat([east, west], dim=lon_c)
    else:
        da = da.sel({lon_c: slice(lon_min, lon_max)})

    return da


def _box_weighted_mean(da: xr.DataArray, lat_c: str, lon_c: str) -> xr.DataArray:
    """Area-weighted mean over all spatial dims, preserving time."""
    weights = np.cos(np.deg2rad(da[lat_c]))
    weights.name = "weights"
    return da.weighted(weights).mean([lat_c, lon_c])


def _monthly_anomaly(ts: xr.DataArray, time_c: str, start_year: int, end_year: int) -> xr.DataArray:
    """Compute monthly anomaly relative to a base period climatology."""
    base = ts.sel({time_c: slice(str(start_year), str(end_year))})
    if base[time_c].size == 0:
        raise ValueError(
            f"No data in base period {start_year}–{end_year}. "
            f"Dataset spans: {ts[time_c].values[0]} – {ts[time_c].values[-1]}"
        )
    clim = base.groupby(f"{time_c}.month").mean(time_c)
    return ts.groupby(f"{time_c}.month") - clim


def _nino_index(
    ds: xr.Dataset,
    sst_variable: str,
    box_key: str,
    base_period: tuple[int, int],
) -> xr.DataArray:
    """Generic Niño index: box-averaged SST monthly anomaly."""
    da = _require_var(ds, sst_variable)
    lat_c, lon_c, time_c = _require_coords(da, _LAT_ALIASES, _LON_ALIASES, _TIME_ALIASES)
    if lat_c is None or lon_c is None or time_c is None:
        raise ValueError(
            f"Variable '{sst_variable}' must have lat, lon, and time coordinates"
        )

    lat_min, lat_max, lon_min, lon_max = _NINO_BOXES[box_key]
    da_box = _select_latlon_box(da, lat_c, lon_c, lat_min, lat_max, lon_min, lon_max)
    ts = _box_weighted_mean(da_box, lat_c, lon_c)
    return _monthly_anomaly(ts, time_c, *base_period)


def _ensure_mm_day(da: xr.DataArray) -> xr.DataArray:
    """
    Convert precipitation to mm/day.

    CMIP6 standard is kg m-2 s-1 = mm/s. ERA5 uses the same convention.
    If the units attribute indicates the data is already in mm/day, no
    conversion is applied. Unknown units are left unchanged with a warning.
    """
    units = str(da.attrs.get("units", "")).strip().lower()

    # mm/s or kg/m²/s → multiply by 86400
    if units in ("kg m-2 s-1", "kg/m2/s", "kg/m^2/s", "mm/s", "mm s-1",
                 "kg m**-2 s**-1"):
        da = da * 86400.0
        da.attrs["units"] = "mm/day"

    # m/s (rare but occurs in some observational products)
    elif units in ("m s-1", "m/s"):
        da = da * 86_400_000.0
        da.attrs["units"] = "mm/day"

    # Already in mm/day
    elif units in ("mm/day", "mm day-1", "mm d-1", "mm/d"):
        pass

    else:
        logger.warning(
            "Unrecognised precipitation units '%s'; assuming already in mm/day. "
            "Set da.attrs['units'] explicitly to suppress this warning.",
            da.attrs.get("units", ""),
        )

    return da


def _max_consecutive_run_1d(mask: np.ndarray) -> int:
    """Maximum number of consecutive True values in a 1D boolean array."""
    if not mask.any():
        return 0
    padded = np.concatenate([[False], mask.astype(bool), [False]])
    changes = np.diff(padded.astype(np.int8))
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    runs = ends - starts
    return int(runs.max())


def _annual_max_consecutive(mask: xr.DataArray, time_c: str) -> xr.DataArray:
    """Annual maximum consecutive run of True values via xr.apply_ufunc."""
    return xr.apply_ufunc(
        _max_consecutive_run_1d,
        mask,
        input_core_dims=[[time_c]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[np.int32],
    )


# ---------------------------------------------------------------------------
# ENSO indices
# ---------------------------------------------------------------------------


def compute_nino34(
    ds: xr.Dataset,
    sst_variable: str = "tos",
    base_period: tuple[int, int] = (1991, 2020),
) -> xr.DataArray:
    """
    Niño 3.4 index: area-weighted SST anomaly over 5°S-5°N, 170°W-120°W.

    The most commonly used ENSO index for operational climate monitoring.
    Positive values indicate El Niño conditions.

    Args:
        ds: Dataset with SST variable and monthly time resolution.
        sst_variable: Name of the sea surface temperature variable.
        base_period: (start_year, end_year) for the climatological mean.

    Returns:
        Monthly time series of Niño 3.4 anomalies (units: same as input SST).
    """
    result = _nino_index(ds, sst_variable, "3.4", base_period)
    result.name = "nino34"
    result.attrs["long_name"] = "Niño 3.4 SST anomaly"
    result.attrs["region"] = "5°S-5°N, 170°W-120°W"
    return result


def compute_nino3(
    ds: xr.Dataset,
    sst_variable: str = "tos",
    base_period: tuple[int, int] = (1991, 2020),
) -> xr.DataArray:
    """Niño 3 index: SST anomaly over 5°S-5°N, 150°W-90°W."""
    result = _nino_index(ds, sst_variable, "3", base_period)
    result.name = "nino3"
    result.attrs["long_name"] = "Niño 3 SST anomaly"
    result.attrs["region"] = "5°S-5°N, 150°W-90°W"
    return result


def compute_nino4(
    ds: xr.Dataset,
    sst_variable: str = "tos",
    base_period: tuple[int, int] = (1991, 2020),
) -> xr.DataArray:
    """Niño 4 index: SST anomaly over 5°S-5°N, 160°E-150°W."""
    result = _nino_index(ds, sst_variable, "4", base_period)
    result.name = "nino4"
    result.attrs["long_name"] = "Niño 4 SST anomaly"
    result.attrs["region"] = "5°S-5°N, 160°E-150°W"
    return result


def compute_nino12(
    ds: xr.Dataset,
    sst_variable: str = "tos",
    base_period: tuple[int, int] = (1991, 2020),
) -> xr.DataArray:
    """Niño 1+2 index: SST anomaly over 10°S-0°, 90°W-80°W."""
    result = _nino_index(ds, sst_variable, "1+2", base_period)
    result.name = "nino12"
    result.attrs["long_name"] = "Niño 1+2 SST anomaly"
    result.attrs["region"] = "10°S-0°, 90°W-80°W"
    return result


def compute_oni(
    nino34: xr.DataArray,
    window: int = 3,
) -> xr.DataArray:
    """
    Oceanic Niño Index (ONI): running mean of Niño 3.4.

    El Niño/La Niña events are defined as 5+ consecutive months with ONI ≥ +0.5°C
    or ≤ -0.5°C (NOAA/CPC definition).

    Args:
        nino34: Monthly Niño 3.4 time series from compute_nino34().
        window: Running mean window in months (default: 3, the standard ONI).

    Returns:
        Smoothed monthly Niño 3.4 time series.
    """
    time_c = detect_coord(nino34, _TIME_ALIASES) or "time"
    oni = nino34.rolling({time_c: window}, center=True, min_periods=window).mean()
    oni.name = "oni"
    oni.attrs.update(nino34.attrs)
    oni.attrs["long_name"] = f"Oceanic Niño Index ({window}-month mean of Niño 3.4)"
    oni.attrs["oni_window_months"] = window
    return oni


# ---------------------------------------------------------------------------
# NAO index (Hurrell station-based)
# ---------------------------------------------------------------------------


def compute_nao(
    ds: xr.Dataset,
    slp_variable: str = "psl",
    base_period: tuple[int, int] = (1991, 2020),
) -> xr.DataArray:
    """
    North Atlantic Oscillation (NAO) index, station-based (Hurrell 1995).

    Computed as the normalised SLP anomaly difference between the Azores and
    Iceland. Box averages (2°×2°) centred on Ponta Delgada and Reykjavik are
    used instead of single grid points for robustness with coarse models.

    NAO = (Azores_anomaly / Azores_std) − (Iceland_anomaly / Iceland_std)

    Positive NAO: stronger Azores High + deeper Icelandic Low → enhanced
    westerlies over the North Atlantic.

    Args:
        ds: Dataset with sea-level pressure variable and monthly time resolution.
        slp_variable: Name of the SLP (or MSLP) variable.
        base_period: Reference period for anomaly and normalisation.

    Returns:
        Monthly NAO index time series (dimensionless, normalised).
    """
    da = _require_var(ds, slp_variable)
    lat_c, lon_c, time_c = _require_coords(da, _LAT_ALIASES, _LON_ALIASES, _TIME_ALIASES)
    if lat_c is None or lon_c is None or time_c is None:
        raise ValueError(
            f"Variable '{slp_variable}' must have lat, lon, and time coordinates"
        )

    def _station_normalised(
        lat_min: float, lat_max: float, lon_min: float, lon_max: float
    ) -> xr.DataArray:
        box = _select_latlon_box(da, lat_c, lon_c, lat_min, lat_max, lon_min, lon_max)
        ts = _box_weighted_mean(box, lat_c, lon_c)
        anomaly = _monthly_anomaly(ts, time_c, *base_period)
        # Normalise by std dev over base period
        base_std = anomaly.sel(
            {time_c: slice(str(base_period[0]), str(base_period[1]))}
        ).std(time_c)
        return anomaly / base_std

    nao_azores  = _station_normalised(*_NAO_AZORES_BOX)
    nao_iceland = _station_normalised(*_NAO_ICELAND_BOX)

    nao = nao_azores - nao_iceland
    nao.name = "nao"
    nao.attrs["long_name"] = "North Atlantic Oscillation index (Hurrell station-based)"
    nao.attrs["base_period"] = f"{base_period[0]}-{base_period[1]}"
    nao.attrs["units"] = "1"
    return nao


# ---------------------------------------------------------------------------
# ETCCDI precipitation extremes
# ---------------------------------------------------------------------------


def compute_rx1day(
    ds: xr.Dataset,
    pr_variable: str = "pr",
) -> xr.DataArray:
    """
    Rx1day: Monthly maximum 1-day precipitation (ETCCDI).

    Requires daily precipitation input data.

    Args:
        ds: Dataset with daily precipitation variable.
        pr_variable: Variable name (converted to mm/day automatically).

    Returns:
        Monthly maximum daily precipitation [mm/day].
    """
    da = _ensure_mm_day(_require_var(ds, pr_variable))
    time_c = detect_coord(da, _TIME_ALIASES) or "time"

    result = da.resample({time_c: "1MS"}).max(time_c)
    result.name = "rx1day"
    result.attrs["long_name"] = "Monthly maximum 1-day precipitation"
    result.attrs["units"] = "mm/day"
    return result


def compute_rx5day(
    ds: xr.Dataset,
    pr_variable: str = "pr",
) -> xr.DataArray:
    """
    Rx5day: Monthly maximum consecutive 5-day precipitation total (ETCCDI).

    Requires daily precipitation input data.

    Args:
        ds: Dataset with daily precipitation variable.
        pr_variable: Variable name.

    Returns:
        Monthly maximum 5-day precipitation total [mm].
    """
    da = _ensure_mm_day(_require_var(ds, pr_variable))
    time_c = detect_coord(da, _TIME_ALIASES) or "time"

    rolling_5d = da.rolling({time_c: 5}, center=False, min_periods=5).sum()
    result = rolling_5d.resample({time_c: "1MS"}).max(time_c)
    result.name = "rx5day"
    result.attrs["long_name"] = "Monthly maximum consecutive 5-day precipitation"
    result.attrs["units"] = "mm"
    return result


def compute_r95p(
    ds: xr.Dataset,
    pr_variable: str = "pr",
    base_period: tuple[int, int] = (1991, 2020),
) -> xr.DataArray:
    """
    R95p: Annual total precipitation on days exceeding the 95th percentile
    of wet-day precipitation over the base period (ETCCDI).

    Requires daily precipitation input data.

    Args:
        ds: Dataset with daily precipitation variable.
        pr_variable: Variable name.
        base_period: (start_year, end_year) used to define the 95th percentile.

    Returns:
        Annual total very-heavy precipitation [mm/year].
    """
    da = _ensure_mm_day(_require_var(ds, pr_variable))
    time_c = detect_coord(da, _TIME_ALIASES) or "time"

    # 95th percentile computed on the base period (wet days only, pr ≥ 1 mm/day)
    base = da.sel({time_c: slice(str(base_period[0]), str(base_period[1]))})
    wet_base = base.where(base >= 1.0)
    p95 = wet_base.quantile(0.95, dim=time_c)

    # Annual sum of days exceeding p95
    exceedance = da.where(da > p95)
    result = exceedance.resample({time_c: "1YS"}).sum(time_c)
    result.name = "r95p"
    result.attrs["long_name"] = (
        "Annual total precipitation when daily precipitation > 95th percentile"
    )
    result.attrs["units"] = "mm/year"
    result.attrs["base_period"] = f"{base_period[0]}-{base_period[1]}"
    return result


def compute_prcptot(
    ds: xr.Dataset,
    pr_variable: str = "pr",
    threshold_mm_day: float = 1.0,
) -> xr.DataArray:
    """
    PRCPTOT: Annual total precipitation on wet days (ETCCDI).

    A wet day is defined as any day with precipitation ≥ threshold_mm_day.
    Requires daily precipitation input data.

    Args:
        ds: Dataset with daily precipitation variable.
        pr_variable: Variable name.
        threshold_mm_day: Wet-day threshold in mm/day (default: 1.0).

    Returns:
        Annual total wet-day precipitation [mm/year].
    """
    da = _ensure_mm_day(_require_var(ds, pr_variable))
    time_c = detect_coord(da, _TIME_ALIASES) or "time"

    wet_days = da.where(da >= threshold_mm_day)
    result = wet_days.resample({time_c: "1YS"}).sum(time_c)
    result.name = "prcptot"
    result.attrs["long_name"] = "Annual total precipitation on wet days"
    result.attrs["units"] = "mm/year"
    result.attrs["wet_day_threshold_mm_day"] = threshold_mm_day
    return result


def compute_cdd(
    ds: xr.Dataset,
    pr_variable: str = "pr",
    threshold_mm_day: float = 1.0,
) -> xr.DataArray:
    """
    CDD: Annual maximum number of consecutive dry days (ETCCDI).

    A dry day is any day with precipitation < threshold_mm_day.
    Requires daily precipitation input data.

    Args:
        ds: Dataset with daily precipitation variable.
        pr_variable: Variable name.
        threshold_mm_day: Dry-day threshold in mm/day (default: 1.0).

    Returns:
        Annual maximum consecutive dry-day spell length [days].
    """
    da = _ensure_mm_day(_require_var(ds, pr_variable))
    time_c = detect_coord(da, _TIME_ALIASES) or "time"

    dry_mask = da < threshold_mm_day

    result = dry_mask.resample({time_c: "1YS"}).map(
        lambda g: _annual_max_consecutive(g, time_c)
    )
    result.name = "cdd"
    result.attrs["long_name"] = "Annual maximum consecutive dry days"
    result.attrs["units"] = "days"
    result.attrs["dry_day_threshold_mm_day"] = threshold_mm_day
    return result


def compute_cwd(
    ds: xr.Dataset,
    pr_variable: str = "pr",
    threshold_mm_day: float = 1.0,
) -> xr.DataArray:
    """
    CWD: Annual maximum number of consecutive wet days (ETCCDI).

    A wet day is any day with precipitation ≥ threshold_mm_day.
    Requires daily precipitation input data.

    Args:
        ds: Dataset with daily precipitation variable.
        pr_variable: Variable name.
        threshold_mm_day: Wet-day threshold in mm/day (default: 1.0).

    Returns:
        Annual maximum consecutive wet-day spell length [days].
    """
    da = _ensure_mm_day(_require_var(ds, pr_variable))
    time_c = detect_coord(da, _TIME_ALIASES) or "time"

    wet_mask = da >= threshold_mm_day

    result = wet_mask.resample({time_c: "1YS"}).map(
        lambda g: _annual_max_consecutive(g, time_c)
    )
    result.name = "cwd"
    result.attrs["long_name"] = "Annual maximum consecutive wet days"
    result.attrs["units"] = "days"
    result.attrs["wet_day_threshold_mm_day"] = threshold_mm_day
    return result
