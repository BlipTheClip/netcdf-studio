import { useState, useEffect } from "react";
import { health, ApiError } from "@/api/client";

export type BackendStatus = "checking" | "ready" | "error";

interface BackendStatusResult {
  status: BackendStatus;
  version: string | null;
  error: string | null;
}

/**
 * Polls GET /api/health at the given interval.
 * Transitions: checking → ready (or) checking → error.
 * After the first success the interval continues so the UI reflects a lost
 * backend (e.g. the process crashed).
 */
export function useBackendStatus(intervalMs = 5000): BackendStatusResult {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [version, setVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const res = await health.check();
        if (!cancelled) {
          setStatus("ready");
          setVersion(res.version);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setStatus("error");
          setError(err instanceof ApiError ? err.message : String(err));
        }
      }
    };

    check();
    const id = setInterval(check, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [intervalMs]);

  return { status, version, error };
}
