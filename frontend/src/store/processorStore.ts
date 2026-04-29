import { create } from "zustand";
import type {
  FileMetadata,
  IndexResult,
  SliceResult,
  SpatialMeanResult,
} from "@/api/types";

type ActiveTab =
  | "metadata"
  | "climatology"
  | "anomaly"
  | "spatial-mean"
  | "preview"
  | "indices";

interface ProcessorState {
  // ── Loaded file ─────────────────────────────────────────────────────────
  filePath: string | null;
  metadata: FileMetadata | null;
  /** Variable selected in the file-loader step; propagated to all sub-forms. */
  selectedVariable: string | null;
  /** Pressure levels selected in the file-loader step. */
  selectedPlevLevels: number[] | null;

  // ── Operation outputs ────────────────────────────────────────────────────
  climatologyOutputPath: string | null;
  anomalyOutputPath: string | null;
  spatialMeanResult: SpatialMeanResult | null;
  previewResult: SliceResult | null;
  indexResult: IndexResult | null;

  // ── UI state ─────────────────────────────────────────────────────────────
  activeTab: ActiveTab;
  isLoading: boolean;
  error: string | null;

  // ── Actions ──────────────────────────────────────────────────────────────
  setFilePath: (path: string | null) => void;
  setMetadata: (meta: FileMetadata | null) => void;
  setSelectedVariable: (variable: string | null) => void;
  setSelectedPlevLevels: (levels: number[] | null) => void;
  setClimatologyOutputPath: (path: string | null) => void;
  setAnomalyOutputPath: (path: string | null) => void;
  setSpatialMeanResult: (result: SpatialMeanResult | null) => void;
  setPreviewResult: (result: SliceResult | null) => void;
  setIndexResult: (result: IndexResult | null) => void;
  setActiveTab: (tab: ActiveTab) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

const initialState = {
  filePath: null,
  metadata: null,
  selectedVariable: null,
  selectedPlevLevels: null,
  climatologyOutputPath: null,
  anomalyOutputPath: null,
  spatialMeanResult: null,
  previewResult: null,
  indexResult: null,
  activeTab: "metadata" as ActiveTab,
  isLoading: false,
  error: null,
};

export const useProcessorStore = create<ProcessorState>((set) => ({
  ...initialState,

  setFilePath:              (path)   => set({ filePath: path }),
  setMetadata:              (meta)   => set({ metadata: meta }),
  setSelectedVariable:      (v)      => set({ selectedVariable: v }),
  setSelectedPlevLevels:    (levels) => set({ selectedPlevLevels: levels }),
  setClimatologyOutputPath: (path)   => set({ climatologyOutputPath: path }),
  setAnomalyOutputPath:     (path)   => set({ anomalyOutputPath: path }),
  setSpatialMeanResult:     (r)      => set({ spatialMeanResult: r }),
  setPreviewResult:         (r)      => set({ previewResult: r }),
  setIndexResult:           (r)      => set({ indexResult: r }),
  setActiveTab:             (tab)    => set({ activeTab: tab }),
  setIsLoading:             (l)      => set({ isLoading: l }),
  setError:                 (e)      => set({ error: e }),
  reset:                    ()       => set(initialState),
}));
