# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""References for tests"""

import numpy as np
import numpy.typing as npt
from perseo_core.geometry.coordinates.conversions import llh2xyz
from perseo_core.timing import PreciseDateTime
from pyproj import Geod

WGS84 = Geod(ellps="WGS84")


ORBIT_POSITIONS = np.array(
    [
        [5358022.689895, 640124.830137, 4568097.701216],
        [5312423.936863, 616644.77881, 4624085.829849],
        [5266195.447276, 593162.562568, 4679551.792466],
        [5219342.417957, 569681.730049, 4734489.338955],
        [5171870.120938, 546205.822005, 4788892.279426],
        [5123783.902842, 522738.370793, 4842754.484928],
        [5075089.184206, 499282.899851, 4896069.88813],
        [5025791.458771, 475842.923169, 4948832.484032],
        [4975896.292858, 452421.94479, 5001036.330612],
        [4925409.324702, 429023.458324, 5052675.549421],
        [4874336.263787, 405650.946442, 5103744.326233],
        [4822682.890177, 382307.880365, 5154236.911727],
        [4770455.053883, 358997.719369, 5204147.622161],
        [4717658.674113, 335723.910276, 5253470.839977],
        [4664299.738497, 312489.886944, 5302201.014445],
        [4610384.302372, 289299.069781, 5350332.662252],
    ]
)

ORBIT_VELOCITIES = np.array(
    [
        [-4528.217145, -2347.778426, 5624.711331],
        [-4591.44812, -2348.172598, 5572.809214],
        [-4654.163185, -2348.211527, 5520.279106],
        [-4716.354796, -2347.895979, 5467.126991],
        [-4778.015466, -2347.226769, 5413.358927],
        [-4839.137774, -2346.204763, 5358.98104],
        [-4899.714363, -2344.830877, 5303.999522],
        [-4959.737938, -2343.106081, 5248.420635],
        [-5019.201271, -2341.031392, 5192.250709],
        [-5078.097203, -2338.607879, 5135.496138],
        [-5136.418641, -2335.836664, 5078.163383],
        [-5194.158563, -2332.718917, 5020.258968],
        [-5251.310017, -2329.255858, 4961.78948],
        [-5307.866122, -2325.448757, 4902.761567],
        [-5363.820068, -2321.298933, 4843.181938],
        [-5419.165117, -2316.807753, 4783.057362],
    ]
)

ORBIT_TIMES = PreciseDateTime.from_utc_string("06-JUN-2026 17:04:58.282101000000") + np.arange(16) * 10

DEM_LAT_AXIS = np.linspace(46.64141174, 44.66641174, 238)
DEM_LON_AXIS = np.linspace(9.685214, 11.57688066, 228)

RANGE_TIMES = np.linspace(0.005331285117519462, 0.005691358382843831, 23170)
AZIMUTH_TIMES = np.linspace(
    PreciseDateTime.from_utc_string("06-JUN-2026 17:06:10.957486799999"),
    PreciseDateTime.from_utc_string("06-JUN-2026 17:06:10.975986806699"),
    10,
)


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
