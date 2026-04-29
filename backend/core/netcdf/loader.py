"""
NetCDF file loading and metadata extraction using xarray and dask.

All functions are pure — no side effects beyond the returned dataset objects.
Callers are responsible for closing datasets via close_dataset().
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import xarray as xr

from ._coords import (
    _LAT_ALIASES,
    _LON_ALIASES,
    _PLEV_ALIASES,
    _TIME_ALIASES,
    detect_coord as _detect_coord,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class VariableInfo:
    name: str
    long_name: str
    units: str
    dimensions: tuple[str, ...]
    shape: tuple[int, ...]
    dtype: str


@dataclass
class CoordinateInfo:
    time_start: str | None = None
    time_end: str | None = None
    time_steps: int | None = None
    lat_min: float | None = None
    lat_max: float | None = None
    lat_n: int | None = None
    lon_min: float | None = None
    lon_max: float | None = None
    lon_n: int | None = None
    plev_levels: list[float] | None = None
    plev_units: str | None = None


@dataclass
class FileMetadata:
    path: str
    file_size_mb: float
    variables: dict[str, VariableInfo]
    coordinates: CoordinateInfo
    global_attrs: dict[str, str]
    has_plev: bool
    time_frequency: str | None
    lat_lon_resolution_deg: float | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------



def _select_plev(
    ds: xr.Dataset, plev_levels: Sequence[float], plev_coord: str
) -> xr.Dataset:
    """
    Select pressure levels immediately after file open, before data enters memory.

    Uses nearest-neighbour matching to handle floating-point differences between
    requested values and stored coordinate values (e.g. 85000.0 vs 85000.00001).
    """
    ds = ds.sel({plev_coord: list(plev_levels)}, method="nearest")
    logger.debug(
        "Selected %d pressure level(s) on coord '%s': %s",
        len(plev_levels),
        plev_coord,
        plev_levels,
    )
    return ds


def _drop_duplicate_times(ds: xr.Dataset, time_coord: str) -> xr.Dataset:
    """Remove duplicate time steps that appear at file boundaries, keeping first occurrence."""
    time_vals = ds[time_coord].values
    _, unique_idx = np.unique(time_vals, return_index=True)
    n_dropped = len(time_vals) - len(unique_idx)
    if n_dropped > 0:
        logger.warning("Dropped %d duplicate time step(s) across files", n_dropped)
        ds = ds.isel({time_coord: sorted(unique_idx)})
    return ds


def _infer_time_frequency(ds: xr.Dataset, time_coord: str) -> str | None:
    """
    Infer temporal frequency from median step size between time values.

    Returns one of: '1hr', '3hr', '6hr', 'day', 'mon', 'season', 'yr', or None.
    """
    time = ds[time_coord]
    if time.size < 2:
        return None
    try:
        deltas_h = np.diff(time.values).astype("timedelta64[h]").astype(float)
        median_h = float(np.median(deltas_h))
    except Exception:
        logger.debug("Could not infer time frequency: failed to compute time deltas")
        return None

    if median_h <= 1.5:
        return "1hr"
    if median_h <= 4.5:
        return "3hr"
    if median_h <= 9:
        return "6hr"
    if median_h <= 30:
        return "day"
    if median_h <= 800:
        return "mon"
    if median_h <= 2200:
        return "season"
    return "yr"


def _estimate_grid_resolution(ds: xr.Dataset, lat_coord: str) -> float | None:
    """Estimate spatial resolution in degrees from median latitude spacing."""
    lat = ds[lat_coord].values
    if lat.ndim != 1 or lat.size < 2:
        return None
    return float(round(abs(float(np.median(np.diff(np.sort(lat))))), 4))


def _build_coord_info(ds: xr.Dataset) -> CoordinateInfo:
    """Populate CoordinateInfo from dataset coordinates without triggering computation."""
    info = CoordinateInfo()

    time_c = _detect_coord(ds, _TIME_ALIASES)
    if time_c and time_c in ds.coords:
        t = ds[time_c]
        info.time_steps = int(t.size)
        try:
            info.time_start = str(t.values[0])
            info.time_end = str(t.values[-1])
        except Exception:
            pass

    lat_c = _detect_coord(ds, _LAT_ALIASES)
    if lat_c and lat_c in ds.coords:
        lat = ds[lat_c].values
        info.lat_min = float(lat.min())
        info.lat_max = float(lat.max())
        info.lat_n = int(lat.size)

    lon_c = _detect_coord(ds, _LON_ALIASES)
    if lon_c and lon_c in ds.coords:
        lon = ds[lon_c].values
        info.lon_min = float(lon.min())
        info.lon_max = float(lon.max())
        info.lon_n = int(lon.size)

    plev_c = _detect_coord(ds, _PLEV_ALIASES)
    if plev_c and plev_c in ds.coords:
        plev = ds[plev_c]
        info.plev_levels = [float(v) for v in plev.values]
        info.plev_units = str(plev.attrs.get("units", "Pa"))

    return info


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def open_dataset(
    path: str | Path,
    plev_levels: Sequence[float] | None = None,
    chunks: str | dict = "auto",
) -> xr.Dataset:
    """
    Open a single NetCDF file with dask-backed lazy loading.

    Pressure level selection is applied immediately after opening, before any
    data is brought into memory — mandatory for large 4D atmospheric files
    which can exceed 50 GB at full resolution.

    Args:
        path: Path to the NetCDF file.
        plev_levels: Pressure levels to retain (same units as the file's plev
                     coordinate, typically Pa for CMIP6). Pass None to keep all.
        chunks: Dask chunk specification forwarded to xr.open_dataset.
                'auto' lets dask choose chunk sizes based on available RAM.

    Returns:
        Lazily loaded xr.Dataset backed by dask arrays.

    Raises:
        FileNotFoundError: If the file does not exist at the given path.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"NetCDF file not found: {path}")

    logger.info("Opening dataset: %s", path)
    ds = xr.open_dataset(
        path,
        chunks=chunks,
        mask_and_scale=True,
        decode_times=True,
    )

    if plev_levels is not None:
        plev_c = _detect_coord(ds, _PLEV_ALIASES)
        if plev_c is None:
            logger.warning(
                "plev_levels requested but no pressure coordinate found in %s; "
                "loading all levels",
                path,
            )
        else:
            ds = _select_plev(ds, plev_levels, plev_c)

    logger.debug("Dataset opened with variables: %s", list(ds.data_vars))
    return ds


