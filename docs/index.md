# NetCDF Studio

**NetCDF Studio** is an open-source desktop application for climatologists and meteorologists that brings together the most common climate data workflows into a single, reproducible environment.

---

## What it does

Working with climate model output typically requires switching between a web browser (to find and download data), a terminal (to run processing scripts), a separate plotting tool, and a dashboard for exploration. NetCDF Studio replaces this fragmented workflow with five integrated modules:

| Module | Name | What it does |
|---|---|---|
| **A** | Downloader | Search and download from ESGF, Copernicus CDS, World Bank CCKP, NASA/NOAA AWS, and ESA CCI — in parallel, with automatic folder organisation |
| **B** | Processor | Compute climatologies, anomalies, area-weighted means, and standard climate indices (ENSO, NAO, ETCCDI) using xarray and dask |
| **C** | Map imagery | Generate publication-ready cartopy maps in batch — hundreds of files with a single configuration |
| **D** | Visual workbench | Interactive, synchronised multi-panel dashboards with Hovmöller diagrams and Taylor diagrams |
| **E** | MCP interface | Natural language control of all modules via Claude or any MCP-compatible LLM |

---

## Supported data sources

=== "ESGF"
    **Earth System Grid Federation** — CMIP3, CMIP5, CMIP6, CORDEX, obs4MIPs.
    Requires an OpenID account for some nodes. Automatic node failover is built in.

=== "Copernicus CDS"
    **ECMWF Climate Data Store** — ERA5 reanalysis (1940–present), ERA5-Land, CMIP6 projections, seasonal forecasts.
    Requires a free API key from [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu).

=== "World Bank CCKP"
    **Climate Knowledge Portal** — CMIP6 downscaled and bias-corrected data (0.25°), ERA5 (0.25°), CRU (0.5°).
    No account required. Accessed via anonymous S3.

=== "NASA / NOAA AWS"
    **AWS Open Data Registry** — CESM Large Ensemble (40 members, 1920–2100), CMAQ, Argo floats, AIRS satellite.
    No account required. Accessed via anonymous S3.

=== "ESA CCI"
    **Climate Change Initiative** — 27 Essential Climate Variables including SST, soil moisture, ozone, sea level, and glaciers.
    Requires a free registration at [climate.esa.int](https://climate.esa.int).

---

## Quick start

### 1. Install

```bash
# Create the conda environment
conda env create -f backend/environment.yml
conda activate netcdf-studio

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Start the app

```bash
cd frontend
npm run electron:dev
```

The Electron shell will open automatically once the Python backend is ready.

### 3. Backend API only (for development or scripting)

```bash
uvicorn backend.main:app --reload --port 8000
```

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Architecture overview

```
┌──────────────────────────────────────────────────────┐
│  Electron shell (Node.js)                            │
│  Spawns the Python backend · Opens the browser window│
└──────────────────────┬───────────────────────────────┘
                       │ child_process
┌──────────────────────▼───────────────────────────────┐
│  React + TypeScript (Vite)          port 5173 (dev)  │
│  Tailwind CSS · Plotly.js (Module D)                 │
│  Zustand global state                                │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP REST + WebSocket
┌──────────────────────▼───────────────────────────────┐
│  FastAPI (Python 3.11)              port 8000         │
│  REST  → single operations (metadata, climatology…)  │
│  WS    → batch/long-running tasks (downloads, maps…) │
└──────────────────────┬───────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   xarray + dask    cartopy      FastMCP
   (Modules A-B)  (Module C)   (Module E)
```

---

## Scientific design principles

NetCDF Studio enforces scientific correctness at the library level — not just in documentation.

**Area-weighted averages**
:   Every spatial mean uses cosine-latitude weighting. The raw `da.mean(['lat', 'lon'])` function is never used internally.

**Configurable base periods**
:   Climatology reference periods default to 1991–2020 (current WMO standard) but are always a user parameter. No base period is hardcoded.

**Memory-safe pressure level loading**
:   Pressure level selection happens at file-open time, before any data is read into memory. Loading a full 4D atmospheric file (which can exceed 50 GB) and then subsetting is not permitted.

**Conservative regridding**
:   `xesmf` conservative regridding is the default. Bilinear interpolation is offered only for variables where conservation of the quantity is not required.

**Non-standard calendars**
:   CMIP6 models use 360-day and `noleap` calendars. All time-axis operations use `cftime` and `nc-time-axis` to handle these correctly.

---

## Climate indices (Module B)

### ENSO

| Index | Box | Description |
|---|---|---|
| Niño 3.4 | 5°S-5°N, 170°W-120°W | Primary ENSO monitoring index |
| Niño 3 | 5°S-5°N, 150°W-90°W | Eastern tropical Pacific |
| Niño 4 | 5°S-5°N, 160°E-150°W | Central tropical Pacific |
| Niño 1+2 | 10°S-0°, 90°W-80°W | Eastern Pacific coast |
| ONI | — | 3-month running mean of Niño 3.4 (NOAA/CPC definition) |

### NAO

Station-based NAO (Hurrell 1995): normalised SLP anomaly difference between the Azores and Iceland, computed on box averages for robustness with coarse-resolution models.

### ETCCDI precipitation extremes (daily data required)

| Index | Description |
|---|---|
| Rx1day | Monthly maximum 1-day precipitation |
| Rx5day | Monthly maximum consecutive 5-day total |
| R95p | Annual total precipitation on days > 95th percentile |
| PRCPTOT | Annual total wet-day precipitation |
| CDD | Annual maximum consecutive dry days |
| CWD | Annual maximum consecutive wet days |

---

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup, code conventions, and scientific correctness requirements.

Bug reports and feature requests: [GitHub Issues](https://github.com/BlipTheClip/netcdf-studio/issues)

---

## License

NetCDF Studio is released under the [MIT License](../LICENSE).
