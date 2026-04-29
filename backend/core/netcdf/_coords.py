"""
Coordinate alias sets and detection utility shared across the netcdf package.

Centralised here so loader.py and processor.py stay in sync when new
conventions are added (CMIP7, new reanalysis products, etc.).
"""

from __future__ import annotations

import xarray as xr

_LAT_ALIASES: frozenset[str] = frozenset(
    {"lat", "latitude", "LAT", "LATITUDE", "nav_lat"}
)
_LON_ALIASES: frozenset[str] = frozenset(
    {"lon", "longitude", "LON", "LONGITUDE", "nav_lon"}
)
_PLEV_ALIASES: frozenset[str] = frozenset(
    {"plev", "level", "lev", "pressure_level", "pressure", "air_pressure", "lev_p"}
)
_TIME_ALIASES: frozenset[str] = frozenset({"time", "TIME"})


def detect_coord(
    obj: xr.Dataset | xr.DataArray, aliases: frozenset[str]
) -> str | None:
    """Return the first coord or dim name in obj that matches any alias, else None."""
    for name in list(obj.coords) + list(obj.dims):
        if name in aliases:
            return str(name)
    return None
