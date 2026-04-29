import { useState } from "react";
import { imagery, ApiError } from "@/api/client";
import { useImageryStore, type TaylorModelEntry } from "@/store/imageryStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { ImagePreview } from "./ImagePreview";

const SECTION = "text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 mt-4 first:mt-0";

const MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "h", "p"].map((m) => ({
  value: m, label: m,
}));

// ── Single model row ──────────────────────────────────────────────────────────

function ModelRow({ model, onUpdate, onRemove }: {
  model: TaylorModelEntry;
  onUpdate: (patch: Partial<TaylorModelEntry>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-2 items-end">
      <Input
        label="Name"
        value={model.name}
        onChange={(e) => onUpdate({ name: e.target.value })}
        placeholder="CESM2"
      />
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">σ ratio</label>
        <input
          type="number" step="0.01" min={0} max={3}
          value={model.std_ratio}
          onChange={(e) => onUpdate({ std_ratio: parseFloat(e.target.value) || 0 })}
          className="w-20 rounded-md bg-slate-800 border border-slate-600 px-2 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">Corr</label>
        <input
          type="number" step="0.01" min={-1} max={1}
          value={model.correlation}
          onChange={(e) => onUpdate({ correlation: parseFloat(e.target.value) || 0 })}
          className="w-20 rounded-md bg-slate-800 border border-slate-600 px-2 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">Color</label>
        <input
          type="color"
          value={model.color || "#1f77b4"}
          onChange={(e) => onUpdate({ color: e.target.value })}
          className="w-10 h-9 rounded cursor-pointer bg-transparent border-0 p-0"
        />
      </div>
      <div className="flex flex-col gap-1 w-14">
        <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">Marker</label>
        <select
          value={model.marker}
          onChange={(e) => onUpdate({ marker: e.target.value })}
          className="rounded-md bg-slate-800 border border-slate-600 px-2 py-2 text-sm text-slate-100 focus:outline-none"
        >
          <option value="">auto</option>
          {MARKERS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </div>
      <button
        onClick={onRemove}
        className="self-end h-9 px-2 rounded-md text-slate-500 hover:text-red-400 hover:bg-slate-700 transition-colors text-lg"
        title="Remove model"
      >
        ×
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function TaylorForm() {
  const {
    taylorModels,
    taylorPreviewPath, taylorLoading, taylorError,
    addTaylorModel, removeTaylorModel, updateTaylorModel,
    setTaylorPreviewPath, setTaylorLoading, setTaylorError,
  } = useImageryStore();

  const [outputPath,   setOutputPath]   = useState("");
  const [title,        setTitle]        = useState("Taylor Diagram");
  const [maxStdRatio,  setMaxStdRatio]  = useState("1.5");
  const [dpi,          setDpi]          = useState("150");
  const [fW,           setFW]           = useState("8");
  const [fH,           setFH]           = useState("7");

  const pickOutput = async () => {
    const p = await window.electronAPI?.saveFile() ?? window.prompt("Output path (.png):");
    if (p) setOutputPath(p.endsWith(".png") ? p : `${p}.png`);
  };

  const handleRender = async () => {
    if (taylorModels.length === 0 || !outputPath) return;
    setTaylorLoading(true);
    setTaylorError(null);
    setTaylorPreviewPath(null);
    try {
      const result = await imagery.renderTaylor({
        output_path:   outputPath,
        title,
        max_std_ratio: parseFloat(maxStdRatio) || 1.5,
        dpi:           parseInt(dpi) || 150,
        figsize:       [parseFloat(fW) || 8, parseFloat(fH) || 7],
        models:        taylorModels.map((m) => ({
          name:        m.name,
          std_ratio:   m.std_ratio,
          correlation: m.correlation,
          color:       m.color || undefined,
          marker:      m.marker || undefined,
        })),
      });
      setTaylorPreviewPath(result.output_path);
    } catch (e) {
      setTaylorError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setTaylorLoading(false);
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Left panel ─────────────────────────────────────────────────── */}
      <aside className="w-[30rem] shrink-0 border-r border-slate-800 overflow-y-auto p-4">

        {/* Models table */}
        <div className="flex items-center justify-between mb-3">
          <p className={`${SECTION} !mt-0 !mb-0`}>Models</p>
          <Button size="sm" variant="secondary" onClick={() => addTaylorModel()}>
            + Add Model
          </Button>
        </div>

        {taylorModels.length === 0 ? (
          <p className="text-sm text-slate-500 mb-4">
            Add at least one model to compare against the reference.
          </p>
        ) : (
          <div className="space-y-3 mb-4">
            {taylorModels.map((m) => (
              <ModelRow
                key={m.id}
                model={m}
                onUpdate={(patch) => updateTaylorModel(m.id, patch)}
                onRemove={() => removeTaylorModel(m.id)}
              />
            ))}
          </div>
        )}

        <div className="border-t border-slate-700 pt-3">
          <p className="text-xs text-slate-500 mb-3">
            σ ratio = std_model / std_reference (reference at 1.0). Correlation with reference (−1 to 1).
          </p>
        </div>

        {/* Diagram settings */}
        <p className={SECTION}>Diagram Settings</p>
        <div className="grid grid-cols-2 gap-2">
          <Input label="Max σ ratio" type="number" step="0.1" min={0.5}
            value={maxStdRatio} onChange={(e) => setMaxStdRatio(e.target.value)} />
          <Input label="DPI" type="number" value={dpi}
            onChange={(e) => setDpi(e.target.value)} />
          <Input label="Width (in)" type="number" value={fW}
            onChange={(e) => setFW(e.target.value)} />
          <Input label="Height (in)" type="number" value={fH}
            onChange={(e) => setFH(e.target.value)} />
          <Input label="Title" value={title} className="col-span-2"
            onChange={(e) => setTitle(e.target.value)} />
        </div>

        <div className="mt-4 flex gap-2">
          <input readOnly value={outputPath} placeholder="output.png"
            className="flex-1 min-w-0 rounded-md bg-slate-800 border border-slate-600 px-3 py-2 text-sm text-slate-300 placeholder:text-slate-600" />
          <Button size="sm" variant="secondary" onClick={pickOutput}>Save as</Button>
        </div>

        <div className="mt-4">
          <Button className="w-full" onClick={handleRender}
            disabled={taylorModels.length === 0 || !outputPath} loading={taylorLoading}>
            Render Taylor Diagram
          </Button>
        </div>
      </aside>

      <ImagePreview path={taylorPreviewPath} loading={taylorLoading} error={taylorError}
        label="Add models and click Render to generate the Taylor diagram." />
    </div>
  );
}
