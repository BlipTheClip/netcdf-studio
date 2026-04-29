"""
Abstract base classes and shared data models for all data source connectors.

Pattern for async generators in subclasses
──────────────────────────────────────────
``download()`` is declared as returning ``AsyncIterator[Progress]`` so the
abstract contract is clear.  Concrete subclasses implement it as *async
generator functions* (containing ``yield``), which return an
``AsyncGenerator[Progress, None]``—a proper subtype of ``AsyncIterator``.
Callers always use ``async for p in connector.download(dataset, path): ...``
and never need to ``await`` the call itself.
"""

from __future__ import annotations

import enum
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Enums & data models
# ─────────────────────────────────────────────────────────────────────────────


class DownloadStatus(str, enum.Enum):
    QUEUED      = "queued"
    DOWNLOADING = "downloading"
    COMPLETED   = "completed"
    FAILED      = "failed"


@dataclass
class SearchQuery:
    """Source-agnostic query.

    ``params`` carries source-specific fields (e.g. CMIP6 project,
    CDS dataset name, S3 prefix) that each connector interprets independently.
    """

    variable:   str | None         = None
    start_year: int | None         = None
    end_year:   int | None         = None
    frequency:  str | None         = None   # "mon", "day", "6hr", …
    limit:      int                = 50
    params:     dict[str, Any]     = field(default_factory=dict)


