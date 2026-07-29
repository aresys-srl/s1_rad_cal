# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Core functionalities for DEM exploitation"""

from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr
from eo_products.dem.getasse30 import get_dem_roi
from numpy import typing as npt
from perseo_core.geometry.coordinates.conversions import llh2xyz, xyz2llh
from perseo_core.geometry.core.angles import compute_nadir_from_sensor_positions
from perseo_core.geometry.geocoding import (
    direct_geocoding_monostatic,
    inverse_geocoding_monostatic,
)
from perseo_core.geometry.navigation.trajectory import Trajectory
from scipy.interpolate import griddata

SensorLookDirection = Literal["RIGHT", "LEFT"]

RANGE_MARGIN_SEC = 0.0001
AZIMUTH_MARGIN_SEC = 0.5


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
        DEM heights of shape (N_lat, N_lon).
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
    ground_points = project_dem_to_raster(
        dem_values=dem_values,
        dem_lat_axis=dem_lat_axis,
        dem_lon_axis=dem_lon_axis,
        trajectory=trajectory,
        range_times=range_times,
        azimuth_times=azimuth_times,
        doppler_frequency=doppler_frequency,
        wavelength=wavelength,
    )
    sensor_positions = trajectory.position(azimuth_times)
    angles = _look_angles_from_ecef_positions(
        sensor_pos_ecef=sensor_positions,
        ground_pos_ecef=ground_points,
        radians=radians,
    )
    return angles


