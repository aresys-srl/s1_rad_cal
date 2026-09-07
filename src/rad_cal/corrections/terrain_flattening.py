# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Terrain Flattening
------------------
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
from eo_products.sentinel1.utilities import S1ChannelMetadata
from perseo_core.geometry.angles import compute_incidence_angles

from rad_cal.core.angles import compute_terrain_corrected_incidence_angles
from rad_cal.core.common import load_dem_from_sar_times


def compute_terrain_flattening_correction(
    channel_metadata: S1ChannelMetadata,
    swath: str,
    az_block_size: npt.NDArray[np.integer],
    bc_num: int,
    dem: Path | None = None,
) -> npt.NDArray[np.floating]:
    """Compute terrain flattening correction for each pixel of the current block

    Parameters
    ----------
    channel_metadata : S1ChannelMetadata
        S1ChannelMetadata object
    swath : str
        swath name
    az_block_size : npt.NDArray[np.integer]
        Azimuth lines of each azimuth block
    bc_num : int
        Block center index
    dem : Path | None, optional
        path to DEM tiles folder, by default None

    Returns
    -------
    npt.NDArray[np.floating]
        terrain flattening correction as an array of shape (``len(azimuth_times)``, ``len(range_times)``)
    """
    azimuth_times = channel_metadata.raster_info.lines.axis[
        int(np.sum(az_block_size[:bc_num])) : int(np.sum(az_block_size[:bc_num]) + az_block_size[bc_num])
    ]
    range_times = channel_metadata.raster_info.samples.axis

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

    return np.tan(incidence_angles)
