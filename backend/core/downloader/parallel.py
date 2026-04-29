"""
Asyncio-based parallel download manager.

Runs up to ``max_concurrent`` downloads simultaneously using an
``asyncio.Semaphore``.  Progress events from all workers are merged into a
single async generator so the WebSocket handler has a single stream to
consume.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

from .base import DataSourceConnector, Dataset, DownloadStatus, Progress

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Extended progress type
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class BatchProgress:
    """Progress snapshot enriched with batch-level counters."""

    file:             str
    downloaded_bytes: int
    total_bytes:      int
    speed_mbps:       float
    status:           DownloadStatus
    error:            str | None
    current_file:     int           # 1-based index of the file being downloaded
    total_files:      int
    percent:          float         # 0–100, computed from file-level progress

    @classmethod
    def from_progress(
        cls,
        p: Progress,
        current_file: int,
        total_files: int,
    ) -> "BatchProgress":
        return cls(
            file=p.file,
            downloaded_bytes=p.downloaded_bytes,
            total_bytes=p.total_bytes,
            speed_mbps=p.speed_mbps,
            status=p.status,
            error=p.error,
            current_file=current_file,
            total_files=total_files,
            percent=round(p.percent, 1),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Parallel download coordinator
# ─────────────────────────────────────────────────────────────────────────────


async def parallel_download(
    connector: DataSourceConnector,
    tasks: list[tuple[Dataset, Path]],
    max_concurrent: int = 4,
) -> AsyncGenerator[BatchProgress, None]:
    """
    Download all *tasks* concurrently (up to *max_concurrent* at a time).

    Yields ``BatchProgress`` events from all workers merged into a single
    stream.  Guarantees a final event per file (COMPLETED or FAILED) before
    the generator returns.

    Usage::

        async for bp in parallel_download(connector, tasks, max_concurrent=4):
            # bp.current_file, bp.total_files, bp.percent, bp.status, …
    """
    if not tasks:
        return

    total_files = len(tasks)
    semaphore = asyncio.Semaphore(max_concurrent)
    queue: asyncio.Queue[BatchProgress | None] = asyncio.Queue()
    pending_count = total_files
    pending_lock = asyncio.Lock()

    async def _worker(dataset: Dataset, dest: Path, file_idx: int) -> None:
        nonlocal pending_count

        async with semaphore:
            try:
                async for p in connector.download(dataset, dest):
                    await queue.put(
                        BatchProgress.from_progress(p, file_idx, total_files)
                    )
            except Exception as exc:
                logger.exception(
                    "Worker error for file %d/%d: %s",
                    file_idx, total_files, dataset.title,
                )
                await queue.put(
                    BatchProgress(
                        file=dest.name,
                        downloaded_bytes=0,
                        total_bytes=0,
                        speed_mbps=0.0,
                        status=DownloadStatus.FAILED,
                        error=str(exc),
                        current_file=file_idx,
                        total_files=total_files,
                        percent=0.0,
                    )
                )
            finally:
                async with pending_lock:
                    pending_count -= 1
                    if pending_count == 0:
                        await queue.put(None)   # sentinel — all workers done

    # Fire all workers.  asyncio.create_task() schedules them without blocking.
    for idx, (dataset, dest) in enumerate(tasks, start=1):
        asyncio.create_task(_worker(dataset, dest, idx))

    # Drain the queue until the sentinel arrives.
    while True:
        item = await queue.get()
        if item is None:
            return
        yield item
