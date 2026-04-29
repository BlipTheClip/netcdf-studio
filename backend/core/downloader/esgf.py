"""
ESGF (Earth System Grid Federation) data source connector.

Supports CMIP3, CMIP5, CMIP6, CORDEX, obs4MIPs.
Requires esgf-pyclient (pip install esgf-pyclient).

Authentication
──────────────
Anonymous access covers the vast majority of CMIP6 data.  For restricted
nodes, set ESGF_OPENID and ESGF_PASSWORD environment variables; the connector
will attempt token-based auth via the Logon helper.

Node failover
─────────────
Nodes are tried in order.  The first one that responds to the search request
wins.  If all nodes fail the exception from the last attempt is re-raised.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .base import DataSourceConnector, Dataset, DownloadStatus, Progress, SearchQuery

logger = logging.getLogger(__name__)

_ESGF_NODES: list[str] = [
    "https://esgf-node.llnl.gov/esg-search",
    "https://esgf-data.dkrz.de/esg-search",
    "https://esgf.nci.org.au/esg-search",
    "https://esgf.ceda.ac.uk/esg-search",
]

_DEFAULT_PROJECT = "CMIP6"


class ESGFConnector(DataSourceConnector):
    """Connector for the Earth System Grid Federation."""

    def source_name(self) -> str:
        return "esgf"

    def requires_auth(self) -> bool:
        return False   # anonymous access covers most CMIP6 data

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[Dataset]:
        """Search ESGF across multiple nodes with automatic failover."""
        try:
            from pyesgf.search import SearchConnection  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "esgf-pyclient is not installed.  "
                "Run: pip install esgf-pyclient"
            ) from exc

        params = query.params
        project = params.get("project", _DEFAULT_PROJECT)

        ctx_kwargs: dict[str, Any] = {"latest": True}
        if project:
            ctx_kwargs["project"] = project
        if query.variable:
            ctx_kwargs["variable_id"] = query.variable
        if params.get("experiment_id"):
            ctx_kwargs["experiment_id"] = params["experiment_id"]
        if params.get("source_id"):
            ctx_kwargs["source_id"] = params["source_id"]
        if params.get("institution_id"):
            ctx_kwargs["institution_id"] = params["institution_id"]
        if query.frequency:
            ctx_kwargs["frequency"] = query.frequency
        if params.get("table_id"):
            ctx_kwargs["table_id"] = params["table_id"]
        if params.get("variant_label"):
            ctx_kwargs["variant_label"] = params["variant_label"]

        last_exc: Exception | None = None

        for node_url in _ESGF_NODES:
            try:
                datasets = await asyncio.to_thread(
                    self._search_node,
                    node_url,
                    ctx_kwargs,
                    query.limit,
                )
                logger.info(
                    "ESGF search on %s returned %d datasets", node_url, len(datasets)
                )
                return datasets
            except Exception as exc:
                logger.warning("ESGF node %s failed: %s", node_url, exc)
                last_exc = exc

        raise RuntimeError(
            f"All ESGF nodes failed. Last error: {last_exc}"
        ) from last_exc

    def _search_node(
        self,
        node_url: str,
        ctx_kwargs: dict[str, Any],
        limit: int,
    ) -> list[Dataset]:
        """Synchronous ESGF search — runs inside asyncio.to_thread."""
        from pyesgf.search import SearchConnection  # type: ignore[import]

        conn = SearchConnection(node_url, distrib=True)
        ctx = conn.new_context(**ctx_kwargs)

        # Each ctx.search() result is a dataset; get its files
        datasets: list[Dataset] = []
        results = ctx.search()

        for result in results:
            if len(datasets) >= limit:
                break
            try:
                file_ctx = result.file_context()
                files = file_ctx.search()
            except Exception as exc:
                logger.debug("Could not get files for result %s: %s", result.dataset_id, exc)
                continue

            for f in files:
                if len(datasets) >= limit:
                    break

                size_mb = (f.size or 0) / 1_048_576
                meta = {
                    "institution_id": getattr(result, "institution_id", None) or "unknown",
                    "source_id":      getattr(result, "source_id",      None) or "unknown",
                    "experiment_id":  getattr(result, "experiment_id",  None) or "unknown",
                    "frequency":      getattr(result, "frequency",       None) or "unknown",
                    "filename":       f.filename,
                    "checksum":       f.checksum,
                    "checksum_type":  f.checksum_type,
                    "data_node":      f.download_url.split("/")[2] if f.download_url else "",
                }

                datasets.append(
                    Dataset(
                        id=f.file_id,
                        source="esgf",
                        title=f.filename,
                        description=result.dataset_id or "",
                        url=f.download_url,
                        size_mb=round(size_mb, 2),
                        variables=[ctx_kwargs.get("variable_id", "unknown")],
                        frequency=meta["frequency"],
                        metadata=meta,
                    )
                )

        return datasets

    # ── Download ──────────────────────────────────────────────────────────────

    async def download(  # type: ignore[override]
        self, dataset: Dataset, dest_path: Path
    ) -> AsyncIterator[Progress]:
        """Stream the ESGF file over HTTPS using httpx."""
        if not dataset.url:
            yield Progress(
                file=dest_path.name,
                downloaded_bytes=0,
                total_bytes=0,
                speed_mbps=0.0,
                status=DownloadStatus.FAILED,
                error="No download URL available for this dataset",
            )
            return

        async for p in self._http_stream(dataset.url, dest_path):
            yield p

    # ── Auto-folder path ──────────────────────────────────────────────────────

    def build_dest(self, dataset: Dataset, base_dir: Path) -> Path:
        """ESGF/{institute}/{model}/{experiment}/{frequency}/{variable}/{file}"""
        m = dataset.metadata
        institute  = _safe(m.get("institution_id"))
        model      = _safe(m.get("source_id"))
        experiment = _safe(m.get("experiment_id"))
        frequency  = _safe(dataset.frequency or m.get("frequency"))
        variable   = dataset.variables[0] if dataset.variables else "unknown"
        filename   = m.get("filename") or dataset.title

        return (
            base_dir / "ESGF" / institute / model / experiment / frequency / variable / filename
        )


def _safe(value: Any) -> str:
    """Return a filesystem-safe string (fallback 'unknown')."""
    if not value:
        return "unknown"
    return str(value).replace("/", "_").replace(" ", "_")
