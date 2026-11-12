# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Radiometric Conversion
----------------------
"""

import logging
from pathlib import Path

import numpy as np
import numpy.typing as npt
from eo_products.sentinel1.utilities import S1ChannelMetadata
from perseo_core.geometry.angles import compute_incidence_angles
from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity

from s1_rad_cal.core.angles import compute_terrain_corrected_incidence_angles
from s1_rad_cal.core.common import load_dem_from_sar_times

logger = logging.getLogger(__name__)


def _compute_incidence_angles(
    channel_metadata: S1ChannelMetadata,
    swath: str,
    range_times: npt.NDArray,
    azimuth_times: npt.NDArray,
    dem: Path | None,
) -> npt.NDArray[np.floating]:
    """Compute incidence angles for a SAR area."""
    if dem is not None:
        burst_area_dem = load_dem_from_sar_times(
            dem=dem,
            trajectory=channel_metadata.orbit,
            range_times=range_times,
            azimuth_times=azimuth_times,
            look_direction=channel_metadata.dataset_info.side_looking,
        )

        incidence_angles = compute_terrain_corrected_incidence_angles(
            dem_values=burst_area_dem.values,
            dem_lat_axis=burst_area_dem.lat.values,
            dem_lon_axis=burst_area_dem.lon.values,
            trajectory=channel_metadata.orbit,
            range_times=range_times,
            azimuth_times=azimuth_times,
        )
    else:
        time_idx = np.argmin(
            abs(channel_metadata.antenna_pattern[swath].time_axis - azimuth_times[len(azimuth_times) // 2])
        )
        incidence_angles = compute_incidence_angles(
            trajectory=channel_metadata.orbit,
            azimuth_time=azimuth_times[len(azimuth_times) // 2],
            range_times=range_times,
            look_direction=channel_metadata.dataset_info.side_looking,
            geodetic_altitude=channel_metadata.antenna_pattern[swath].terrain_height[time_idx],
        )
        incidence_angles = np.broadcast_to(incidence_angles, (len(azimuth_times), len(range_times)))

    return incidence_angles


def radiometric_quantity_conversion(
    target_area: npt.NDArray,
    channel_metadata: S1ChannelMetadata,
    swath: str,
    azimuth_times: npt.NDArray,
    range_times: npt.NDArray[np.floating],
    output_quantity: SARRadiometricQuantity,
    dem: Path | None = None,
) -> npt.NDArray[np.floating]:
    """Convert a complex SLC calibrated to beta naught amplitude to the requested  `output_quantity`.
    The returned complex data satisfy:

        abs(slc_sigma)**2 = sigma0
        abs(slc_gamma)**2 = gamma0

    If `dem` is provided, local incidence angles are used for conversion,
    otherwise the incidence angles are computed from the inflated ellipsoid.

    Parameters
    ----------
    target_area : npt.NDArray
        target area data in beta naught
    channel_metadata : S1ChannelMetadata
        S1ChannelMetadata object
    swath : str
        swath name
    azimuth_times : npt.NDArray
        Azimuth time axis of the block
    range_times : npt.NDArray[np.floating]
        Slant range axis of the block
    output_quantity : SARRadiometricQuantity
        output radiometric quantity
    dem : Path | None, optional
        path to DEM tiles folder, by default None

    Returns
    -------
    npt.NDArray[np.floating]
        converted target area data
    """
    if output_quantity == SARRadiometricQuantity.BETA_NOUGHT:
        return target_area

    incidence_angles = _compute_incidence_angles(
        channel_metadata=channel_metadata, swath=swath, range_times=range_times, azimuth_times=azimuth_times, dem=dem
    )

    if output_quantity == SARRadiometricQuantity.SIGMA_NOUGHT:
        logger.info("Converting data from beta nought to sigma nought")
        return target_area * np.sqrt(np.sin(incidence_angles))
    elif output_quantity == SARRadiometricQuantity.GAMMA_NOUGHT:
        logger.info("Converting data from beta nought to gamma nought")
        return target_area * np.sqrt(np.tan(incidence_angles))
    raise ValueError(f"Unsupported output quantity {output_quantity.name} provided")
