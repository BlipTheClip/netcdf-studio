import { useProcessorStore } from "@/store/processorStore";
import { FileLoader } from "./FileLoader";
import { MetadataPanel } from "./MetadataPanel";
import { ClimatologyForm } from "./ClimatologyForm";
import { AnomalyForm } from "./AnomalyForm";
import { SpatialMeanPanel } from "./SpatialMeanPanel";
import { PreviewPanel } from "./PreviewPanel";
import { IndicesPanel } from "./IndicesPanel";

const TABS = [
  { id: "metadata",     label: "Metadata" },
  { id: "climatology",  label: "Climatology" },
  { id: "anomaly",      label: "Anomaly" },
  { id: "spatial-mean", label: "Spatial Mean" },
  { id: "preview",      label: "Map Preview" },
  { id: "indices",      label: "Indices" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function ProcessorPage() {
  const { metadata, activeTab, setActiveTab } = useProcessorStore();

  return (
    <div className="flex flex-col h-full gap-3 p-4 overflow-hidden">
      {/* File loader is always visible at top */}
      <FileLoader />

      {/* Tabs + content only after a file is loaded */}
      {metadata && (
        <>
          <div className="flex gap-0.5 border-b border-slate-700 shrink-0">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabId)}
                className={`
                  px-4 py-2 text-sm font-medium transition-colors rounded-t
                  ${activeTab === tab.id
                    ? "text-blue-400 border-b-2 border-blue-400 -mb-px bg-slate-800/50"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
                  }
                `}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-auto">
            {activeTab === "metadata"     && <MetadataPanel />}
            {activeTab === "climatology"  && <ClimatologyForm />}
            {activeTab === "anomaly"      && <AnomalyForm />}
            {activeTab === "spatial-mean" && <SpatialMeanPanel />}
            {activeTab === "preview"      && <PreviewPanel />}
            {activeTab === "indices"      && <IndicesPanel />}
          </div>
        </>
      )}

      {/* Hint when no file is open */}
      {!metadata && (
        <div className="flex-1 flex items-center justify-center text-slate-600 text-sm select-none">
          Open a NetCDF file to begin
        </div>
      )}
    </div>
  );
}
