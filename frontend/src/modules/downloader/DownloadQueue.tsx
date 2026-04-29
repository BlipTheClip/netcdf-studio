import { useDownloaderStore } from "@/store/downloaderStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

interface Props {
  onStartDownload: () => void;
}

export function DownloadQueue({ onStartDownload }: Props) {
  const {
    selectedDatasets,
    searchResults,
    destDir,
    setDestDir,
    maxConcurrent,
    setMaxConcurrent,
    clearDatasetSelection,
    isDownloading,
  } = useDownloaderStore();

  const selectedItems = searchResults.filter((d) => selectedDatasets[d.id]);
  if (selectedItems.length === 0) return null;

  const handleBrowse = async () => {
    if (window.electronAPI) {
      const path = await window.electronAPI.openFile();
      if (path) setDestDir(path);
    } else {
      const path = window.prompt("Destination directory:");
      if (path) setDestDir(path);
    }
  };

  return (
    <div className="pt-3 border-t border-slate-700 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
          Queue{" "}
          <span className="text-blue-400 normal-case font-normal">
            ({selectedItems.length} file{selectedItems.length !== 1 ? "s" : ""})
          </span>
        </h3>
        <Button variant="ghost" size="sm" onClick={clearDatasetSelection}>
          Clear
        </Button>
      </div>

      {/* Destination */}
      <div className="space-y-1">
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <Input
              label="Destination"
              value={destDir}
              onChange={(e) => setDestDir(e.target.value)}
              placeholder="/path/to/download"
            />
          </div>
          <Button variant="secondary" size="sm" onClick={handleBrowse}>
            …
          </Button>
        </div>
      </div>

      {/* Concurrency */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-slate-400 shrink-0">Concurrency</span>
        <input
          type="range"
          min={1}
          max={8}
          step={1}
          value={maxConcurrent}
          onChange={(e) => setMaxConcurrent(parseInt(e.target.value))}
          className="flex-1 accent-blue-500"
        />
        <span className="text-xs text-slate-300 w-4 text-right font-mono">
          {maxConcurrent}
        </span>
      </div>

      <Button
        variant="primary"
        size="sm"
        className="w-full"
        onClick={onStartDownload}
        disabled={!destDir || isDownloading}
        loading={isDownloading}
      >
        Start Download
      </Button>
    </div>
  );
}
