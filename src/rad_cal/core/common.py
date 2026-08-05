# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Common functionalities for terrain-corrected angles computation"""

from pathlib import Path
from typing import Literal

import numpy as np
import xarray as xr
from eo_products.dem.getasse30 import get_dem_roi
from numpy import typing as npt
from perseo_core.geometry.coordinates.conversions import xyz2llh
from perseo_core.geometry.geocoding import direct_geocoding_monostatic
from perseo_core.geometry.navigation.trajectory import Trajectory

SensorLookDirection = Literal["RIGHT", "LEFT"]

RANGE_MARGIN_SEC = 0.0001
AZIMUTH_MARGIN_SEC = 0.5


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
