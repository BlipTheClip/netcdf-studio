import { useProcessorStore } from "@/store/processorStore";
import { Card } from "@/components/Card";
import { TIME_FREQUENCY_LABELS } from "@/api/types";
import type { ReactNode } from "react";

export function MetadataPanel() {
  const { metadata } = useProcessorStore();
  if (!metadata) return null;

  const { coordinates: c, variables, global_attrs } = metadata;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pb-4">
      {/* File summary */}
      <Card title="File information">
        <dl className="space-y-2 text-sm">
          <Row label="Size"          value={`${metadata.file_size_mb.toFixed(2)} MB`} />
          <Row label="Time frequency" value={
            metadata.time_frequency
              ? TIME_FREQUENCY_LABELS[metadata.time_frequency]
              : "—"
          } />
          <Row label="Grid resolution" value={
            metadata.lat_lon_resolution_deg
              ? `${metadata.lat_lon_resolution_deg}°`
              : "—"
          } />
          <Row label="Pressure levels" value={metadata.has_plev ? "Yes" : "No"} />
        </dl>
      </Card>

      {/* Coordinate extent */}
      <Card title="Coordinate extent">
        <dl className="space-y-2 text-sm">
          {c.time_start  && <Row label="Time start"  value={c.time_start} />}
          {c.time_end    && <Row label="Time end"    value={c.time_end} />}
          {c.time_steps !== null && (
            <Row label="Time steps" value={String(c.time_steps)} />
          )}
          {c.lat_min !== null && (
            <Row
              label="Latitude"
              value={`${c.lat_min}° – ${c.lat_max}° (${c.lat_n} pts)`}
            />
          )}
          {c.lon_min !== null && (
            <Row
              label="Longitude"
              value={`${c.lon_min}° – ${c.lon_max}° (${c.lon_n} pts)`}
            />
          )}
          {c.plev_levels && (
            <Row
              label="Plevels"
              value={c.plev_levels.join(", ") + (c.plev_units ? ` ${c.plev_units}` : "")}
            />
          )}
        </dl>
      </Card>

      {/* Variables table */}
      <Card title="Variables" className="lg:col-span-2">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b border-slate-700">
                <Th>Name</Th>
                <Th>Long name</Th>
                <Th>Units</Th>
                <Th>Shape</Th>
                <Th>Dimensions</Th>
                <Th>DType</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {Object.values(variables).map((v) => (
                <tr key={v.name} className="hover:bg-slate-700/30">
                  <td className="py-2 pr-4 font-mono text-blue-400">{v.name}</td>
                  <td className="py-2 pr-4 text-slate-300">{v.long_name || "—"}</td>
                  <td className="py-2 pr-4 text-slate-400">{v.units || "—"}</td>
                  <td className="py-2 pr-4 text-slate-400 font-mono">[{v.shape.join(", ")}]</td>
                  <td className="py-2 pr-4 text-slate-500 font-mono">{v.dimensions.join(", ")}</td>
                  <td className="py-2 text-slate-500 font-mono">{v.dtype}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Global attributes */}
      {Object.keys(global_attrs).length > 0 && (
        <Card title="Global attributes" className="lg:col-span-2">
          <dl className="space-y-2 text-sm">
            {Object.entries(global_attrs).map(([k, v]) => (
              <Row key={k} label={k} value={v} mono />
            ))}
          </dl>
        </Card>
      )}
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-3">
      <dt className="w-36 shrink-0 text-slate-500">{label}</dt>
      <dd className={`text-slate-200 break-all ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

function Th({ children }: { children: ReactNode }) {
  return (
    <th className="py-2 pr-4 text-xs font-medium text-slate-500 uppercase tracking-wide">
      {children}
    </th>
  );
}
