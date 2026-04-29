import { useImageryStore } from "@/store/imageryStore";
import { Button } from "@/components/Button";
import { Spinner } from "@/components/Spinner";
import type { BatchImageryProgressPayload } from "@/api/types";

const STATUS_COLOR: Record<BatchImageryProgressPayload["status"], string> = {
  rendering:  "text-blue-400",
  completed:  "text-green-400",
  failed:     "text-red-400",
};

const STATUS_BAR: Record<BatchImageryProgressPayload["status"], string> = {
  rendering:  "bg-blue-500",
  completed:  "bg-green-500",
  failed:     "bg-red-500",
};

function JobRow({ entry, total }: { entry: BatchImageryProgressPayload; total: number }) {
  const pct = entry.status === "completed" ? 100
    : entry.status === "failed"     ? 100
    : Math.round(((entry.current - 0.5) / total) * 100);

  return (
    <div className="rounded-lg border border-slate-700 p-3 space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm text-slate-100 font-mono truncate flex-1">{entry.file}</span>
        <span className={`text-xs font-semibold shrink-0 ${STATUS_COLOR[entry.status]}`}>
          {entry.status.toUpperCase()}
        </span>
      </div>

      <div className="w-full h-1.5 rounded-full bg-slate-700">
        <div
          className={`h-full rounded-full transition-all duration-300 ${STATUS_BAR[entry.status]}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <p className="text-xs text-slate-400">{entry.message}</p>
      {entry.error && <p className="text-xs text-red-400">{entry.error}</p>}
    </div>
  );
}

export function BatchProgress() {
  const {
    batchJobs, isBatching, batchProgress, batchResult, batchError, resetBatch,
  } = useImageryStore();

  const total       = batchJobs.length;
  const entries     = Object.values(batchProgress).sort((a, b) => a.current - b.current);
  const completedN  = entries.filter((e) => e.status === "completed").length;
  const failedN     = entries.filter((e) => e.status === "failed").length;
  const renderingN  = entries.filter((e) => e.status === "rendering").length;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 shrink-0 flex items-center gap-4">
        {isBatching && <Spinner size="sm" />}
        <div className="flex-1">
          <p className="text-sm font-semibold text-slate-100">
            {isBatching ? `Rendering batch… ${completedN + failedN} / ${total}` : "Batch complete"}
          </p>
          <p className="text-xs text-slate-400">
            {completedN} completed · {failedN} failed
            {renderingN > 0 && ` · ${renderingN} rendering`}
          </p>
        </div>
        {!isBatching && (
          <Button size="sm" variant="secondary" onClick={resetBatch}>
            ← Back to jobs
          </Button>
        )}
      </div>

      {/* Overall progress bar */}
      <div className="px-4 pt-2 pb-1 shrink-0">
        <div className="w-full h-2 rounded-full bg-slate-700">
          <div
            className="h-full rounded-full bg-blue-500 transition-all duration-300"
            style={{ width: `${Math.round(((completedN + failedN) / Math.max(total, 1)) * 100)}%` }}
          />
        </div>
      </div>

      {/* Job rows */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {entries.map((e) => (
          <JobRow key={e.current} entry={e} total={total} />
        ))}
        {isBatching && entries.length === 0 && (
          <div className="flex justify-center pt-8">
            <Spinner size="md" label="Waiting for first job…" />
          </div>
        )}
      </div>

      {/* Final summary */}
      {batchResult && !isBatching && (
        <div className={[
          "mx-4 mb-4 rounded-lg border p-4",
          batchResult.failed === 0
            ? "border-green-700 bg-green-900/20"
            : "border-yellow-700 bg-yellow-900/20",
        ].join(" ")}>
          <p className={`text-sm font-semibold ${batchResult.failed === 0 ? "text-green-400" : "text-yellow-300"}`}>
            {batchResult.failed === 0
              ? `All ${batchResult.completed} maps saved successfully.`
              : `${batchResult.completed} maps saved, ${batchResult.failed} failed.`}
          </p>
          {batchResult.files.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {batchResult.files.map((f) => (
                <li key={f} className="text-xs text-slate-400 font-mono truncate">{f}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {batchError && !isBatching && (
        <div className="mx-4 mb-4 rounded-lg border border-red-700 bg-red-900/20 p-4">
          <p className="text-sm text-red-400">{batchError}</p>
        </div>
      )}
    </div>
  );
}
