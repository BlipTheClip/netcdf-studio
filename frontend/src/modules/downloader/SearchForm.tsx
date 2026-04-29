import { useState } from "react";
import { downloader, ApiError } from "@/api/client";
import { useDownloaderStore } from "@/store/downloaderStore";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import type { DownloaderSearchRequest } from "@/api/types";

export function SearchForm() {
  const {
    selectedSource,
    sources,
    isSearching,
    setSearchResults,
    setIsSearching,
    setSearchError,
  } = useDownloaderStore();

  const [variable, setVariable] = useState("");
  const [startYear, setStartYear] = useState("");
  const [endYear, setEndYear] = useState("");
  const [frequency, setFrequency] = useState("");
  const [limit, setLimit] = useState("50");
  const [extraParams, setExtraParams] = useState<Record<string, string>>({});

  if (!selectedSource || !sources) return null;
  const sourceMeta = sources[selectedSource];

  const setParam = (key: string, value: string) =>
    setExtraParams((prev) => ({ ...prev, [key]: value }));

  const handleSearch = async () => {
    setIsSearching(true);
    setSearchError(null);
    try {
      const req: DownloaderSearchRequest = {
        limit: Math.max(1, Math.min(500, parseInt(limit) || 50)),
        params: Object.fromEntries(
          Object.entries(extraParams).filter(([, v]) => v !== ""),
        ),
      };
      if (variable) req.variable = variable;
      if (startYear) req.start_year = parseInt(startYear);
      if (endYear) req.end_year = parseInt(endYear);
      if (frequency) req.frequency = frequency;

      const result = await downloader.search(selectedSource, req);
      setSearchResults(result.datasets, result.total);
    } catch (e) {
      setSearchError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-slate-200">
        Search {sourceMeta.full_name}
      </h3>

      <Input
        label="Variable"
        value={variable}
        onChange={(e) => setVariable(e.target.value)}
        placeholder="e.g. tas, pr, sst"
      />

      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Start year"
          value={startYear}
          onChange={(e) => setStartYear(e.target.value)}
          placeholder="1980"
        />
        <Input
          label="End year"
          value={endYear}
          onChange={(e) => setEndYear(e.target.value)}
          placeholder="2020"
        />
      </div>

      <Input
        label="Frequency"
        value={frequency}
        onChange={(e) => setFrequency(e.target.value)}
        placeholder="mon, day, 6hr…"
      />

      {Object.keys(sourceMeta.search_params).length > 0 && (
        <div className="pt-2 border-t border-slate-700 space-y-2">
          <p className="text-xs text-slate-500 font-medium">Source filters</p>
          {Object.entries(sourceMeta.search_params).map(([key, desc]) => (
            <Input
              key={key}
              label={key}
              value={extraParams[key] ?? ""}
              onChange={(e) => setParam(key, e.target.value)}
              placeholder={desc}
            />
          ))}
        </div>
      )}

      <Input
        label="Max results"
        value={limit}
        onChange={(e) => setLimit(e.target.value)}
        placeholder="50"
      />

      <Button
        variant="primary"
        size="sm"
        className="w-full"
        onClick={handleSearch}
        loading={isSearching}
        disabled={isSearching}
      >
        Search
      </Button>

      {sourceMeta.requires_auth && sourceMeta.auth_instructions && (
        <p className="text-xs text-orange-400 leading-relaxed">
          {sourceMeta.auth_instructions}
        </p>
      )}
    </div>
  );
}
