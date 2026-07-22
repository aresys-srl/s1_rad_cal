# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Elevation Antenna Pattern Gain Computation
------------------------------------------
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
from eo_products.sentinel1.utilities import S1ChannelMetadata
from lxml import etree
from perseo_core.geometry.angles import compute_look_angles
from perseo_core.timing.precise_datetime import PreciseDateTime
from sct_sentinel1_reader.protocol_implementation import Sentinel1ChannelManager

from rad_cal import GETASSE_DEM_FOLDER
from rad_cal.core.look_angles import compute_terrain_corrected_look_angles, load_dem_from_sar_times
from rad_cal.corrections.common import apply_roll_correction


def compute_eap_gain_correction(
    channel_metadata: S1ChannelMetadata,
    channel_manager: Sentinel1ChannelManager,
    swath: str,
    polarization: str,
    aux_cal_xml_path: Path | str,
    az_block_size: npt.NDArray[np.integer],
    bc_num: int,
) -> npt.NDArray[np.floating]:
    """Compute elevation antenna pattern gain correction [dB] for each pixel of the current azimuth block

    Parameters
    ----------
    channel_metadata : S1ChannelMetadata
        S1ChannelMetadata object
    channel_manager : Sentinel1ChannelManager
        Sentinel1ChannelManager object
    swath : str
        swath name
    polarization : str
        polarization
    aux_cal_xml_path : Path | str
       Path to the AUX_CAL xml file
    az_block_size : npt.NDArray[np.integer]
        Azimuth lines of each azimuth block
    bc_num : int
        Block center index

    Returns
    -------
    npt.NDArray[np.floating]
        elevation antenna pattern gain correction [dB]
    """

    aux_cal_xml_path = Path(aux_cal_xml_path)
    azimuth_times = channel_manager.azimuth_axis[
        np.sum(az_block_size[:bc_num]) : np.sum(az_block_size[:bc_num]) + az_block_size[bc_num]
    ]
    burst_area_dem = load_dem_from_sar_times(
        dem=GETASSE_DEM_FOLDER,
        trajectory=channel_manager.trajectory,
        range_times=channel_manager.range_axis,
        azimuth_times=azimuth_times,
        look_direction=channel_manager.looking_side.name.split("_")[0],
    )

    terrain_corrected_look_angles = compute_terrain_corrected_look_angles(
        dem_values=burst_area_dem.values,
        dem_lat_axis=burst_area_dem.lat.values,
        dem_lon_axis=burst_area_dem.lon.values,
        trajectory=channel_manager.trajectory,
        range_times=channel_manager.range_axis,
        azimuth_times=azimuth_times,
        radians=False,
    )
    az_time = azimuth_times[az_block_size[bc_num] // 2]
    block_look_angles = compute_look_angles(
        trajectory=channel_metadata.orbit,
        azimuth_time=az_time,
        range_times=channel_manager.range_axis,
        look_direction=channel_metadata.dataset_info.side_looking,
        radians=False,
    )
    original_eap = compute_antenna_pattern_gain_from_metadata(
        channel_metadata=channel_metadata,
        swath=swath,
        az_time=az_time,
        look_angles_axis=block_look_angles,
    )
    antenna_pattern_id = (
        np.ma.masked_greater(channel_metadata.antenna_pattern[swath].time_axis - az_time, 0).astype(float).argmax()
    )
    roll = apply_roll_correction(
        roll=channel_metadata.antenna_pattern[swath].roll[antenna_pattern_id],
        mission_id=channel_metadata.general_info.mission_id,
        az_time=az_time,
    )
    new_eap, new_look_angles = get_elevation_antenna_pattern_from_aux_cal(
        xml_path=aux_cal_xml_path, swath=swath, polarization=polarization, roll=roll
    )
    new_eap = np.interp(terrain_corrected_look_angles, new_look_angles, new_eap)
    eap_gain_correction = original_eap - new_eap

    return eap_gain_correction


def compute_antenna_pattern_gain_from_metadata(
    channel_metadata: S1ChannelMetadata,
    swath: str,
    az_time: PreciseDateTime,
    look_angles_axis: npt.NDArray[np.floating],
) -> npt.NDArray[np.floating]:
    """Compute antenna pattern gain [dB]

    Parameters
    ----------
    channel_metadata : S1ChannelMetadata
        Sentinel1 Channel Metadata class
    swath : str
        swath name
    az_time : PreciseDateTime
        azimuth time
    look_angles_axis : npt.NDArray[np.floating]
        look angles on which the antenna pattern gain is interpolated

    Returns
    -------
    npt.NDArray[np.floating]
        antenna pattern gain re-interpolated on the look angles axis
    """
    antenna_pattern_id = (
        np.ma.masked_greater(channel_metadata.antenna_pattern[swath].time_axis - az_time, 0).astype(float).argmax()
    )
    antenna_pattern = channel_metadata.antenna_pattern[swath].elevation_pattern_array[antenna_pattern_id, :]
    antenna_pattern_reinterp = np.interp(
        look_angles_axis,
        channel_metadata.antenna_pattern[swath].elevation_angle_array[antenna_pattern_id],
        antenna_pattern,
    )
    return 10 * np.log10(abs(antenna_pattern_reinterp))


def get_elevation_antenna_pattern_from_aux_cal(
    xml_path: str | Path,
    swath: str,
    polarization: str,
    roll: float,
) -> tuple[npt.NDArray[np.floating], npt.NDArray[np.floating]]:
    """Get the elevation antenna pattern [dB] from AUX_CAL xml file

    Parameters
    ----------
    xml_path : str | Path
        path to AUX_CAL file
    swath : str
        swath name
    polarization : str
        polarization
    roll : float
        roll angle [deg]

    Returns
    -------
    npt.NDArray[np.floating]
        Elevation antenna pattern [dB]
    npt.NDArray[np.floating]
        Look angles array [deg]
    """
    root = etree.parse(Path(xml_path)).getroot()
    for param in root.findall(".//calibrationParams"):
        sw = param.find("swath").text
        pol = param.find("polarisation").text
        if sw == swath and pol == polarization:
            eap_real = np.array(param.find("elevationAntennaPattern/values").text.split(" ")[::2], dtype=float)
            eap_imag = np.array(param.find("elevationAntennaPattern/values").text.split(" ")[1::2], dtype=float)
            ea_increment = float(param.find("elevationAntennaPattern/elevationAngleIncrement").text)
            count = len(eap_real)
            elevation_angles = np.arange(-(count - 1) / 2 * ea_increment, count / 2 * ea_increment, ea_increment)

            eap_complex = eap_real + 1j * eap_imag

    return 10 * np.log10(abs(eap_complex)), elevation_angles + roll
