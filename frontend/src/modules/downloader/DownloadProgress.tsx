import { useDownloaderStore } from "@/store/downloaderStore";
import { Button } from "@/components/Button";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import type { DownloadProgressPayload } from "@/api/types";

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

const STATUS_COLORS: Record<string, string> = {
  completed:   "bg-green-900/50 text-green-300",
  failed:      "bg-red-900/50 text-red-300",
  downloading: "bg-blue-900/50 text-blue-300",
  queued:      "bg-slate-700 text-slate-400",
};

const BAR_COLORS: Record<string, string> = {
  completed:   "bg-green-500",
  failed:      "bg-red-500",
  downloading: "bg-blue-500",
  queued:      "bg-slate-600",
};

export function DownloadProgress() {
  const {
    fileProgress,
    downloadResult,
    downloadError,
    isDownloading,
    resetDownload,
  } = useDownloaderStore();

  const files = Object.values(fileProgress);
  const total = files.length > 0 ? files[0].total_files : 0;
  const completedCount = files.filter((f) => f.status === "completed").length;
  const activeFile = files.find((f) => f.status === "downloading");

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isDownloading && <Spinner size="sm" />}
          <h2 className="text-sm font-semibold text-slate-200">
            {isDownloading
              ? `Downloading… (${completedCount}/${total})`
              : downloadResult
              ? "Download complete"
              : "Download progress"}
          </h2>
        </div>
        {!isDownloading && (
          <Button variant="ghost" size="sm" onClick={resetDownload}>
            ← Back
          </Button>
        )}
      </div>

      {downloadError && <ErrorBanner message={downloadError} />}

      {/* Summary card */}
      {downloadResult && (
        <div
          className={[
            "p-3 rounded-lg border text-sm",
            downloadResult.failed === 0
              ? "border-green-700 bg-green-900/20 text-green-300"
              : "border-yellow-700 bg-yellow-900/20 text-yellow-300",
          ].join(" ")}
        >
          <p className="font-medium">
            {downloadResult.completed} of{" "}
            {downloadResult.completed + downloadResult.failed} files downloaded
            {downloadResult.failed > 0 && (
              <span className="text-red-400 ml-1">
                · {downloadResult.failed} failed
              </span>
            )}
          </p>
          <p className="text-xs text-slate-400 mt-1 font-mono truncate">
            {downloadResult.dest_dir}
          </p>
        </div>
      )}

      {/* Active file speed */}
      {isDownloading && activeFile && activeFile.speed_mbps > 0 && (
        <p className="text-xs text-slate-400">
          {activeFile.speed_mbps.toFixed(1)} MB/s ·{" "}
          {activeFile.message}
        </p>
      )}

      {/* Per-file rows */}
      <div className="space-y-2">
        {files.map((f) => (
          <FileRow key={f.file} progress={f} />
        ))}
      </div>
    </div>
  );
}

function FileRow({ progress }: { progress: DownloadProgressPayload }) {
  const fileName =
    progress.file.split(/[\\/]/).pop() ?? progress.file;
  const statusColor = STATUS_COLORS[progress.status] ?? STATUS_COLORS.queued;
  const barColor = BAR_COLORS[progress.status] ?? BAR_COLORS.queued;

  return (
    <div className="p-3 rounded-lg border border-slate-700 bg-slate-800">
      <div className="flex items-center justify-between mb-1.5 gap-2">
        <span
          className="text-xs text-slate-300 font-mono truncate"
          title={progress.file}
        >
          {fileName}
        </span>
        <div className="flex items-center gap-2 shrink-0">
          {progress.status === "downloading" && progress.speed_mbps > 0 && (
            <span className="text-xs text-slate-500">
              {progress.speed_mbps.toFixed(1)} MB/s
            </span>
          )}
          <span
            className={`text-xs px-1.5 py-0.5 rounded font-medium ${statusColor}`}
          >
            {progress.status}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${progress.percent}%` }}
        />
      </div>

      <div className="flex items-center justify-between mt-1">
        <span className="text-xs text-slate-500">
          {progress.percent.toFixed(0)}%
        </span>
        {progress.total_bytes > 0 && (
          <span className="text-xs text-slate-500">
            {formatBytes(progress.downloaded_bytes)} /{" "}
            {formatBytes(progress.total_bytes)}
          </span>
        )}
      </div>

      {progress.status === "failed" && progress.error && (
        <p className="text-xs text-red-400 mt-1 truncate" title={progress.error}>
          {progress.error}
        </p>
      )}
    </div>
  );
}
