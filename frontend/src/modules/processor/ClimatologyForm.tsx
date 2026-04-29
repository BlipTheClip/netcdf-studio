import { useState } from "react";
import { processor, ApiError } from "@/api/client";
import { useProcessorStore } from "@/store/processorStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Select } from "@/components/Select";
import { Card } from "@/components/Card";
import { ErrorBanner } from "@/components/ErrorBanner";
import { VariableSelector } from "./VariableSelector";
import { PlevSelector } from "./PlevSelector";
import { SuccessBanner } from "./SuccessBanner";

export function ClimatologyForm() {
  const { filePath, selectedVariable, selectedPlevLevels, setClimatologyOutputPath } =
    useProcessorStore();

  const [variable,   setVariable]   = useState(selectedVariable ?? "");
  const [startYear,  setStartYear]  = useState("1991");
  const [endYear,    setEndYear]    = useState("2020");
  const [freq,       setFreq]       = useState<"month" | "dayofyear">("month");
  const [plevLevels, setPlevLevels] = useState<number[] | null>(selectedPlevLevels);
  const [outputPath, setOutputPath] = useState("");
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState<string | null>(null);
  const [success,    setSuccess]    = useState<string | null>(null);

  const chooseOutput = async () => {
    const path = await window.electronAPI?.saveFile("climatology.nc");
    if (path) setOutputPath(path);
  };

  const run = async () => {
    if (!filePath || !variable || !outputPath) return;
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await processor.computeClimatology({
        path: filePath,
        variable,
        output_path: outputPath,
        start_year: Number(startYear),
        end_year:   Number(endYear),
        freq,
        plev_levels: plevLevels,
      });
      setClimatologyOutputPath(result.output_path);
      setSuccess(`Saved → ${result.output_path}  (shape: [${result.shape.join(", ")}])`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-4 pb-4">
      <Card title="Climatological mean  (x̄)">
        <div className="space-y-4">
          <VariableSelector value={variable} onChange={setVariable} />

          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Start year"
              type="number"
              value={startYear}
              onChange={(e) => setStartYear(e.target.value)}
              min={1850} max={2200}
            />
            <Input
              label="End year"
              type="number"
              value={endYear}
              onChange={(e) => setEndYear(e.target.value)}
              min={1850} max={2200}
            />
          </div>

          <Select
            label="Frequency"
            options={[
              { value: "month",     label: "Monthly — 12 climatological values" },
              { value: "dayofyear", label: "Day of year — 365/366 values" },
            ]}
            value={freq}
            onChange={(e) => setFreq(e.target.value as "month" | "dayofyear")}
          />

          <PlevSelector selected={plevLevels} onChange={setPlevLevels} />

          <div className="flex gap-2 items-end">
            <Input
              label="Output path (.nc)"
              value={outputPath}
              onChange={(e) => setOutputPath(e.target.value)}
              placeholder="/path/to/climatology.nc"
              className="flex-1"
            />
            {window.electronAPI && (
              <Button variant="secondary" onClick={chooseOutput}>Browse</Button>
            )}
          </div>

          {error   && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
          {success && <SuccessBanner message={success} />}

          <Button
            onClick={run}
            loading={loading}
            disabled={!variable || !outputPath}
          >
            Compute climatology
          </Button>
        </div>
      </Card>
    </div>
  );
}
