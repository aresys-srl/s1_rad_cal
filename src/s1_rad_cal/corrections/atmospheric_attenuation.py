# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Atmospheric attenuation according to Recommendation ITU-R P.676-13
------------------------------------------------------------------
"""

from typing import Literal

import numpy as np
import numpy.typing as npt
import xarray as xr
from eo_products.sentinel1.utilities import S1ChannelMetadata
from itur.models.itu676 import gaseous_attenuation_slant_path
from perseo_core.geometry.angles import compute_incidence_angles
from perseo_core.geometry.coordinates.conversions import llh2xyz
from perseo_core.geometry.geocoding import inverse_geocoding_monostatic
from scipy.interpolate import LinearNDInterpolator

ComputationMode = Literal["exact", "approx"]


def compute_atmospheric_attenuation(
    channel_metadata: S1ChannelMetadata,
    azimuth_times: npt.NDArray[np.floating],
    range_times: npt.NDArray[np.floating],
    weather: xr.Dataset,
    mode: ComputationMode,
) -> npt.NDArray[np.floating]:
    """Compute atmospheric attenuation using the ITU-R 676 recommendation.

    Parameters
    ----------
    channel_metadata : S1ChannelMetadata
        Sentinel-1 channel metadata.
    azimuth_times : npt.NDArray
        Azimuth time axis, as PreciseDateTime, onto which the attenuation is interpolated.
    range_times : npt.NDArray[np.floating]
        Range time axis onto which the attenuation is interpolated.
    weather : xr.Dataset
        weather Dataset containing values for temperature `T` [K], pressure `P` [hPa],
        and water vapor density `rho` [g/m^3].
    mode: ComputationMode
        `gaseous_attenuation_slant_path` computation mode, "approx" or "exact"
    Returns
    -------
    npt.NDArray[np.floating]
        Atmospheric attenuation [dB] of shape `(len(azimuth_times), len(range_times)`.
    """

    az_time = azimuth_times[len(azimuth_times) // 2]  # block center
    weather_lon_grid, weather_lat_grid = np.meshgrid(weather.longitude.values, weather.latitude.values)
    weather_coords = np.column_stack((weather_lat_grid.ravel(), weather_lon_grid.ravel()))
    weather_data_ground_points = llh2xyz(
        coordinates=np.column_stack((np.deg2rad(weather_coords), np.zeros(len(weather_coords))))
    )
    weather_az_time, weather_range_time = inverse_geocoding_monostatic(
        trajectory=channel_metadata.orbit,
        ground_points=weather_data_ground_points,
        doppler_frequencies=0.0,
        wavelength=1.0,
        az_initial_time_guesses=az_time,
    )
    rho = np.squeeze(weather["rho"].values)
    pressure = np.squeeze(weather["P"].values)
    temperature = np.squeeze(weather["T"].values)

    # Incidence angle assumed azimuth-invariant
    incidence_angles = compute_incidence_angles(
        trajectory=channel_metadata.orbit,
        azimuth_time=az_time,
        range_times=weather_range_time,
        look_direction=channel_metadata.dataset_info.side_looking,
        radians=False,
    )
    elevation = 90.0 - incidence_angles.reshape(rho.shape)
    attenuation = (
        2
        * gaseous_attenuation_slant_path(
            f=channel_metadata.dataset_info.fc_hz / 1e9,
            el=elevation,
            rho=rho,
            P=pressure,
            T=temperature,
            mode=mode,
        ).value
    )
    az0 = azimuth_times[0]
    az_grid, rg_grid = np.meshgrid(azimuth_times - az0, range_times, indexing="ij")
    interp = LinearNDInterpolator(
        np.column_stack([weather_az_time - az0, weather_range_time]),
        attenuation.flatten(),
        fill_value=0.0,
        rescale=True,
    )
    return interp(az_grid, rg_grid)
