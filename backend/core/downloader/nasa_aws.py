"""
NASA / NOAA AWS Open Data Registry connector.

Provides access to large datasets hosted on public S3 buckets.
No credentials required.

Supported datasets
──────────────────
  cesm-lens  — CESM Large Ensemble (40 members, 1920–2100)
               s3://ncar-cesm-lens/
  cmaq       — CMAQ air quality model output
               s3://noaa-nos-ofs-pds/
  argo       — Argo ocean float profiles (GDAC)
               s3://argo-gdac-sandbox/
  airs       — AIRS satellite atmospheric sounder (GESDISC public)
               s3://gesdisc-cumulus-prod-protected/ (requires auth)

Auto-folder: NASA_AWS/{dataset}/{variable}/{file}
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .base import DataSourceConnector, Dataset, DownloadStatus, Progress, SearchQuery

logger = logging.getLogger(__name__)

# Publicly accessible (anonymous) NASA / NOAA S3 buckets
_DATASET_BUCKETS: dict[str, str] = {
    "cesm-lens": "ncar-cesm-lens",
    "argo":      "argo-gdac-sandbox",
}

# S3 key prefix templates per dataset (variables fill in later)
_DATASET_PREFIXES: dict[str, str] = {
    "cesm-lens": "atm/proc/tseries/month_1/{variable}/",
    "argo":      "dac/",
}


def _get_s3_client() -> Any:
    try:
        import boto3  # type: ignore[import]
        from botocore import UNSIGNED  # type: ignore[import]
        from botocore.config import Config  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "boto3 / botocore is not installed.  "
            "Run: conda install -c conda-forge boto3"
        ) from exc

    return boto3.client("s3", config=Config(signature_version=UNSIGNED))


class NASAConnector(DataSourceConnector):
    """Connector for NASA / NOAA public AWS datasets."""

    def source_name(self) -> str:
        return "nasa_aws"

    def requires_auth(self) -> bool:
        return False  # anonymous S3 access

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[Dataset]:
        """
        List S3 objects for the requested dataset.

        Required params:
          - ``dataset`` : one of the keys in _DATASET_BUCKETS
                          (default: "cesm-lens")

        Optional params:
          - ``prefix``  : override the default S3 key prefix
          - ``ensemble``: ensemble member pattern (e.g. "b.e11.B20TRC5CNBDRD*")
        """
        import asyncio

        params  = query.params
        dataset = params.get("dataset", "cesm-lens")

        if dataset not in _DATASET_BUCKETS:
            raise ValueError(
                f"Unknown NASA/AWS dataset '{dataset}'. "
                f"Supported: {list(_DATASET_BUCKETS)}"
            )

        bucket = _DATASET_BUCKETS[dataset]
        template = _DATASET_PREFIXES.get(dataset, "")
        variable = query.variable or params.get("variable", "")
        prefix = params.get("prefix") or template.format(variable=variable)

        datasets = await asyncio.to_thread(
            self._list_objects, dataset, bucket, prefix, query.limit
        )
        logger.info(
            "NASA/AWS search found %d objects in s3://%s/%s", len(datasets), bucket, prefix
        )
        return datasets

    def _list_objects(
        self, dataset_name: str, bucket: str, prefix: str, limit: int
    ) -> list[Dataset]:
        """Synchronous S3 listing — runs in asyncio.to_thread."""
        s3 = _get_s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        results: list[Dataset] = []

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if len(results) >= limit:
                    break
                key: str = obj["Key"]
                if not key.endswith(".nc"):
                    continue

                parts    = key.split("/")
                variable = parts[-2] if len(parts) >= 2 else "unknown"
                filename = parts[-1]

                results.append(
                    Dataset(
                        id=f"s3://{bucket}/{key}",
                        source="nasa_aws",
                        title=filename,
                        description=f"NASA/AWS {dataset_name} — {key}",
                        url=None,
                        size_mb=round(obj["Size"] / 1_048_576, 2),
                        variables=[variable],
                        frequency=None,
                        metadata={
                            "dataset":  dataset_name,
                            "bucket":   bucket,
                            "key":      key,
                            "variable": variable,
                            "filename": filename,
                        },
                    )
                )

            if len(results) >= limit:
                break

        return results

    # ── Download ──────────────────────────────────────────────────────────────

    async def download(  # type: ignore[override]
        self, dataset: Dataset, dest_path: Path
    ) -> AsyncIterator[Progress]:
        """Download S3 object via boto3 with callback progress."""
        m      = dataset.metadata
        bucket = str(m.get("bucket", ""))
        key    = str(m.get("key",    ""))

        if not bucket or not key:
            yield Progress(
                file=dest_path.name,
                downloaded_bytes=0,
                total_bytes=0,
                speed_mbps=0.0,
                status=DownloadStatus.FAILED,
                error="Missing bucket or key in dataset metadata",
            )
            return

        s3 = _get_s3_client()
        total_bytes = int((dataset.size_mb or 0) * 1_048_576)

        async for p in self._s3_download(s3, bucket, key, dest_path, total_bytes):
            yield p

    # ── Auto-folder path ──────────────────────────────────────────────────────

    def build_dest(self, dataset: Dataset, base_dir: Path) -> Path:
        """NASA_AWS/{dataset}/{variable}/{file}"""
        m        = dataset.metadata
        ds_name  = str(m.get("dataset",  "unknown"))
        variable = dataset.variables[0] if dataset.variables else "unknown"
        filename = str(m.get("filename") or dataset.title)

        return base_dir / "NASA_AWS" / ds_name / variable / filename
