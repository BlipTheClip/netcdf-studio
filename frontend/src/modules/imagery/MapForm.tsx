import { useState } from "react";
import { imagery, ApiError } from "@/api/client";
import { useImageryStore } from "@/store/imageryStore";
import { useFileMetadata } from "@/hooks/useFileMetadata";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Spinner } from "@/components/Spinner";
import { ImagePreview } from "./ImagePreview";
import type { ProjectionName } from "@/api/types";

// ── Constant option lists ─────────────────────────────────────────────────────

const PROJECTIONS: { value: string; label: string }[] = [
  { value: "PlateCarree",      label: "Plate Carrée (lon/lat)" },
  { value: "Robinson",         label: "Robinson (global)" },
  { value: "Mollweide",        label: "Mollweide (equal-area)" },
  { value: "NorthPolarStereo", label: "North Polar Stereographic" },
  { value: "SouthPolarStereo", label: "South Polar Stereographic" },
  { value: "LambertConformal", label: "Lambert Conformal" },
  { value: "Mercator",         label: "Mercator" },
];

const COLORMAPS: { value: string; label: string }[] = [
  { value: "RdBu_r",    label: "RdBu_r (diverging, reversed)" },
  { value: "RdYlBu_r",  label: "RdYlBu_r (diverging)" },
  { value: "coolwarm",  label: "coolwarm (diverging)" },
  { value: "BrBG",      label: "BrBG (diverging)" },
  { value: "PiYG",      label: "PiYG (diverging)" },
  { value: "viridis",   label: "viridis (sequential)" },
  { value: "plasma",    label: "plasma (sequential)" },
  { value: "magma",     label: "magma (sequential)" },
  { value: "inferno",   label: "inferno (sequential)" },
  { value: "Blues",     label: "Blues (sequential)" },
  { value: "Reds",      label: "Reds (sequential)" },
  { value: "Greens",    label: "Greens (sequential)" },
  { value: "hot_r",     label: "hot_r (heatmap)" },
  { value: "jet",       label: "jet (legacy)" },
];

const SECTION = "text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 mt-4 first:mt-0";

// ── Component ─────────────────────────────────────────────────────────────────

