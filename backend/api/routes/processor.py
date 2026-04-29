"""
FastAPI router for Module B — NetCDF data processor.

All endpoints delegate computation to backend/core/netcdf/ pure functions.
Blocking dask operations are offloaded to a thread pool via asyncio.to_thread()
so the event loop is never stalled during heavy computation.

Endpoint summary
----------------
POST /api/processor/metadata      — extract file metadata (no data loaded)
POST /api/processor/variables     — list variables in a file
POST /api/processor/climatology   — compute and save climatological mean
POST /api/processor/anomaly       — compute and save anomaly time series
POST /api/processor/spatial-mean  — compute area-weighted time series (returns JSON)
POST /api/processor/preview       — extract single 2D lat/lon slice (returns JSON)
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.netcdf.loader import close_dataset, extract_metadata, open_dataset
from backend.core.netcdf.processor import (
    SpatialMeanResult,
    SliceResult,
    compute_anomaly,
    compute_climatology,
    extract_2d_slice,
    save_dataarray,
    weighted_spatial_mean,
)
from backend.core.netcdf._coords import _TIME_ALIASES, detect_coord
from backend.core.netcdf.indices import (
    compute_cdd,
    compute_cwd,
    compute_nao,
    compute_nino12,
    compute_nino3,
    compute_nino34,
    compute_nino4,
    compute_oni,
    compute_prcptot,
    compute_r95p,
    compute_rx1day,
    compute_rx5day,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/processor", tags=["processor"])


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _ok(data: object) -> dict:
    return {"status": "ok", "data": data}


def _err(message: str, detail: str = "", status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "error": message, "detail": detail},
    )


def _format_time(t: object) -> str:
    if hasattr(t, "isoformat"):
        return t.isoformat()
    try:
        return str(np.datetime_as_string(t, unit="D"))  # type: ignore[arg-type]
    except Exception:
        return str(t)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class PathRequest(BaseModel):
    path: str


class ClimatologyRequest(BaseModel):
    path: str
    variable: str
    output_path: str
    start_year: int = Field(default=1991, ge=1850, le=2200)
    end_year: int = Field(default=2020, ge=1850, le=2200)
    freq: Literal["month", "dayofyear"] = "month"
    plev_levels: list[float] | None = None


class AnomalyRequest(BaseModel):
    path: str
    variable: str
    output_path: str
    start_year: int = Field(default=1991, ge=1850, le=2200)
    end_year: int = Field(default=2020, ge=1850, le=2200)
    freq: Literal["month", "dayofyear"] = "month"
    plev_levels: list[float] | None = None
    # Optional: path to a pre-computed climatology NetCDF.
    # If omitted the climatology is computed inline from the same file.
    climatology_path: str | None = None


class SpatialMeanRequest(BaseModel):
    path: str
    variable: str
    plev_levels: list[float] | None = None
    lat_min: float = Field(default=-90.0, ge=-90.0, le=90.0)
    lat_max: float = Field(default=90.0, ge=-90.0, le=90.0)
    lon_min: float = Field(default=-180.0, ge=-180.0, le=360.0)
    lon_max: float = Field(default=180.0, ge=-180.0, le=360.0)


class PreviewRequest(BaseModel):
    path: str
    variable: str
    time_index: int = Field(default=0, ge=0)
    plev_level: float | None = None
    # If the file has multiple pressure levels and you only want a subset open
    plev_levels: list[float] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/metadata")
async def get_metadata(req: PathRequest) -> dict:
    """
    Extract file metadata without loading any data arrays into memory.
    Fast even for files exceeding 50 GB.
    """
    try:
        meta = await asyncio.to_thread(extract_metadata, req.path)
        return _ok(dataclasses.asdict(meta))
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except Exception as exc:
        logger.exception("Error extracting metadata from %s", req.path)
        return _err(str(exc), status_code=500)


@router.post("/variables")
async def list_variables(req: PathRequest) -> dict:
    """
    List all data variables in a file with their shape, units, and dimensions.
    """
    try:
        meta = await asyncio.to_thread(extract_metadata, req.path)
        return _ok(
            {
                "variables": [
                    dataclasses.asdict(v) for v in meta.variables.values()
                ],
                "has_plev": meta.has_plev,
                "plev_levels": meta.coordinates.plev_levels,
                "plev_units": meta.coordinates.plev_units,
            }
        )
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except Exception as exc:
        logger.exception("Error listing variables in %s", req.path)
        return _err(str(exc), status_code=500)


@router.post("/climatology")
async def compute_climatology_endpoint(req: ClimatologyRequest) -> dict:
    """
    Compute the climatological mean over a reference period and save to disk.

    The reference period (start_year–end_year) defines x̄ for anomaly computation.
    Defaults to 1991–2020 (WMO standard). plev_levels, if provided, are selected
    before any data is read into memory.
    """
    if req.start_year >= req.end_year:
        return _err(
            "start_year must be less than end_year",
            f"Got {req.start_year}–{req.end_year}",
        )

    def _run() -> dict:
        ds = open_dataset(req.path, plev_levels=req.plev_levels)
        try:
            clim = compute_climatology(
                ds, req.variable, req.start_year, req.end_year, req.freq
            )
            save_dataarray(clim, req.output_path, req.variable)
            return {"output_path": req.output_path, "shape": list(clim.shape)}
        finally:
            close_dataset(ds)

    try:
        data = await asyncio.to_thread(_run)
        return _ok(data)
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except (KeyError, ValueError) as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("Error computing climatology for %s", req.path)
        return _err(str(exc), status_code=500)


@router.post("/anomaly")
async def compute_anomaly_endpoint(req: AnomalyRequest) -> dict:
    """
    Compute anomalies (x' = x - x̄) and save to disk.

    If climatology_path is provided the pre-computed climatology is loaded from
    that file.  Otherwise the climatology is computed inline over start_year–end_year
    from the same dataset — useful for a single-step workflow.
    """
    if req.start_year >= req.end_year and req.climatology_path is None:
        return _err(
            "start_year must be less than end_year when computing climatology inline",
            f"Got {req.start_year}–{req.end_year}",
        )

    def _run() -> dict:
        ds = open_dataset(req.path, plev_levels=req.plev_levels)
        try:
            da = ds[req.variable]

            if req.climatology_path:
                clim_ds = xr.open_dataset(req.climatology_path, chunks=None)
                clim = clim_ds[req.variable]
            else:
                clim = compute_climatology(
                    ds, req.variable, req.start_year, req.end_year, req.freq
                )

            anomaly = compute_anomaly(da, clim, req.freq)
            save_dataarray(anomaly, req.output_path, req.variable)

            if req.climatology_path:
                clim_ds.close()

            return {"output_path": req.output_path, "shape": list(anomaly.shape)}
        finally:
            close_dataset(ds)

    try:
        data = await asyncio.to_thread(_run)
        return _ok(data)
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except (KeyError, ValueError) as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("Error computing anomaly for %s", req.path)
        return _err(str(exc), status_code=500)


@router.post("/spatial-mean")
async def compute_spatial_mean_endpoint(req: SpatialMeanRequest) -> dict:
    """
    Compute the area-weighted spatial mean time series and return as JSON.

    Cosine-latitude weighting is always applied — unweighted spatial averages
    are not offered because they are scientifically incorrect.
    """
    if req.lat_min >= req.lat_max:
        return _err("lat_min must be less than lat_max")
    if req.lon_min >= req.lon_max:
        return _err("lon_min must be less than lon_max")

    def _run() -> dict:
        ds = open_dataset(req.path, plev_levels=req.plev_levels)
        try:
            if req.variable not in ds:
                raise KeyError(
                    f"Variable '{req.variable}' not found. "
                    f"Available: {list(ds.data_vars)}"
                )
            da = ds[req.variable]
            mean_da = weighted_spatial_mean(
                da, req.lat_min, req.lat_max, req.lon_min, req.lon_max
            )
            result = mean_da.compute()

            time_c = detect_coord(result, _TIME_ALIASES)
            times: list[str] = []
            if time_c and time_c in result.coords:
                times = [_format_time(t) for t in result[time_c].values]

            flat = result.values.flatten()
            values = [None if np.isnan(v) else float(v) for v in flat]

            return {
                "variable": req.variable,
                "units": str(da.attrs.get("units", "")),
                "time": times,
                "values": values,
            }
        finally:
            close_dataset(ds)

    try:
        data = await asyncio.to_thread(_run)
        return _ok(data)
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except (KeyError, ValueError) as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("Error computing spatial mean for %s", req.path)
        return _err(str(exc), status_code=500)


@router.post("/preview")
async def preview_slice(req: PreviewRequest) -> dict:
    """
    Extract a single 2D lat/lon slice for frontend visualisation.

    Only the requested slice is computed — the rest of the file stays on disk.
    NaN values are returned as JSON null.
    """
    def _run() -> dict:
        ds = open_dataset(req.path, plev_levels=req.plev_levels)
        try:
            result: SliceResult = extract_2d_slice(
                ds, req.variable, req.time_index, req.plev_level
            )
            return dataclasses.asdict(result)
        finally:
            close_dataset(ds)

    try:
        data = await asyncio.to_thread(_run)
        return _ok(data)
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except (KeyError, ValueError) as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("Error generating preview for %s", req.path)
        return _err(str(exc), status_code=500)


# ---------------------------------------------------------------------------
# Climate indices endpoint
# ---------------------------------------------------------------------------

_ENSO_INDICES: frozenset[str] = frozenset({"nino34", "nino3", "nino4", "nino12", "oni"})
_NAO_INDICES: frozenset[str] = frozenset({"nao"})
_PRECIP_INDICES: frozenset[str] = frozenset(
    {"rx1day", "rx5day", "r95p", "prcptot", "cdd", "cwd"}
)

IndexName = Literal[
    "nino34", "nino3", "nino4", "nino12", "oni",
    "nao",
    "rx1day", "rx5day", "r95p", "prcptot", "cdd", "cwd",
]


class IndicesRequest(BaseModel):
    path: str
    index: IndexName
    variable: str = Field(
        description=(
            "Variable name in the file. "
            "Typical values: 'tos'/'sst' (ENSO), 'psl'/'msl' (NAO), 'pr'/'tp' (ETCCDI)."
        )
    )
    output_path: str | None = Field(
        default=None,
        description="(ETCCDI only) Save the full spatial field to this NetCDF path.",
    )
    start_year: int = Field(default=1991, ge=1850, le=2200)
    end_year: int = Field(default=2020, ge=1850, le=2200)
    plev_levels: list[float] | None = None
    oni_window: int = Field(default=3, ge=2, le=12, description="Running mean window for ONI (months).")
    pr_threshold_mm_day: float = Field(
        default=1.0, gt=0.0, description="Wet/dry day threshold for CDD, CWD, PRCPTOT (mm/day)."
    )


def _ts_to_dict(result: xr.DataArray, index_name: str) -> dict:
    """Serialise a 1D time-series DataArray to a JSON-safe response dict."""
    time_c = detect_coord(result, _TIME_ALIASES)
    times: list[str] = []
    if time_c and time_c in result.coords:
        times = [_format_time(t) for t in result[time_c].values]
    flat = result.values.flatten().astype(float)
    values: list[float | None] = [None if np.isnan(v) else float(v) for v in flat]
    return {
        "index": index_name,
        "time": times,
        "values": values,
        "units": str(result.attrs.get("units", "")),
        "long_name": str(result.attrs.get("long_name", index_name)),
    }


@router.post("/indices")
async def compute_index(req: IndicesRequest) -> dict:
    """
    Compute a climate index and return a JSON time series.

    **ENSO indices** (`nino34`, `nino3`, `nino4`, `nino12`, `oni`)
    — Area-weighted SST anomaly over the relevant Niño box. The spatial
    averaging is applied internally; the response is a 1-D monthly time series.
    Pass the SST variable name in `variable` (e.g. `tos` for CMIP6, `sst` for ERA5).

    **NAO index** (`nao`)
    — Station-based Hurrell (1995) NAO: normalised SLP anomaly difference
    between Azores and Iceland box averages. Pass the SLP variable in `variable`
    (e.g. `psl` for CMIP6, `msl` for ERA5).

    **ETCCDI precipitation extremes** (`rx1day`, `rx5day`, `r95p`, `prcptot`, `cdd`, `cwd`)
    — Require **daily** precipitation input. Pass the precipitation variable in
    `variable` (e.g. `pr` for CMIP6). Units are auto-converted from kg m⁻² s⁻¹
    to mm/day. The response always contains the global area-weighted mean as a
    time series. If `output_path` is provided, the full spatial field
    (time × lat × lon) is also saved to that NetCDF file.
    """
    if req.start_year >= req.end_year:
        return _err("start_year must be less than end_year")

    def _run() -> dict:
        ds = open_dataset(req.path, plev_levels=req.plev_levels)
        try:
            base = (req.start_year, req.end_year)

            # ---- ENSO indices ------------------------------------------------
            if req.index in _ENSO_INDICES:
                _enso_dispatch = {
                    "nino34": compute_nino34,
                    "nino3":  compute_nino3,
                    "nino4":  compute_nino4,
                    "nino12": compute_nino12,
                }
                if req.index == "oni":
                    raw = compute_nino34(ds, req.variable, base)
                    da_lazy = compute_oni(raw, req.oni_window)
                else:
                    da_lazy = _enso_dispatch[req.index](ds, req.variable, base)
                return _ts_to_dict(da_lazy.compute(), req.index)

            # ---- NAO index ---------------------------------------------------
            if req.index in _NAO_INDICES:
                da_lazy = compute_nao(ds, req.variable, base)
                return _ts_to_dict(da_lazy.compute(), req.index)

            # ---- ETCCDI precipitation indices --------------------------------
            _precip_dispatch = {
                "rx1day":  lambda: compute_rx1day(ds, req.variable),
                "rx5day":  lambda: compute_rx5day(ds, req.variable),
                "r95p":    lambda: compute_r95p(ds, req.variable, base),
                "prcptot": lambda: compute_prcptot(ds, req.variable, req.pr_threshold_mm_day),
                "cdd":     lambda: compute_cdd(ds, req.variable, req.pr_threshold_mm_day),
                "cwd":     lambda: compute_cwd(ds, req.variable, req.pr_threshold_mm_day),
            }
            da_lazy = _precip_dispatch[req.index]()

            # Optionally persist the full spatial field
            saved_path: str | None = None
            if req.output_path:
                save_dataarray(da_lazy, req.output_path, req.index)
                saved_path = req.output_path

            # Global weighted mean for the JSON response (always returned)
            global_mean = weighted_spatial_mean(da_lazy).compute()
            ts_dict = _ts_to_dict(global_mean, req.index)
            ts_dict["output_path"] = saved_path
            return ts_dict

        finally:
            close_dataset(ds)

    try:
        data = await asyncio.to_thread(_run)
        return _ok(data)
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except (KeyError, ValueError) as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("Error computing index '%s' for %s", req.index, req.path)
        return _err(str(exc), status_code=500)
