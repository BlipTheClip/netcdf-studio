import { lazy, Suspense, useState } from "react";
import { processor, ApiError } from "@/api/client";
import { useProcessorStore } from "@/store/processorStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import { VariableSelector } from "./VariableSelector";
import type { SliceResult } from "@/api/types";

const Plot = lazy(() => import("react-plotly.js"));

export function PreviewPanel() {
  const { filePath, selectedVariable, metadata } = useProcessorStore();

  const [variable,   setVariable]   = useState(selectedVariable ?? "");
  const [timeIndex,  setTimeIndex]  = useState("0");
  const [plevLevel,  setPlevLevel]  = useState("");
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [result,     setResult]     = useState<SliceResult | null>(null);

  const plevOptions = metadata?.coordinates.plev_levels ?? [];

  const run = async () => {
    if (!filePath || !variable) return;
    setLoading(true);
    setError(null);

    try {
      const res = await processor.getPreview({
        path: filePath,
        variable,
        time_index: Number(timeIndex),
        plev_level: plevLevel ? Number(plevLevel) : null,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const title = result
    ? `${result.variable}  [${result.units}]  —  ${result.time_label}${result.plev_label ? `, ${result.plev_label}` : ""}`
    : "2D map preview";

  return (
    <div className="space-y-4 pb-4">
      <Card title="2D map preview">
        <div className="space-y-4 max-w-2xl">
          <VariableSelector value={variable} onChange={setVariable} />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Time index"
              type="number"
              value={timeIndex}
              onChange={(e) => setTimeIndex(e.target.value)}
              min={0}
            />

            {plevOptions.length > 0 && (
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
                  Pressure level
                </label>
                <select
                  className="w-full rounded-md bg-slate-800 border border-slate-600 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={plevLevel}
                  onChange={(e) => setPlevLevel(e.target.value)}
                >
                  <option value="">First level</option>
                  {plevOptions.map((l) => (
                    <option key={l} value={String(l)}>{l}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

          <Button onClick={run} loading={loading} disabled={!variable}>
            Load preview
          </Button>
        </div>
      </Card>

      {result && (
        <Card title={title}>
          <Suspense fallback={<Spinner label="Loading map…" />}>
            <Plot
              data={[{
                type: "heatmap",
                z: result.values,
                x: result.lon,
                y: result.lat,
                colorscale: "RdBu",
                reversescale: true,
                colorbar: {
                  thickness: 15,
                  title: { text: result.units, side: "right" },
                  tickfont:  { color: "#94a3b8" },
                  titlefont: { color: "#94a3b8" },
                },
              }]}
              layout={{
                paper_bgcolor: "transparent",
                plot_bgcolor:  "#1e293b",
                font:    { color: "#cbd5e1", size: 11 },
                margin:  { t: 10, r: 90, b: 55, l: 65 },
                xaxis:   { gridcolor: "#334155", title: { text: "Longitude (°E)" } },
                yaxis:   { gridcolor: "#334155", title: { text: "Latitude (°N)" } },
                autosize: true,
              }}
              useResizeHandler
              style={{ width: "100%", height: "460px" }}
              config={{ displayModeBar: true, responsive: true }}
            />
          </Suspense>
        </Card>
      )}
    </div>
  );
}
