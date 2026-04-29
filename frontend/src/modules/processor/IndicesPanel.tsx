import { lazy, Suspense, useState } from "react";
import { processor, ApiError } from "@/api/client";
import { useProcessorStore } from "@/store/processorStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import { VariableSelector } from "./VariableSelector";
import { INDEX_LABELS, type IndexName, type IndexResult } from "@/api/types";

const Plot = lazy(() => import("react-plotly.js"));

const INDEX_OPTIONS = (Object.entries(INDEX_LABELS) as [IndexName, string][]).map(
  ([value, label]) => ({ value, label }),
);

const ENSO_INDICES  = new Set<IndexName>(["nino34", "nino3", "nino4", "nino12", "oni"]);
const ETCCDI_INDICES = new Set<IndexName>(["rx1day", "rx5day", "r95p", "prcptot", "cdd", "cwd"]);

const ENSO_HINTS: Partial<Record<IndexName, string>> = {
  nino34: "5°S–5°N, 170°W–120°W",
  nino3:  "5°S–5°N, 150°W–90°W",
  nino4:  "5°S–5°N, 160°E–150°W  (wraps antimeridian)",
  nino12: "10°S–0°, 90°W–80°W",
  oni:    "3-month running mean of Niño 3.4 (NOAA/CPC)",
};

export function IndicesPanel() {
  const { filePath, selectedVariable } = useProcessorStore();

  const [index,       setIndex]       = useState<IndexName>("nino34");
  const [variable,    setVariable]    = useState(selectedVariable ?? "");
  const [startYear,   setStartYear]   = useState("1991");
  const [endYear,     setEndYear]     = useState("2020");
  const [oniWindow,   setOniWindow]   = useState("3");
  const [prThreshold, setPrThreshold] = useState("1.0");
  const [outputPath,  setOutputPath]  = useState("");
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const [result,      setResult]      = useState<IndexResult | null>(null);

  const isENSO   = ENSO_INDICES.has(index);
  const isNAO    = index === "nao";
  const isETCCDI = ETCCDI_INDICES.has(index);

  const chooseOutput = async () => {
    const path = await window.electronAPI?.saveFile(`${index}.nc`);
    if (path) setOutputPath(path);
  };

  const run = async () => {
    if (!filePath || !variable) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await processor.computeIndex({
        path: filePath,
        index,
        variable,
        start_year: Number(startYear),
        end_year:   Number(endYear),
        output_path: isETCCDI && outputPath ? outputPath : null,
        ...(index === "oni" ? { oni_window: Number(oniWindow) } : {}),
        ...(isETCCDI        ? { pr_threshold_mm_day: Number(prThreshold) } : {}),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 pb-4">
      <Card title="Climate indices">
        <div className="space-y-4 max-w-2xl">
          <Select
            label="Index"
            options={INDEX_OPTIONS}
            value={index}
            onChange={(e) => {
              setIndex(e.target.value as IndexName);
              setResult(null);
            }}
          />

          <VariableSelector value={variable} onChange={setVariable} />

          <div className="grid grid-cols-2 gap-3">
            <Input label="Start year" type="number" value={startYear} onChange={(e) => setStartYear(e.target.value)} min={1850} max={2200} />
            <Input label="End year"   type="number" value={endYear}   onChange={(e) => setEndYear(e.target.value)}   min={1850} max={2200} />
          </div>

          {index === "oni" && (
            <Input
              label="ONI window (months)"
              type="number"
              value={oniWindow}
              onChange={(e) => setOniWindow(e.target.value)}
              min={2} max={12}
            />
          )}

          {isETCCDI && (
            <>
              <Input
                label="Wet/dry threshold (mm/day)"
                type="number"
                step={0.1}
                value={prThreshold}
                onChange={(e) => setPrThreshold(e.target.value)}
                min={0.1}
              />
              <div className="flex gap-2 items-end">
                <Input
                  label="Save spatial field to (.nc, optional)"
                  value={outputPath}
                  onChange={(e) => setOutputPath(e.target.value)}
                  placeholder="Leave empty — global mean only"
                  className="flex-1"
                />
                {window.electronAPI && (
                  <Button variant="secondary" onClick={chooseOutput}>Browse</Button>
                )}
              </div>
            </>
          )}

          {/* Context hints */}
          {(isENSO || isNAO) && (
            <p className="text-xs text-slate-500 leading-relaxed">
              {isNAO
                ? "Hurrell (1995) station-based NAO: normalised SLP anomaly difference between Azores (28°–40°N, 28°W–0°) and Iceland (63°–70°N, 25°W–10°W) boxes."
                : `ENSO ${INDEX_LABELS[index]}: area-weighted SST anomaly — ${ENSO_HINTS[index] ?? ""}.`
              }
            </p>
          )}

          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

          <Button onClick={run} loading={loading} disabled={!variable}>
            Compute {INDEX_LABELS[index]}
          </Button>
        </div>
      </Card>

      {result && (
        <Card title={`${result.long_name}  [${result.units}]`}>
          <Suspense fallback={<Spinner label="Loading chart…" />}>
            <Plot
              data={[
                {
                  type: "scatter",
                  mode: "lines",
                  x: result.time,
                  y: result.values,
                  line: { color: "#f59e0b", width: 1.5 },
                  name: result.long_name,
                },
                // Zero baseline for anomaly-based indices
                ...(isENSO || isNAO
                  ? [{
                      type: "scatter" as const,
                      mode: "lines" as const,
                      x: [result.time[0], result.time[result.time.length - 1]],
                      y: [0, 0],
                      line: { color: "#475569", width: 1, dash: "dash" as const },
                      showlegend: false,
                      hoverinfo: "skip" as const,
                    }]
                  : []),
              ]}
              layout={{
                paper_bgcolor: "transparent",
                plot_bgcolor:  "#1e293b",
                font:    { color: "#cbd5e1", size: 12 },
                margin:  { t: 10, r: 20, b: 50, l: 70 },
                xaxis:   { gridcolor: "#334155", title: { text: "Time" } },
                yaxis:   { gridcolor: "#334155", title: { text: result.units } },
                legend:  { bgcolor: "rgba(0,0,0,0)", font: { color: "#cbd5e1" } },
                autosize: true,
              }}
              useResizeHandler
              style={{ width: "100%", height: "360px" }}
              config={{ displayModeBar: true, responsive: true }}
            />
          </Suspense>

          {result.output_path && (
            <p className="mt-2 text-xs text-slate-400 font-mono">
              Spatial field saved: {result.output_path}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
