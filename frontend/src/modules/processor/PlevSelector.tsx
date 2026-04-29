import { useProcessorStore } from "@/store/processorStore";

interface PlevSelectorProps {
  selected: number[] | null;
  onChange: (levels: number[] | null) => void;
}

/**
 * Chip-based selector for pressure levels.
 * "All" / "None" shortcuts are shown alongside the label.
 * Only renders when the loaded file has a pressure dimension.
 */
export function PlevSelector({ selected, onChange }: PlevSelectorProps) {
  const { metadata } = useProcessorStore();

  if (!metadata?.has_plev || !metadata.coordinates.plev_levels) return null;

  const levels = metadata.coordinates.plev_levels;
  const units = metadata.coordinates.plev_units ?? "";

  const toggle = (level: number) => {
    if (!selected) {
      onChange([level]);
    } else if (selected.includes(level)) {
      const next = selected.filter((l) => l !== level);
      onChange(next.length === 0 ? null : next);
    } else {
      onChange([...selected, level].sort((a, b) => a - b));
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
          Pressure levels{units && ` (${units})`}
        </label>
        <div className="flex gap-3 text-xs">
          <button
            onClick={() => onChange(levels)}
            className="text-blue-400 hover:text-blue-300 transition-colors"
          >
            All
          </button>
          <button
            onClick={() => onChange(null)}
            className="text-slate-500 hover:text-slate-300 transition-colors"
          >
            None
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {levels.map((level) => {
          const active = !selected || selected.includes(level);
          return (
            <button
              key={level}
              onClick={() => toggle(level)}
              className={`
                px-2 py-0.5 rounded text-xs font-mono transition-colors
                ${active
                  ? "bg-blue-600 text-white"
                  : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                }
              `}
            >
              {level}
            </button>
          );
        })}
      </div>
    </div>
  );
}
