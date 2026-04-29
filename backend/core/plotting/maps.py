"""
Static map image generation using matplotlib + cartopy (Module C).

Entry point: render_map()

Design notes:
- matplotlib backend is forced to "Agg" (headless); cartopy is used for projections
  and coastlines only — never for interactive display.
- Statistical stippling is overlaid as a scatter plot so it is projection-aware.
- Each call is side-effect-free aside from writing the output file; callers control
  Dataset lifetime and RAM budget.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import matplotlib
matplotlib.use("Agg")  # must come before pyplot import; safe to call multiple times
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    _CARTOPY_AVAILABLE = True
except ImportError:
    _CARTOPY_AVAILABLE = False
    ccrs = None  # type: ignore[assignment]
    cfeature = None  # type: ignore[assignment]

from backend.core.netcdf._coords import (
    _LAT_ALIASES,
    _LON_ALIASES,
    _PLEV_ALIASES,
    _TIME_ALIASES,
    detect_coord,
)

logger = logging.getLogger(__name__)

ProjectionName = Literal[
    "PlateCarree", "Robinson", "Mollweide",
    "NorthPolarStereo", "SouthPolarStereo",
    "LambertConformal", "Mercator",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_cartopy() -> None:
    if not _CARTOPY_AVAILABLE:
        raise ImportError(
            "cartopy is required for map generation. "
            "Install with: conda install -c conda-forge cartopy"
        )


def _get_projection(name: str, central_longitude: float = 0.0):
    """Return a cartopy CRS for the given projection name string."""
    _require_cartopy()
    dispatch = {
        "PlateCarree":      ccrs.PlateCarree(central_longitude=central_longitude),
        "Robinson":         ccrs.Robinson(central_longitude=central_longitude),
        "Mollweide":        ccrs.Mollweide(central_longitude=central_longitude),
        "NorthPolarStereo": ccrs.NorthPolarStereo(central_longitude=central_longitude),
        "SouthPolarStereo": ccrs.SouthPolarStereo(central_longitude=central_longitude),
        "LambertConformal": ccrs.LambertConformal(central_longitude=central_longitude),
        "Mercator":         ccrs.Mercator(central_longitude=central_longitude),
    }
    proj = dispatch.get(name)
    if proj is None:
        logger.warning("Unknown projection '%s'; using PlateCarree", name)
        return ccrs.PlateCarree(central_longitude=central_longitude)
    return proj


def _extract_slice(
    ds: xr.Dataset,
    variable: str,
    time_index: int,
    plev_level: float | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract a 2D (lat × lon) numpy slice from a dataset.

    Returns:
        Tuple of (lat, lon, data) — all float64 numpy arrays.
        data shape: (n_lat, n_lon).
    """
    if variable not in ds:
        raise KeyError(f"Variable '{variable}' not found. Available: {list(ds.data_vars)}")

    da = ds[variable]
    time_c = detect_coord(da, _TIME_ALIASES)
    plev_c = detect_coord(da, _PLEV_ALIASES)
    lat_c  = detect_coord(da, _LAT_ALIASES)
    lon_c  = detect_coord(da, _LON_ALIASES)

    if lat_c is None or lon_c is None:
        raise ValueError(f"Variable '{variable}' is missing lat or lon coordinates")

    if time_c and time_c in da.dims:
        n = int(da.sizes[time_c])
        da = da.isel({time_c: min(time_index, n - 1)})

    if plev_c and plev_c in da.dims:
        if plev_level is not None:
            da = da.sel({plev_c: plev_level}, method="nearest")
        else:
            da = da.isel({plev_c: 0})

    for dim in list(da.dims):
        if dim not in (lat_c, lon_c):
            logger.warning("Unexpected dim '%s' in slice; taking index 0", dim)
            da = da.isel({dim: 0})

    da = da.transpose(lat_c, lon_c)
    data = da.compute().values.astype(float)
    lat  = ds[lat_c].values.astype(float)
    lon  = ds[lon_c].values.astype(float)
    return lat, lon, data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_map(
    ds: xr.Dataset,
    variable: str,
    output_path: str | Path,
    *,
    time_index: int = 0,
    plev_level: float | None = None,
    projection: str = "PlateCarree",
    central_longitude: float = 0.0,
    cmap: str = "RdBu_r",
    vmin: float | None = None,
    vmax: float | None = None,
    title: str = "",
    dpi: int = 150,
    figsize: tuple[float, float] = (12, 6),
    add_coastlines: bool = True,
    add_borders: bool = True,
    add_gridlines: bool = True,
    add_colorbar: bool = True,
    stipple_mask: np.ndarray | None = None,
    lat_min: float | None = None,
    lat_max: float | None = None,
    lon_min: float | None = None,
    lon_max: float | None = None,
    # Optional vector-field quiver overlay
    u_variable: str | None = None,
    v_variable: str | None = None,
    quiver_stride: int = 5,
    quiver_scale: float | None = None,
    quiver_color: str = "black",
    quiver_alpha: float = 0.7,
) -> Path:
    """
    Render a 2D lat/lon map and save it as a PNG image.

    Args:
        ds: Open xarray Dataset (may be dask-backed).
        variable: Variable name to plot.
        output_path: Destination .png path (parent directories are created).
        time_index: Integer time step to extract.
        plev_level: Pressure level to select (same units as the file).
                    None → first available level.
        projection: Cartopy projection name (PlateCarree, Robinson, …).
        central_longitude: Central meridian for the projection (degrees).
        cmap: Matplotlib colormap name.
        vmin / vmax: Color scale limits. Both None → symmetric around the data max.
        title: Title string. Empty → auto-generated from variable long_name + units.
        dpi: Output resolution (dots per inch).
        figsize: Figure size in inches (width, height).
        add_coastlines: Overlay Natural Earth coastlines.
        add_borders: Overlay country borders.
        add_gridlines: Draw latitude/longitude grid lines with labels.
        add_colorbar: Add a horizontal colour bar beneath the map.
        stipple_mask: Boolean 2D array (lat × lon) where True marks stippled points
                      (e.g. statistically significant grid cells). Overlaid as dots.
        lat_min/lat_max/lon_min/lon_max: Restrict map extent to a bounding box.

    Returns:
        Absolute Path to the saved PNG file.

    Raises:
        ImportError: cartopy not installed.
        KeyError: variable not in dataset.
        ValueError: lat or lon coordinates missing.
    """
    _require_cartopy()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lat, lon, data = _extract_slice(ds, variable, time_index, plev_level)

    # Bounding box clipping
    clip = any(v is not None for v in (lat_min, lat_max, lon_min, lon_max))
    if clip:
        _lat_min = lat_min if lat_min is not None else float(lat.min())
        _lat_max = lat_max if lat_max is not None else float(lat.max())
        _lon_min = lon_min if lon_min is not None else float(lon.min())
        _lon_max = lon_max if lon_max is not None else float(lon.max())
        lat_mask = (lat >= _lat_min) & (lat <= _lat_max)
        lon_mask = (lon >= _lon_min) & (lon <= _lon_max)
        lat  = lat[lat_mask]
        lon  = lon[lon_mask]
        data = data[np.ix_(lat_mask, lon_mask)]
        if stipple_mask is not None:
            stipple_mask = stipple_mask[np.ix_(lat_mask, lon_mask)]

    # Auto colour scale (symmetric around zero by default)
    if vmin is None and vmax is None:
        abs_max = float(np.nanmax(np.abs(data)))
        vmin, vmax = -abs_max, abs_max
    elif vmin is None:
        vmin = float(np.nanmin(data))
    elif vmax is None:
        vmax = float(np.nanmax(data))

    units     = str(ds[variable].attrs.get("units", ""))
    long_name = str(ds[variable].attrs.get("long_name", variable))
    if not title:
        title = f"{long_name} [{units}]" if units else long_name

    proj = _get_projection(projection, central_longitude)

    fig = plt.figure(figsize=figsize, dpi=dpi)
    ax  = fig.add_subplot(1, 1, 1, projection=proj)

    if clip:
        ax.set_extent([lon.min(), lon.max(), lat.min(), lat.max()], crs=ccrs.PlateCarree())
    else:
        ax.set_global()

    lon_grid, lat_grid = np.meshgrid(lon, lat)
    pcm = ax.pcolormesh(
        lon_grid, lat_grid, data,
        cmap=cmap, vmin=vmin, vmax=vmax,
        transform=ccrs.PlateCarree(),
        shading="auto",
    )

    # Statistical stippling: small dots at significant grid cells
    if stipple_mask is not None and stipple_mask.any():
        ax.scatter(
            lon_grid[stipple_mask], lat_grid[stipple_mask],
            s=0.8, c="k", alpha=0.45,
            transform=ccrs.PlateCarree(),
            zorder=5,
        )

    # Quiver overlay: draw wind / vector arrows
    if u_variable and v_variable:
        try:
            lat_q, lon_q, u_data = _extract_slice(ds, u_variable, time_index, plev_level)
            _,     _,     v_data = _extract_slice(ds, v_variable, time_index, plev_level)
            lat_qt = lat_q[::quiver_stride]
            lon_qt = lon_q[::quiver_stride]
            u_q    = u_data[::quiver_stride, ::quiver_stride]
            v_q    = v_data[::quiver_stride, ::quiver_stride]
            lon_qg, lat_qg = np.meshgrid(lon_qt, lat_qt)
            ax.quiver(
                lon_qg, lat_qg, u_q, v_q,
                transform=ccrs.PlateCarree(),
                color=quiver_color,
                alpha=quiver_alpha,
                scale=quiver_scale,
                zorder=4,
            )
        except Exception as qe:
            logger.warning("Quiver overlay skipped (%s / %s): %s", u_variable, v_variable, qe)

    if add_coastlines:
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=3)
    if add_borders:
        ax.add_feature(cfeature.BORDERS, linewidth=0.3, alpha=0.6, zorder=3)

    if add_gridlines:
        gl = ax.gridlines(
            draw_labels=True, linewidth=0.3, alpha=0.45, linestyle="--", zorder=2
        )
        gl.top_labels   = False
        gl.right_labels = False

    if add_colorbar:
        cbar = fig.colorbar(pcm, ax=ax, orientation="horizontal", pad=0.05, fraction=0.05)
        cbar.set_label(units, fontsize=9)
        cbar.ax.tick_params(labelsize=8)

    ax.set_title(title, fontsize=11, pad=8)

    fig.savefig(str(output_path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    logger.info(
        "Map saved: %s  projection=%s  dpi=%d", output_path.name, projection, dpi
    )
    return output_path
