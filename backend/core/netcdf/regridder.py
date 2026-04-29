"""
Conservative regridding wrapper around xesmf.

Conservative regridding is the default because it preserves the integral of
quantities like precipitation and energy fluxes. Bilinear is offered for
variables where conservation is not required (e.g. temperature for plotting).

xesmf is an optional heavy dependency (requires ESMF). An ImportError with a
clear install hint is raised if xesmf is not available.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

RegridMethod = Literal["conservative", "bilinear", "nearest_s2d", "patch"]

_XESMF_AVAILABLE = False
try:
    import xesmf as xe  # type: ignore[import-untyped]
    _XESMF_AVAILABLE = True
except ImportError:
    pass


def _require_xesmf() -> None:
    if not _XESMF_AVAILABLE:
        raise ImportError(
            "xesmf is required for regridding but is not installed. "
            "Install it with: conda install -c conda-forge xesmf"
        )


# ---------------------------------------------------------------------------
# Grid construction
# ---------------------------------------------------------------------------


def make_target_grid(
    resolution_deg: float,
    lat_bounds: tuple[float, float] = (-90.0, 90.0),
    lon_bounds: tuple[float, float] = (-180.0, 180.0),
) -> xr.Dataset:
    """
    Build a regular lat/lon target grid Dataset for use with regrid().

    Grid centres are placed at half-resolution offsets from the boundaries so
    that the grid is cell-centred (standard for conservative regridding).

    Args:
        resolution_deg: Cell size in degrees (both lat and lon).
        lat_bounds: (south, north) extent in degrees.
        lon_bounds: (west, east) extent in degrees.

    Returns:
        Minimal xr.Dataset with 'lat' and 'lon' coordinate variables.
    """
    half = resolution_deg / 2.0
    lat = np.arange(lat_bounds[0] + half, lat_bounds[1], resolution_deg)
    lon = np.arange(lon_bounds[0] + half, lon_bounds[1], resolution_deg)

    ds = xr.Dataset(
        {
            "lat": ("lat", lat, {"units": "degrees_north", "axis": "Y"}),
            "lon": ("lon", lon, {"units": "degrees_east", "axis": "X"}),
        }
    )
    logger.debug(
        "Target grid: %.3f° resolution, lat %s..%s (%d), lon %s..%s (%d)",
        resolution_deg,
        lat[0], lat[-1], lat.size,
        lon[0], lon[-1], lon.size,
    )
    return ds


# ---------------------------------------------------------------------------
# Core regridding
# ---------------------------------------------------------------------------


def regrid(
    ds: xr.Dataset,
    target_grid: xr.Dataset,
    variables: list[str] | None = None,
    method: RegridMethod = "conservative",
    weights_path: str | Path | None = None,
    ignore_degenerate: bool = True,
) -> xr.Dataset:
    """
    Regrid one or more variables from ds onto target_grid.

    Weight computation is the expensive step. Pass weights_path to persist the
    sparse weight matrix and reuse it across calls with identical grids.

    Args:
        ds: Source dataset opened with open_dataset() (dask-backed).
        target_grid: Target grid from make_target_grid() or any Dataset with
                     'lat' and 'lon' coordinates.
        variables: Variables to regrid. If None, all data_vars are regridded.
        method: Regridding algorithm. 'conservative' preserves grid-cell
                integrals — use this for precipitation, fluxes, and any
                quantity that must be conserved. 'bilinear' is faster and
                appropriate for temperature and similar continuous fields.
        weights_path: Path to save/load the xesmf weight file (.nc).
                      If the file exists it is loaded; otherwise computed and saved.
        ignore_degenerate: Skip degenerate cells (needed for coastal ocean grids).

    Returns:
        New xr.Dataset with regridded variables on the target grid.

    Raises:
        ImportError: If xesmf is not installed.
        KeyError: If a requested variable is not in ds.
    """
    _require_xesmf()

    target_vars = variables if variables is not None else list(ds.data_vars)
    missing = [v for v in target_vars if v not in ds]
    if missing:
        raise KeyError(f"Variable(s) not found in dataset: {missing}")

    weights_path = Path(weights_path) if weights_path else None
    reuse = weights_path is not None and weights_path.exists()

    regridder_kwargs: dict = {
        "method": method,
        "ignore_degenerate": ignore_degenerate,
    }
    if reuse:
        regridder_kwargs["weights"] = str(weights_path)
        logger.debug("Loading regrid weights from %s", weights_path)
    else:
        logger.info(
            "Building %s regridder (%s → %s)…",
            method,
            _grid_summary(ds),
            _grid_summary(target_grid),
        )

    regridder = xe.Regridder(ds, target_grid, **regridder_kwargs)

    if weights_path and not reuse:
        weights_path.parent.mkdir(parents=True, exist_ok=True)
        regridder.to_netcdf(str(weights_path))
        logger.debug("Regrid weights saved to %s", weights_path)

    # Regrid each requested variable and rebuild into a single Dataset
    regridded_vars: dict[str, xr.DataArray] = {}
    for var in target_vars:
        regridded_vars[var] = regridder(ds[var])
        logger.debug("Regridded '%s'", var)

    ds_out = xr.Dataset(regridded_vars)
    ds_out.attrs.update(ds.attrs)
    ds_out.attrs["regrid_method"] = method
    return ds_out


def regrid_to_resolution(
    ds: xr.Dataset,
    resolution_deg: float,
    variables: list[str] | None = None,
    method: RegridMethod = "conservative",
    weights_path: str | Path | None = None,
) -> xr.Dataset:
    """
    Convenience wrapper: regrid ds to a global regular grid at resolution_deg.

    Equivalent to calling make_target_grid() then regrid().

    Args:
        ds: Source dataset.
        resolution_deg: Target resolution in degrees.
        variables: Variables to regrid (None = all).
        method: Regridding algorithm (default: conservative).
        weights_path: Optional path to cache the weight file.

    Returns:
        Regridded xr.Dataset on the new regular grid.
    """
    target = make_target_grid(resolution_deg)
    return regrid(ds, target, variables=variables, method=method, weights_path=weights_path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _grid_summary(ds: xr.Dataset) -> str:
    """Return a short 'NlatxNlon' description for logging."""
    n_lat = ds.dims.get("lat", ds.dims.get("latitude", "?"))
    n_lon = ds.dims.get("lon", ds.dims.get("longitude", "?"))
    return f"{n_lat}×{n_lon}"