export function MapForm() {
  const {
    mapPreviewPath, mapLoading, mapError,
    setMapPreviewPath, setMapLoading, setMapError,
  } = useImageryStore();

  const file = useFileMetadata();

  // Form fields
  const [variable,    setVariable]    = useState("");
  const [timeIndex,   setTimeIndex]   = useState("0");
  const [plevLevel,   setPlevLevel]   = useState("");
  const [projection,  setProjection]  = useState<ProjectionName>("PlateCarree");
  const [centralLon,  setCentralLon]  = useState("0");
  const [cmap,        setCmap]        = useState("RdBu_r");
  const [vmin,        setVmin]        = useState("");
  const [vmax,        setVmax]        = useState("");
  const [latMin,      setLatMin]      = useState("");
  const [latMax,      setLatMax]      = useState("");
  const [lonMin,      setLonMin]      = useState("");
  const [lonMax,      setLonMax]      = useState("");
  const [dpi,         setDpi]         = useState("150");
  const [fW,          setFW]          = useState("12");
  const [fH,          setFH]          = useState("6");
  const [coastlines,  setCoastlines]  = useState(true);
  const [borders,     setBorders]     = useState(true);
  const [gridlines,   setGridlines]   = useState(true);
  const [colorbar,    setColorbar]    = useState(true);
  const [title,       setTitle]       = useState("");
  const [outputPath,  setOutputPath]  = useState("");

  // Quiver
  const [quiverOn,     setQuiverOn]     = useState(false);
  const [uVar,         setUVar]         = useState("");
  const [vVar,         setVVar]         = useState("");
  const [quiverStride, setQuiverStride] = useState("5");
  const [quiverColor,  setQuiverColor]  = useState("black");

  const varOptions = file.variables.map((v) => ({ value: v.name, label: `${v.name} — ${v.long_name}` }));
  const plevOptions = [
    { value: "", label: "— none (first level) —" },
    ...file.plevLevels.map((p) => ({ value: String(p), label: `${p} ${file.meta?.coordinates.plev_units ?? "Pa"}` })),
  ];

  const pickOutput = async () => {
    const p = await window.electronAPI?.saveFile() ?? window.prompt("Output path (.png):");
    if (p) setOutputPath(p.endsWith(".png") ? p : `${p}.png`);
  };

  const handleRender = async () => {
    if (!file.path || !variable || !outputPath) return;
    setMapLoading(true);
    setMapError(null);
    setMapPreviewPath(null);
    try {
      const result = await imagery.renderMap({
        path:              file.path,
        variable,
        output_path:       outputPath,
        time_index:        parseInt(timeIndex) || 0,
        plev_level:        plevLevel ? parseFloat(plevLevel) : null,
        projection:        projection as ProjectionName,
        central_longitude: parseFloat(centralLon) || 0,
        cmap,
        vmin: vmin !== "" ? parseFloat(vmin) : null,
        vmax: vmax !== "" ? parseFloat(vmax) : null,
        title,
        dpi:            parseInt(dpi) || 150,
        figsize:        [parseFloat(fW) || 12, parseFloat(fH) || 6],
        add_coastlines: coastlines,
        add_borders:    borders,
        add_gridlines:  gridlines,
        add_colorbar:   colorbar,
        lat_min: latMin !== "" ? parseFloat(latMin) : null,
        lat_max: latMax !== "" ? parseFloat(latMax) : null,
        lon_min: lonMin !== "" ? parseFloat(lonMin) : null,
        lon_max: lonMax !== "" ? parseFloat(lonMax) : null,
        u_variable:    quiverOn && uVar ? uVar : null,
        v_variable:    quiverOn && vVar ? vVar : null,
        quiver_stride: parseInt(quiverStride) || 5,
        quiver_color:  quiverColor,
      });
      setMapPreviewPath(result.output_path);
    } catch (e) {
      setMapError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setMapLoading(false);
    }
  };

  const canRender = !!file.path && !!variable && !!outputPath && !mapLoading;

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="w-80 shrink-0 border-r border-slate-800 overflow-y-auto p-4">

        {/* File */}
        <p className={SECTION}>File</p>
        <div className="flex gap-2">
          <input
            readOnly
            value={file.path}
            placeholder="No file selected"
            className="flex-1 min-w-0 rounded-md bg-slate-800 border border-slate-600 px-3 py-2 text-sm text-slate-300 placeholder:text-slate-600"
          />
          <Button size="sm" variant="secondary" onClick={file.browse} loading={file.loading}>
            Browse
          </Button>
        </div>
        {file.error && <p className="text-xs text-red-400 mt-1">{file.error}</p>}

        {/* Variable & Slice */}
        <p className={SECTION}>Variable & Time</p>
        {varOptions.length > 0 ? (
          <Select label="Variable" options={varOptions} value={variable}
            onChange={(e) => setVariable(e.target.value)} />
        ) : (
          <Input label="Variable" value={variable} onChange={(e) => setVariable(e.target.value)}
            placeholder="e.g. tas, pr, ua" />
        )}

        <div className="grid grid-cols-2 gap-2 mt-2">
          <Input label="Time index" type="number" min={0} value={timeIndex}
            onChange={(e) => setTimeIndex(e.target.value)} />
          {plevOptions.length > 1 ? (
            <Select label="Plev level" options={plevOptions} value={plevLevel}
              onChange={(e) => setPlevLevel(e.target.value)} />
          ) : (
            <Input label="Plev level" type="number" value={plevLevel}
              onChange={(e) => setPlevLevel(e.target.value)} placeholder="e.g. 85000" />
          )}
        </div>

        {/* Projection */}
        <p className={SECTION}>Projection</p>
        <Select options={PROJECTIONS} value={projection}
          onChange={(e) => setProjection(e.target.value as ProjectionName)} />
        <div className="mt-2">
          <Input label="Central longitude (°)" type="number" value={centralLon}
            onChange={(e) => setCentralLon(e.target.value)} />
        </div>

        {/* Colors */}
        <p className={SECTION}>Colors</p>
        <Select label="Colormap" options={COLORMAPS} value={cmap}
          onChange={(e) => setCmap(e.target.value)} />
        <div className="grid grid-cols-2 gap-2 mt-2">
          <Input label="vmin" type="number" value={vmin}
            onChange={(e) => setVmin(e.target.value)} placeholder="auto" />
          <Input label="vmax" type="number" value={vmax}
            onChange={(e) => setVmax(e.target.value)} placeholder="auto" />
        </div>

        {/* Bounding box */}
        <p className={SECTION}>Extent (leave blank for global)</p>
        <div className="grid grid-cols-2 gap-2">
          <Input label="Lat min" type="number" value={latMin}
            onChange={(e) => setLatMin(e.target.value)} placeholder="-90" />
          <Input label="Lat max" type="number" value={latMax}
            onChange={(e) => setLatMax(e.target.value)} placeholder="90" />
          <Input label="Lon min" type="number" value={lonMin}
            onChange={(e) => setLonMin(e.target.value)} placeholder="-180" />
          <Input label="Lon max" type="number" value={lonMax}
            onChange={(e) => setLonMax(e.target.value)} placeholder="180" />
        </div>

        {/* Vector overlay */}
        <p className={SECTION}>Vector overlay (quiver)</p>
        <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
          <input type="checkbox" checked={quiverOn}
            onChange={(e) => setQuiverOn(e.target.checked)}
            className="accent-blue-500" />
          Enable wind / vector arrows
        </label>

        {quiverOn && (
          <div className="mt-2 space-y-2">
            {varOptions.length > 0 ? (
              <>
                <Select label="U variable (eastward)"
                  options={[{ value: "", label: "— none —" }, ...varOptions]}
                  value={uVar} onChange={(e) => setUVar(e.target.value)} />
                <Select label="V variable (northward)"
                  options={[{ value: "", label: "— none —" }, ...varOptions]}
                  value={vVar} onChange={(e) => setVVar(e.target.value)} />
              </>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                <Input label="U variable" value={uVar}
                  onChange={(e) => setUVar(e.target.value)} placeholder="ua" />
                <Input label="V variable" value={vVar}
                  onChange={(e) => setVVar(e.target.value)} placeholder="va" />
              </div>
            )}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
                  Stride (1–20)
                </label>
                <input type="range" min={1} max={20} value={quiverStride}
                  onChange={(e) => setQuiverStride(e.target.value)}
                  className="w-full accent-blue-500" />
                <span className="text-xs text-slate-400">every {quiverStride} pts</span>
              </div>
              <Input label="Arrow color" value={quiverColor}
                onChange={(e) => setQuiverColor(e.target.value)} placeholder="black" />
            </div>
          </div>
        )}

        {/* Output */}
        <p className={SECTION}>Output</p>
        <div className="grid grid-cols-2 gap-2">
          <Input label="DPI" type="number" min={72} max={600} value={dpi}
            onChange={(e) => setDpi(e.target.value)} />
          <Input label="Width (in)" type="number" value={fW}
            onChange={(e) => setFW(e.target.value)} />
          <Input label="Height (in)" type="number" value={fH}
            onChange={(e) => setFH(e.target.value)} />
          <Input label="Title" value={title}
            onChange={(e) => setTitle(e.target.value)} placeholder="auto" />
        </div>

        <div className="mt-2 flex flex-wrap gap-3">
          {[
            ["Coastlines", coastlines, setCoastlines],
            ["Borders",    borders,    setBorders],
            ["Gridlines",  gridlines,  setGridlines],
            ["Colorbar",   colorbar,   setColorbar],
          ].map(([label, val, setter]) => (
            <label key={label as string}
              className="flex items-center gap-1.5 text-sm text-slate-300 cursor-pointer">
              <input type="checkbox" checked={val as boolean}
                onChange={(e) => (setter as (v: boolean) => void)(e.target.checked)}
                className="accent-blue-500" />
              {label as string}
            </label>
          ))}
        </div>

        <div className="mt-3 flex gap-2">
          <input
            readOnly
            value={outputPath}
            placeholder="output.png"
            className="flex-1 min-w-0 rounded-md bg-slate-800 border border-slate-600 px-3 py-2 text-sm text-slate-300 placeholder:text-slate-600"
          />
          <Button size="sm" variant="secondary" onClick={pickOutput}>Save as</Button>
        </div>

        <div className="mt-4">
          <Button
            className="w-full"
            onClick={handleRender}
            disabled={!canRender}
            loading={mapLoading}
          >
            Render Map
          </Button>
        </div>
      </aside>

      {/* ── Preview ──────────────────────────────────────────────────────── */}
      <ImagePreview path={mapPreviewPath} loading={mapLoading} error={mapError} />
    </div>
  );
}
