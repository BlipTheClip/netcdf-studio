import { useDownloaderStore } from "@/store/downloaderStore";
import { Spinner } from "@/components/Spinner";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Button } from "@/components/Button";
import type { DatasetItem } from "@/api/types";

function formatSize(mb: number | null): string {
  if (mb === null) return "—";
  if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`;
  return `${mb.toFixed(0)} MB`;
}

export function SearchResults() {
  const {
    searchResults,
    searchTotal,
    isSearching,
    searchError,
    selectedDatasets,
    toggleDataset,
    selectAllDatasets,
    clearDatasetSelection,
  } = useDownloaderStore();

  if (isSearching) {
    return (
      <div className="flex items-center justify-center h-48">
        <Spinner label="Searching…" />
      </div>
    );
  }

  if (searchError) {
    return <ErrorBanner message={searchError} />;
  }

  if (searchResults.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-slate-500 text-sm gap-2">
        <span className="text-2xl select-none">🔍</span>
        <p>Use the form to search for datasets.</p>
      </div>
    );
  }

  const selectedCount = Object.values(selectedDatasets).filter(Boolean).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-400">
          {searchTotal} result{searchTotal !== 1 ? "s" : ""}
          {selectedCount > 0 && (
            <span className="text-blue-400 ml-2">· {selectedCount} selected</span>
          )}
        </span>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={selectAllDatasets}>
            All
          </Button>
          <Button variant="ghost" size="sm" onClick={clearDatasetSelection}>
            None
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        {searchResults.map((ds) => (
          <DatasetCard
            key={ds.id}
            dataset={ds}
            selected={!!selectedDatasets[ds.id]}
            onToggle={() => toggleDataset(ds.id)}
          />
        ))}
      </div>
    </div>
  );
}

function DatasetCard({
  dataset,
  selected,
  onToggle,
}: {
  dataset: DatasetItem;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      onClick={onToggle}
      className={[
        "p-3 rounded-lg border cursor-pointer transition-colors select-none",
        selected
          ? "border-blue-500 bg-blue-900/20"
          : "border-slate-700 bg-slate-800 hover:border-slate-600",
      ].join(" ")}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          onClick={(e) => e.stopPropagation()}
          className="mt-0.5 accent-blue-500 shrink-0"
        />
        <div className="flex-1 min-w-0">
          <p
            className="text-sm font-medium text-slate-200 truncate"
            title={dataset.title}
          >
            {dataset.title}
          </p>
          {dataset.description && (
            <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">
              {dataset.description}
            </p>
          )}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {dataset.variables.map((v) => (
              <span
                key={v}
                className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 font-mono"
              >
                {v}
              </span>
            ))}
            {dataset.frequency && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-900/50 text-indigo-300">
                {dataset.frequency}
              </span>
            )}
            <span className="text-xs px-1.5 py-0.5 rounded bg-slate-700 text-slate-400 ml-auto">
              {formatSize(dataset.size_mb)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
