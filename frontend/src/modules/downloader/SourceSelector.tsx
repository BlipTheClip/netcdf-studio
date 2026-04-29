import { useEffect } from "react";
import { downloader, ApiError } from "@/api/client";
import { useDownloaderStore } from "@/store/downloaderStore";
import { Spinner } from "@/components/Spinner";
import { ErrorBanner } from "@/components/ErrorBanner";

const SOURCE_ORDER = ["esgf", "copernicus", "worldbank", "nasa_aws", "esa_cci"] as const;

export function SourceSelector() {
  const {
    sources,
    sourcesLoading,
    sourcesError,
    selectedSource,
    setSelectedSource,
    setSources,
    setSourcesLoading,
    setSourcesError,
  } = useDownloaderStore();

  useEffect(() => {
    if (sources !== null) return;
    setSourcesLoading(true);
    downloader
      .getSources()
      .then((data) => setSources(data.sources))
      .catch((e) => setSourcesError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setSourcesLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (sourcesLoading) {
    return (
      <div className="flex justify-center p-4">
        <Spinner size="sm" label="Loading sources…" />
      </div>
    );
  }

  if (sourcesError) {
    return (
      <div className="p-4">
        <ErrorBanner message={sourcesError} />
      </div>
    );
  }

  if (!sources) return null;

  return (
    <div className="border-b border-slate-800 p-4">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
        Data Source
      </p>
      <div className="flex flex-wrap gap-3">
        {SOURCE_ORDER.map((key) => {
          const meta = sources[key];
          if (!meta) return null;
          const isSelected = selectedSource === key;
          return (
            <button
              key={key}
              onClick={() => setSelectedSource(isSelected ? null : key)}
              className={[
                "text-left p-3 rounded-lg border transition-all w-44",
                isSelected
                  ? "border-blue-500 bg-blue-900/30 ring-1 ring-blue-500"
                  : "border-slate-700 bg-slate-800 hover:border-slate-600",
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="text-sm font-semibold text-slate-100 leading-tight">
                  {meta.name}
                </span>
                <span
                  className={[
                    "shrink-0 text-xs px-1.5 py-0.5 rounded font-medium",
                    meta.requires_auth
                      ? "bg-orange-900/50 text-orange-300"
                      : "bg-green-900/50 text-green-300",
                  ].join(" ")}
                >
                  {meta.requires_auth ? "Auth" : "Free"}
                </span>
              </div>
              <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                {meta.description}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
