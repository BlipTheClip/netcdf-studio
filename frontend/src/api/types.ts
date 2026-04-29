/**
 * API type definitions for NetCDF Studio.
 *
 * Every interface here mirrors a backend Pydantic model or dataclass exactly,
 * using the same snake_case field names as the JSON wire format.
 * Do not camelCase these — it avoids a transformation layer and keeps
 * backend/frontend in sync by name.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Generic API envelope
// ─────────────────────────────────────────────────────────────────────────────

export interface ApiOk<T> {
  status: "ok";
  data: T;
}

export interface ApiErrorResponse {
  status: "error";
  error: string;
  detail: string;
}

export type ApiEnvelope<T> = ApiOk<T> | ApiErrorResponse;

// ─────────────────────────────────────────────────────────────────────────────
// Health
// ─────────────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: "ok";
  version: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Core NetCDF data types
// Mirrors: backend/core/netcdf/loader.py  (VariableInfo, CoordinateInfo, FileMetadata)
// ─────────────────────────────────────────────────────────────────────────────

export interface VariableInfo {
  name: string;
  long_name: string;
  units: string;
  dimensions: string[];
  shape: number[];
  dtype: string;
}

export interface CoordinateInfo {
  time_start: string | null;
  time_end: string | null;
  time_steps: number | null;
  lat_min: number | null;
  lat_max: number | null;
  lat_n: number | null;
  lon_min: number | null;
  lon_max: number | null;
  lon_n: number | null;
  plev_levels: number[] | null;
  plev_units: string | null;
}

export interface FileMetadata {
  path: string;
  file_size_mb: number;
  variables: Record<string, VariableInfo>;
  coordinates: CoordinateInfo;
  global_attrs: Record<string, string>;
  has_plev: boolean;
  time_frequency: TimeFrequency | null;
  lat_lon_resolution_deg: number | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Module B — Processor
// Request bodies (mirror Pydantic models in backend/api/routes/processor.py)
// ─────────────────────────────────────────────────────────────────────────────

/** Temporal grouping for climatology / anomaly computation. */
export type ClimatologyFreq = "month" | "dayofyear";

export interface ClimatologyRequest {
  path: string;
  variable: string;
  output_path: string;
  /** First year of the reference period (inclusive). Default: 1991. */
  start_year?: number;
  /** Last year of the reference period (inclusive). Default: 2020. */
  end_year?: number;
  /** Default: "month" (12 climatological values). */
  freq?: ClimatologyFreq;
  /** Pressure levels to select before loading. Null = all levels. */
  plev_levels?: number[] | null;
}

export interface AnomalyRequest {
  path: string;
  variable: string;
  output_path: string;
  start_year?: number;
  end_year?: number;
  freq?: ClimatologyFreq;
  plev_levels?: number[] | null;
  /**
   * Path to a pre-computed climatology NetCDF file produced by
   * `computeClimatology`. If omitted the climatology is computed inline.
   */
  climatology_path?: string | null;
}

export interface SpatialMeanRequest {
  path: string;
  variable: string;
  plev_levels?: number[] | null;
  /** Bounding box in degrees. Defaults to global extent (-90/90/-180/180). */
  lat_min?: number;
  lat_max?: number;
  lon_min?: number;
  lon_max?: number;
}

export interface PreviewRequest {
  path: string;
  variable: string;
  /** Integer index along the time axis. Default: 0. */
  time_index?: number;
  /** Pressure level value (same units as the file). Null = first level. */
  plev_level?: number | null;
  /** Levels to select when opening the file (applied before loading). */
  plev_levels?: number[] | null;
}

/** All available climate index identifiers. */
export type IndexName =
  | "nino34"
  | "nino3"
  | "nino4"
  | "nino12"
  | "oni"
  | "nao"
  | "rx1day"
  | "rx5day"
  | "r95p"
  | "prcptot"
  | "cdd"
  | "cwd";

