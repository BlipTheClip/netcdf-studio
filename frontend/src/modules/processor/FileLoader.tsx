import { useState } from "react";
import { processor, ApiError } from "@/api/client";
import { useProcessorStore } from "@/store/processorStore";
import { Button } from "@/components/Button";
import { ErrorBanner } from "@/components/ErrorBanner";

export function FileLoader() {
  const { filePath, metadata, setFilePath, setMetadata, setSelectedVariable, reset } =
    useProcessorStore();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openFile = async () => {
    let path: string | null = null;

    if (window.electronAPI) {
      path = await window.electronAPI.openFile();
    } else {
      // Browser dev fallback
      path = window.prompt("Enter the full path to a .nc file:");
    }

    if (!path) return;

    setLoading(true);
    setError(null);

    try {
      const meta = await processor.getMetadata(path);
      setFilePath(path);
      setMetadata(meta);
      // Pre-select the first data variable
      const vars = Object.keys(meta.variables);
      setSelectedVariable(vars[0] ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl bg-slate-800 border border-slate-700 p-3 shrink-0">
      <div className="flex items-center gap-3">
        <Button onClick={openFile} loading={loading}>
          Open NetCDF file
        </Button>

        {filePath && (
          <>
            <span
              className="flex-1 text-sm text-slate-400 truncate font-mono"
              title={filePath}
            >
              {filePath}
            </span>

            {metadata && (
              <span className="text-xs text-slate-500 shrink-0 tabular-nums">
                {metadata.file_size_mb.toFixed(1)} MB
                {metadata.time_frequency && ` · ${metadata.time_frequency}`}
              </span>
            )}

            <Button variant="ghost" size="sm" onClick={reset}>
              Close
            </Button>
          </>
        )}
      </div>

      {error && (
        <div className="mt-2">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}
    </div>
  );
}
