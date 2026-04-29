"""
Copernicus CDS (Climate Data Store) connector.

Supports ERA5 reanalysis, ERA5-Land, CMIP6 projections, and seasonal forecasts.
Requires cdsapi (pip install cdsapi) and a free API key from:
  https://cds.climate.copernicus.eu

Credentials
───────────
CDS reads credentials from ~/.cdsapirc:

    url: https://cds.climate.copernicus.eu/api
    key: <uid>:<api-key>

Or from environment variables CDSAPI_URL and CDSAPI_KEY.

Progress reporting
──────────────────
cdsapi is synchronous and manages polling internally.  We run it in a thread
executor and monitor the growing output file to estimate transfer progress.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .base import DataSourceConnector, Dataset, DownloadStatus, Progress, SearchQuery

logger = logging.getLogger(__name__)

# Well-known CDS dataset names with their metadata
_CDS_DATASETS: dict[str, dict[str, Any]] = {
    "reanalysis-era5-pressure-levels": {
        "description": "ERA5 hourly pressure-level data (1940–present)",
        "variables": ["temperature", "u_component_of_wind", "v_component_of_wind",
                      "geopotential", "specific_humidity", "relative_humidity"],
    },
    "reanalysis-era5-single-levels": {
        "description": "ERA5 hourly single-level data (2m temperature, total precipitation, …)",
        "variables": ["2m_temperature", "total_precipitation", "mean_sea_level_pressure",
                      "10m_u_component_of_wind", "10m_v_component_of_wind"],
    },
    "reanalysis-era5-land": {
        "description": "ERA5-Land hourly data (0.1° land-only, 1950–present)",
        "variables": ["2m_temperature", "total_precipitation", "soil_temperature_level_1"],
    },
    "projections-cmip6": {
        "description": "CMIP6 global climate projections",
        "variables": ["near_surface_air_temperature", "precipitation"],
    },
}


class CopernicusConnector(DataSourceConnector):
    """Connector for the ECMWF Copernicus Climate Data Store."""

    def source_name(self) -> str:
        return "copernicus"

    def requires_auth(self) -> bool:
        return True  # ~/.cdsapirc or CDSAPI_KEY env var

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[Dataset]:
        """
        CDS does not have a free-text search API; users specify dataset names
        and request parameters explicitly.  This method validates the
        requested dataset name and returns a single Dataset descriptor.

        Required params:
          - ``dataset``  : CDS dataset identifier (e.g. "reanalysis-era5-pressure-levels")
          - ``variables``: list of CDS variable names
          - ``years``    : list of year strings (e.g. ["2020", "2021"])
          - ``months``   : list of month strings (e.g. ["01", "06"])

        Optional params:
          - ``area``          : [north, west, south, east] for spatial subsetting
          - ``pressure_levels``: list of pressure level strings (e.g. ["500", "850"])
          - ``grid``          : e.g. "1.0/1.0" for ERA5 native-to-regular conversion
        """
        try:
            import cdsapi  # noqa: F401 — just check it's installed
        except ImportError as exc:
            raise RuntimeError(
                "cdsapi is not installed.  Run: pip install cdsapi"
            ) from exc

        params = query.params
        dataset_name = params.get("dataset", "reanalysis-era5-pressure-levels")
        meta = _CDS_DATASETS.get(dataset_name, {})

        variables = params.get("variables") or ([query.variable] if query.variable else [])
        years: list[str] = params.get("years", [])
        months: list[str] = params.get("months", ["01"])

        request_params = self._build_request(params, variables, years, months)

        return [
            Dataset(
                id=f"cds:{dataset_name}:{':'.join(variables)}:{':'.join(years)}",
                source="copernicus",
                title=f"{dataset_name} — {', '.join(variables)}",
                description=meta.get("description", dataset_name),
                url=None,   # URL is determined at download time by cdsapi
                size_mb=None,
                variables=variables,
                frequency=query.frequency or "hourly",
                metadata={
                    "dataset":        dataset_name,
                    "request_params": request_params,
                    "year":           years[0] if years else "unknown",
                    "years":          years,
                    "months":         months,
                },
            )
        ]

    def _build_request(
        self,
        params: dict[str, Any],
        variables: list[str],
        years: list[str],
        months: list[str],
    ) -> dict[str, Any]:
        """Construct the cdsapi request dict from high-level parameters."""
        req: dict[str, Any] = {
            "product_type": params.get("product_type", ["reanalysis"]),
            "variable":     variables,
            "year":         years,
            "month":        months,
            "day":          params.get("day", [str(d).zfill(2) for d in range(1, 32)]),
            "time":         params.get("time", ["00:00", "06:00", "12:00", "18:00"]),
            "data_format":  "netcdf",  # Always request NetCDF, not GRIB
            "download_format": "unarchived",
        }

        if params.get("pressure_levels"):
            req["pressure_level"] = params["pressure_levels"]
        if params.get("area"):
            req["area"] = params["area"]   # [north, west, south, east]
        if params.get("grid"):
            req["grid"] = params["grid"]   # e.g. "1.0/1.0"

        return req

    # ── Download ──────────────────────────────────────────────────────────────

    async def download(  # type: ignore[override]
        self, dataset: Dataset, dest_path: Path
    ) -> AsyncIterator[Progress]:
        """
        Download via cdsapi in a thread executor.
        While cdsapi polls the CDS queue, we monitor the file size for progress.
        """
        try:
            import cdsapi
        except ImportError as exc:
            yield Progress(
                file=dest_path.name,
                downloaded_bytes=0,
                total_bytes=0,
                speed_mbps=0.0,
                status=DownloadStatus.FAILED,
                error=f"cdsapi not installed: {exc}",
            )
            return

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        m = dataset.metadata
        dataset_name  = m.get("dataset", "")
        request_params = dict(m.get("request_params", {}))
        total_bytes   = int((dataset.size_mb or 0) * 1_048_576)

        loop  = asyncio.get_running_loop()
        error_holder: list[Exception] = []

        def _cdsapi_download() -> None:
            try:
                client = cdsapi.Client(quiet=True, progress=False)
                client.retrieve(dataset_name, request_params, str(dest_path))
            except Exception as exc:
                error_holder.append(exc)

        start = time.monotonic()
        fut = loop.run_in_executor(None, _cdsapi_download)

        # Stream progress by polling file size while cdsapi runs
        while not fut.done():
            await asyncio.sleep(2)
            current_bytes = dest_path.stat().st_size if dest_path.exists() else 0
            elapsed = time.monotonic() - start
            speed = current_bytes / elapsed / 1_048_576 if elapsed > 0 else 0.0

            yield Progress(
                file=dest_path.name,
                downloaded_bytes=current_bytes,
                total_bytes=total_bytes or max(current_bytes, 1),
                speed_mbps=round(speed, 2),
                status=DownloadStatus.DOWNLOADING,
            )

        await fut  # propagate any asyncio executor exception

        if error_holder:
            yield Progress(
                file=dest_path.name,
                downloaded_bytes=0,
                total_bytes=total_bytes,
                speed_mbps=0.0,
                status=DownloadStatus.FAILED,
                error=str(error_holder[0]),
            )
            return

        final_bytes = dest_path.stat().st_size if dest_path.exists() else 0
        yield Progress(
            file=dest_path.name,
            downloaded_bytes=final_bytes,
            total_bytes=final_bytes,
            speed_mbps=0.0,
            status=DownloadStatus.COMPLETED,
        )

    # ── Auto-folder path ──────────────────────────────────────────────────────

    def build_dest(self, dataset: Dataset, base_dir: Path) -> Path:
        """CDS/{dataset}/{variable}/{year}/{file}"""
        m        = dataset.metadata
        ds_name  = str(m.get("dataset", "unknown"))
        variable = dataset.variables[0] if dataset.variables else "unknown"
        year     = str(m.get("year", "unknown"))
        filename = f"{ds_name}_{variable}_{year}.nc"

        return base_dir / "CDS" / ds_name / variable / year / filename
