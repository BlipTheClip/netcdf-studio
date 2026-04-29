"""
FastAPI router for Module C — static map and diagram image generation.

REST endpoints
──────────────
  POST /api/imagery/render-map        — render a single cartopy map
  POST /api/imagery/render-hovmoller  — render a Hovmöller diagram
  POST /api/imagery/render-taylor     — render a Taylor diagram

WebSocket endpoint
──────────────────
  WS /ws/imagery/batch                — batch map rendering with RAM budget control

Batch WebSocket protocol
─────────────────────────
Client → Server (once, after connecting):
  {
    "jobs": [
      {
        "path": "/data/tas.nc",
        "variable": "tas",
        "output_path": "/out/map_001.png",
        "time_index": 0,
        "plev_level": null,
        "projection": "PlateCarree",
        "cmap": "RdBu_r",
        "title": "",
        "dpi": 150,
        "add_coastlines": true,
        "add_gridlines": true
      },
      ...
    ],
    "max_ram_gb": 4.0
  }

Server → Client (progress, one per job):
  {
    "type": "progress",
    "payload": {
      "current":  1,
      "total":    10,
      "file":     "map_001.png",
      "status":   "rendering" | "completed" | "failed",
      "message":  "Rendering map 1 / 10",
      "error":    "..."   (only when status == "failed")
    }
  }

Server → Client (final result):
  {
    "type": "result",
    "payload": {
      "completed": 9,
      "failed":    1,
      "files":     ["/out/map_001.png", ...]
    }
  }

Server → Client (on fatal error):
  { "type": "error", "payload": { "error": "...", "detail": "..." } }
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.netcdf.loader import close_dataset, open_dataset
from backend.core.plotting.hovmoller import render_hovmoller
from backend.core.plotting.maps import render_map
from backend.core.plotting.taylor import ModelStat, render_taylor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["imagery"])

# Try to import psutil for RAM tracking; degrade gracefully if not installed
try:
    import psutil as _psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False
    logger.warning("psutil not installed — RAM budget enforcement disabled")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(data: object) -> dict[str, Any]:
    return {"status": "ok", "data": data}


def _err(message: str, detail: str = "", status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "error": message, "detail": detail},
    )


def _current_ram_gb() -> float:
    """Return current process RSS in GB. Returns 0.0 if psutil unavailable."""
    if not _PSUTIL_AVAILABLE:
        return 0.0
    try:
        return _psutil.Process(os.getpid()).memory_info().rss / (1024 ** 3)
    except Exception:
        return 0.0


def _enforce_ram(max_ram_gb: float) -> None:
    """
    Collect garbage if we are close to the RAM limit.

    Does not block — if RAM is still over limit after gc, we proceed anyway
    (the OS will page; the caller logs a warning).
    """
    if max_ram_gb <= 0 or not _PSUTIL_AVAILABLE:
        return
    if _current_ram_gb() > max_ram_gb * 0.85:
        gc.collect()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class MapRenderRequest(BaseModel):
    path: str
    variable: str
    output_path: str
    time_index: int                = Field(default=0, ge=0)
    plev_level: float | None      = None
    plev_levels: list[float] | None = None
    projection: str               = "PlateCarree"
    central_longitude: float      = 0.0
    cmap: str                     = "RdBu_r"
    vmin: float | None            = None
    vmax: float | None            = None
    title: str                    = ""
    dpi: int                      = Field(default=150, ge=72, le=600)
    figsize: tuple[float, float]  = (12.0, 6.0)
    add_coastlines: bool          = True
    add_borders: bool             = True
    add_gridlines: bool           = True
    add_colorbar: bool            = True
    lat_min: float | None         = None
    lat_max: float | None         = None
    lon_min: float | None         = None
    lon_max: float | None         = None


class HovmollerRenderRequest(BaseModel):
    path: str
    variable: str
    output_path: str
    mode: Literal["lat", "lon"]   = "lat"
    plev_level: float | None      = None
    plev_levels: list[float] | None = None
    lat_min: float                = -90.0
    lat_max: float                = 90.0
    lon_min: float                = -180.0
    lon_max: float                = 180.0
    cmap: str                     = "RdBu_r"
    vmin: float | None            = None
    vmax: float | None            = None
    title: str                    = ""
    dpi: int                      = Field(default=150, ge=72, le=600)
    figsize: tuple[float, float]  = (10.0, 7.0)
    add_colorbar: bool            = True
    n_time_ticks: int             = Field(default=12, ge=4, le=50)


class TaylorModelItem(BaseModel):
    name: str
    std_ratio: float  = Field(gt=0.0)
    correlation: float = Field(ge=-1.0, le=1.0)
    color: str        = ""
    marker: str       = ""


class TaylorRenderRequest(BaseModel):
    models: list[TaylorModelItem]  = Field(min_length=1)
    output_path: str
    title: str                     = "Taylor Diagram"
    max_std_ratio: float           = Field(default=1.5, gt=0.0)
    dpi: int                       = Field(default=150, ge=72, le=600)
    figsize: tuple[float, float]   = (8.0, 7.0)


class BatchMapJob(BaseModel):
    """One map render job within a batch request."""
    path: str
    variable: str
    output_path: str
    time_index: int               = Field(default=0, ge=0)
    plev_level: float | None      = None
    plev_levels: list[float] | None = None
    projection: str               = "PlateCarree"
    central_longitude: float      = 0.0
    cmap: str                     = "RdBu_r"
    vmin: float | None            = None
    vmax: float | None            = None
    title: str                    = ""
    dpi: int                      = Field(default=150, ge=72, le=600)
    figsize: tuple[float, float]  = (12.0, 6.0)
    add_coastlines: bool          = True
    add_borders: bool             = True
    add_gridlines: bool           = True
    add_colorbar: bool            = True
    lat_min: float | None         = None
    lat_max: float | None         = None
    lon_min: float | None         = None
    lon_max: float | None         = None


class BatchRequest(BaseModel):
    jobs: list[BatchMapJob] = Field(min_length=1)
    max_ram_gb: float       = Field(default=4.0, gt=0.0, le=256.0)


# ---------------------------------------------------------------------------
# REST — single map
# ---------------------------------------------------------------------------


@router.post("/api/imagery/render-map")
async def render_single_map(req: MapRenderRequest) -> dict | JSONResponse:
    """
    Render one cartopy map PNG from a NetCDF variable.

    The map is always saved to disk at output_path.  The response contains the
    output path and image dimensions so the frontend can display a thumbnail.
    """
    def _run() -> dict:
        ds = open_dataset(req.path, plev_levels=req.plev_levels)
        try:
            out = render_map(
                ds, req.variable, req.output_path,
                time_index       = req.time_index,
                plev_level       = req.plev_level,
                projection       = req.projection,
                central_longitude= req.central_longitude,
                cmap             = req.cmap,
                vmin             = req.vmin,
                vmax             = req.vmax,
                title            = req.title,
                dpi              = req.dpi,
                figsize          = tuple(req.figsize),  # type: ignore[arg-type]
                add_coastlines   = req.add_coastlines,
                add_borders      = req.add_borders,
                add_gridlines    = req.add_gridlines,
                add_colorbar     = req.add_colorbar,
                lat_min          = req.lat_min,
                lat_max          = req.lat_max,
                lon_min          = req.lon_min,
                lon_max          = req.lon_max,
            )
            w_px = int(req.figsize[0] * req.dpi)
            h_px = int(req.figsize[1] * req.dpi)
            return {"output_path": str(out), "width_px": w_px, "height_px": h_px}
        finally:
            close_dataset(ds)

    try:
        data = await asyncio.to_thread(_run)
        return _ok(data)
    except FileNotFoundError as exc:
        return _err(str(exc), status_code=404)
    except ImportError as exc:
        return _err(str(exc), status_code=503)
    except (KeyError, ValueError) as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("Error rendering map for %s", req.path)
        return _err(str(exc), status_code=500)


# ---------------------------------------------------------------------------
# REST — Hovmöller diagram
# ---------------------------------------------------------------------------


@router.post("/api/imagery/render-hovmoller")
async def render_hovmoller_endpoint(req: HovmollerRenderRequest) -> dict | JSONResponse:
    """
    Render a Hovmöller diagram (time × lat or time × lon).

    mode="lat"  — longitude-averaged; x-axis = latitude
    mode="lon"  — cosine-latitude-weighted mean; x-axis = longitude
    """
    def _run() -> dict:
        ds = open_dataset(req.path, plev_levels=req.plev_levels)
        try:
            out = render_hovmoller(
                ds, req.variable, req.output_path,
                mode        = req.mode,
                plev_level  = req.plev_level,
                lat_min     = req.lat_min,
                lat_max     = req.lat_max,
                lon_min     = req.lon_min,
                lon_max     = req.lon_max,
                cmap        = req.cmap,
                vmin        = req.vmin,
                vmax        = req.vmax,
                title       = req.title,
                dpi         = req.dpi,
                figsize     = tuple(req.figsize),  # type: ignore[arg-type]
                add_colorbar= req.add_colorbar,
                n_time_ticks= req.n_time_ticks,
            )
            return {"output_path": str(out)}
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
        logger.exception("Error rendering Hovmöller for %s", req.path)
        return _err(str(exc), status_code=500)


# ---------------------------------------------------------------------------
# REST — Taylor diagram
# ---------------------------------------------------------------------------


@router.post("/api/imagery/render-taylor")
async def render_taylor_endpoint(req: TaylorRenderRequest) -> dict | JSONResponse:
    """
    Render a Taylor diagram comparing one or more models against a reference.

    Each model entry provides:
      - name: display label
      - std_ratio: std_model / std_reference (1.0 = perfect match)
      - correlation: Pearson correlation with the reference (range −1 to 1)

    The reference point (std_ratio=1, corr=1) is always drawn as a star.
    """
    def _run() -> dict:
        model_stats = [
            ModelStat(
                name        = m.name,
                std_ratio   = m.std_ratio,
                correlation = m.correlation,
                color       = m.color,
                marker      = m.marker,
            )
            for m in req.models
        ]
        out = render_taylor(
            model_stats, req.output_path,
            title         = req.title,
            max_std_ratio = req.max_std_ratio,
            dpi           = req.dpi,
            figsize       = tuple(req.figsize),  # type: ignore[arg-type]
        )
        return {"output_path": str(out)}

    try:
        data = await asyncio.to_thread(_run)
        return _ok(data)
    except ValueError as exc:
        return _err(str(exc))
    except Exception as exc:
        logger.exception("Error rendering Taylor diagram")
        return _err(str(exc), status_code=500)


# ---------------------------------------------------------------------------
# WebSocket — batch map rendering
# ---------------------------------------------------------------------------


@router.websocket("/ws/imagery/batch")  # full path; no router prefix
async def ws_batch_imagery(ws: WebSocket) -> None:
    """
    Batch map rendering with per-job progress and RAM budget enforcement.

    Renders jobs sequentially (one at a time) in a thread pool.  Before each
    job the server checks current RSS; if above 85 % of max_ram_gb it calls
    gc.collect() to release matplotlib figure memory from the previous job.
    """
    await ws.accept()
    logger.info("Batch imagery WebSocket connected")

    # 1. Parse the batch request
    try:
        raw     = await ws.receive_json()
        request = BatchRequest(**raw)
    except Exception as exc:
        await ws.send_json(
            {"type": "error", "payload": {"error": "Invalid request", "detail": str(exc)}}
        )
        await ws.close()
        return

    jobs      = request.jobs
    total     = len(jobs)
    max_ram   = request.max_ram_gb
    completed : list[str] = []
    failed    = 0

    logger.info("Batch imagery: %d jobs, RAM limit=%.1f GB", total, max_ram)

    for i, job in enumerate(jobs, start=1):
        out_name = Path(job.output_path).name

        # RAM guard before each render
        _enforce_ram(max_ram)
        ram_now = _current_ram_gb()
        if max_ram > 0 and ram_now > max_ram:
            logger.warning(
                "RAM %.2f GB exceeds limit %.2f GB before job %d/%d — proceeding anyway",
                ram_now, max_ram, i, total,
            )

        # Send "rendering" progress update
        await ws.send_json({
            "type": "progress",
            "payload": {
                "current": i,
                "total":   total,
                "file":    out_name,
                "status":  "rendering",
                "message": f"Rendering map {i} / {total}",
            },
        })

        # Run blocking render in thread pool
        def _render_job(j: BatchMapJob = job) -> str:
            ds = open_dataset(j.path, plev_levels=j.plev_levels)
            try:
                out = render_map(
                    ds, j.variable, j.output_path,
                    time_index       = j.time_index,
                    plev_level       = j.plev_level,
                    projection       = j.projection,
                    central_longitude= j.central_longitude,
                    cmap             = j.cmap,
                    vmin             = j.vmin,
                    vmax             = j.vmax,
                    title            = j.title,
                    dpi              = j.dpi,
                    figsize          = tuple(j.figsize),  # type: ignore[arg-type]
                    add_coastlines   = j.add_coastlines,
                    add_borders      = j.add_borders,
                    add_gridlines    = j.add_gridlines,
                    add_colorbar     = j.add_colorbar,
                    lat_min          = j.lat_min,
                    lat_max          = j.lat_max,
                    lon_min          = j.lon_min,
                    lon_max          = j.lon_max,
                )
                return str(out)
            finally:
                close_dataset(ds)

        try:
            out_path = await asyncio.to_thread(_render_job)
            completed.append(out_path)

            await ws.send_json({
                "type": "progress",
                "payload": {
                    "current": i,
                    "total":   total,
                    "file":    out_name,
                    "status":  "completed",
                    "message": f"Completed {i} / {total}",
                },
            })
            logger.debug("Batch job %d/%d completed: %s", i, total, out_name)

        except WebSocketDisconnect:
            logger.info("Batch imagery: client disconnected at job %d/%d", i, total)
            return

        except Exception as exc:
            failed += 1
            err_msg = str(exc)
            logger.warning("Batch job %d/%d FAILED (%s): %s", i, total, out_name, err_msg)

            try:
                await ws.send_json({
                    "type": "progress",
                    "payload": {
                        "current": i,
                        "total":   total,
                        "file":    out_name,
                        "status":  "failed",
                        "message": f"Failed {i} / {total}: {err_msg}",
                        "error":   err_msg,
                    },
                })
            except Exception:
                return  # client disconnected

    # 2. Send final summary
    try:
        await ws.send_json({
            "type": "result",
            "payload": {
                "completed": len(completed),
                "failed":    failed,
                "files":     completed,
            },
        })
        logger.info(
            "Batch imagery finished: completed=%d failed=%d", len(completed), failed
        )
    except Exception:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
