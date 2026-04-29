import { useState, useCallback } from "react";
import { processor, ApiError } from "@/api/client";
import type { FileMetadata, VariableInfo } from "@/api/types";

/**
 * Shared hook that opens a file picker, loads its metadata from the backend,
 * and exposes the variable list + pressure levels for form population.
 *
 * Falls back to window.prompt() when Electron APIs are not available (browser dev).
 */
export function useFileMetadata() {
  const [path, setPath]       = useState("");
  const [meta, setMeta]       = useState<FileMetadata | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const variables : VariableInfo[] = meta ? Object.values(meta.variables) : [];
  const plevLevels: number[]       = meta?.coordinates.plev_levels ?? [];

  const loadPath = useCallback(async (p: string) => {
    setPath(p);
    if (!p) { setMeta(null); return; }
    setLoading(true);
    setError(null);
    try {
      const result = await processor.getMetadata(p);
      setMeta(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setMeta(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const browse = useCallback(async () => {
    const picked = await window.electronAPI?.openFile() ?? null;
    if (picked) {
      await loadPath(picked);
      return;
    }
    // Browser dev fallback
    const fallback = window.prompt("Enter absolute path to NetCDF file:");
    if (fallback) await loadPath(fallback);
  }, [loadPath]);

  const reset = useCallback(() => {
    setPath("");
    setMeta(null);
    setError(null);
  }, []);

  return { path, meta, variables, plevLevels, loading, error, browse, loadPath, reset };
}
