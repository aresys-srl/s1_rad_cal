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
from perseo_core.timing.precise_datetime import PreciseDateTime


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
    """Get the elevation antenna pattern from AUX_CAL xml file

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
    tuple[npt.NDArray[np.floating], npt.NDArray[np.floating]]
        Elevation antenna pattern and look angles array [deg]
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
