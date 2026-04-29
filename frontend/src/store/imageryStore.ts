import { create } from "zustand";
import type { BatchImageryProgressPayload, BatchImageryResultPayload } from "@/api/types";

export type ImageryTab = "map" | "hovmoller" | "taylor" | "batch";

// ── Taylor model entry (form-level, includes React key `id`) ─────────────────

export interface TaylorModelEntry {
  id: string;
  name: string;
  std_ratio: number;
  correlation: number;
  color: string;
  marker: string;
}

// ── Batch job entry (form-level) ─────────────────────────────────────────────

export interface BatchJobEntry {
  id: string;
  path: string;
  variable: string;
  output_path: string;
  time_index: number;
  plev_level: number | null;
  projection: string;
  central_longitude: number;
  cmap: string;
  title: string;
  dpi: number;
  add_coastlines: boolean;
  add_gridlines: boolean;
  u_variable: string;
  v_variable: string;
  quiver_stride: number;
  quiver_color: string;
}

const DEFAULT_JOB: Omit<BatchJobEntry, "id"> = {
  path: "",
  variable: "",
  output_path: "",
  time_index: 0,
  plev_level: null,
  projection: "PlateCarree",
  central_longitude: 0,
  cmap: "RdBu_r",
  title: "",
  dpi: 150,
  add_coastlines: true,
  add_gridlines: true,
  u_variable: "",
  v_variable: "",
  quiver_stride: 5,
  quiver_color: "black",
};

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

// ── Store interface ───────────────────────────────────────────────────────────

interface ImageryState {
  activeTab: ImageryTab;

  // Map single render
  mapPreviewPath: string | null;
  mapLoading: boolean;
  mapError: string | null;

  // Hovmöller single render
  hovPreviewPath: string | null;
  hovLoading: boolean;
  hovError: string | null;

  // Taylor
  taylorModels: TaylorModelEntry[];
  taylorPreviewPath: string | null;
  taylorLoading: boolean;
  taylorError: string | null;

  // Batch
  batchJobs: BatchJobEntry[];
  maxRamGb: number;
  isBatching: boolean;
  batchProgress: Record<number, BatchImageryProgressPayload>;
  batchResult: BatchImageryResultPayload | null;
  batchError: string | null;

  // Actions — tab
  setActiveTab: (tab: ImageryTab) => void;

  // Actions — map
  setMapPreviewPath: (path: string | null) => void;
  setMapLoading: (v: boolean) => void;
  setMapError: (e: string | null) => void;

  // Actions — Hovmöller
  setHovPreviewPath: (path: string | null) => void;
  setHovLoading: (v: boolean) => void;
  setHovError: (e: string | null) => void;

  // Actions — Taylor
  addTaylorModel: (m?: Partial<TaylorModelEntry>) => void;
  removeTaylorModel: (id: string) => void;
  updateTaylorModel: (id: string, patch: Partial<TaylorModelEntry>) => void;
  setTaylorPreviewPath: (path: string | null) => void;
  setTaylorLoading: (v: boolean) => void;
  setTaylorError: (e: string | null) => void;

  // Actions — batch
  addBatchJob: (job?: Partial<Omit<BatchJobEntry, "id">>) => void;
  removeBatchJob: (id: string) => void;
  updateBatchJob: (id: string, patch: Partial<BatchJobEntry>) => void;
  setMaxRamGb: (gb: number) => void;
  setIsBatching: (v: boolean) => void;
  updateBatchProgress: (payload: BatchImageryProgressPayload) => void;
  setBatchResult: (result: BatchImageryResultPayload | null) => void;
  setBatchError: (e: string | null) => void;
  resetBatch: () => void;
}

// ── Store implementation ──────────────────────────────────────────────────────

export const useImageryStore = create<ImageryState>((set) => ({
  activeTab: "map",

  mapPreviewPath: null,
  mapLoading:     false,
  mapError:       null,

  hovPreviewPath: null,
  hovLoading:     false,
  hovError:       null,

  taylorModels:      [],
  taylorPreviewPath: null,
  taylorLoading:     false,
  taylorError:       null,

  batchJobs:     [],
  maxRamGb:      4,
  isBatching:    false,
  batchProgress: {},
  batchResult:   null,
  batchError:    null,

  setActiveTab: (tab) => set({ activeTab: tab }),

  setMapPreviewPath: (path) => set({ mapPreviewPath: path }),
  setMapLoading:     (v)    => set({ mapLoading: v }),
  setMapError:       (e)    => set({ mapError: e }),

  setHovPreviewPath: (path) => set({ hovPreviewPath: path }),
  setHovLoading:     (v)    => set({ hovLoading: v }),
  setHovError:       (e)    => set({ hovError: e }),

  addTaylorModel: (m = {}) =>
    set((s) => ({
      taylorModels: [
        ...s.taylorModels,
        {
          id:          newId(),
          name:        m.name        ?? `Model ${s.taylorModels.length + 1}`,
          std_ratio:   m.std_ratio   ?? 1.0,
          correlation: m.correlation ?? 0.9,
          color:       m.color       ?? "",
          marker:      m.marker      ?? "",
        },
      ],
    })),

  removeTaylorModel: (id) =>
    set((s) => ({ taylorModels: s.taylorModels.filter((m) => m.id !== id) })),

  updateTaylorModel: (id, patch) =>
    set((s) => ({
      taylorModels: s.taylorModels.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),

  setTaylorPreviewPath: (path) => set({ taylorPreviewPath: path }),
  setTaylorLoading:     (v)    => set({ taylorLoading: v }),
  setTaylorError:       (e)    => set({ taylorError: e }),

  addBatchJob: (job = {}) =>
    set((s) => ({
      batchJobs: [
        ...s.batchJobs,
        { id: newId(), ...DEFAULT_JOB, ...job },
      ],
    })),

  removeBatchJob: (id) =>
    set((s) => ({ batchJobs: s.batchJobs.filter((j) => j.id !== id) })),

  updateBatchJob: (id, patch) =>
    set((s) => ({
      batchJobs: s.batchJobs.map((j) => (j.id === id ? { ...j, ...patch } : j)),
    })),

  setMaxRamGb:   (gb) => set({ maxRamGb: gb }),
  setIsBatching: (v)  => set({ isBatching: v }),

  updateBatchProgress: (payload) =>
    set((s) => ({
      batchProgress: { ...s.batchProgress, [payload.current - 1]: payload },
    })),

  setBatchResult: (result) => set({ batchResult: result }),
  setBatchError:  (e)      => set({ batchError: e }),

  resetBatch: () =>
    set({ isBatching: false, batchProgress: {}, batchResult: null, batchError: null }),
}));
