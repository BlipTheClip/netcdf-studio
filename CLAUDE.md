# CLAUDE.md — NetCDF Studio

This file provides Claude Code with full context about the project architecture, conventions, and decisions already made. Read this before touching any file.

---

## Project Summary

**NetCDF Studio** is an open-source desktop application for climatologists and meteorologists. It has 5 modules:

- **Module A** — ESGF dataset downloader (parallel, auto-merge, auto-folder)
- **Module B** — NetCDF data processor (xarray/dask, climatologies, anomalies, indices)
- **Module C** — Map image generator (matplotlib/cartopy, batch, preview)
- **Module D** — Visual workbench (synchronized multi-panel dashboards, Hovmöller, Taylor diagrams)
- **Module E** — MCP interface (FastMCP, natural language AI control of all modules)

---

## Architecture

### Frontend
- **Electron** (desktop shell) + **React** + **TypeScript**
- **Tailwind CSS** for styling
- **Plotly.js** for interactive visualizations in Module D
- Located in `/frontend/`
- Each module has its own folder under `/frontend/src/modules/`
- Communication with backend via `/frontend/src/api/client.ts`

### Backend
- **Python 3.10+** with **FastAPI**
- Runs locally on `http://localhost:8000`
- REST for standard operations, WebSockets for long-running tasks with progress
- Located in `/backend/`
- Each module has its own router under `/backend/api/routes/`

### MCP Server
- **FastMCP** (Python)
- Located in `/backend/mcp/`
- Exposes all major backend functions as MCP tools
- Connects to Claude or any MCP-compatible LLM

---

## Cross-Platform Compatibility

NetCDF Studio targets **Windows, macOS, and Linux**. Every code and packaging decision must work on all three.

### Distribution
- Use **electron-builder** to produce platform installers:
  - Windows: `.exe` (NSIS installer) and optionally `.msi`
  - macOS: `.dmg` + code-signed `.app` bundle
  - Linux: `.AppImage` (primary), `.deb`, `.rpm`
- The conda environment is bundled or the installer bootstraps miniconda — the user should never need to run `conda` manually.
- The Electron main process must locate the Python interpreter relative to the bundle, not from `PATH`.

### Path handling
- **Never hardcode path separators.** Use `pathlib.Path` in Python and `path.join()` / `path.resolve()` in Node.js/TypeScript.
- In Python, always call `str(path)` when passing to xarray/netCDF4 (they do not accept `Path` objects on all platforms).
- In Electron, use `path.join(app.getPath('userData'), ...)` for user data, never `__dirname` strings with manual separators.

### xesmf on Windows
- xesmf depends on ESMF, which has no official Windows conda package on conda-forge as of 2024.
- **Workaround**: xesmf is an optional dependency. Wrap every import in `try/except ImportError` and degrade gracefully (disable the regrid UI panel, show a banner explaining ESMF is unavailable on Windows).
- In `regridder.py`, the `ImportError` guard is already in place — do not remove it.
- The installation README must document: "xesmf/ESMF are not available on native Windows. Use WSL2 or a Linux/macOS machine if conservative regridding is required."
- Alternatively, if running under WSL2, xesmf works normally — detect via `platform.system() == "Linux"` inside a Windows build.

### Platform-specific gotchas
- **Windows file locking**: NetCDF files opened with netCDF4/HDF5 are write-locked. Always call `ds.close()` (or use a context manager) before attempting to overwrite an output file.
- **macOS Gatekeeper**: The app bundle must be code-signed and notarized for distribution. CI should use `electron-builder`'s `--publish` flag with Apple credentials.
- **Linux font rendering**: cartopy maps use matplotlib fonts — ensure `matplotlib.font_manager.rebuild()` is called on first run if fonts are missing.
- **Windows console encoding**: Set `PYTHONUTF8=1` in the Electron main process's environment before spawning the Python subprocess to avoid cp1252 encoding errors in log output.

---

## Key Technical Decisions

### Why Electron (not Tauri)
Electron was chosen because Node.js's `child_process` makes it straightforward to launch and communicate with the Python backend. Tauri's Rust core complicates Python subprocess management.

