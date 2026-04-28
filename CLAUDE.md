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