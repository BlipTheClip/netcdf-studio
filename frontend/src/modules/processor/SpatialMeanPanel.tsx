import { lazy, Suspense, useState } from "react";
import { processor, ApiError } from "@/api/client";
import { useProcessorStore } from "@/store/processorStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import { VariableSelector } from "./VariableSelector";
import { PlevSelector } from "./PlevSelector";
import type { SpatialMeanResult } from "@/api/types";

// Lazy-load Plotly — it's large and only needed when this tab is active.
const Plot = lazy(() => import("react-plotly.js"));

export function SpatialMeanPanel() {
  const { filePath, selectedVariable, selectedPlevLevels } = useProcessorStore();

  const [variable,   setVariable]   = useState(selectedVariable ?? "");
  const [plevLevels, setPlevLevels] = useState<number[] | null>(selectedPlevLevels);
  const [latMin,     setLatMin]     = useState("-90");
  const [latMax,     setLatMax]     = useState("90");
  const [lonMin,     setLonMin]     = useState("-180");
  const [lonMax,     setLonMax]     = useState("180");
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [result,     setResult]     = useState<SpatialMeanResult | null>(null);

  const run = async () => {
    if (!filePath || !variable) return;
    setLoading(true);
    setError(null);

    try {
      const res = await processor.computeSpatialMean({
        path: filePath,
        variable,
        plev_levels: plevLevels,
        lat_min: Number(latMin),
        lat_max: Number(latMax),
        lon_min: Number(lonMin),
        lon_max: Number(lonMax),
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
      <Card title="Area-weighted spatial mean  (cosine-latitude)">
        <div className="space-y-4 max-w-2xl">
          <VariableSelector value={variable} onChange={setVariable} />
          <PlevSelector selected={plevLevels} onChange={setPlevLevels} />

          <div className="grid grid-cols-2 gap-3">
            <Input label="Lat min (°)" type="number" value={latMin} onChange={(e) => setLatMin(e.target.value)} min={-90}  max={90} />
            <Input label="Lat max (°)" type="number" value={latMax} onChange={(e) => setLatMax(e.target.value)} min={-90}  max={90} />
            <Input label="Lon min (°)" type="number" value={lonMin} onChange={(e) => setLonMin(e.target.value)} min={-180} max={180} />
            <Input label="Lon max (°)" type="number" value={lonMax} onChange={(e) => setLonMax(e.target.value)} min={-180} max={180} />
          </div>

          {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

          <Button onClick={run} loading={loading} disabled={!variable}>
            Compute
          </Button>
        </div>
      </Card>

      {result && (
        <Card title={`${result.variable}  [${result.units}]  —  time series`}>
          <Suspense fallback={<Spinner label="Loading chart…" />}>
            <Plot
              data={[{
                type: "scatter",
                mode: "lines",
                x: result.time,
                y: result.values,
                line: { color: "#3b82f6", width: 1.5 },
                name: result.variable,
              }]}
              layout={{
                paper_bgcolor: "transparent",
                plot_bgcolor:  "#1e293b",
                font:    { color: "#cbd5e1", size: 12 },
                margin:  { t: 10, r: 20, b: 50, l: 70 },
                xaxis:   { gridcolor: "#334155", title: { text: "Time" } },
                yaxis:   { gridcolor: "#334155", title: { text: `${result.variable} (${result.units})` } },
                autosize: true,
              }}
              useResizeHandler
              style={{ width: "100%", height: "360px" }}
              config={{ displayModeBar: true, responsive: true }}
            />
          </Suspense>
        </Card>
      )}
    </div>
  );
}
