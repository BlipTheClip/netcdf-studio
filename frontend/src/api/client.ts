/**
 * NetCDF Studio API client.
 *
 * All HTTP calls go through `apiFetch` which:
 *   - Handles network failures with a clear error message
 *   - Unwraps the {"status","data"} envelope
 *   - Throws ApiError for both HTTP errors and {"status":"error"} responses
 *
 * All WebSocket connections go through `createWsConnection` which returns a
 * WsHandle (send / close / readyState). React hooks consume this handle via
 * useRef inside a useEffect — see frontend/src/hooks/useWebSocket.ts.
 */

import type {
  AnomalyRequest,
  BatchImageryRequest,
  BatchImageryResultPayload,
  BatchImageryProgressPayload,
  ClimatologyRequest,
  DownloaderSearchRequest,
  DownloaderSearchResponse,
  FileMetadata,
  HealthResponse,
  HovmollerRenderRequest,
  HovmollerRenderResponse,
  IndexResult,
  IndicesRequest,
  MapRenderRequest,
  MapRenderResponse,
  PreviewRequest,
  ProcessedFileResult,
  SliceResult,
  SourcesData,
  SpatialMeanRequest,
  SpatialMeanResult,
  TaylorRenderRequest,
  TaylorRenderResponse,
  VariablesResponse,
  WsBatchImageryMessage,
  WsDownloadMessage,
  WsHandle,
  WsMessage,
  WsProgressPayload,
} from "./types";

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

const BASE_URL = "http://localhost:8000";
const WS_BASE  = "ws://localhost:8000";

// ─────────────────────────────────────────────────────────────────────────────
// Error class
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Thrown by all client functions on any failure:
 *   - Network / fetch error
 *   - Non-JSON server response
 *   - {"status":"error"} response from the backend
 */
export class ApiError extends Error {
  readonly detail: string;

  constructor(message: string, detail = "") {
    super(message);
    this.name = "ApiError";
    this.detail = detail;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Central fetch wrapper. Handles all error cases and unwraps the API envelope.
 * All public client functions funnel through here.
 */
async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${BASE_URL}${endpoint}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers ?? {}),
      },
      ...options,
    });
  } catch (cause) {
    throw new ApiError(
      "Network error — is the backend running on port 8000?",
      cause instanceof Error ? cause.message : String(cause),
    );
  }

  // The backend always sends JSON. Parse it regardless of HTTP status.
  let envelope: { status: string; data?: T; error?: string; detail?: string };
  try {
    envelope = await response.json() as typeof envelope;
  } catch {
    const text = await response.text().catch(() => "(unreadable)");
    throw new ApiError(
      `Server returned a non-JSON response (HTTP ${response.status})`,
      text,
    );
  }

  if (envelope.status === "error") {
    throw new ApiError(envelope.error ?? "Unknown server error", envelope.detail ?? "");
  }

  // envelope.status === "ok" — data is always present
  return envelope.data as T;
}