### Why FastAPI (not Flask)
FastAPI has native async/await support (critical for parallel ESGF downloads with asyncio) and native WebSocket support (needed for real-time download/batch progress). It also auto-generates OpenAPI docs that the MCP layer can leverage.

### Why REST + WebSockets (not WebSockets only)
- REST for: load file metadata, compute single climatology, generate single image, list files
- WebSockets for: batch downloads (50+ models in parallel), batch image generation (hundreds of files)

### Data Processing Stack
- **xarray** — primary data structure for all NetCDF operations
- **dask** — lazy loading, out-of-core computation for large files
- **ALWAYS use dask chunks** when opening files: `xr.open_dataset(path, chunks='auto')`
- **xesmf** — conservative regridding between grids
- **matplotlib + cartopy** — map generation (NOT interactive, only for final image export)
- **Plotly.js** (frontend only) — interactive visualization in Module D

### Memory Management
- Pressure level (`plev`) selection MUST happen at file open time using `xr.open_dataset(...).sel(plev=selected_levels)` BEFORE loading to memory
- Batch image generation must respect a user-defined RAM limit (configurable in UI)
- Use `dask.compute()` only when actually needed for output

---

## Folder Structure

```
netcdf-studio/
├── frontend/
│   ├── electron/
│   │   └── main.ts              # Electron main process
│   ├── src/
│   │   ├── modules/
│   │   │   ├── downloader/      # Module A components
│   │   │   ├── processor/       # Module B components
│   │   │   ├── imagery/         # Module C components
│   │   │   └── visualizer/      # Module D components
│   │   ├── components/          # Shared: Button, Slider, FileSelector, etc.
│   │   ├── hooks/               # useWebSocket, useBackendStatus, etc.
│   │   ├── api/
│   │   │   └── client.ts        # All HTTP + WebSocket calls to backend
│   │   ├── store/               # Global state (Zustand)
│   │   └── App.tsx
│   ├── package.json
│   └── tsconfig.json
│
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── downloader.py    # /api/downloader/*
│   │   │   ├── processor.py     # /api/processor/*
│   │   │   ├── imagery.py       # /api/imagery/*
│   │   │   └── visualizer.py    # /api/visualizer/*
│   │   └── ws/
│   │       ├── download_ws.py   # WebSocket for download progress
│   │       └── batch_ws.py      # WebSocket for batch image progress
│   ├── core/
│   │   ├── netcdf/
│   │   │   ├── loader.py        # Open/close NetCDF, metadata extraction
│   │   │   ├── processor.py     # Anomalies, climatologies, area-weighting
│   │   │   ├── regridder.py     # xesmf wrapper
│   │   │   └── indices.py       # ENSO, NAO, precipitation extremes
│   │   ├── plotting/
│   │   │   ├── maps.py          # cartopy map generation
│   │   │   ├── hovmoller.py     # Hovmöller diagrams
│   │   │   └── taylor.py        # Taylor diagrams
│   │   └── downloader/
│   │       ├── base.py          # Abstract base class for all connectors
│   │       ├── esgf.py          # ESGF API client (esgf-pyclient)
│   │       ├── copernicus.py    # Copernicus CDS connector (cdsapi) — ERA5
│   │       ├── worldbank.py     # World Bank CCKP connector (S3 boto3)
│   │       ├── nasa_aws.py      # NASA/NOAA AWS Open Data connector (S3 boto3)
│   │       ├── esa_cci.py       # ESA Climate Change Initiative connector
│   │       └── parallel.py      # asyncio parallel download manager
│   ├── mcp/
│   │   └── server.py            # FastMCP server exposing all tools
│   ├── main.py                  # FastAPI app entry point
│   └── environment.yml          # Conda environment
│
├── docs/                        # MkDocs
├── examples/
│   └── sample_data/             # Small .nc file for testing
├── CLAUDE.md                    # This file
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

---

## Coding Conventions

### Python (backend)
- Python 3.10+, type hints everywhere
- `async def` for all FastAPI route handlers
- All core functions in `/core/` must be pure functions (no side effects, easy to test)
- Error handling: always return structured JSON errors `{"error": "message", "detail": "..."}`
- Logging: use Python's `logging` module, not `print()`
- Never load full 4D arrays into memory without dask chunks

### TypeScript (frontend)
- Strict TypeScript mode enabled
- All API responses must have corresponding TypeScript interfaces in `/src/api/types.ts`
- State management with **Zustand** (not Redux — simpler for this project)
- Each module is self-contained: its own components, hooks, and local state

### API Design
- All REST endpoints prefixed with `/api/`
- WebSocket endpoints prefixed with `/ws/`
- REST responses always include `{"status": "ok"|"error", "data": ...}`
- WebSocket messages always include `{"type": "progress"|"result"|"error", "payload": ...}`

---

## Module Implementation Priority

Implement in this order:
1. **Backend core/netcdf/loader.py** — foundation everything else depends on
2. **Backend api/routes/processor.py** — verify data flows correctly
3. **Frontend Module B** — test the full stack with a real .nc file
4. **Backend core/downloader/** — ESGF integration
5. **Frontend Module A** — download UI
6. **Backend core/plotting/maps.py** — image generation
7. **Frontend Module C** — image generator UI
8. **Module D** — visual workbench (most complex frontend work)
9. **Module E (MCP)** — expose everything via FastMCP

---

## Estado actual del desarrollo

| Módulo | Backend | Frontend |
|--------|---------|----------|
| A — Downloader | ✅ Completo | ✅ Completo |
| B — Processor  | ✅ Completo | ✅ Completo |
| C — Imagery    | ✅ Completo | ✅ Completo |
| D — Visualizer | ⬜ Pendiente | ⬜ Pendiente |
| E — MCP        | ⬜ Pendiente | — (sin UI) |

**Próximo paso:** Backend Module D — Visual workbench (`frontend/src/modules/visualizer/` + `backend/api/routes/visualizer.py`).

### Resumen de lo implementado

**Module B — Processor (backend)**
- `backend/core/netcdf/_coords.py` — detección de coordenadas (lat/lon/plev/time) compartida
- `backend/core/netcdf/loader.py` — metadatos sin cargar datos, detección de frecuencia temporal, resolución de grilla
- `backend/core/netcdf/processor.py` — climatologías, anomalías, media espacial con pesos coseno-latitud
- `backend/core/netcdf/regridder.py` — wrapper xesmf con guard `try/except ImportError` para Windows
- `backend/core/netcdf/indices.py` — 12 índices: ENSO (Niño 3.4/3/4/1+2/ONI), NAO, 6 ETCCDI de precipitación
- `backend/api/routes/processor.py` — REST: `/api/processor/{metadata,variables,climatology,anomaly,spatial-mean,preview,indices}`

**Module A — Downloader (backend)**
- `backend/core/downloader/base.py` — ABC + dataclasses `SearchQuery`/`Dataset`/`Progress` + helpers `_http_stream`/`_s3_download`
- `backend/core/downloader/parallel.py` — descarga paralela con `asyncio.Semaphore` + `asyncio.Queue`
- `backend/core/downloader/esgf.py` — pyesgf, failover 4 nodos, descarga HTTPS
- `backend/core/downloader/copernicus.py` — cdsapi en executor, polling de tamaño de archivo para progreso
- `backend/core/downloader/worldbank.py` — boto3 UNSIGNED, `s3://wbg-cckp/`
- `backend/core/downloader/nasa_aws.py` — boto3 UNSIGNED, CESM-LE + Argo
- `backend/core/downloader/esa_cci.py` — catálogo CEDA REST, httpx, Basic auth por env vars
- `backend/api/routes/downloader.py` — GET `/api/downloader/sources`, POST `/api/downloader/{source}/search`, WS `/ws/download`

