import { useRef } from "react";
import { createDownloadWs } from "@/api/client";
import { useDownloaderStore } from "@/store/downloaderStore";
import type { DownloadWsRequest, WsHandle } from "@/api/types";
import { SourceSelector } from "./SourceSelector";
import { SearchForm } from "./SearchForm";
import { SearchResults } from "./SearchResults";
import { DownloadQueue } from "./DownloadQueue";
import { DownloadProgress } from "./DownloadProgress";

export function DownloaderPage() {
  const wsRef = useRef<WsHandle | null>(null);

  const {
    selectedSource,
    selectedDatasets,
    searchResults,
    destDir,
    maxConcurrent,
    isDownloading,
    downloadResult,
    setIsDownloading,
    setDownloadError,
    updateFileProgress,
    setDownloadResult,
  } = useDownloaderStore();

  const showProgress = isDownloading || downloadResult !== null;

  const handleStartDownload = () => {
    const selectedItems = searchResults.filter((d) => selectedDatasets[d.id]);
    if (!selectedSource || selectedItems.length === 0 || !destDir) return;

    const request: DownloadWsRequest = {
      source: selectedSource,
      datasets: selectedItems,
      dest_dir: destDir,
      max_concurrent: maxConcurrent,
    };

    setIsDownloading(true);
    setDownloadError(null);

    wsRef.current = createDownloadWs(
      (msg) => {
        switch (msg.type) {
          case "progress":
            updateFileProgress(msg.payload);
            break;
          case "result":
            setDownloadResult(msg.payload);
            setIsDownloading(false);
            wsRef.current = null;
            break;
          case "error":
            setDownloadError(msg.payload.error);
            setIsDownloading(false);
            wsRef.current = null;
            break;
        }
      },
      // onOpen: send the batch request as soon as the socket is ready
      () => {
        wsRef.current?.send(request);
      },
      // onClose: guard against unexpected disconnects mid-batch
      () => {
        const { isDownloading: stillDownloading } = useDownloaderStore.getState();
        if (stillDownloading) {
          setDownloadError("WebSocket connection closed unexpectedly.");
          setIsDownloading(false);
        }
      },
    );
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <SourceSelector />

      {selectedSource ? (
        <div className="flex flex-1 min-h-0">
          {/* Sidebar: search form + download queue */}
          <aside className="w-72 shrink-0 border-r border-slate-800 overflow-y-auto p-4 space-y-4">
            <SearchForm />
            <DownloadQueue onStartDownload={handleStartDownload} />
          </aside>

          {/* Main area: search results or download progress */}
          <div className="flex-1 overflow-y-auto p-4">
            {showProgress ? <DownloadProgress /> : <SearchResults />}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
          Select a data source above to begin.
        </div>
      )}
    </div>
  );
}