async function post<TReq, TRes>(endpoint: string, body: TReq): Promise<TRes> {
  return apiFetch<TRes>(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

async function get<TRes>(endpoint: string): Promise<TRes> {
  return apiFetch<TRes>(endpoint, { method: "GET" });
}

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket utility
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Open a typed WebSocket connection to a backend endpoint.
 *
 * The returned WsHandle is intended to be stored in a React ref and cleaned
 * up in a useEffect destructor — see hooks/useWebSocket.ts.
 *
 * @param endpoint  - Path starting with "/ws/", e.g. "/ws/download"
 * @param onMessage - Called on every parsed server message (progress/result/error)
 * @param onOpen    - Called when the connection is established
 * @param onClose   - Called when the connection closes (after cleanup)
 *
 * @example
 * const handle = createWsConnection<DownloadResult, WsDownloadProgressPayload>(
 *   "/ws/download",
 *   (msg) => {
 *     if (msg.type === "progress") setPercent(msg.payload.percent);
 *     if (msg.type === "result")   setFiles(msg.payload.files);
 *     if (msg.type === "error")    setError(msg.payload.error);
 *   },
 *   () => handle.send(downloadRequest),
 * );
 */
export function createWsConnection<
  TResult,
  TProgress extends WsProgressPayload = WsProgressPayload,
>(
  endpoint: string,
  onMessage: (msg: WsMessage<TResult, TProgress>) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WsHandle {
  const ws = new WebSocket(`${WS_BASE}${endpoint}`);

  ws.addEventListener("open", () => onOpen?.());

  ws.addEventListener("close", () => onClose?.());

  ws.addEventListener("message", (event: MessageEvent<string>) => {
    try {
      const msg = JSON.parse(event.data) as WsMessage<TResult, TProgress>;
      onMessage(msg);
    } catch {
      console.error("[ws] Failed to parse message:", event.data);
    }
  });

  // The WebSocket "error" event carries no useful diagnostic — the "close"
  // event that immediately follows will have a code and reason.
  ws.addEventListener("error", () => {
    console.error("[ws] Error on", endpoint);
  });

  return {
    send: (data: unknown) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
      } else {
        console.warn("[ws] send() called before connection is open on", endpoint);
      }
    },
    close: () => ws.close(),
    get readyState() {
      return ws.readyState;
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Module: health
// ─────────────────────────────────────────────────────────────────────────────

export const health = {
  /**
   * Poll this at startup to confirm the Python backend is ready.
   * The Electron main process should expose the app window only after
   * this resolves without throwing.
   */
  check: (): Promise<HealthResponse> =>
    get<HealthResponse>("/api/health"),
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Module B: processor
// ─────────────────────────────────────────────────────────────────────────────

export const processor = {
  /**
   * Extract metadata from a NetCDF file without loading any data arrays.
   * Returns variables, coordinates, global attributes, and derived info
   * (time frequency, grid resolution, available pressure levels).
   * Fast even for files exceeding 50 GB.
   */
  getMetadata: (path: string): Promise<FileMetadata> =>
    post<{ path: string }, FileMetadata>("/api/processor/metadata", { path }),

  /**
   * List all data variables in a file together with their shape, units, and
   * dimension names. Also returns available pressure levels when present.
   *
   * Use this to populate the variable selector before any heavy computation.
   */
  listVariables: (path: string): Promise<VariablesResponse> =>
    post<{ path: string }, VariablesResponse>("/api/processor/variables", { path }),

  /**
   * Compute the climatological mean over a reference period and save to disk.
   *
   * The default base period is 1991–2020 (WMO standard). Pressure level
   * selection (plev_levels) is applied before any data enters memory —
   * critical for large 4D atmospheric files.
   *
   * Returns the output file path and the shape of the saved array.
   */
  computeClimatology: (req: ClimatologyRequest): Promise<ProcessedFileResult> =>
    post<ClimatologyRequest, ProcessedFileResult>("/api/processor/climatology", req),

  /**
   * Compute anomalies (x′ = x − x̄) and save to disk.
   *
   * If climatology_path is provided, the pre-computed climatology file is
   * loaded (useful when reusing the same baseline across multiple variables).
   * If omitted, the climatology is computed inline from the same dataset.
   */
  computeAnomaly: (req: AnomalyRequest): Promise<ProcessedFileResult> =>
    post<AnomalyRequest, ProcessedFileResult>("/api/processor/anomaly", req),

  /**
   * Compute the area-weighted spatial mean time series.
   *
   * Cosine-latitude weighting is always applied — unweighted spatial averages
   * are not offered because they are scientifically incorrect.
   * An optional bounding box restricts the average to a sub-region.
   */
  computeSpatialMean: (req: SpatialMeanRequest): Promise<SpatialMeanResult> =>
    post<SpatialMeanRequest, SpatialMeanResult>("/api/processor/spatial-mean", req),

  /**
   * Extract a single 2-D lat/lon slice for immediate frontend rendering.
   *
   * Only the selected time step and pressure level are computed — the rest of
   * the file stays on disk. NaN values are returned as null in the grid.
   */
  getPreview: (req: PreviewRequest): Promise<SliceResult> =>
    post<PreviewRequest, SliceResult>("/api/processor/preview", req),

  /**
   * Compute a standard climate index and return a JSON time series.
   *
   * **ENSO** (`nino34`, `nino3`, `nino4`, `nino12`, `oni`):
   *   Area-weighted SST anomaly in the Niño box. Pass the SST variable name
   *   (e.g. "tos" for CMIP6, "sst" for ERA5-derived products).
   *
   * **NAO** (`nao`):
   *   Station-based Hurrell (1995) index: normalised SLP anomaly difference
   *   between Azores and Iceland boxes. Pass the SLP variable (e.g. "psl").
   *
   * **ETCCDI** (`rx1day`, `rx5day`, `r95p`, `prcptot`, `cdd`, `cwd`):
   *   Require daily precipitation. Units are auto-converted from kg m⁻² s⁻¹.
   *   The response always contains the global weighted mean. If output_path
   *   is set, the full spatial field is also saved to that NetCDF file.
   */
  computeIndex: (req: IndicesRequest): Promise<IndexResult> =>
    post<IndicesRequest, IndexResult>("/api/processor/indices", req),
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Module A: downloader
// ─────────────────────────────────────────────────────────────────────────────

export const downloader = {
  /** Return metadata for all supported data sources (used to build the source selector UI). */
  getSources: (): Promise<SourcesData> =>
    get<SourcesData>("/api/downloader/sources"),

  /** Search a specific source for datasets matching the query. */
  search: (source: string, req: DownloaderSearchRequest): Promise<DownloaderSearchResponse> =>
    post<DownloaderSearchRequest, DownloaderSearchResponse>(
      `/api/downloader/${source}/search`,
      req,
    ),
} as const;

/**
 * Open the /ws/download WebSocket endpoint and return a WsHandle.
 *
 * In `onOpen`, call `handle.send(request)` via the returned WsHandle (or a ref
 * to it) to start the download batch.  The `onMessage` callback receives typed
 * progress/result/error events.
 *
 * WsDownloadMessage uses different field names than the generic WsProgressPayload,
 * so we open the connection with loose types and re-cast inside the callback.
 */
export function createDownloadWs(
  onMessage: (msg: WsDownloadMessage) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WsHandle {
  return createWsConnection<unknown, WsProgressPayload>(
    "/ws/download",
    (raw) => onMessage(raw as unknown as WsDownloadMessage),
    onOpen,
    onClose,
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Module C: imagery
// ─────────────────────────────────────────────────────────────────────────────

export const imagery = {
  /** Render a single cartopy map and save to disk. Returns output path + dimensions. */
  renderMap: (req: MapRenderRequest): Promise<MapRenderResponse> =>
    post<MapRenderRequest, MapRenderResponse>("/api/imagery/render-map", req),

  /** Render a Hovmöller diagram (time × lat or time × lon). */
  renderHovmoller: (req: HovmollerRenderRequest): Promise<HovmollerRenderResponse> =>
    post<HovmollerRenderRequest, HovmollerRenderResponse>("/api/imagery/render-hovmoller", req),

  /** Render a Taylor diagram comparing multiple models against a reference. */
  renderTaylor: (req: TaylorRenderRequest): Promise<TaylorRenderResponse> =>
    post<TaylorRenderRequest, TaylorRenderResponse>("/api/imagery/render-taylor", req),
} as const;

/**
 * Open the /ws/imagery/batch WebSocket and return a WsHandle.
 *
 * In `onOpen`, call `handle.send(request)` via a ref to start the batch.
 * The `onMessage` callback receives typed progress/result/error events.
 */
export function createBatchImageryWs(
  onMessage: (msg: WsBatchImageryMessage) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WsHandle {
  return createWsConnection<unknown, WsProgressPayload>(
    "/ws/imagery/batch",
    (raw) => onMessage(raw as unknown as WsBatchImageryMessage),
    onOpen,
    onClose,
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Default export — convenience bundle for components that need all modules
// ─────────────────────────────────────────────────────────────────────────────

const api = { health, processor, downloader, imagery } as const;

export default api;