export interface IndicesRequest {
  path: string;
  index: IndexName;
  /**
   * Variable name in the file.
   * Typical: "tos" / "sst" (ENSO), "psl" / "msl" (NAO), "pr" / "tp" (ETCCDI).
   */
  variable: string;
  /**
   * (ETCCDI only) Save the full spatial field (time × lat × lon) to this path.
   * The JSON response always contains the global weighted mean regardless.
   */
  output_path?: string | null;
  start_year?: number;
  end_year?: number;
  plev_levels?: number[] | null;
  /** Running-mean window for ONI in months. Default: 3. */
  oni_window?: number;
  /** Wet/dry day threshold for CDD, CWD, PRCPTOT in mm/day. Default: 1.0. */
  pr_threshold_mm_day?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Module B — Processor response data shapes
// (the `data` field inside ApiOk<T>)
// ─────────────────────────────────────────────────────────────────────────────

export interface VariablesResponse {
  variables: VariableInfo[];
  has_plev: boolean;
  plev_levels: number[] | null;
  plev_units: string | null;
}

/** Returned by computeClimatology and computeAnomaly. */
export interface ProcessedFileResult {
  output_path: string;
  shape: number[];
}

export interface SpatialMeanResult {
  variable: string;
  units: string;
  /** ISO date strings, one per time step. */
  time: string[];
  /** Null where the value was NaN (e.g. masked ocean / land points). */
  values: (number | null)[];
}

export interface SliceResult {
  variable: string;
  units: string;
  /** Human-readable label for the selected time step (ISO string). */
  time_label: string;
  /** Human-readable label for the selected pressure level. Null if no plev dim. */
  plev_label: string | null;
  /** Latitude values in degrees north [n_lat]. */
  lat: number[];
  /** Longitude values in degrees east [n_lon]. */
  lon: number[];
  /** 2-D grid [n_lat][n_lon]. Null where the value was NaN. */
  values: (number | null)[][];
}

export interface IndexResult {
  index: IndexName;
  /** ISO date strings, one per time step. */
  time: string[];
  values: (number | null)[];
  units: string;
  long_name: string;
  /**
   * Only present for ETCCDI indices when output_path was requested.
   * Null if no file was saved.
   */
  output_path?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// WebSocket message types
// Mirrors: CLAUDE.md  {"type": "progress"|"result"|"error", "payload": {...}}
// ─────────────────────────────────────────────────────────────────────────────

export interface WsProgressPayload {
  current: number;
  total: number;
  /** 0–100, computed server-side. */
  percent: number;
  message: string;
}

/** Extended progress payload for Module A parallel downloads. */
export interface WsDownloadProgressPayload extends WsProgressPayload {
  file: string;
  speed_mbps: number;
  eta_seconds: number;
}

/** Extended progress payload for Module C batch image generation. */
export interface WsBatchProgressPayload extends WsProgressPayload {
  output_path: string;
}

export interface WsErrorPayload {
  error: string;
  detail: string;
}

export interface WsProgressMessage<P extends WsProgressPayload = WsProgressPayload> {
  type: "progress";
  payload: P;
}

export interface WsResultMessage<T> {
  type: "result";
  payload: T;
}

export interface WsErrorMessage {
  type: "error";
  payload: WsErrorPayload;
}

/**
 * Discriminated union for all WebSocket messages.
 *
 * @typeParam TResult  - Shape of the final result payload.
 * @typeParam TProgress - Shape of the progress payload (defaults to base type).
 *
 * Usage in a switch:
 * ```ts
 * switch (msg.type) {
 *   case "progress": ... msg.payload.percent ...
 *   case "result":   ... msg.payload ...
 *   case "error":    ... msg.payload.error ...
 * }
 * ```
 */
export type WsMessage<
  TResult,
  TProgress extends WsProgressPayload = WsProgressPayload,
> = WsProgressMessage<TProgress> | WsResultMessage<TResult> | WsErrorMessage;

// ─────────────────────────────────────────────────────────────────────────────
// Helper / union types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Temporal frequency strings returned by the loader's metadata extraction.
 * Match the values from backend/core/netcdf/loader.py::_infer_time_frequency.
 */
export type TimeFrequency = "1hr" | "3hr" | "6hr" | "day" | "mon" | "season" | "yr";

/** Opaque handle returned by createWsConnection. */
export interface WsHandle {
  send: (data: unknown) => void;
  close: () => void;
  readonly readyState: number;
}

/** Descriptive labels for display in the UI. */
export const INDEX_LABELS: Record<IndexName, string> = {
  nino34: "Niño 3.4",
  nino3:  "Niño 3",
  nino4:  "Niño 4",
  nino12: "Niño 1+2",
  oni:    "ONI",
  nao:    "NAO",
  rx1day: "Rx1day",
  rx5day: "Rx5day",
  r95p:   "R95p",
  prcptot:"PRCPTOT",
  cdd:    "CDD",
  cwd:    "CWD",
} as const;

export const TIME_FREQUENCY_LABELS: Record<TimeFrequency, string> = {
  "1hr":    "Hourly",
  "3hr":    "3-hourly",
  "6hr":    "6-hourly",
  day:      "Daily",
  mon:      "Monthly",
  season:   "Seasonal",
  yr:       "Annual",
} as const;
