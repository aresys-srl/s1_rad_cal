# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""References for tests"""

import numpy as np
import numpy.typing as npt
from perseo_core.geometry.coordinates.conversions import llh2xyz
from pyproj import Geod

WGS84 = Geod(ellps="WGS84")


def compute_terrain_normal_numeric(
    dem_values: npt.NDArray[np.floating],
    dem_lat_axis: npt.NDArray[np.floating],
    dem_lon_axis: npt.NDArray[np.floating],
) -> npt.NDArray[np.floating]:
    """
    Computes ECEF terrain unit normal vectors via fully numeric differentiation
    of the llh2xyz transform. Used to cross-validate the analytic implementation
    in `compute_terrain_normal`.

    Parameters
    ----------
    dem_values : npt.NDArray[np.floating]
        DEM heights of shape (N_lat, N_lon).
    dem_lat_axis : npt.NDArray[np.floating]
        Latitude axis in degrees of shape (N_lat,).
    dem_lon_axis : npt.NDArray[np.floating]
        Longitude axis in degrees of shape (N_lon,).

    Returns
    -------
    npt.NDArray[np.floating]
        Array of shape (N_lat, N_lon, 3) with unit normal components (nx, ny, nz).
    """
    if not np.all(np.diff(dem_lon_axis) > 0):
        msg = "dem_lon_axis must be monotonic increasing. If it crosses the antimeridian, unwrap it first"
        raise ValueError(msg)
    if dem_values.shape != (len(dem_lat_axis), len(dem_lon_axis)):
        msg = (
            f"dem_values shape {dem_values.shape} does not match "
            f"axis lengths ({len(dem_lat_axis)}, {len(dem_lon_axis)})"
        )
        raise ValueError(msg)

    lat_rad = np.radians(dem_lat_axis)
    lon_rad = np.radians(dem_lon_axis)

    lat_grid, lon_grid = np.meshgrid(lat_rad, lon_rad, indexing="ij")

    # Stack into (N_lat * N_lon, 3) for llh2xyz, then reshape back to the grid
    # NOTE: llh2xyz seems to take a lot of time
    llh = np.stack([lat_grid.ravel(), lon_grid.ravel(), dem_values.ravel()], axis=-1)
    xyz = llh2xyz(llh, radians=True).reshape(*dem_values.shape, 3)

    # Numeric partials w.r.t. lat_rad / lon_rad, one vector per grid node
    dR_dlat = np.gradient(xyz, lat_rad, axis=0)
    dR_dlon = np.gradient(xyz, lon_rad, axis=1)

    # Outward normal: East x North = Up
    n_raw = np.cross(dR_dlon, dR_dlat)
    norm = np.linalg.norm(n_raw, axis=-1, keepdims=True)

    return n_raw / norm
