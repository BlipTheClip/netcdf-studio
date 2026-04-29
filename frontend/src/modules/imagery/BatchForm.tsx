import { useRef } from "react";
import { createBatchImageryWs } from "@/api/client";
import { useImageryStore, type BatchJobEntry } from "@/store/imageryStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { BatchProgress } from "./BatchProgress";
import type { WsHandle, BatchImageryJob } from "@/api/types";

// ── Projection options ────────────────────────────────────────────────────────

const PROJECTIONS = [
  { value: "PlateCarree",      label: "Plate Carrée" },
  { value: "Robinson",         label: "Robinson" },
  { value: "Mollweide",        label: "Mollweide" },
  { value: "NorthPolarStereo", label: "N. Polar Stereo" },
  { value: "SouthPolarStereo", label: "S. Polar Stereo" },
  { value: "LambertConformal", label: "Lambert Conformal" },
  { value: "Mercator",         label: "Mercator" },
];

const COLORMAPS = [
  "RdBu_r", "coolwarm", "BrBG", "viridis", "plasma", "Blues", "Reds", "jet",
].map((c) => ({ value: c, label: c }));

// ── Convert store entry → API request body ────────────────────────────────────

function jobToApi(j: BatchJobEntry): BatchImageryJob {
  return {
    path:             j.path,
    variable:         j.variable,
    output_path:      j.output_path,
    time_index:       j.time_index,
    plev_level:       j.plev_level,
    projection:       j.projection as BatchImageryJob["projection"],
    central_longitude:j.central_longitude,
    cmap:             j.cmap,
    title:            j.title || undefined,
    dpi:              j.dpi,
    add_coastlines:   j.add_coastlines,
    add_gridlines:    j.add_gridlines,
    u_variable:       j.u_variable || null,
    v_variable:       j.v_variable || null,
    quiver_stride:    j.quiver_stride,
    quiver_color:     j.quiver_color,
  };
}

// ── Single job row ────────────────────────────────────────────────────────────

