# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Absolute Calibration Constant
-----------------------------
"""

from functools import lru_cache
from pathlib import Path

from lxml import etree


@lru_cache(maxsize=20)
def compute_absolute_calibration_correction(aux_cal_xml_path_new: Path, aux_cal_xml_path_original: Path) -> float:
    """Compute absolute calibration correction in dB

    Parameters
    ----------
    aux_cal_xml_path_new : Path
        path to AUX_CAL xml file to be applied
    aux_cal_xml_path_original : Path
        path to the original AUX_CAL xml

    Returns
    -------
    float
        absolute calibration correction [dB]
    """
    abs_cal_original = get_abs_cal_constant_from_cal_file(aux_cal_xml_path_original)
    abs_cal_new = get_abs_cal_constant_from_cal_file(aux_cal_xml_path_new)
    return abs_cal_original / abs_cal_new


def get_abs_cal_constant_from_cal_file(aux_cal_xml_path: str | Path) -> dict:
    """Retrieve absolute calibration constant from AUX_CAL file"""
    root = etree.parse(Path(aux_cal_xml_path)).getroot()
    return float(root.findall(".//absoluteCalibrationConstant")[0].text)
