"""
ESA Climate Change Initiative (CCI) Open Data Portal connector.

Provides access to 27 Essential Climate Variables (ECVs) including SST,
soil moisture, ozone, sea level, glaciers, and land cover.

Registration required: https://climate.esa.int
Credentials: set ESA_CCI_USER and ESA_CCI_PASS environment variables, or
configure ~/.netrc with host climate.esa.int.

Search
──────
Uses the CEDA OpenSearch catalogue:
  https://catalogue.ceda.ac.uk/api/v2/results.json

Download
────────
Files are served over HTTPS.  Most are freely accessible; some require
OpenID credentials stored in ~/.netrc or passed via Authorization headers.

Auto-folder: ESA_CCI/{ecv}/{sensor}/{file}
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from .base import DataSourceConnector, Dataset, DownloadStatus, Progress, SearchQuery

logger = logging.getLogger(__name__)

_CEDA_SEARCH_URL = "https://catalogue.ceda.ac.uk/api/v2/results.json"

# ESA CCI ECV identifiers → human-readable names
_ECV_NAMES: dict[str, str] = {
    "sst":           "Sea Surface Temperature",
    "soil-moisture": "Soil Moisture",
    "ozone":         "Ozone",
    "sea-level":     "Sea Level",
    "glaciers":      "Glaciers",
    "land-cover":    "Land Cover",
    "aerosol":       "Aerosol",
    "cloud":         "Cloud",
    "fire":          "Fire",
    "lakes":         "Lakes",
    "salinity":      "Ocean Salinity",
    "snow":          "Snow Cover",
    "biomass":       "Biomass",
}


class ESACCIConnector(DataSourceConnector):
    """Connector for the ESA Climate Change Initiative Open Data Portal."""

    def source_name(self) -> str:
        return "esa_cci"

    def requires_auth(self) -> bool:
        return True   # free registration at climate.esa.int

    # ── Credential helpers ────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        """Build Basic-auth header from env vars ESA_CCI_USER / ESA_CCI_PASS."""
        user = os.environ.get("ESA_CCI_USER", "")
        pw   = os.environ.get("ESA_CCI_PASS", "")
        if not user or not pw:
            return {}
        import base64
        token = base64.b64encode(f"{user}:{pw}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[Dataset]:
        """
        Query the CEDA catalogue for ESA CCI datasets.

        Params:
          - ``ecv``    : ECV identifier (e.g. "sst", "soil-moisture")
          - ``sensor`` : sensor/platform (e.g. "ATSR2-AATSR", "MERGED")
          - ``version``: dataset version (e.g. "3.0")
        """
        params = query.params
        ecv    = params.get("ecv", query.variable or "sst")
        sensor = params.get("sensor", "")

        search_terms = [f"CCI {_ECV_NAMES.get(ecv, ecv.upper())}"]
        if sensor:
            search_terms.append(sensor)
        q = " ".join(search_terms)

        try:
            results = await self._catalogue_search(q, query.limit)
        except Exception as exc:
            logger.warning("ESA CCI catalogue search failed: %s", exc)
            return []

        datasets: list[Dataset] = []
        for rec in results:
            try:
                ds = self._record_to_dataset(rec, ecv, sensor)
                datasets.append(ds)
            except Exception:
                logger.debug("Skipping malformed record: %s", rec.get("title", "?"))

        return datasets

    async def _catalogue_search(self, q: str, limit: int) -> list[dict]:
        """Query the CEDA REST API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                _CEDA_SEARCH_URL,
                params={
                    "q":           q,
                    "record_type": "Dataset",
                    "num_results": min(limit, 100),
                    "page":        1,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

    def _record_to_dataset(self, rec: dict, ecv: str, sensor: str) -> Dataset:
        """Convert a CEDA catalogue record to a Dataset object."""
        record_id = rec.get("identifier", rec.get("id", ""))
        title     = rec.get("title", record_id)
        abstract  = rec.get("abstract", "")

        # Extract download URL from the record links
        url: str | None = None
        for link in rec.get("online_resources", []) or []:
            if link.get("function") in ("download", "offlineAccess"):
                url = link.get("url")
                break

        size_mb: float | None = None
        file_size = rec.get("file_size")
        if file_size:
            try:
                size_mb = float(file_size) / 1_048_576
            except (ValueError, TypeError):
                pass

        return Dataset(
            id=record_id,
            source="esa_cci",
            title=title,
            description=abstract,
            url=url,
            size_mb=size_mb,
            variables=[ecv],
            frequency=None,
            metadata={
                "ecv":    ecv,
                "sensor": sensor or "unknown",
                "record": record_id,
                "filename": title.replace(" ", "_") + ".nc",
            },
        )

    # ── Download ──────────────────────────────────────────────────────────────

    async def download(  # type: ignore[override]
        self, dataset: Dataset, dest_path: Path
    ) -> AsyncIterator[Progress]:
        """Stream the ESA CCI file over HTTPS using httpx."""
        if not dataset.url:
            yield Progress(
                file=dest_path.name,
                downloaded_bytes=0,
                total_bytes=0,
                speed_mbps=0.0,
                status=DownloadStatus.FAILED,
                error="No download URL available — the CEDA catalogue did not return a direct link",
            )
            return

        headers = self._auth_headers()
        async for p in self._http_stream(dataset.url, dest_path, headers=headers):
            yield p

    # ── Auto-folder path ──────────────────────────────────────────────────────

    def build_dest(self, dataset: Dataset, base_dir: Path) -> Path:
        """ESA_CCI/{ecv}/{sensor}/{file}"""
        m        = dataset.metadata
        ecv      = str(m.get("ecv",    "unknown"))
        sensor   = str(m.get("sensor", "unknown"))
        filename = str(m.get("filename") or dataset.title)

        return base_dir / "ESA_CCI" / ecv / sensor / filename
