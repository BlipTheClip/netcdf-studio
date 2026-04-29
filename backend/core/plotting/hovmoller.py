"""
Hovmöller diagram generation using matplotlib (Module C).

A Hovmöller diagram displays a 2D field where one spatial dimension is averaged
away, leaving time on one axis and the remaining spatial dimension on the other.

Two modes:
  - "lat": time × latitude (longitude-averaged). No weighting needed — equal
    longitude spacing makes the simple mean correct for this average.
  - "lon": time × longitude (latitude-averaged, cosine-weighted). Area weighting
    is mandatory here because latitude bands have different physical widths.

Entry points:
  render_hovmoller(ds, variable, output_path, mode="lat" | "lon", **kwargs) → Path
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import xarray as xr

from backend.core.netcdf._coords import (
    _LAT_ALIASES,
    _LON_ALIASES,
    _PLEV_ALIASES,
    _TIME_ALIASES,
    detect_coord,
)

logger = logging.getLogger(__name__)

HovmollerMode = Literal["lat", "lon"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_time_labels(time_vals: np.ndarray) -> list[str]:
    """Format numpy datetime64 or cftime values as short year-month strings."""
    labels: list[str] = []
    for t in time_vals:
        if hasattr(t, "isoformat"):
            labels.append(t.strftime("%Y-%m") if hasattr(t, "strftime") else t.isoformat()[:7])
        else:
            try:
                labels.append(str(np.datetime_as_string(t, unit="M")))
            except Exception:
                labels.append(str(t)[:7])
    return labels


def _weighted_lon_mean(da: xr.DataArray, lat_c: str, lon_c: str) -> xr.DataArray:
    """Cosine-latitude weighted mean over latitude, returning a (time × lon) array."""
    weights = np.cos(np.deg2rad(da[lat_c]))
    weights.name = "weights"
    return da.weighted(weights).mean(lat_c)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_hovmoller(
    ds: xr.Dataset,
    variable: str,
    output_path: str | Path,
    *,
    mode: HovmollerMode = "lat",
    plev_level: float | None = None,
    lat_min: float = -90.0,
    lat_max: float = 90.0,
    lon_min: float = -180.0,
    lon_max: float = 180.0,
    cmap: str = "RdBu_r",
    vmin: float | None = None,
    vmax: float | None = None,
    title: str = "",
    dpi: int = 150,
    figsize: tuple[float, float] = (10, 7),
    add_colorbar: bool = True,
    n_time_ticks: int = 12,
) -> Path:
    """
    Render a Hovmöller diagram and save it as a PNG image.

    Args:
        ds: Open xarray Dataset.
        variable: Variable to plot.
        output_path: Destination .png path.
        mode: "lat" → time × latitude (avg over longitude);
              "lon" → time × longitude (cosine-weighted avg over latitude).
        plev_level: Pressure level to select (None → first level).
        lat_min/lat_max/lon_min/lon_max: Spatial domain for the average.
        cmap: Matplotlib colormap.
        vmin/vmax: Color scale limits (None → symmetric around zero).
        title: Plot title. Empty → auto-generated.
        dpi: Output resolution.
        figsize: Figure size in inches (width, height).
        add_colorbar: Include a horizontal colour bar.
        n_time_ticks: Approximate number of time axis tick marks.

    Returns:
        Path to the saved PNG file.

    Raises:
        KeyError: variable not found.
        ValueError: coordinates missing or domain is empty.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if variable not in ds:
        raise KeyError(f"Variable '{variable}' not found. Available: {list(ds.data_vars)}")

    da = ds[variable]
    time_c = detect_coord(da, _TIME_ALIASES)
    plev_c = detect_coord(da, _PLEV_ALIASES)
    lat_c  = detect_coord(da, _LAT_ALIASES)
    lon_c  = detect_coord(da, _LON_ALIASES)

    if lat_c is None or lon_c is None:
        raise ValueError(f"Variable '{variable}' is missing lat or lon coordinates")
    if time_c is None or time_c not in da.dims:
        raise ValueError(f"Variable '{variable}' has no time dimension — Hovmöller requires time")

    # Select pressure level
    if plev_c and plev_c in da.dims:
        if plev_level is not None:
            da = da.sel({plev_c: plev_level}, method="nearest")
        else:
            da = da.isel({plev_c: 0})

    # Clip to bounding box
    da = da.sel({
        lat_c: slice(lat_min, lat_max),
        lon_c: slice(lon_min, lon_max),
    })

    if da[lat_c].size == 0 or da[lon_c].size == 0:
        raise ValueError(
            f"Bounding box ({lat_min}–{lat_max}°N, {lon_min}–{lon_max}°E) "
            "contains no grid points"
        )

    # Reduce spatial dimension
    if mode == "lat":
        # Average over longitude — shape becomes (time, lat)
        reduced = da.mean(lon_c).compute()
        spatial_vals = reduced[lat_c].values.astype(float)
        spatial_label = "Latitude (°N)"
        data = reduced.transpose(time_c, lat_c).values  # (time, lat)
    else:
        # Cosine-latitude weighted average over latitude — shape becomes (time, lon)
        reduced = _weighted_lon_mean(da, lat_c, lon_c).compute()
        spatial_vals = reduced[lon_c].values.astype(float)
        spatial_label = "Longitude (°E)"
        data = reduced.transpose(time_c, lon_c).values  # (time, lon)

    time_vals = ds[time_c].values
    n_time    = len(time_vals)

    # Auto colour scale
    if vmin is None and vmax is None:
        abs_max = float(np.nanmax(np.abs(data)))
        vmin, vmax = -abs_max, abs_max
    elif vmin is None:
        vmin = float(np.nanmin(data))
    elif vmax is None:
        vmax = float(np.nanmax(data))

    units     = str(da.attrs.get("units", ""))
    long_name = str(da.attrs.get("long_name", variable))
    if not title:
        avg_over = "longitude-averaged" if mode == "lat" else "latitude-averaged (cosine-weighted)"
        title    = f"{long_name} — {avg_over}"
        if units:
            title += f"  [{units}]"

    # Build time axis as integer indices — matplotlib doesn't handle all cftime types
    time_idx = np.arange(n_time)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    pcm = ax.pcolormesh(
        spatial_vals, time_idx, data,
        cmap=cmap, vmin=vmin, vmax=vmax,
        shading="auto",
    )

    # Time tick labels
    step = max(1, n_time // n_time_ticks)
    tick_idx    = time_idx[::step]
    tick_labels = _format_time_labels(time_vals[::step])
    ax.set_yticks(tick_idx)
    ax.set_yticklabels(tick_labels, fontsize=8)
    ax.invert_yaxis()  # time flows downward (conventional)

    ax.set_xlabel(spatial_label, fontsize=10)
    ax.set_ylabel("Time", fontsize=10)
    ax.set_title(title, fontsize=11, pad=8)

    if add_colorbar:
        cbar = fig.colorbar(pcm, ax=ax, orientation="horizontal", pad=0.12, fraction=0.04)
        cbar.set_label(units, fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info("Hovmöller saved: %s  mode=%s", output_path.name, mode)
    return output_path