def open_mfdataset(
    paths: Sequence[str | Path],
    plev_levels: Sequence[float] | None = None,
    chunks: str | dict = "auto",
    drop_duplicate_times: bool = True,
) -> xr.Dataset:
    """
    Open and concatenate multiple NetCDF files into a single dataset.

    Uses xr.open_mfdataset with combine='by_coords'. Pressure level selection
    is applied per-file in the preprocess step so that large files are never
    fully loaded. Duplicate time steps that span file boundaries (common in
    raw CMIP/ESGF downloads) are removed when drop_duplicate_times is True.

    Args:
        paths: NetCDF file paths to merge. Must share compatible coordinates.
        plev_levels: Pressure levels to select (applied before concatenation).
        chunks: Dask chunk specification.
        drop_duplicate_times: Remove duplicate time steps across file boundaries.

    Returns:
        Lazily loaded combined xr.Dataset.

    Raises:
        FileNotFoundError: If any file in paths does not exist.
        ValueError: If paths is empty.
    """
    paths = [Path(p) for p in paths]
    if not paths:
        raise ValueError("paths must contain at least one file")

    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing file(s): {missing}")

    logger.info("Opening %d file(s) with open_mfdataset", len(paths))

    # Capture plev_levels in a default argument to avoid late-binding closure issues
    def _preprocess(ds: xr.Dataset, _levels: Sequence[float] = plev_levels) -> xr.Dataset:  # type: ignore[assignment]
        if _levels is not None:
            plev_c = _detect_coord(ds, _PLEV_ALIASES)
            if plev_c is not None:
                ds = _select_plev(ds, _levels, plev_c)
        return ds

    ds = xr.open_mfdataset(
        [str(p) for p in paths],
        combine="by_coords",
        chunks=chunks,
        mask_and_scale=True,
        decode_times=True,
        preprocess=_preprocess,
        data_vars="minimal",
        coords="minimal",
        compat="override",
    )

    if drop_duplicate_times:
        time_c = _detect_coord(ds, _TIME_ALIASES)
        if time_c is not None:
            ds = _drop_duplicate_times(ds, time_c)

    logger.debug("Multi-file dataset opened with %d variable(s)", len(ds.data_vars))
    return ds


def extract_metadata(path: str | Path) -> FileMetadata:
    """
    Extract metadata from a NetCDF file without loading data arrays into memory.

    Opens the file without dask to read only header information (coordinates,
    attributes, shapes), then closes it. Fast even for files exceeding 50 GB
    because no data is transferred from disk.

    Args:
        path: Path to the NetCDF file.

    Returns:
        FileMetadata with variables, coordinates, global attributes, and
        derived information (has_plev, time_frequency, grid resolution).

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"NetCDF file not found: {path}")

    file_size_mb = round(os.path.getsize(path) / (1024**2), 2)

    # Open without chunks: we only need header metadata, no dask graph needed
    with xr.open_dataset(path, chunks=None, mask_and_scale=True, decode_times=True) as ds:
        variables: dict[str, VariableInfo] = {
            str(var_name): VariableInfo(
                name=str(var_name),
                long_name=str(var.attrs.get("long_name", var_name)),
                units=str(var.attrs.get("units", "")),
                dimensions=tuple(str(d) for d in var.dims),
                shape=tuple(var.shape),
                dtype=str(var.dtype),
            )
            for var_name, var in ds.data_vars.items()
        }

        coord_info = _build_coord_info(ds)
        plev_c = _detect_coord(ds, _PLEV_ALIASES)
        time_c = _detect_coord(ds, _TIME_ALIASES)
        lat_c = _detect_coord(ds, _LAT_ALIASES)

        time_freq = _infer_time_frequency(ds, time_c) if time_c else None
        resolution = _estimate_grid_resolution(ds, lat_c) if lat_c else None

        global_attrs: dict[str, str] = {
            k: str(v)
            for k, v in ds.attrs.items()
            if isinstance(v, (str, int, float))
        }

    logger.info(
        "Metadata extracted from %s: %d variable(s), %.1f MB, frequency=%s",
        path,
        len(variables),
        file_size_mb,
        time_freq,
    )

    return FileMetadata(
        path=str(path),
        file_size_mb=file_size_mb,
        variables=variables,
        coordinates=coord_info,
        global_attrs=global_attrs,
        has_plev=plev_c is not None,
        time_frequency=time_freq,
        lat_lon_resolution_deg=resolution,
    )


def close_dataset(ds: xr.Dataset) -> None:
    """Close a dataset, releasing file handles and dask resources."""
    try:
        ds.close()
        logger.debug("Dataset closed")
    except Exception as exc:
        logger.warning("Error while closing dataset: %s", exc)
