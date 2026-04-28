# 🌍 NetCDF Studio

> A professional open-source desktop application for climatologists and meteorologists to download, process, and visualize NetCDF climate data — powered by an AI-native MCP interface.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Status](https://img.shields.io/badge/status-in%20development-orange)
![Stack](https://img.shields.io/badge/stack-Electron%20%2B%20React%20%2B%20FastAPI-informational)

---

## ✨ Overview

**NetCDF Studio** is a full-featured desktop application that brings together the entire climate data workflow in a single interface:

- 📥 **Download** — Browse and download datasets from ESGF nodes in parallel
- 🔬 **Process** — Manipulate variables, compute climatologies, anomalies, ensembles, and climate indices
- 🗺️ **Visualize** — Generate publication-quality maps with full control over colorbars, projections, and overlays
- 🤖 **AI Interface** — Describe what you want in plain language and let the AI execute the full workflow via MCP

---

## 🧩 Modules

### Module A — Multi-Source Climate Data Downloader

NetCDF Studio connects to **5 major public climate data repositories**, all from a single unified interface:

| Source | Content | Auth |
|---|---|---|
| **ESGF** | CMIP3/5/6, CORDEX, obs4MIPs | OpenID (free) |
| **Copernicus CDS** | ERA5 reanalysis (1940–present), ERA5-Land, seasonal forecasts | API key (free) |
| **World Bank CCKP** | CMIP6 downscaled+bias-corrected, CRU, ERA5 0.25° | None |
| **NASA/NOAA AWS** | CESM Large Ensemble (40 members), CMAQ, Argo ocean floats | None |
| **ESA CCI** | 27 Essential Climate Variables (SST, soil moisture, ozone, glaciers...) | Registration (free) |

Features:
- Unified search interface across all sources simultaneously
- Select multiple models/experiments and download in parallel
- Automatic folder structure: `{source}/{model}/{experiment}/{variable}/`
- Auto-merge multi-file datasets (e.g. files split by year) using `xr.open_mfdataset`
- Resume interrupted downloads
- Real-time progress per file via WebSocket
- Server-side subsetting where available (e.g. CDS pressure level and area selection before download)

### Module B — Data Processor
- Inspect metadata and dimensions of any `.nc` file
- Merge variables from different files into a single dataset
- Select specific pressure levels (`plev`) before loading to RAM — critical for 4D atmospheric data
- Subset by year range, season, latitude/longitude box
- Regrid between different grids using `xesmf` (conservative, bilinear)
- **Climatology computation** with custom base period (e.g. 1991–2020)
- **Anomaly calculation** (x' = x - x̄) spatial and temporal
- **Area-weighted spatial averages** (cosine-latitude weighting — prevents the classic polar averaging error)
- **Time series extraction** from a point (lat/lon) or averaged over a bounding box
- Ensemble generation (multi-model mean, spread)
- Standard climate indices: ENSO (Niño 3.4), NAO, precipitation extremes
- Export to `.csv`, `.nc`, or `GeoTIFF`

### Module C — Image Generator
- Choose colorbar, range, projection (PlateCarree, Mollweide, Polar, etc.)
- Add wind vectors with `quiver` (control arrow length/density)
- Composite images (overlay multiple variables)
- Mask ocean or land
- Mark points, regions, or non-convergence zones
- Statistical significance overlay (stippling / hatching for p < 0.05)
- Preview single image before batch generation
- Batch generation with RAM control (process N files at a time)
- Choose input folder and output format (PNG, PDF, SVG, EPS)
- Delete/replace bad images from within the app

### Module D — Visual Workbench
- **Multi-panel synchronized dashboards** (2×2, 3×3, custom) — zoom/pan syncs across all panels
- Compare same region across different models or emission scenarios (SSP245 vs SSP585)
- **Hovmöller diagrams** — Longitude/Latitude vs Time
- **Taylor diagrams** — Compare model skill (correlation, RMSE, std deviation) in a single plot
- Side-by-side comparison mode for different simulations

### Module E — MCP Interface (AI-Powered)
- Exposes all processing and visualization functions as MCP tools
- Connect to Claude or any MCP-compatible AI
- Natural language workflow: *"Generate the JJA climatology of temperature at 850hPa for CESM2 and compare it with ERA5"*
- The AI executes the full chain: load → subset plev → compute climatology → generate comparison map

---

## 🏗️ Architecture

```
netcdf-studio/
├── frontend/                  # Electron + React + TypeScript
│   ├── src/
│   │   ├── modules/
│   │   │   ├── downloader/    # Module A
│   │   │   ├── processor/     # Module B
│   │   │   ├── imagery/       # Module C
│   │   │   └── visualizer/    # Module D
│   │   ├── components/        # Shared UI components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── api/               # HTTP + WebSocket client
│   │   └── App.tsx
│   ├── electron/              # Main process
│   └── package.json
│
├── backend/                   # Python + FastAPI
│   ├── api/
│   │   ├── routes/            # REST endpoints per module
│   │   └── ws/                # WebSocket handlers
│   ├── core/
│   │   ├── netcdf/            # xarray, dask, xesmf processing
│   │   ├── plotting/          # matplotlib, cartopy image generation
│   │   ├── downloader/        # ESGF API, asyncio parallel downloads
│   │   └── indices/           # Climate indices (ENSO, NAO, etc.)
│   ├── mcp/                   # FastMCP server (Module E)
│   └── main.py
│
├── docs/                      # MkDocs documentation
├── examples/                  # Sample .nc files and workflow scripts
├── CLAUDE.md                  # Instructions for Claude Code
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

**Communication:**
- **REST** (HTTP) — Standard operations: load file, generate image, compute anomaly
- **WebSockets** — Long operations with real-time progress: batch downloads, batch image generation
- **MCP** (FastMCP) — AI interface for natural language control

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron |
| UI framework | React + TypeScript |
| Styling | Tailwind CSS |
| Interactive viz | Plotly.js |
| Backend API | FastAPI (Python) |
| Data processing | xarray + dask |
| Regridding | xesmf |
| Plotting | matplotlib + cartopy |
| Data sources | ESGF, Copernicus CDS, World Bank CCKP, NASA/NOAA AWS, ESA CCI |
| Parallel downloads | asyncio + aiohttp + boto3 |
| AI interface | FastMCP |
| Documentation | MkDocs |

---

## 🚀 Getting Started

### Prerequisites
- Node.js >= 18
- Python >= 3.10
- Conda or mamba (recommended for geospatial dependencies)

### Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/netcdf-studio.git
cd netcdf-studio

# Install Python backend
cd backend
conda env create -f environment.yml
conda activate netcdf-studio
uvicorn main:app --port 8000

# Install and run frontend
cd ../frontend
npm install
npm run dev
```

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a PR.

Areas where help is especially needed:
- Additional climate indices
- New map projections and plot types
- ESGF node reliability improvements
- Documentation and tutorials

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built for the climate science community. Inspired by the daily workflows of climatologists and meteorologists who deserve better tooling.