@dataclass
class Dataset:
    """A searchable and downloadable dataset entry returned by a connector."""

    id:          str
    source:      str                # "esgf" | "copernicus" | "worldbank" | "nasa_aws" | "esa_cci"
    title:       str
    description: str
    url:         str | None         # Direct download URL (known at search time for HTTP sources)
    size_mb:     float | None
    variables:   list[str]
    frequency:   str | None
    metadata:    dict[str, Any]     = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":          self.id,
            "source":      self.source,
            "title":       self.title,
            "description": self.description,
            "url":         self.url,
            "size_mb":     self.size_mb,
            "variables":   self.variables,
            "frequency":   self.frequency,
            "metadata":    self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Dataset":
        return cls(
            id=d["id"],
            source=d["source"],
            title=d["title"],
            description=d.get("description", ""),
            url=d.get("url"),
            size_mb=d.get("size_mb"),
            variables=d.get("variables", []),
            frequency=d.get("frequency"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class Progress:
    """Per-file download progress snapshot."""

    file:             str
    downloaded_bytes: int
    total_bytes:      int
    speed_mbps:       float
    status:           DownloadStatus
    error:            str | None    = None

    @property
    def percent(self) -> float:
        if not self.total_bytes:
            return 0.0
        return min(100.0, self.downloaded_bytes / self.total_bytes * 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# Abstract connector
# ─────────────────────────────────────────────────────────────────────────────


class DataSourceConnector(ABC):
    """Abstract base for all data source connectors."""

    # ── Identity ─────────────────────────────────────────────────────────────

    @abstractmethod
    def source_name(self) -> str:
        """Identifier used in API routes and Dataset.source field."""

    @abstractmethod
    def requires_auth(self) -> bool:
        """True when the source requires credentials to download files."""

    # ── Core interface ────────────────────────────────────────────────────────

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[Dataset]:
        """Query the data catalogue and return matching Dataset objects."""

    @abstractmethod
    def download(
        self, dataset: Dataset, dest_path: Path
    ) -> AsyncIterator[Progress]:
        """
        Download *dataset* to *dest_path*, yielding Progress updates.

        Implementations should:
        - Create parent directories before writing.
        - Yield at least one DOWNLOADING event while in progress.
        - Yield a final COMPLETED (or FAILED) event before returning.
        - Never raise exceptions; encode errors in a FAILED Progress event.
        """

    @abstractmethod
    def build_dest(self, dataset: Dataset, base_dir: Path) -> Path:
        """
        Compute the auto-organised local file path under *base_dir*.

        Each connector implements its own folder hierarchy:
        - ESGF    → ESGF/{institute}/{model}/{experiment}/{frequency}/{variable}/
        - CDS     → CDS/{dataset}/{variable}/{year}/
        - CCKP    → CCKP/{collection}/{variable}/
        - NASA_AWS→ NASA_AWS/{dataset}/{variable}/
        - ESA_CCI → ESA_CCI/{ecv}/{sensor}/
        """

    # ── Shared HTTP streaming helper ──────────────────────────────────────────

    async def _http_stream(
        self,
        url: str,
        dest_path: Path,
        *,
        headers: dict[str, str] | None = None,
        chunk_size: int = 65_536,
    ) -> AsyncIterator[Progress]:
        """
        Stream *url* to *dest_path* via HTTPS using httpx.
        Yields Progress events; the final event has status COMPLETED.

        Used by HTTP-based connectors (ESGF file downloads, ESA CCI).
        """
        import httpx

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        total = 0
        start = time.monotonic()

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=300.0) as client:
                async with client.stream(
                    "GET", url, headers=headers or {}
                ) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length", 0))

                    with open(dest_path, "wb") as fh:
                        async for chunk in response.aiter_bytes(chunk_size):
                            fh.write(chunk)
                            downloaded += len(chunk)
                            elapsed = time.monotonic() - start
                            speed = downloaded / elapsed / 1_048_576 if elapsed > 0 else 0.0

                            yield Progress(
                                file=dest_path.name,
                                downloaded_bytes=downloaded,
                                total_bytes=total or downloaded,
                                speed_mbps=round(speed, 2),
                                status=DownloadStatus.DOWNLOADING,
                            )

            yield Progress(
                file=dest_path.name,
                downloaded_bytes=downloaded,
                total_bytes=downloaded,
                speed_mbps=0.0,
                status=DownloadStatus.COMPLETED,
            )

        except Exception as exc:
            yield Progress(
                file=dest_path.name,
                downloaded_bytes=downloaded,
                total_bytes=total,
                speed_mbps=0.0,
                status=DownloadStatus.FAILED,
                error=str(exc),
            )

    # ── Shared S3 download helper ─────────────────────────────────────────────

    async def _s3_download(
        self,
        s3_client: Any,
        bucket: str,
        key: str,
        dest_path: Path,
        total_bytes: int = 0,
    ) -> AsyncIterator[Progress]:
        """
        Download an S3 object using a boto3 *s3_client* with callback progress.
        The callback is called from the boto3 thread; an asyncio Queue bridges
        it to this async generator.

        *s3_client* must already be configured with the correct credentials /
        UNSIGNED config for the target bucket.
        """
        import asyncio

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[int | Exception | None] = asyncio.Queue()

        def _callback(bytes_amount: int) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, bytes_amount)

        def _download() -> None:
            try:
                s3_client.download_file(bucket, key, str(dest_path), Callback=_callback)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        downloaded = 0
        start = time.monotonic()
        download_task = loop.run_in_executor(None, _download)

        while True:
            item = await queue.get()

            if item is None:
                break

            if isinstance(item, Exception):
                yield Progress(
                    file=dest_path.name,
                    downloaded_bytes=downloaded,
                    total_bytes=total_bytes,
                    speed_mbps=0.0,
                    status=DownloadStatus.FAILED,
                    error=str(item),
                )
                await download_task
                return

            downloaded += item
            elapsed = time.monotonic() - start
            speed = downloaded / elapsed / 1_048_576 if elapsed > 0 else 0.0

            yield Progress(
                file=dest_path.name,
                downloaded_bytes=downloaded,
                total_bytes=total_bytes or downloaded,
                speed_mbps=round(speed, 2),
                status=DownloadStatus.DOWNLOADING,
            )

        await download_task

        yield Progress(
            file=dest_path.name,
            downloaded_bytes=downloaded,
            total_bytes=downloaded,
            speed_mbps=0.0,
            status=DownloadStatus.COMPLETED,
        )
