"""
Pure computation functions for Module B — NetCDF data processing.

All functions accept xarray objects backed by dask and return lazy results.
No data is transferred from disk until the caller explicitly triggers
.compute() or writes to disk with .to_netcdf().
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr

from ._coords import _LAT_ALIASES, _LON_ALIASES, _PLEV_ALIASES, _TIME_ALIASES, detect_coord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types (serialisation-friendly, no xarray objects)
# ---------------------------------------------------------------------------


@dataclass
class SpatialMeanResult:
    variable: str
    units: str
    time: list[str]
    values: list[float | None]


@dataclass
class SliceResult:
    variable: str
    units: str
    time_label: str
    plev_label: str | None
    lat: list[float]
    lon: list[float]
    values: list[list[float | None]]  # shape [n_lat][n_lon]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_time(da: xr.DataArray, variable: str) -> str:
    time_c = detect_coord(da, _TIME_ALIASES)
    if time_c is None:
        raise ValueError(f"Variable '{variable}' has no recognisable time coordinate")
    return time_c


def _format_time(t: object) -> str:
    """Convert numpy.datetime64 or cftime object to an ISO-style string."""
    if hasattr(t, "isoformat"):
        return t.isoformat()
    try:
        return str(np.datetime_as_string(t, unit="D"))  # type: ignore[arg-type]
    except Exception:
        return str(t)


def _nan_to_none(v: float) -> float | None:
    return None if np.isnan(v) else float(v)


# ---------------------------------------------------------------------------
# Public computation functions
# ---------------------------------------------------------------------------


def compute_climatology(
    ds: xr.Dataset,
    variable: str,
    start_year: int = 1991,
    end_year: int = 2020,
    freq: Literal["month", "dayofyear"] = "month",
) -> xr.DataArray:
    """
    Compute the climatological mean over a user-defined reference period.

    Defines x̄ in the anomaly formula x' = x - x̄. The base period defaults
    to 1991–2020 (WMO standard) but must always be configurable by the user.

    Args:
        ds: Dataset with the target variable and a time coordinate.
        variable: Variable name to process.
        start_year: First year of the reference period (inclusive).
        end_year: Last year of the reference period (inclusive).
        freq: 'month' → 12 output values; 'dayofyear' → 365/366 values.

    Returns:
        Lazy DataArray with 'month' or 'dayofyear' as the leading dimension.

    Raises:
        KeyError: Variable not in dataset.
        ValueError: Time coordinate missing or reference period yields no data.
    """
    if variable not in ds:
        raise KeyError(
            f"Variable '{variable}' not found. Available: {list(ds.data_vars)}"
        )

    da = ds[variable]
    time_c = _require_time(da, variable)

    base = da.sel({time_c: slice(str(start_year), str(end_year))})
    if base[time_c].size == 0:
        raise ValueError(
            f"No time steps found for {start_year}–{end_year}. "
            f"Dataset spans: {da[time_c].values[0]} – {da[time_c].values[-1]}"
        )

    clim = base.groupby(f"{time_c}.{freq}").mean(time_c)
    clim.attrs.update(da.attrs)
    clim.attrs["climatology_period"] = f"{start_year}-{end_year}"
    clim.attrs["climatology_freq"] = freq

    logger.debug(
        "Climatology computed for '%s' (%s) over %d–%d, shape=%s",
        variable, freq, start_year, end_year, clim.shape,
    )
    return clim


def compute_anomaly(
    da: xr.DataArray,
    climatology: xr.DataArray,
    freq: Literal["month", "dayofyear"] = "month",
) -> xr.DataArray:
    """
    Compute anomalies as x' = x - x̄ where x̄ is the climatological mean.

    Args:
        da: Full time-series DataArray.
        climatology: DataArray from compute_climatology() — must have a 'month'
                     or 'dayofyear' dimension matching freq.
        freq: Grouping key; must match the freq used to produce climatology.

    Returns:
        Lazy DataArray of anomalies with the same shape as da.
    """
    time_c = _require_time(da, str(da.name or "unknown"))

    anomaly = da.groupby(f"{time_c}.{freq}") - climatology
    anomaly.attrs.update(da.attrs)
    existing = anomaly.attrs.get("cell_methods", "")
    anomaly.attrs["cell_methods"] = f"{existing} anomaly".strip()
    anomaly.attrs["anomaly_base_period"] = climatology.attrs.get(
        "climatology_period", "unknown"
    )
    return anomaly


def weighted_spatial_mean(
    da: xr.DataArray,
    lat_min: float = -90.0,
    lat_max: float = 90.0,
    lon_min: float = -180.0,
    lon_max: float = 180.0,
) -> xr.DataArray:
    """
    Compute area-weighted spatial mean using cosine-latitude weighting.

    Spatial averages without latitude weighting are scientifically incorrect
    for any non-trivial domain. This function enforces weighting at all times.

    Args:
        da: DataArray with lat and lon coordinates.
        lat_min/lat_max/lon_min/lon_max: Bounding box in degrees (defaults: global).

    Returns:
        Lazy DataArray with lat and lon dimensions reduced.

    Raises:
        ValueError: If lat or lon coordinates cannot be detected.
    """
    lat_c = detect_coord(da, _LAT_ALIASES)
    lon_c = detect_coord(da, _LON_ALIASES)
    if lat_c is None or lon_c is None:
        raise ValueError(
            "DataArray must have detectable lat and lon coordinates for spatial mean"
        )

    da = da.sel({lat_c: slice(lat_min, lat_max), lon_c: slice(lon_min, lon_max)})

    weights = np.cos(np.deg2rad(da[lat_c]))
    weights.name = "weights"

    return da.weighted(weights).mean([lat_c, lon_c])


def extract_2d_slice(
    ds: xr.Dataset,
    variable: str,
    time_index: int = 0,
    plev_level: float | None = None,
) -> SliceResult:
    """
    Extract a single 2D lat/lon slice and return a serialisable result.

    Triggers dask computation for this slice only — does not load the full array.

    Args:
        ds: Dataset containing the variable (opened with open_dataset).
        variable: Variable name.
        time_index: Integer index along the time axis.
        plev_level: Pressure level to select (same units as the file coordinate).
                    If the variable has a plev dimension and this is None, the
                    first level is used.

    Returns:
        SliceResult with JSON-serialisable lat, lon, and value lists.

    Raises:
        KeyError: Variable not found.
        ValueError: Lat or lon coordinates missing; result is not 2D.
    """
    if variable not in ds:
        raise KeyError(
            f"Variable '{variable}' not found. Available: {list(ds.data_vars)}"
        )

    da = ds[variable]
    time_c = detect_coord(da, _TIME_ALIASES)
    plev_c = detect_coord(da, _PLEV_ALIASES)
    lat_c = detect_coord(da, _LAT_ALIASES)
    lon_c = detect_coord(da, _LON_ALIASES)

    if lat_c is None or lon_c is None:
        raise ValueError(f"Variable '{variable}' is missing lat or lon coordinates")

    # --- Select time step ---
    time_label = ""
    if time_c is not None and time_c in da.dims:
        n_times = int(da.sizes[time_c])
        if time_index >= n_times:
            raise ValueError(
                f"time_index {time_index} out of range (dataset has {n_times} steps)"
            )
        da = da.isel({time_c: time_index})
        time_label = _format_time(ds[time_c].values[time_index])

    # --- Select pressure level ---
    plev_label: str | None = None
    if plev_c is not None and plev_c in da.dims:
        if plev_level is not None:
            da = da.sel({plev_c: plev_level}, method="nearest")
        else:
            da = da.isel({plev_c: 0})
        plev_label = str(float(da[plev_c].values))

    # --- Drop any remaining non-spatial dims (safety) ---
    extra_dims = [d for d in da.dims if d not in (lat_c, lon_c)]
    for dim in extra_dims:
        logger.warning(
            "Unexpected dimension '%s' remaining after time/plev selection; "
            "taking index 0",
            dim,
        )
        da = da.isel({dim: 0})

    # --- Ensure lat × lon ordering ---
    da = da.transpose(lat_c, lon_c)

    # Compute only this 2D slice — does not load the full dataset
    arr = da.compute().values

    lat_vals = [float(v) for v in ds[lat_c].values]
    lon_vals = [float(v) for v in ds[lon_c].values]
    grid = [[_nan_to_none(v) for v in row] for row in arr]

    return SliceResult(
        variable=variable,
        units=str(da.attrs.get("units", "")),
        time_label=time_label,
        plev_label=plev_label,
        lat=lat_vals,
        lon=lon_vals,
        values=grid,
    )


def save_dataarray(
    da: xr.DataArray,
    output_path: str | Path,
    variable_name: str,
    compress: bool = True,
) -> None:
    """
    Compute a lazy DataArray and write it to a NetCDF file.

    This is the only function in this module with a side effect (disk write).
    Kept here rather than in the route layer so it can be tested without FastAPI.

    Args:
        da: Lazy DataArray to compute and save.
        output_path: Destination .nc file path.
        variable_name: Name to use for the variable in the output file.
        compress: Whether to apply zlib compression (level 4).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ds_out = da.to_dataset(name=variable_name)
    encoding: dict = {}
    if compress:
        encoding[variable_name] = {"zlib": True, "complevel": 4, "dtype": "float32"}

    ds_out.to_netcdf(str(output_path), encoding=encoding)
    logger.info("Saved '%s' to %s", variable_name, output_path)