def project_dem_to_raster(
    dem_values: npt.NDArray[np.floating],
    dem_lat_axis: npt.NDArray[np.floating],
    dem_lon_axis: npt.NDArray[np.floating],
    trajectory: Trajectory,
    range_times: npt.NDArray[np.floating],
    azimuth_times: npt.NDArray,
    doppler_frequency: float = 0.0,
    wavelength: float = 1.0,
) -> npt.NDArray[np.floating]:
    """Project and interpolate DEM values from its lat/lon grid defined by ``dem_lat_axis`` and ``dem_lon_axis`` onto
    the sensor raster grid and return ECEF coordinates.

    Parameters
    ----------
    dem_values : npt.NDArray[np.floating]
        DEM height values of shape (N_lat, N_lon) to be projected onto raster grid.
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
    doppler_frequency : float, optional
        doppler frequency centroid values to perform the inverse geocoding, by default 0.0
    wavelength : float, optional
        carrier signal wavelength, by default 1.

    Returns
    -------
    npt.NDArray[np.floating]
        ECEF coordinates on sensor raster grid of shape (len(azimuth_times), len(range_times), 3)
    """
    if dem_values.shape != (len(dem_lat_axis), len(dem_lon_axis)):
        raise ValueError("Mismatch between DEM and latitude/longitude axis")
    lat_grid, lon_grid = np.meshgrid(dem_lat_axis, dem_lon_axis, indexing="ij")
    llh = np.column_stack(
        [
            np.deg2rad(lat_grid.ravel()),
            np.deg2rad(lon_grid.ravel()),
            dem_values.ravel(),
        ]
    )
    ecef = llh2xyz(llh)

    # Project DEM points into sensor coordinates
    az_time, rg_time = inverse_geocoding_monostatic(
        trajectory=trajectory,
        ground_points=ecef,
        doppler_frequencies=doppler_frequency,
        wavelength=wavelength,
        az_initial_time_guesses=np.full(
            len(ecef),
            azimuth_times[len(azimuth_times) // 2],
        ),
    )
    az0 = np.min(az_time)
    dem_sar_coords = np.column_stack(
        [
            az_time - az0,
            rg_time,
        ]
    )
    # sensor raster grid
    az_grid, rg_grid = np.meshgrid(
        azimuth_times - az0,
        range_times,
        indexing="ij",
    )
    # Interpolate ECEF coordinates onto sensor grid
    ecef_grid = griddata(
        points=dem_sar_coords,
        values=ecef,
        xi=(az_grid, rg_grid),
        method="linear",
        rescale=True,
        fill_value=np.nan,
    )
    return ecef_grid


def _look_angles_from_ecef_positions(
    sensor_pos_ecef: npt.NDArray[np.floating], ground_pos_ecef: npt.NDArray[np.floating], *, radians: bool = True
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
    radians : bool, optional
        Output angles are expressed in radians if this flag is set to True (default), if False
        are expressed in degrees.

    Returns
    -------
    npt.NDArray[np.floating]
        Look angles with shape (L, M), where L is the number of sensor positions and M is the
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

    if not radians:
        return np.rad2deg(angles)
    return angles


def _compute_footprint_from_times(
    range_times: npt.NDArray[np.floating],
    azimuth_times: npt.NDArray,
    trajectory: Trajectory,
    wavelength: float,
    doppler_frequency: float,
    look_direction: SensorLookDirection,
) -> tuple[float, float, float, float]:
    """Compute footprint from azimuth and range time axis

    Parameters
    ----------
    range_times : npt.NDArray[np.floating]
        range times
    azimuth_times : npt.NDArray[np.floating]
        azimuth times
    trajectory : Trajectory
        sensor trajectory
    wavelength : float
        carrier signal wavelength
    doppler_frequency : float
        doppler frequency [Hz]
    look_direction : SensorLookDirection
        geocoding side, "RIGHT" or "LEFT"

    Returns
    -------
    tuple[float, float, float, float]
        footprint as (``lat_start``, ``lon_start``, ``lat_size``, ``lon_size``) expressed in degrees
    """
    footprint_ecef = direct_geocoding_monostatic(
        sensor_positions=trajectory.position(
            np.array(
                [
                    azimuth_times[0] - AZIMUTH_MARGIN_SEC,
                    azimuth_times[-1] + AZIMUTH_MARGIN_SEC,
                ]
            )
        ),
        sensor_velocities=trajectory.velocity(
            np.array(
                [
                    azimuth_times[0] - AZIMUTH_MARGIN_SEC,
                    azimuth_times[-1] + AZIMUTH_MARGIN_SEC,
                ]
            )
        ),
        range_times=[
            range_times[0] - RANGE_MARGIN_SEC,
            range_times[-1] + RANGE_MARGIN_SEC,
        ],
        altitude=0.0,
        doppler_frequencies=doppler_frequency,
        wavelength=wavelength,
        look_direction=look_direction,
    )
    footprint_vertices = np.rad2deg(xyz2llh(np.vstack((footprint_ecef[0], footprint_ecef[1])))[:, 0:2])
    min_lat = np.min(footprint_vertices[:, 0])
    max_lat = np.max(footprint_vertices[:, 0])

    lon_start, lon_size = _antimeridian_safe_lon_bounds(
        lon_a_deg=footprint_vertices[0, 1], lon_b_deg=footprint_vertices[1, 1]
    )

    return (
        min_lat,
        lon_start,
        max_lat - min_lat,
        lon_size,
    )


def _antimeridian_safe_lon_bounds(lon_a_deg: float, lon_b_deg: float) -> tuple[float, float]:
    """Compute (lon_start, lon_size) for two footprint-edge longitudes, correctly
    handling the case where they straddle the antimeridian.

    Parameters
    ----------
    lon_a_deg : float
        First longitude, degrees.
    lon_b_deg : float
        Second longitude, degrees.

    Returns
    -------
    tuple[float, float]
        (lon_start, lon_size) in degrees. lon_start is in [-180, 180) and
        lon_size >= 0; lon_start + lon_size may exceed 180 deg, which is the
        convention get_dem_roi expects to indicate antimeridian crossing.
    """
    lon_low, lon_high = sorted((lon_a_deg, lon_b_deg))
    direct_size = lon_high - lon_low
    wrap_size = 360 - direct_size

    if direct_size < wrap_size:
        return lon_low, direct_size
    else:
        return lon_high, wrap_size


def load_dem_from_sar_times(
    dem: Path | str,
    trajectory: Trajectory,
    range_times: npt.NDArray[np.floating],
    azimuth_times: npt.NDArray,
    look_direction: SensorLookDirection,
    wavelength: float = 1.0,
    doppler_frequency: float = 0.0,
) -> xr.DataArray:
    """Load DEM data corresponding to the scene defined by range and azimuth times

    Parameters
    ----------
    dem : Path | str
      path to DEM tiles folder
    trajectory : Trajectory
        sensor trajectory
    range_times : npt.NDArray[np.floating]
        range_times
    azimuth_times : npt.NDArray[np.floating]
        azimuth_times
    look_direction : SensorLookDirection
        sensor side looking
    wavelength : float, optional
        carrier signal wavelength, by default 1
    doppler_frequency : float, optional
        doppler frequency [Hz], by default 0


    Returns
    -------
    xr.DataArray
        DEM data
    """
    dem = Path(dem)
    footprint = _compute_footprint_from_times(
        range_times=range_times,
        azimuth_times=azimuth_times,
        trajectory=trajectory,
        wavelength=wavelength,
        doppler_frequency=doppler_frequency,
        look_direction=look_direction,
    )
    dem_area = get_dem_roi(
        lat_start_deg=footprint[0],
        lon_start_deg=footprint[1],
        lat_size_deg=footprint[2],
        lon_size_deg=footprint[3],
        dem=dem,
    )
    return dem_area
