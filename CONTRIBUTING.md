# Contributing to NetCDF Studio

Thank you for your interest in contributing. NetCDF Studio is a scientific tool — correctness matters as much as clean code. Please read this guide before opening a PR.

---

## Table of contents

- [Prerequisites](#prerequisites)
- [Development setup](#development-setup)
- [Running the app](#running-the-app)
- [Project structure](#project-structure)
- [Code conventions](#code-conventions)
- [Scientific correctness requirements](#scientific-correctness-requirements)
- [Testing](#testing)
- [Submitting a pull request](#submitting-a-pull-request)

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| [Miniforge / Conda](https://github.com/conda-forge/miniforge) | latest | Strongly prefer conda-forge channel |
| [Node.js](https://nodejs.org/) | ≥ 20 LTS | For the Electron/React frontend |
| [Git](https://git-scm.com/) | ≥ 2.40 | |
| Python | 3.11 | Managed by the conda environment |

> **Windows note:** Install xesmf via conda-forge before trying pip: `conda install -c conda-forge xesmf`. The ESMF C library does not build from pip on Windows.

---

## Development setup

```bash
# 1. Fork and clone
git clone https://github.com/<your-fork>/netcdf-studio.git
cd netcdf-studio

# 2. Create the conda environment (all backend dependencies)
conda env create -f backend/environment.yml
conda activate netcdf-studio

# 3. Install the backend in editable mode
pip install -e backend/

# 4. Install frontend dependencies
cd frontend && npm install && cd ..
```

### Environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```
CDS_API_KEY=your-copernicus-cds-key
CDS_API_URL=https://cds.climate.copernicus.eu/api/v2
ESGF_USERNAME=your-esgf-openid
ESGF_PASSWORD=your-esgf-password
```

API keys are never committed to the repository. Use `python-dotenv` in code; never hardcode credentials.

---

## Running the app

### Backend only (API development)

```bash
conda activate netcdf-studio
uvicorn backend.main:app --reload --port 8000
```

The interactive API docs are at `http://localhost:8000/docs`.

### Frontend only (UI development)

```bash
cd frontend
npm run dev        # starts Vite dev server on port 5173
```

### Full app (Electron)

```bash
cd frontend
npm run electron:dev
```

This starts both the React dev server and the Electron shell. The Electron main process spawns the Python backend automatically and polls `/api/health` before opening the window.

---

## Project structure

```
netcdf-studio/
├── backend/
│   ├── core/netcdf/        ← pure functions (loader, processor, indices, regridder)
│   ├── api/routes/         ← FastAPI routers (one file per module)
│   ├── api/ws/             ← WebSocket handlers for long-running tasks
│   ├── mcp/                ← FastMCP server (Module E)
│   └── main.py             ← FastAPI app entry point
└── frontend/
    ├── src/modules/        ← one folder per module (A-D)
    ├── src/api/client.ts   ← all HTTP + WebSocket calls
    └── src/store/          ← Zustand global state
```

---

## Code conventions

### Python

- **Type hints everywhere.** Every function signature must be fully annotated. Run `mypy backend/` before pushing.
- **`async def` for all FastAPI route handlers**, even if the body is synchronous (for future-proofing).
- **Core functions are pure.** `backend/core/` must have no file I/O, no HTTP calls, and no global state mutations. Only `save_dataarray()` is a deliberate exception.
- **Dask is always on.** Never call `xr.open_dataset(path)` without `chunks=`. Use `chunks='auto'` unless you have a specific reason.
- **Logging, not print.** Use `logging.getLogger(__name__)` and appropriate levels (DEBUG for variable names, INFO for file-level events, WARNING for recoverable issues, ERROR for failures).
- **Error format.** Route handlers return `{"status": "error", "error": "...", "detail": "..."}` — do not let FastAPI's default error format leak through.
- **Formatter:** `black`. Linter: `ruff`. Both run in CI.

### TypeScript

- **Strict mode** is enabled in `tsconfig.json`. No `any` without a comment explaining why.
- All API response shapes must have a corresponding interface in `src/api/types.ts`.
- State management is **Zustand** only — no Redux, no Context for global state.
- Each module (`src/modules/<name>/`) is self-contained. Do not import from another module's internal components.

---

## Scientific correctness requirements

These are **non-negotiable**. PRs that violate them will not be merged regardless of code quality.

1. **Area-weighted averages:** Every spatial average must use `np.cos(np.deg2rad(lat))` as weights via `da.weighted(weights).mean()`. Unweighted spatial means are never acceptable.

2. **Configurable base periods:** The reference period for climatologies and anomalies must always be user-configurable. Never hardcode `1981–2010` or any other period.

3. **Pressure level selection at open time:** For variables with a `plev` dimension, selection must happen in `xr.open_dataset(...).sel(plev=...)` before any data enters memory. Loading a full 4D atmospheric field and then subsetting is not acceptable.

4. **Conservative regridding by default:** Use `xesmf` with `method="conservative"` for precipitation, fluxes, and any quantity that must be conserved. Bilinear is only appropriate for temperature and similar continuous fields used for visualisation.

5. **Non-standard calendars:** CMIP data uses 360-day and `noleap` calendars. Always test with a `noleap` or `360_day` file. Do not assume `datetime64`.

If your change involves a new computation, add a note to the PR explaining how scientific correctness was verified (e.g., "compared against published Niño 3.4 values from NOAA/CPC").

---

## Testing

```bash
# Run the full test suite
pytest backend/tests/ -v

# Run with coverage
pytest backend/tests/ --cov=backend --cov-report=term-missing
```

- Every new core function in `backend/core/` must have at least one test in `backend/tests/`.
- Use the sample NetCDF file in `examples/sample_data/` for integration tests — do not require internet access in tests.
- FastAPI route tests use `httpx.AsyncClient` — see existing tests for the pattern.
- Do not mock the xarray/dask stack. Tests must open real `.nc` files.

---

## Submitting a pull request

1. **Open an issue first** for anything beyond a trivial bug fix. This avoids duplicate work and lets maintainers give early feedback on the approach.
2. **Branch from `main`:** `git checkout -b feat/your-feature-name`
3. **Keep PRs focused.** One feature or bug fix per PR. Refactoring in a separate PR.
4. **Fill in the PR template** — especially the scientific correctness section.
5. **Ensure CI is green** before requesting review: `black backend/`, `ruff check backend/`, `mypy backend/`, `pytest`.
6. **Squash-merge preferred** for feature branches. Maintainers will squash if you don't.

For questions, open a [Discussion](https://github.com/BlipTheClip/netcdf-studio/discussions) rather than an issue.