**Module B — Processor (frontend)**
- `frontend/src/store/processorStore.ts` — Zustand store (filePath, metadata, results, activeTab)
- `ProcessorPage`, `FileLoader`, `MetadataPanel`, `VariableSelector`, `PlevSelector` (chips)
- `ClimatologyForm`, `AnomalyForm`, `SpatialMeanPanel` (Plotly lazy), `PreviewPanel` (heatmap lazy), `IndicesPanel` (12 índices, Plotly lazy)

**Module C — Imagery (frontend)**
- `frontend/src/api/types.ts` — ProjectionName, MapRenderRequest/Response, HovmollerRenderRequest/Response, TaylorModelItem/RenderRequest/Response, BatchImageryJob/Request/Progress/Result, WsBatchImageryMessage
- `frontend/src/api/client.ts` — imagery.renderMap/renderHovmoller/renderTaylor, createBatchImageryWs
- `frontend/src/hooks/useFileMetadata.ts` — browse dialog → getMetadata → variables + plev levels
- `frontend/src/store/imageryStore.ts` — Zustand: activeTab, map/hovmoller/taylor previews, Taylor models list, batch jobs + progress + result
- `ImageryPage.tsx` — 4 tabs: Map | Hovmöller | Taylor | Batch
- `MapForm.tsx` — proyección (7), colormap, bbox, quiver config, render + preview
- `HovmollerForm.tsx` — modo lat/lon, dominio espacial, render + preview
- `TaylorForm.tsx` — tabla de modelos editable (std_ratio, corr, color, marker), render + preview
- `BatchForm.tsx` — lista de jobs editable, RAM slider, WS lifecycle con wsRef pattern
- `BatchProgress.tsx` — barras de progreso por job, resumen final, botón Back
- `ImagePreview.tsx` — file:// URL → `<img>` con normalización de paths Windows/Unix

