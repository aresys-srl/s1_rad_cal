# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Terrain-corrected incidence and look angles computation"""

import numpy as np
import numpy.typing as npt
from perseo_core.geometry.angles import compute_incidence_angles_core
from perseo_core.geometry.coordinates.conversions import llh2xyz
from perseo_core.geometry.core.angles import compute_nadir_from_sensor_positions
from perseo_core.geometry.geocoding import inverse_geocoding_monostatic
from perseo_core.geometry.navigation.trajectory import Trajectory
from pyproj import Geod
from scipy.interpolate import LinearNDInterpolator

WGS84 = Geod(ellps="WGS84")


def _geocode_dem_to_sar_raster(
    dem_values: npt.NDArray[np.floating],
    dem_lat_axis: npt.NDArray[np.floating],
    dem_lon_axis: npt.NDArray[np.floating],
    trajectory: Trajectory,
    range_times: npt.NDArray[np.floating],
    azimuth_times: npt.NDArray,
    doppler_frequency: float,
    wavelength: float,
    *,
    terrain_normal: bool = False,
) -> tuple[npt.NDArray[np.floating], npt.NDArray[np.floating] | None]:
    """Geocode a DEM into SAR (azimuth time, range time) raster space.

    Each DEM grid point is converted to ECEF and located in the SAR acquisition
    via inverse geocoding, giving each point an (azimuth time, range time)
    coordinate. These scattered (az, rg) points, together with their ECEF
    positions (and, optionally, terrain normals), are then interpolated with a
    single Delaunay triangulation (``LinearNDInterpolator``) onto the regular
    ``azimuth_times`` / ``range_times`` raster grid.

    Parameters
    ----------
    dem_values : npt.NDArray[np.floating]
        DEM heights of shape (N_lat, N_lon).
    dem_lat_axis : npt.NDArray[np.floating]
        Latitude axis in degrees of shape (N_lat,).
    dem_lon_axis : npt.NDArray[np.floating]
        Longitude axis in degrees of shape (N_lon,).
    trajectory : Trajectory
        Sensor trajectory.
    range_times : npt.NDArray[np.floating]
        Range time axis onto which the DEM is interpolated.
    azimuth_times : npt.NDArray
        Azimuth time axis, as PreciseDateTime, onto which the DEM is interpolated.
    doppler_frequency : float
        Doppler frequency centroid used for the inverse geocoding.
    wavelength : float
        Carrier signal wavelength.
    terrain_normal : bool, optional
        If True, also compute ECEF terrain unit normals on the DEM grid and
        interpolate them onto the raster grid alongside the ground points, by
        default False.

    Returns
    -------
    tuple[npt.NDArray[np.floating], npt.NDArray[np.floating] | None]
        ``(ground_points_raster, normal_raster)``, where ``ground_points_raster``
        has shape ``(len(azimuth_times), len(range_times), 3)`` with ECEF
        coordinates, and ``normal_raster`` has the same shape with unit terrain
        normal vectors if ``terrain_normal`` is True, otherwise None.
    """
    if dem_values.shape != (len(dem_lat_axis), len(dem_lon_axis)):
        raise ValueError("Mismatch between DEM and latitude/longitude axis")

    lat_grid, lon_grid = np.meshgrid(dem_lat_axis, dem_lon_axis, indexing="ij")
    llh = np.column_stack([np.deg2rad(lat_grid.ravel()), np.deg2rad(lon_grid.ravel()), dem_values.ravel()])
    ecef = llh2xyz(llh)

    az_time, rg_time = inverse_geocoding_monostatic(
        trajectory=trajectory,
        ground_points=ecef,
        doppler_frequencies=doppler_frequency,
        wavelength=wavelength,
        az_initial_time_guesses=np.full(len(ecef), azimuth_times[len(azimuth_times) // 2]),
    )
    az0 = np.min(az_time)
    src_points = np.column_stack([az_time - az0, rg_time])
    az_grid, rg_grid = np.meshgrid(azimuth_times - az0, range_times, indexing="ij")

    normal_raster = None
    if terrain_normal:
        normals = compute_terrain_normal(dem_values, dem_lat_axis, dem_lon_axis).reshape(-1, 3)
        interp = LinearNDInterpolator(src_points, np.hstack([ecef, normals]), fill_value=np.nan, rescale=True)
    else:
        interp = LinearNDInterpolator(src_points, ecef, fill_value=np.nan, rescale=True)
    raster = interp(az_grid, rg_grid)
    ground_points_raster = raster[..., :3]
    if terrain_normal:
        normal_raster = raster[..., 3:]
        norm = np.linalg.norm(normal_raster, axis=-1, keepdims=True)
        norm = np.where(norm > np.finfo(float).eps, norm, np.nan)
        normal_raster = normal_raster / norm

    return ground_points_raster, normal_raster


def _compute_df_dh(cos_lat, sin_lat, cos_lon, sin_lon):
    """
    Computes the partial derivative of ECEF coordinates with respect to height (df/dh).
    """
    x = cos_lat * cos_lon
    y = cos_lat * sin_lon
    z = sin_lat * np.ones_like(cos_lon)
    return x, y, z


def _compute_df_dlat(cos_lat, sin_lat, cos_lon, sin_lon, height_m, M):
    """
    Computes the partial derivative of ECEF coordinates with respect to
    latitude in radians (df/dlat).
    """
    scale = M + height_m

    x = -scale * sin_lat * cos_lon
    y = -scale * sin_lat * sin_lon
    z = scale * cos_lat * np.ones_like(cos_lon)

    return x, y, z


def _compute_df_dlon(cos_lat, cos_lon, sin_lon, height_m, N):
    """
    Computes the partial derivative of ECEF coordinates with respect to
    longitude in radians (df/dlon).
    """
    scale = (N + height_m) * cos_lat

    x = -scale * sin_lon
    y = scale * cos_lon
    z = np.zeros_like(x)

    return x, y, z


def compute_terrain_normal(
    dem_values: npt.NDArray[np.floating],
    dem_lat_axis: npt.NDArray[np.floating],
    dem_lon_axis: npt.NDArray[np.floating],
) -> npt.NDArray[np.floating]:
    """Computes ECEF terrain unit normal vectors.

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

    dh_dlat = np.gradient(dem_values, lat_rad, axis=0)
    dh_dlon = np.gradient(dem_values, lon_rad, axis=1)

    # Use broadcasting instead of np.meshgrid to avoid allocating full lat/lon matrices
    cos_lat = np.cos(lat_rad)[:, None]
    sin_lat = np.sin(lat_rad)[:, None]
    cos_lon = np.cos(lon_rad)[None, :]
    sin_lon = np.sin(lon_rad)[None, :]

    denom_M = (1.0 - WGS84.es * sin_lat[:, 0] ** 2) ** 1.5
    M = (WGS84.a * (1.0 - WGS84.es) / denom_M)[:, None]

    denom_N = np.sqrt(1.0 - WGS84.es * sin_lat[:, 0] ** 2)
    N = (WGS84.a / denom_N)[:, None]

    dh_x, dh_y, dh_z = _compute_df_dh(cos_lat, sin_lat, cos_lon, sin_lon)
    dlat_x, dlat_y, dlat_z = _compute_df_dlat(cos_lat, sin_lat, cos_lon, sin_lon, dem_values, M)
    dlon_x, dlon_y, dlon_z = _compute_df_dlon(cos_lat, cos_lon, sin_lon, dem_values, N)

    dR_dlat_x = dlat_x + dh_x * dh_dlat
    dR_dlat_y = dlat_y + dh_y * dh_dlat
    dR_dlat_z = dlat_z + dh_z * dh_dlat

    dR_dlon_x = dlon_x + dh_x * dh_dlon
    dR_dlon_y = dlon_y + dh_y * dh_dlon
    dR_dlon_z = dlon_z + dh_z * dh_dlon

    nx_raw = dR_dlon_y * dR_dlat_z - dR_dlon_z * dR_dlat_y
    ny_raw = dR_dlon_z * dR_dlat_x - dR_dlon_x * dR_dlat_z
    nz_raw = dR_dlon_x * dR_dlat_y - dR_dlon_y * dR_dlat_x

    norm = np.sqrt(nx_raw**2 + ny_raw**2 + nz_raw**2)
    norm = np.where(norm > np.finfo(float).eps, norm, np.nan)

    normal = np.stack(
        [
            nx_raw / norm,
            ny_raw / norm,
            nz_raw / norm,
        ],
        axis=-1,
    )
    return normal


def compute_terrain_corrected_incidence_angles(
    dem_values: npt.NDArray[np.floating],
    dem_lat_axis: npt.NDArray[np.floating],
    dem_lon_axis: npt.NDArray[np.floating],
    trajectory: Trajectory,
    range_times: npt.NDArray[np.floating],
    azimuth_times: npt.NDArray,
    *,
    radians: bool = True,
    doppler_frequency: float = 0.0,
    wavelength: float = 1.0,
) -> npt.NDArray[np.floating]:
    """Compute incidence angles taking into account terrain elevation and slope

    Parameters
    ----------
    dem_values : npt.NDArray[np.floating]
        DEM heights of shape (N_lat, N_lon). Area covered by DEM
        must correspond to scene area defined by range and azimuth times
        (``load_dem_from_sar_times`` can be used for this purpose).
    dem_lat_axis : npt.NDArray[np.floating]
        Latitude axis in degrees of shape (N_lat,).
    dem_lon_axis : npt.NDArray[np.floating]
        Longitude axis in degrees of shape (N_lon,).
    trajectory : Trajectory
        Sensor trajectory.
    range_times : npt.NDArray[np.floating]
        Range time axis.
    azimuth_times : npt.NDArray
        Azimuth time axis, as PreciseDateTime
    radians : bool, optional
        output angles are expressed in radians if this flag is set to True (default), if False are expressed in degrees
    doppler_frequency : float, optional
        doppler frequency centroid values to perform the inverse geocoding, by default 0.0
    wavelength : float, optional
        carrier signal wavelength, by default 1.0

    Returns
    -------
    npt.NDArray[np.floating]
        incidence angles with shape (len(azimuth_times), len(range_times))
    """
    ground_points, normals = _geocode_dem_to_sar_raster(
        dem_values,
        dem_lat_axis,
        dem_lon_axis,
        trajectory,
        range_times,
        azimuth_times,
        doppler_frequency,
        wavelength,
        terrain_normal=True,
    )

    n_az, n_rng = len(azimuth_times), len(range_times)
    sensor_positions = np.broadcast_to(trajectory.position(azimuth_times)[:, np.newaxis, :], ground_points.shape)

    angles = compute_incidence_angles_core(
        sensor_positions=sensor_positions.reshape(-1, 3),
        ground_points=ground_points.reshape(-1, 3),
        surface_normals=normals.reshape(-1, 3),
        assume_surface_normals_normalized=True,
    ).reshape(n_az, n_rng)

    if not radians:
        return np.rad2deg(angles)
    return angles


def compute_terrain_corrected_look_angles(
    dem_values: npt.NDArray[np.floating],
    dem_lat_axis: npt.NDArray[np.floating],
    dem_lon_axis: npt.NDArray[np.floating],
    trajectory: Trajectory,
    range_times: npt.NDArray[np.floating],
    azimuth_times: npt.NDArray,
    *,
    radians: bool = True,
    doppler_frequency: float = 0.0,
    wavelength: float = 1.0,
) -> npt.NDArray[np.floating]:
    """Compute look angles for each pixel of the raster defined by ``azimuth_times`` and ``range_times`` axis,
    taking DEM into account.

    Parameters
    ----------
    dem_values : npt.NDArray[np.floating]
        DEM heights of shape (N_lat, N_lon). Area covered by DEM
        must correspond to scene area defined by range and azimuth times
        (``load_dem_from_sar_times`` can be used for this purpose).
    dem_lat_axis : npt.NDArray[np.floating]
        Latitude axis in degrees of shape (N_lat,).
    dem_lon_axis : npt.NDArray[np.floating]
        Longitude axis in degrees of shape (N_lon,).
    trajectory : Trajectory
        Sensor trajectory.
    range_times : npt.NDArray[np.floating]
        Range time axis.
    azimuth_times : npt.NDArray
        Azimuth time axis, as PreciseDateTime
    radians : bool, optional
        output angles are expressed in radians if this flag is set to True (default), if False are expressed in degrees
    doppler_frequency : float, optional
        doppler frequency centroid values to perform the inverse geocoding, by default 0.0
    wavelength : float, optional
        carrier signal wavelength, by default 1.

    Returns
    -------
    npt.NDArray[np.floating]
        look angles with shape (len(azimuth_times), len(range_times))
    """
    ground_points, _ = _geocode_dem_to_sar_raster(
        dem_values=dem_values,
        dem_lat_axis=dem_lat_axis,
        dem_lon_axis=dem_lon_axis,
        trajectory=trajectory,
        range_times=range_times,
        azimuth_times=azimuth_times,
        doppler_frequency=doppler_frequency,
        wavelength=wavelength,
        terrain_normal=False,
    )
    sensor_positions = trajectory.position(azimuth_times)
    angles = _look_angles_from_ecef_positions(
        sensor_pos_ecef=sensor_positions,
        ground_pos_ecef=ground_points,
    )
    if not radians:
        return np.rad2deg(angles)
    return angles


def _look_angles_from_ecef_positions(
    sensor_pos_ecef: npt.NDArray[np.floating], ground_pos_ecef: npt.NDArray[np.floating]
) -> npt.NDArray[np.floating]:
    """Compute look angles from sensor and ground ECEF positions

    Parameters
    ----------
    sensor_pos_ecef : npt.NDArray[np.floating]
        Sensor positions with shape (L, 3), where L is the number of unique sensor
        positions (e.g. one per azimuth line).
    ground_pos_ecef : npt.NDArray[np.floating]
        Ground positions with shape (L, M, 3), where M is the number of ground points
        per sensor position (e.g. one per range sample).

    Returns
    -------
    npt.NDArray[np.floating]
        Look angles with shape (L, M) in radians, where L is the number of sensor positions and M is the
        number of ground points per sensor position.
    """
    if sensor_pos_ecef.ndim != 2 or sensor_pos_ecef.shape[1] != 3:
        raise ValueError(f"sensor_pos_ecef must have shape (L, 3), got {sensor_pos_ecef.shape}")
    if ground_pos_ecef.ndim != 3 or ground_pos_ecef.shape[2] != 3:
        raise ValueError(f"ground_pos_ecef must have shape (L, M, 3), got {ground_pos_ecef.shape}")
    if sensor_pos_ecef.shape[0] != ground_pos_ecef.shape[0]:
        raise ValueError(
            f"Azimuth dimension mismatch (L). Sensor has L={sensor_pos_ecef.shape[0]}, "
            f"but Ground has L={ground_pos_ecef.shape[0]}."
        )

    nadir = compute_nadir_from_sensor_positions(sensor_positions=sensor_pos_ecef)
    nadir_hat = nadir / np.linalg.norm(nadir, axis=-1, keepdims=True)

    los = ground_pos_ecef - sensor_pos_ecef[:, np.newaxis, :]
    los_hat = los / np.linalg.norm(los, axis=-1, keepdims=True)

    angles = np.arccos(np.clip(np.einsum("lmk,lk->lm", los_hat, nadir_hat), -1.0, 1.0))

    return angles
