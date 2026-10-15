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

from rad_cal.core.angles import compute_terrain_corrected_look_angles
from rad_cal.core.common import load_dem_from_sar_times
from rad_cal.corrections.common import apply_roll_correction


def compute_eap_gain_correction(
    channel_metadata: S1ChannelMetadata,
    swath: str,
    polarization: str,
    aux_cal_xml_path: Path | str,
    azimuth_times: npt.NDArray[np.floating],
    range_times: npt.NDArray[np.floating],
    dem: Path | None = None,
    is_grd: bool = False,
) -> npt.NDArray[np.complexfloating]:
    """Compute elevation antenna pattern gain correction for each pixel of the block

    Parameters
    ----------
    channel_metadata : S1ChannelMetadata
    swath : str
        (sub-)swath name of the block, e.g. IW1
    polarization : str
    aux_cal_xml_path : Path | str
        path to AUX_CAL xml file
    azimuth_times : npt.NDArray
        Azimuth time axis of the block
    range_times : npt.NDArray[np.floating]
        Slant range time axis of the block
    dem : Path | None, optional
        path to DEM tiles folder, by default None
    is_grd : bool, optional
        flag to mark whether product type is GRD, by default False
    """
    aux_cal_xml_path = Path(aux_cal_xml_path)
    az_time = azimuth_times[len(azimuth_times) // 2]  # block center

    if dem is not None:
        dem_area = load_dem_from_sar_times(
            dem=dem,
            trajectory=channel_metadata.orbit,
            range_times=range_times,
            azimuth_times=azimuth_times,
            look_direction=channel_metadata.dataset_info.side_looking,
        )

        look_angles = compute_terrain_corrected_look_angles(
            dem_values=dem_area.values,
            dem_lat_axis=dem_area.lat.values,
            dem_lon_axis=dem_area.lon.values,
            trajectory=channel_metadata.orbit,
            range_times=range_times,
            azimuth_times=azimuth_times,
            radians=False,
        )
    else:
        time_idx = (
            np.ma.masked_greater(channel_metadata.antenna_pattern[swath].time_axis - az_time, 0).astype(float).argmax()
        )
        look_angles = compute_look_angles(
            trajectory=channel_metadata.orbit,
            azimuth_time=az_time,
            range_times=range_times,
            look_direction=channel_metadata.dataset_info.side_looking,
            geodetic_altitude=channel_metadata.antenna_pattern[swath].terrain_height[time_idx],
            radians=False,
        )
        look_angles = np.broadcast_to(look_angles, (len(azimuth_times), len(range_times)))

    block_look_angles = compute_look_angles(
        trajectory=channel_metadata.orbit,
        azimuth_time=az_time,
        range_times=range_times,
        look_direction=channel_metadata.dataset_info.side_looking,
        radians=False,
    )
    original_eap = _compute_antenna_pattern_gain_from_metadata(
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
    new_eap, new_look_angles = _get_elevation_antenna_pattern_from_aux_cal(
        xml_path=aux_cal_xml_path, swath=swath, polarization=polarization, roll=roll
    )
    new_eap = np.interp(look_angles, new_look_angles, new_eap)
    eap_correction_raw = original_eap / new_eap

    eap_correction_abs = np.sqrt(abs(eap_correction_raw))
    eap_correction_phase = np.angle(eap_correction_raw)

    complex_correction = eap_correction_abs * np.exp(1j * eap_correction_phase)

    return np.abs(complex_correction) if is_grd else complex_correction


def _compute_antenna_pattern_gain_from_metadata(
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
    return antenna_pattern_reinterp


def _get_elevation_antenna_pattern_from_aux_cal(
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

    return eap_complex, elevation_angles + roll