**Module C — Imagery (backend)**
- `backend/core/plotting/maps.py` — `render_map()`: cartopy maps con 7 proyecciones, stippling estadístico, bounding box, coastlines, gridlines, colorbar
- `backend/core/plotting/hovmoller.py` — `render_hovmoller()`: diagramas tiempo×lat (avg lon) y tiempo×lon (avg lat con pesos coseno)
- `backend/core/plotting/taylor.py` — `render_taylor()`: diagrama de Taylor con contornos RMSE, arcos de std, puntos por modelo
- `backend/api/routes/imagery.py` — POST `/api/imagery/{render-map,render-hovmoller,render-taylor}`, WS `/ws/imagery/batch` (control de RAM con psutil)

**Module A — Downloader (frontend)**
- `frontend/src/store/downloaderStore.ts` — Zustand store (sources, search, selection, download state)
- `SourceSelector` — 5 tarjetas de fuentes con badge Free/Auth
- `SearchForm` — campos comunes + params específicos por fuente desde `_SOURCE_META`
- `SearchResults` — lista con checkboxes, chips de variables, tamaño, frecuencia
- `DownloadQueue` — destino, slider de concurrencia, botón Start
- `DownloadProgress` — barras de progreso por archivo, velocidad, resumen final
- WS lifecycle en `DownloaderPage`: `wsRef` + `createDownloadWs()`, envía request en `onOpen`

**Infraestructura frontend**
- Electron 33 + Vite 6 + React 18 + TypeScript strict + Tailwind CSS
- `electron/main.ts` — spawn uvicorn, poll `/api/health` (30s), IPC para diálogos nativos
- `electron/preload.ts` — `contextBridge` expone `window.electronAPI.openFile/saveFile`
- Hooks: `useBackendStatus` (poll cada 5s), `useWebSocket` (WsHandle en useRef)
- Componentes compartidos: Button, Input, Select, Card, Spinner, ErrorBanner

---

## Important Scientific Requirements

These are non-negotiable for scientific correctness:

1. **Area-weighted averages**: NEVER compute spatial averages without cosine-latitude weighting. Use `np.cos(np.deg2rad(ds.lat))` as weights in `ds.weighted(weights).mean()`.

2. **Climatology base period**: Always let the user define the reference period (default: 1991–2020). Never hardcode it.

3. **Anomaly formula**: x' = x - x̄ where x̄ is the climatological mean over the base period.

4. **Pressure level loading**: Always offer plev selection BEFORE loading data. Files with full 3D/4D atmospheric data can be 50GB+. Loading only the needed levels is mandatory, not optional.

