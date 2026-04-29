"""
Module A — Data source connectors and parallel download manager.

All connectors inherit DataSourceConnector (base.py) and implement:
  search()    → list[Dataset]
  download()  → AsyncIterator[Progress]
  build_dest()→ Path  (auto-organised local path)
"""

from .base import (
    DataSourceConnector,
    Dataset,
    DownloadStatus,
    Progress,
    SearchQuery,
)
from .parallel import BatchProgress, parallel_download

__all__ = [
    "DataSourceConnector",
    "Dataset",
    "DownloadStatus",
    "Progress",
    "SearchQuery",
    "BatchProgress",
    "parallel_download",
]
