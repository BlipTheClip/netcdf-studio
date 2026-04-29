"""
World Bank Climate Knowledge Portal (CCKP) connector.

Data source: anonymous S3 at s3://wbg-cckp/
No credentials required.  Data includes CMIP6 downscaled and bias-corrected
output (0.25°), ERA5 (0.25°), CRU (0.5°), and population grids.

Collections
───────────
  cmip6-x0.25/  — CMIP6 downscaled projections
  era5/          — ERA5 reanalysis (0.25°)
  cru/           — CRU TS observational gridded data
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .base import DataSourceConnector, Dataset, DownloadStatus, Progress, SearchQuery

logger = logging.getLogger(__name__)

_BUCKET = "wbg-cckp"

_COLLECTION_PREFIXES: dict[str, str] = {
    "cmip6":  "cmip6-x0.25/",
    "era5":   "era5/",
    "cru":    "cru/",
}


def _get_s3_client() -> Any:
    """Return a boto3 S3 client configured for anonymous access."""
    try:
        import boto3  # type: ignore[import]
        from botocore import UNSIGNED  # type: ignore[import]
        from botocore.config import Config  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "boto3 / botocore is not installed.  Run: conda install -c conda-forge boto3"
        ) from exc

    return boto3.client("s3", config=Config(signature_version=UNSIGNED))


class WorldBankConnector(DataSourceConnector):
    """Connector for the World Bank Climate Knowledge Portal (anonymous S3)."""

    def source_name(self) -> str:
        return "worldbank"

    def requires_auth(self) -> bool:
        return False  # anonymous S3 access

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[Dataset]:
        """
        List S3 objects matching the search criteria.

        Params:
          - ``collection`` : "cmip6" | "era5" | "cru"  (default: "cmip6")
          - ``prefix``     : additional S3 key prefix for fine-grained filtering
        """
        import asyncio

        params = query.params
        collection = params.get("collection", "cmip6")
        prefix = _COLLECTION_PREFIXES.get(collection, f"{collection}/")

        if params.get("prefix"):
            prefix = str(params["prefix"])
        if query.variable:
            prefix += query.variable + "/"

        datasets = await asyncio.to_thread(self._list_objects, prefix, query.limit)
        logger.info("WorldBank search found %d objects under s3://%s/%s", len(datasets), _BUCKET, prefix)
        return datasets

    def _list_objects(self, prefix: str, limit: int) -> list[Dataset]:
        """Synchronous S3 listing — runs inside asyncio.to_thread."""
        s3 = _get_s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        datasets: list[Dataset] = []

        for page in paginator.paginate(Bucket=_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if len(datasets) >= limit:
                    break
                key: str = obj["Key"]
                if not key.endswith(".nc"):
                    continue

                parts = key.split("/")
                collection = parts[0].split("-")[0]  # "cmip6-x0.25" → "cmip6"
                variable   = parts[1] if len(parts) > 1 else "unknown"
                filename   = parts[-1]

                datasets.append(
                    Dataset(
                        id=f"s3://{_BUCKET}/{key}",
                        source="worldbank",
                        title=filename,
                        description=f"World Bank CCKP — {key}",
                        url=None,  # downloaded via boto3, not HTTP
                        size_mb=round(obj["Size"] / 1_048_576, 2),
                        variables=[variable],
                        frequency=None,
                        metadata={
                            "bucket":     _BUCKET,
                            "key":        key,
                            "collection": collection,
                            "variable":   variable,
                            "filename":   filename,
                        },
                    )
                )

            if len(datasets) >= limit:
                break

        return datasets

    # ── Download ──────────────────────────────────────────────────────────────

    async def download(  # type: ignore[override]
        self, dataset: Dataset, dest_path: Path
    ) -> AsyncIterator[Progress]:
        """Download an S3 object via boto3 with callback progress."""
        m = dataset.metadata
        bucket = m.get("bucket", _BUCKET)
        key    = m.get("key", "")

        if not key:
            yield Progress(
                file=dest_path.name,
                downloaded_bytes=0,
                total_bytes=0,
                speed_mbps=0.0,
                status=DownloadStatus.FAILED,
                error="No S3 key found in dataset metadata",
            )
            return

        s3 = _get_s3_client()
        total_bytes = int((dataset.size_mb or 0) * 1_048_576)

        async for p in self._s3_download(s3, bucket, key, dest_path, total_bytes):
            yield p

    # ── Auto-folder path ──────────────────────────────────────────────────────

    def build_dest(self, dataset: Dataset, base_dir: Path) -> Path:
        """CCKP/{collection}/{variable}/{file}"""
        m          = dataset.metadata
        collection = str(m.get("collection", "unknown"))
        variable   = dataset.variables[0] if dataset.variables else "unknown"
        filename   = str(m.get("filename") or dataset.title)

        return base_dir / "CCKP" / collection / variable / filename
