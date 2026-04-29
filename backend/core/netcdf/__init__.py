from .loader import (
    CoordinateInfo,
    FileMetadata,
    VariableInfo,
    close_dataset,
    extract_metadata,
    open_dataset,
    open_mfdataset,
)
from .processor import (
    SliceResult,
    SpatialMeanResult,
    compute_anomaly,
    compute_climatology,
    extract_2d_slice,
    save_dataarray,
    weighted_spatial_mean,
)
from .regridder import (
    RegridMethod,
    make_target_grid,
    regrid,
    regrid_to_resolution,
)
from .indices import (
    compute_cdd,
    compute_cwd,
    compute_nao,
    compute_nino12,
    compute_nino3,
    compute_nino34,
    compute_nino4,
    compute_oni,
    compute_prcptot,
    compute_r95p,
    compute_rx1day,
    compute_rx5day,
)

__all__ = [
    # loader
    "CoordinateInfo",
    "FileMetadata",
    "VariableInfo",
    "close_dataset",
    "extract_metadata",
    "open_dataset",
    "open_mfdataset",
    # processor
    "SliceResult",
    "SpatialMeanResult",
    "compute_anomaly",
    "compute_climatology",
    "extract_2d_slice",
    "save_dataarray",
    "weighted_spatial_mean",
    # regridder
    "RegridMethod",
    "make_target_grid",
    "regrid",
    "regrid_to_resolution",
    # indices
    "compute_cdd",
    "compute_cwd",
    "compute_nao",
    "compute_nino12",
    "compute_nino3",
    "compute_nino34",
    "compute_nino4",
    "compute_oni",
    "compute_prcptot",
    "compute_r95p",
    "compute_rx1day",
    "compute_rx5day",
]