5. **Regridding**: Use conservative regridding by default (xesmf). Bilinear is faster but not appropriate for conservation of quantities like precipitation.

---

## Known Challenges to Handle Carefully

- **ESGF authentication**: Some nodes require OpenID credentials. Use `esgf-pyclient` but implement fallback between nodes.
- **Multi-file merging**: Use `xr.open_mfdataset()` with `combine='by_coords'`. Watch for duplicate time steps between files.
- **Synchronized zoom in Module D**: Use Plotly's `relayout` events and broadcast to all panels via a shared Zustand store.
- **Statistical stippling**: Compute p-values with `scipy.stats`, create a boolean mask, and overlay as scatter points on the cartopy map.
- **Copernicus CDS async jobs**: CDS requests are queued server-side and can take minutes. Use polling with `cdsapi` status checks and report progress via WebSocket.
- **S3 anonymous access (WorldBank/NASA)**: Use `boto3` with `UNSIGNED` config. Never require AWS credentials for these sources.
- **ERA5 GRIB vs NetCDF**: CDS can return GRIB or NetCDF. Always request `'data_format': 'netcdf'` explicitly. Some ERA5 complete datasets require `'grid'` keyword to convert from native grid to regular lat/lon.
- **xesmf on Windows**: ESMF has no native Windows conda package. xesmf import is wrapped in `try/except ImportError` in `regridder.py` — keep it that way. See the Cross-Platform Compatibility section for the full workaround.

---

## Supported Data Sources (Module A)

All connectors inherit from `base.py` and implement a common interface:
```python
class DataSourceConnector:
    def search(self, query: SearchQuery) -> list[Dataset]: ...
    def download(self, dataset: Dataset, dest: Path) -> AsyncIterator[Progress]: ...
    def requires_auth(self) -> bool: ...
```

### 1. ESGF — Earth System Grid Federation
- **Content**: CMIP3, CMIP5, CMIP6, CORDEX, obs4MIPs
- **Library**: `esgf-pyclient`
- **Auth**: OpenID credentials (required for some nodes)
- **Key challenge**: Node reliability — implement fallback across multiple ESGF nodes
- **Auto-folder**: `ESGF/{institute}/{model}/{experiment}/{frequency}/{variable}/`

### 2. Copernicus CDS — ECMWF Climate Data Store
- **Content**: ERA5 reanalysis (1940–present), ERA5-Land, CMIP6 projections, seasonal forecasts
- **Library**: `cdsapi` (official ECMWF package)
- **Auth**: Free API key from https://cds.climate.copernicus.eu
- **Key feature**: Server-side pressure level and area subsetting — request only what you need
- **Key challenge**: Jobs are queued; implement async polling and WebSocket progress updates
- **Auto-folder**: `CDS/{dataset}/{variable}/{year}/`

### 3. World Bank CCKP — Climate Knowledge Portal
- **Content**: CMIP6 downscaled+bias-corrected (0.25°), ERA5 (0.25°), CRU (0.5°), population grids
- **Library**: `boto3` with anonymous S3 access (`s3://wbg-cckp/`)
- **Auth**: None required
- **Key feature**: Pre-processed and bias-corrected data — ideal for impact studies
- **Auto-folder**: `CCKP/{collection}/{variable}/`

### 4. NASA / NOAA — AWS Open Data Registry
- **Content**: CESM Large Ensemble (40 members, 1920–2100), CMAQ air quality, Argo ocean floats, AIRS satellite
- **Library**: `boto3` with anonymous S3 access
- **Auth**: None required
- **Key feature**: Massive ensembles available without registration
- **Auto-folder**: `NASA_AWS/{dataset}/{variable}/`

### 5. ESA CCI — Climate Change Initiative
- **Content**: 27 Essential Climate Variables (SST, soil moisture, ozone, glaciers, sea level, land cover...)
- **Library**: HTTP requests to CCI Open Data Portal
- **Auth**: Free registration at https://climate.esa.int
- **Key feature**: Long satellite records (up to 40 years) for ECVs not available in reanalysis
- **Auto-folder**: `ESA_CCI/{ecv}/{sensor}/`