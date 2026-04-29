import { useState } from "react";
import { imagery, ApiError } from "@/api/client";
import { useImageryStore } from "@/store/imageryStore";
import { useFileMetadata } from "@/hooks/useFileMetadata";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { ImagePreview } from "./ImagePreview";

const COLORMAPS = [
  { value: "RdBu_r",   label: "RdBu_r (diverging)" },
  { value: "coolwarm", label: "coolwarm (diverging)" },
  { value: "BrBG",     label: "BrBG (diverging)" },
  { value: "viridis",  label: "viridis (sequential)" },
  { value: "plasma",   label: "plasma (sequential)" },
  { value: "Blues",    label: "Blues (sequential)" },
  { value: "Reds",     label: "Reds (sequential)" },
];

const SECTION = "text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 mt-4 first:mt-0";

export function HovmollerForm() {
  const {
    hovPreviewPath, hovLoading, hovError,
    setHovPreviewPath, setHovLoading, setHovError,
  } = useImageryStore();

  const file = useFileMetadata();

  const [variable,   setVariable]   = useState("");
  const [mode,       setMode]       = useState<"lat" | "lon">("lat");
  const [plevLevel,  setPlevLevel]  = useState("");
  const [latMin,     setLatMin]     = useState("-90");
  const [latMax,     setLatMax]     = useState("90");
  const [lonMin,     setLonMin]     = useState("-180");
  const [lonMax,     setLonMax]     = useState("180");
  const [cmap,       setCmap]       = useState("RdBu_r");
  const [vmin,       setVmin]       = useState("");
  const [vmax,       setVmax]       = useState("");
  const [title,      setTitle]      = useState("");
  const [dpi,        setDpi]        = useState("150");
  const [fW,         setFW]         = useState("10");
  const [fH,         setFH]         = useState("7");
  const [colorbar,   setColorbar]   = useState(true);
  const [nTicks,     setNTicks]     = useState("12");
  const [outputPath, setOutputPath] = useState("");

  const varOptions = file.variables.map((v) => ({ value: v.name, label: `${v.name} — ${v.long_name}` }));
  const plevOptions = [
    { value: "", label: "— none (first level) —" },
    ...file.plevLevels.map((p) => ({
      value: String(p),
      label: `${p} ${file.meta?.coordinates.plev_units ?? "Pa"}`,
    })),
  ];

  const pickOutput = async () => {
    const p = await window.electronAPI?.saveFile() ?? window.prompt("Output path (.png):");
    if (p) setOutputPath(p.endsWith(".png") ? p : `${p}.png`);
  };

  const handleRender = async () => {
    if (!file.path || !variable || !outputPath) return;
    setHovLoading(true);
    setHovError(null);
    setHovPreviewPath(null);
    try {
      const result = await imagery.renderHovmoller({
        path:        file.path,
        variable,
        output_path: outputPath,
        mode,
        plev_level:  plevLevel ? parseFloat(plevLevel) : null,
        lat_min:     parseFloat(latMin) || -90,
        lat_max:     parseFloat(latMax) || 90,
        lon_min:     parseFloat(lonMin) || -180,
        lon_max:     parseFloat(lonMax) || 180,
        cmap,
        vmin:        vmin !== "" ? parseFloat(vmin) : null,
        vmax:        vmax !== "" ? parseFloat(vmax) : null,
        title,
        dpi:         parseInt(dpi) || 150,
        figsize:     [parseFloat(fW) || 10, parseFloat(fH) || 7],
        add_colorbar: colorbar,
        n_time_ticks: parseInt(nTicks) || 12,
      });
      setHovPreviewPath(result.output_path);
    } catch (e) {
      setHovError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setHovLoading(false);
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      <aside className="w-80 shrink-0 border-r border-slate-800 overflow-y-auto p-4">

        <p className={SECTION}>File</p>
        <div className="flex gap-2">
          <input readOnly value={file.path} placeholder="No file selected"
            className="flex-1 min-w-0 rounded-md bg-slate-800 border border-slate-600 px-3 py-2 text-sm text-slate-300 placeholder:text-slate-600" />
          <Button size="sm" variant="secondary" onClick={file.browse} loading={file.loading}>
            Browse
          </Button>
        </div>
        {file.error && <p className="text-xs text-red-400 mt-1">{file.error}</p>}

        <p className={SECTION}>Variable & Mode</p>
        {varOptions.length > 0 ? (
          <Select options={varOptions} value={variable}
            onChange={(e) => setVariable(e.target.value)} label="Variable" />
        ) : (
          <Input label="Variable" value={variable}
            onChange={(e) => setVariable(e.target.value)} placeholder="e.g. tas" />
        )}

        <div className="mt-2 grid grid-cols-2 gap-2">
          <Select label="Mode" value={mode}
            options={[
              { value: "lat", label: "Time × Latitude" },
              { value: "lon", label: "Time × Longitude" },
            ]}
            onChange={(e) => setMode(e.target.value as "lat" | "lon")} />

          {plevOptions.length > 1 ? (
            <Select label="Plev level" options={plevOptions} value={plevLevel}
              onChange={(e) => setPlevLevel(e.target.value)} />
          ) : (
            <Input label="Plev level" type="number" value={plevLevel}
              onChange={(e) => setPlevLevel(e.target.value)} placeholder="e.g. 85000" />
          )}
        </div>

        <p className={SECTION}>Spatial Domain</p>
        <div className="grid grid-cols-2 gap-2">
          <Input label="Lat min" type="number" value={latMin}
            onChange={(e) => setLatMin(e.target.value)} />
          <Input label="Lat max" type="number" value={latMax}
            onChange={(e) => setLatMax(e.target.value)} />
          <Input label="Lon min" type="number" value={lonMin}
            onChange={(e) => setLonMin(e.target.value)} />
          <Input label="Lon max" type="number" value={lonMax}
            onChange={(e) => setLonMax(e.target.value)} />
        </div>

        <p className={SECTION}>Colors</p>
        <Select label="Colormap" options={COLORMAPS} value={cmap}
          onChange={(e) => setCmap(e.target.value)} />
        <div className="grid grid-cols-2 gap-2 mt-2">
          <Input label="vmin" type="number" value={vmin}
            onChange={(e) => setVmin(e.target.value)} placeholder="auto" />
          <Input label="vmax" type="number" value={vmax}
            onChange={(e) => setVmax(e.target.value)} placeholder="auto" />
        </div>

        <p className={SECTION}>Output</p>
        <div className="grid grid-cols-2 gap-2">
          <Input label="DPI" type="number" value={dpi}
            onChange={(e) => setDpi(e.target.value)} />
          <Input label="Time ticks" type="number" min={4} max={50} value={nTicks}
            onChange={(e) => setNTicks(e.target.value)} />
          <Input label="Width (in)" type="number" value={fW}
            onChange={(e) => setFW(e.target.value)} />
          <Input label="Height (in)" type="number" value={fH}
            onChange={(e) => setFH(e.target.value)} />
          <Input label="Title" value={title} className="col-span-2"
            onChange={(e) => setTitle(e.target.value)} placeholder="auto" />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer mt-2">
          <input type="checkbox" checked={colorbar}
            onChange={(e) => setColorbar(e.target.checked)} className="accent-blue-500" />
          Add colorbar
        </label>

        <div className="mt-3 flex gap-2">
          <input readOnly value={outputPath} placeholder="output.png"
            className="flex-1 min-w-0 rounded-md bg-slate-800 border border-slate-600 px-3 py-2 text-sm text-slate-300 placeholder:text-slate-600" />
          <Button size="sm" variant="secondary" onClick={pickOutput}>Save as</Button>
        </div>

        <div className="mt-4">
          <Button className="w-full" onClick={handleRender}
            disabled={!file.path || !variable || !outputPath} loading={hovLoading}>
            Render Hovmöller
          </Button>
        </div>
      </aside>

      <ImagePreview path={hovPreviewPath} loading={hovLoading} error={hovError}
        label="Configure the Hovmöller settings and click Render." />
    </div>
  );
}
