import { useBackendStatus } from "@/hooks/useBackendStatus";
import { ProcessorPage } from "@/modules/processor/ProcessorPage";
import { Spinner } from "@/components/Spinner";

// Top-level module IDs — extend as other modules are implemented.
type ModuleId = "processor";

const NAV: { id: ModuleId; label: string }[] = [
  { id: "processor", label: "B — Processor" },
];

export default function App() {
  const { status, version, error } = useBackendStatus();

  // ── Backend not yet ready ──────────────────────────────────────────────────

  if (status === "checking") {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-900">
        <Spinner size="lg" label="Connecting to backend…" />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="h-screen flex items-center justify-center bg-slate-900 p-8">
        <div className="max-w-md text-center space-y-4">
          <div className="text-5xl select-none">⚠</div>
          <h1 className="text-xl font-semibold text-red-400">Backend unreachable</h1>
          <p className="text-sm text-slate-400">{error}</p>
          <p className="text-xs text-slate-500">
            Activate the conda environment and run:{" "}
            <code className="font-mono text-blue-400">
              uvicorn backend.main:app --port 8000
            </code>
          </p>
        </div>
      </div>
    );
  }

  // ── Main layout ────────────────────────────────────────────────────────────

  return (
    <div className="h-screen flex flex-col bg-slate-900 text-slate-100 overflow-hidden">
      {/* Title bar / navigation */}
      <header className="flex items-center gap-4 px-4 h-10 bg-slate-950 border-b border-slate-800 shrink-0">
        <span className="text-sm font-bold text-blue-400 select-none tracking-wide">
          NetCDF Studio
        </span>

        <nav className="flex gap-0.5">
          {NAV.map((item) => (
            <button
              key={item.id}
              className="px-3 py-1 rounded text-sm bg-slate-700 text-white"
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="ml-auto text-xs text-slate-600 font-mono select-none">
          v{version}
        </div>
      </header>

      {/* Module content */}
      <main className="flex-1 overflow-hidden">
        <ProcessorPage />
      </main>
    </div>
  );
}
