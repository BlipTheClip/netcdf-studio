"""
Module A — Downloader REST endpoints and WebSocket progress stream.

REST
────
  GET  /api/downloader/sources            — list all data sources with metadata
  POST /api/downloader/{source}/search    — search a specific source

WebSocket
─────────
  WS /ws/download                         — batch download with per-file progress

WebSocket protocol
──────────────────
Client → Server (once, after connecting):
  {
    "source":         "esgf",
    "datasets":       [{...Dataset.to_dict()...}, ...],
    "dest_dir":       "/path/to/download/dir",
    "max_concurrent": 4
  }

Server → Client (progress, repeated):
  {
    "type": "progress",
    "payload": {
      "file":             "tas_Amon_CESM2.nc",
      "current_file":     2,
      "total_files":      10,
      "percent":          45.2,
      "downloaded_bytes": 75123456,
      "total_bytes":      166666666,
      "speed_mbps":       12.3,
      "status":           "downloading",
      "message":          "Downloading file 2 of 10"
    }
  }

Server → Client (final result):
  {
    "type": "result",
    "payload": {
      "completed": 10,
      "failed":    0,
      "dest_dir":  "/path/to/download/dir",
      "files":     ["/path/to/file1.nc", ...]
    }
  }

Server → Client (on error):
  { "type": "error", "payload": { "error": "...", "detail": "..." } }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.core.downloader.base import Dataset, DataSourceConnector, DownloadStatus
from backend.core.downloader.copernicus import CopernicusConnector
from backend.core.downloader.esa_cci import ESACCIConnector
from backend.core.downloader.esgf import ESGFConnector
from backend.core.downloader.nasa_aws import NASAConnector
from backend.core.downloader.parallel import parallel_download
from backend.core.downloader.worldbank import WorldBankConnector
from backend.core.downloader.base import SearchQuery

logger = logging.getLogger(__name__)

router = APIRouter(tags=["downloader"])

# ─────────────────────────────────────────────────────────────────────────────
# Connector registry
# ─────────────────────────────────────────────────────────────────────────────

_CONNECTORS: dict[str, DataSourceConnector] = {
    "esgf":       ESGFConnector(),
    "copernicus": CopernicusConnector(),
    "worldbank":  WorldBankConnector(),
    "nasa_aws":   NASAConnector(),
    "esa_cci":    ESACCIConnector(),
}

_SOURCE_META: dict[str, dict[str, Any]] = {
    "esgf": {
        "name":        "ESGF",
        "full_name":   "Earth System Grid Federation",
        "description": "CMIP3, CMIP5, CMIP6, CORDEX, obs4MIPs",
        "requires_auth": False,
        "auto_folder": "ESGF/{institute}/{model}/{experiment}/{frequency}/{variable}/",
        "search_params": {
            "project":      "CMIP project (e.g. 'CMIP6')",
            "experiment_id":"Experiment (e.g. 'historical', 'ssp585')",
            "source_id":    "Model identifier (e.g. 'CESM2')",
            "institution_id":"Institution (e.g. 'NCAR')",
            "table_id":     "Table / realm (e.g. 'Amon', 'day')",
            "variant_label":"Ensemble member (e.g. 'r1i1p1f1')",
        },
    },
    "copernicus": {
        "name":        "Copernicus CDS",
        "full_name":   "ECMWF Climate Data Store",
        "description": "ERA5 reanalysis (1940–present), ERA5-Land, CMIP6, seasonal forecasts",
        "requires_auth": True,
        "auth_instructions": "Create a free account at cds.climate.copernicus.eu and add your API key to ~/.cdsapirc",
        "auto_folder": "CDS/{dataset}/{variable}/{year}/",
        "search_params": {
            "dataset":        "CDS dataset name (e.g. 'reanalysis-era5-pressure-levels')",
            "variables":      "List of CDS variable names",
            "years":          "List of year strings (e.g. ['2020', '2021'])",
            "months":         "List of month strings (e.g. ['01', '06'])",
            "pressure_levels":"Pressure levels to subset (e.g. ['500', '850'])",
            "area":           "[north, west, south, east] bounding box",
        },
    },
    "worldbank": {
        "name":        "World Bank CCKP",
        "full_name":   "World Bank Climate Knowledge Portal",
        "description": "CMIP6 downscaled (0.25°), ERA5 (0.25°), CRU (0.5°), population grids",
        "requires_auth": False,
        "auto_folder": "CCKP/{collection}/{variable}/",
        "search_params": {
            "collection": "Data collection: 'cmip6', 'era5', or 'cru'",
            "prefix":     "S3 key prefix for fine-grained filtering",
        },
    },
    "nasa_aws": {
        "name":        "NASA/NOAA AWS",
        "full_name":   "NASA / NOAA AWS Open Data Registry",
        "description": "CESM Large Ensemble (40 members), CMAQ, Argo floats",
        "requires_auth": False,
        "auto_folder": "NASA_AWS/{dataset}/{variable}/",
        "search_params": {
            "dataset": "Dataset name: 'cesm-lens' or 'argo'",
            "prefix":  "S3 key prefix override",
        },
    },
    "esa_cci": {
        "name":        "ESA CCI",
        "full_name":   "ESA Climate Change Initiative",
        "description": "27 Essential Climate Variables (SST, soil moisture, ozone, glaciers, …)",
        "requires_auth": True,
        "auth_instructions": "Register free at climate.esa.int and set ESA_CCI_USER / ESA_CCI_PASS env vars",
        "auto_folder": "ESA_CCI/{ecv}/{sensor}/",
        "search_params": {
            "ecv":    "ECV identifier (e.g. 'sst', 'soil-moisture', 'ozone')",
            "sensor": "Sensor / platform (e.g. 'ATSR2-AATSR', 'MERGED')",
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Response helpers
# ─────────────────────────────────────────────────────────────────────────────


def _ok(data: object) -> dict[str, Any]:
    return {"status": "ok", "data": data}


def _err(message: str, detail: str = "", status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "error": message, "detail": detail},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic request models
# ─────────────────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    variable:   str | None         = None
    start_year: int | None         = None
    end_year:   int | None         = None
    frequency:  str | None         = None
    limit:      int                = Field(default=50, ge=1, le=500)
    params:     dict[str, Any]     = Field(default_factory=dict)


class DownloadWsRequest(BaseModel):
    source:         str
    datasets:       list[dict[str, Any]]
    dest_dir:       str
    max_concurrent: int = Field(default=4, ge=1, le=16)


# ─────────────────────────────────────────────────────────────────────────────
# REST — sources catalogue
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/api/downloader/sources")
async def list_sources() -> dict[str, Any]:
    """
    Return metadata for all supported data sources.
    The frontend uses this to populate the source selector and display
    source-specific search parameter descriptions.
    """
    return _ok({"sources": _SOURCE_META})


# ─────────────────────────────────────────────────────────────────────────────
# REST — search
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/api/downloader/{source}/search")
async def search_datasets(source: str, body: SearchRequest) -> dict[str, Any] | JSONResponse:
    """
    Search a data source for datasets matching the query.

    Returns a list of Dataset objects serialised to dicts.  Store these in the
    frontend and pass them back in the WebSocket download request.
    """
    connector = _CONNECTORS.get(source)
    if not connector:
        return _err(f"Unknown source '{source}'", f"Valid sources: {list(_CONNECTORS)}")

    try:
        query = SearchQuery(
            variable=body.variable,
            start_year=body.start_year,
            end_year=body.end_year,
            frequency=body.frequency,
            limit=body.limit,
            params=body.params,
        )
        datasets = await connector.search(query)
    except ValueError as exc:
        return _err(str(exc))
    except RuntimeError as exc:
        return _err("Search failed", str(exc), status_code=502)
    except Exception as exc:
        logger.exception("Unexpected search error for source %s", source)
        return _err("Search failed", str(exc), status_code=500)

    return _ok(
        {
            "source":   source,
            "total":    len(datasets),
            "datasets": [d.to_dict() for d in datasets],
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket — batch download
# ─────────────────────────────────────────────────────────────────────────────


@router.websocket("/ws/download")
async def ws_download(ws: WebSocket) -> None:
    """
    Batch download endpoint with per-file progress streaming.

    1. Accept the WebSocket connection.
    2. Receive a single JSON message with the download request.
    3. Stream BatchProgress events until all files complete.
    4. Send a final "result" message and close.
    """
    await ws.accept()
    logger.info("WebSocket download connection accepted")

    try:
        raw = await ws.receive_json()
        request = DownloadWsRequest(**raw)
    except Exception as exc:
        await ws.send_json(
            {"type": "error", "payload": {"error": "Invalid request", "detail": str(exc)}}
        )
        await ws.close()
        return

    connector = _CONNECTORS.get(request.source)
    if not connector:
        await ws.send_json(
            {
                "type": "error",
                "payload": {
                    "error": f"Unknown source '{request.source}'",
                    "detail": f"Valid sources: {list(_CONNECTORS)}",
                },
            }
        )
        await ws.close()
        return

    # Deserialise datasets and build destination paths
    try:
        datasets = [Dataset.from_dict(d) for d in request.datasets]
    except Exception as exc:
        await ws.send_json(
            {"type": "error", "payload": {"error": "Malformed dataset list", "detail": str(exc)}}
        )
        await ws.close()
        return

    dest_dir = Path(request.dest_dir)
    tasks: list[tuple[Dataset, Path]] = [
        (ds, connector.build_dest(ds, dest_dir)) for ds in datasets
    ]

    logger.info(
        "Starting download: source=%s, files=%d, dest=%s, concurrency=%d",
        request.source, len(tasks), dest_dir, request.max_concurrent,
    )

    completed_paths: list[str] = []
    failed_count = 0

    try:
        async for bp in parallel_download(connector, tasks, request.max_concurrent):
            # Build the progress payload
            payload: dict[str, Any] = {
                "file":             bp.file,
                "current_file":     bp.current_file,
                "total_files":      bp.total_files,
                "percent":          bp.percent,
                "downloaded_bytes": bp.downloaded_bytes,
                "total_bytes":      bp.total_bytes,
                "speed_mbps":       bp.speed_mbps,
                "status":           bp.status.value,
                "message": (
                    f"File {bp.current_file}/{bp.total_files}: {bp.file}"
                ),
            }

            if bp.status == DownloadStatus.FAILED:
                payload["error"] = bp.error
                failed_count += 1
                logger.warning("Download FAILED: %s — %s", bp.file, bp.error)
            elif bp.status == DownloadStatus.COMPLETED:
                completed_paths.append(bp.file)
                logger.debug("Download COMPLETED: %s", bp.file)

            await ws.send_json({"type": "progress", "payload": payload})

        # All done — send the summary
        await ws.send_json(
            {
                "type": "result",
                "payload": {
                    "completed": len(completed_paths),
                    "failed":    failed_count,
                    "dest_dir":  str(dest_dir),
                    "files":     completed_paths,
                },
            }
        )
        logger.info(
            "Download batch finished: completed=%d failed=%d",
            len(completed_paths), failed_count,
        )

    except WebSocketDisconnect:
        logger.info("WebSocket download: client disconnected mid-batch")
    except Exception as exc:
        logger.exception("WebSocket download unexpected error")
        try:
            await ws.send_json(
                {"type": "error", "payload": {"error": str(exc), "detail": type(exc).__name__}}
            )
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
