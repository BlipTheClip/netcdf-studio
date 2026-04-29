import { useImageryStore, type ImageryTab } from "@/store/imageryStore";
import { MapForm } from "./MapForm";
import { HovmollerForm } from "./HovmollerForm";
import { TaylorForm } from "./TaylorForm";
import { BatchForm } from "./BatchForm";

const TABS: { id: ImageryTab; label: string; title: string }[] = [
  { id: "map",       label: "Map",        title: "Single map render" },
  { id: "hovmoller", label: "Hovmöller",  title: "Hovmöller diagram" },
  { id: "taylor",    label: "Taylor",     title: "Taylor diagram" },
  { id: "batch",     label: "Batch",      title: "Batch rendering" },
];

export function ImageryPage() {
  const { activeTab, setActiveTab } = useImageryStore();

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Tab bar */}
      <nav className="flex items-center gap-0.5 px-4 h-10 border-b border-slate-800 shrink-0 bg-slate-950">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            title={tab.title}
            className={[
              "px-3 py-1 rounded text-sm transition-colors",
              activeTab === tab.id
                ? "bg-slate-700 text-white"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800",
            ].join(" ")}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Active tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "map"       && <MapForm />}
        {activeTab === "hovmoller" && <HovmollerForm />}
        {activeTab === "taylor"    && <TaylorForm />}
        {activeTab === "batch"     && <BatchForm />}
      </div>
    </div>
  );
}