function JobRow({ job, index, onUpdate, onRemove }: {
  job: BatchJobEntry;
  index: number;
  onUpdate: (patch: Partial<BatchJobEntry>) => void;
  onRemove: () => void;
}) {
  const browseFile = async () => {
    const p = await window.electronAPI?.openFile() ?? window.prompt("NetCDF path:");
    if (p) onUpdate({ path: p });
  };

  const browseOutput = async () => {
    const p = await window.electronAPI?.saveFile() ?? window.prompt("Output path (.png):");
    if (p) onUpdate({ output_path: p.endsWith(".png") ? p : `${p}.png` });
  };

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 space-y-2">
      {/* Row header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400">Job #{index + 1}</span>
        <button onClick={onRemove}
          className="text-slate-500 hover:text-red-400 transition-colors text-lg leading-none px-1">
          ×
        </button>
      </div>

      {/* File + variable */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
        <Input label="File path" value={job.path}
          onChange={(e) => onUpdate({ path: e.target.value })} placeholder="/data/tas.nc" />
        <Button size="sm" variant="secondary" onClick={browseFile} className="mb-0.5">
          Browse
        </Button>
        <Input label="Variable" value={job.variable}
          onChange={(e) => onUpdate({ variable: e.target.value })} placeholder="tas" />
      </div>

      {/* Output + title */}
      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
        <Input label="Output path (.png)" value={job.output_path}
          onChange={(e) => onUpdate({ output_path: e.target.value })} placeholder="map_001.png" />
        <Button size="sm" variant="secondary" onClick={browseOutput} className="mb-0.5">
          Save as
        </Button>
        <Input label="Title (optional)" value={job.title}
          onChange={(e) => onUpdate({ title: e.target.value })} placeholder="auto" />
      </div>

      {/* Settings row */}
      <div className="grid grid-cols-3 gap-2">
        <Input label="Time index" type="number" min={0} value={job.time_index}
          onChange={(e) => onUpdate({ time_index: parseInt(e.target.value) || 0 })} />
        <Select label="Projection" options={PROJECTIONS} value={job.projection}
          onChange={(e) => onUpdate({ projection: e.target.value })} />
        <Select label="Colormap" options={COLORMAPS} value={job.cmap}
          onChange={(e) => onUpdate({ cmap: e.target.value })} />
      </div>

      {/* Checkboxes + DPI */}
      <div className="flex items-center gap-4 flex-wrap">
        <Input label="DPI" type="number" value={job.dpi} className="w-20"
          onChange={(e) => onUpdate({ dpi: parseInt(e.target.value) || 150 })} />
        {[
          ["Coastlines", "add_coastlines"],
          ["Gridlines",  "add_gridlines"],
        ].map(([label, key]) => (
          <label key={key} className="flex items-center gap-1.5 text-sm text-slate-300 cursor-pointer">
            <input type="checkbox" checked={job[key as keyof BatchJobEntry] as boolean}
              onChange={(e) => onUpdate({ [key]: e.target.checked })}
              className="accent-blue-500" />
            {label}
          </label>
        ))}
      </div>

      {/* Quiver (collapsed unless both are set) */}
      {(job.u_variable || job.v_variable) && (
        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-700">
          <Input label="U variable" value={job.u_variable}
            onChange={(e) => onUpdate({ u_variable: e.target.value })} placeholder="ua" />
          <Input label="V variable" value={job.v_variable}
            onChange={(e) => onUpdate({ v_variable: e.target.value })} placeholder="va" />
          <Input label="Stride" type="number" min={1} max={20} value={job.quiver_stride}
            onChange={(e) => onUpdate({ quiver_stride: parseInt(e.target.value) || 5 })} />
        </div>
      )}
      {!job.u_variable && !job.v_variable && (
        <button
          className="text-xs text-slate-500 hover:text-blue-400 transition-colors"
          onClick={() => onUpdate({ u_variable: "", v_variable: "" })}
        >
          + Add vector overlay (quiver)
        </button>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function BatchForm() {
  const wsRef = useRef<WsHandle | null>(null);

  const {
    batchJobs, maxRamGb, isBatching, batchResult,
    addBatchJob, removeBatchJob, updateBatchJob,
    setMaxRamGb, setIsBatching, updateBatchProgress,
    setBatchResult, setBatchError,
  } = useImageryStore();

  const showProgress = isBatching || batchResult !== null;

  if (showProgress) {
    return <BatchProgress />;
  }

  const handleStart = () => {
    const valid = batchJobs.filter((j) => j.path && j.variable && j.output_path);
    if (valid.length === 0) return;

    const request = { jobs: valid.map(jobToApi), max_ram_gb: maxRamGb };
    setIsBatching(true);
    setBatchError(null);
    setBatchResult(null);

    wsRef.current = createBatchImageryWs(
      (msg) => {
        switch (msg.type) {
          case "progress":
            updateBatchProgress(msg.payload);
            break;
          case "result":
            setBatchResult(msg.payload);
            setIsBatching(false);
            wsRef.current = null;
            break;
          case "error":
            setBatchError(msg.payload.error);
            setIsBatching(false);
            wsRef.current = null;
            break;
        }
      },
      () => { wsRef.current?.send(request); },
      () => {
        const { isBatching: still } = useImageryStore.getState();
        if (still) {
          setBatchError("WebSocket connection closed unexpectedly.");
          setIsBatching(false);
        }
      },
    );
  };

  const validCount = batchJobs.filter((j) => j.path && j.variable && j.output_path).length;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Controls header */}
      <div className="flex items-center gap-4 px-4 py-3 border-b border-slate-800 shrink-0 flex-wrap">
        <Button size="sm" variant="secondary" onClick={() => addBatchJob()}>
          + Add Job
        </Button>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 whitespace-nowrap">
            RAM limit: <span className="text-slate-200 font-mono">{maxRamGb} GB</span>
          </label>
          <input
            type="range" min={1} max={64} step={1} value={maxRamGb}
            onChange={(e) => setMaxRamGb(Number(e.target.value))}
            className="w-28 accent-blue-500"
          />
        </div>

        <div className="ml-auto flex items-center gap-3">
          {batchJobs.length > 0 && (
            <span className="text-xs text-slate-500">
              {validCount} / {batchJobs.length} jobs ready
            </span>
          )}
          <Button
            onClick={handleStart}
            disabled={validCount === 0}
            loading={isBatching}
          >
            Start Batch ({validCount} maps)
          </Button>
        </div>
      </div>

      {/* Job list */}
      <div className="flex-1 overflow-y-auto p-4">
        {batchJobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-500">
            <p className="text-sm">No jobs added yet.</p>
            <Button size="sm" variant="secondary" onClick={() => addBatchJob()}>
              + Add your first job
            </Button>
          </div>
        ) : (
          <div className="space-y-3 max-w-4xl">
            {batchJobs.map((job, i) => (
              <JobRow
                key={job.id}
                job={job}
                index={i}
                onUpdate={(patch) => updateBatchJob(job.id, patch)}
                onRemove={() => removeBatchJob(job.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
