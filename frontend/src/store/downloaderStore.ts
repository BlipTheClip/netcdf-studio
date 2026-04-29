import { create } from "zustand";
import type {
  DatasetItem,
  DownloadProgressPayload,
  DownloadResultPayload,
  SourceMeta,
} from "@/api/types";

interface DownloaderStore {
  // Sources catalogue
  sources: Record<string, SourceMeta> | null;
  sourcesLoading: boolean;
  sourcesError: string | null;
  selectedSource: string | null;

  // Search
  searchResults: DatasetItem[];
  searchTotal: number;
  isSearching: boolean;
  searchError: string | null;

  // Dataset selection: id → selected
  selectedDatasets: Record<string, boolean>;

  // Download settings
  destDir: string;
  maxConcurrent: number;

  // Download state
  isDownloading: boolean;
  downloadError: string | null;
  fileProgress: Record<string, DownloadProgressPayload>;
  downloadResult: DownloadResultPayload | null;

  // Actions
  setSources: (sources: Record<string, SourceMeta>) => void;
  setSourcesLoading: (v: boolean) => void;
  setSourcesError: (e: string | null) => void;
  setSelectedSource: (source: string | null) => void;
  setSearchResults: (results: DatasetItem[], total: number) => void;
  setIsSearching: (v: boolean) => void;
  setSearchError: (e: string | null) => void;
  toggleDataset: (id: string) => void;
  selectAllDatasets: () => void;
  clearDatasetSelection: () => void;
  setDestDir: (dir: string) => void;
  setMaxConcurrent: (n: number) => void;
  setIsDownloading: (v: boolean) => void;
  setDownloadError: (e: string | null) => void;
  updateFileProgress: (payload: DownloadProgressPayload) => void;
  setDownloadResult: (result: DownloadResultPayload | null) => void;
  resetDownload: () => void;
}

export const useDownloaderStore = create<DownloaderStore>((set, get) => ({
  sources: null,
  sourcesLoading: false,
  sourcesError: null,
  selectedSource: null,

  searchResults: [],
  searchTotal: 0,
  isSearching: false,
  searchError: null,

  selectedDatasets: {},

  destDir: "",
  maxConcurrent: 4,

  isDownloading: false,
  downloadError: null,
  fileProgress: {},
  downloadResult: null,

  setSources: (sources) => set({ sources }),
  setSourcesLoading: (sourcesLoading) => set({ sourcesLoading }),
  setSourcesError: (sourcesError) => set({ sourcesError }),

  // Switching source resets search and selection
  setSelectedSource: (selectedSource) =>
    set({
      selectedSource,
      searchResults: [],
      searchTotal: 0,
      searchError: null,
      selectedDatasets: {},
    }),

  setSearchResults: (searchResults, searchTotal) =>
    set({ searchResults, searchTotal }),
  setIsSearching: (isSearching) => set({ isSearching }),
  setSearchError: (searchError) => set({ searchError }),

  toggleDataset: (id) => {
    const prev = get().selectedDatasets;
    set({ selectedDatasets: { ...prev, [id]: !prev[id] } });
  },
  selectAllDatasets: () => {
    const all: Record<string, boolean> = {};
    get().searchResults.forEach((d) => { all[d.id] = true; });
    set({ selectedDatasets: all });
  },
  clearDatasetSelection: () => set({ selectedDatasets: {} }),

  setDestDir: (destDir) => set({ destDir }),
  setMaxConcurrent: (maxConcurrent) => set({ maxConcurrent }),
  setIsDownloading: (isDownloading) => set({ isDownloading }),
  setDownloadError: (downloadError) => set({ downloadError }),
  updateFileProgress: (payload) => {
    const prev = get().fileProgress;
    set({ fileProgress: { ...prev, [payload.file]: payload } });
  },
  setDownloadResult: (downloadResult) => set({ downloadResult }),
  resetDownload: () =>
    set({
      isDownloading: false,
      downloadError: null,
      fileProgress: {},
      downloadResult: null,
    }),
}));
