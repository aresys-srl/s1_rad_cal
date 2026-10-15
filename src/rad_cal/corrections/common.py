# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Common utilities for corrections
--------------------------------
"""

from pathlib import Path
from typing import Literal

from lxml import etree
from perseo_core.timing.precise_datetime import PreciseDateTime

SensorNames = Literal["S1A", "S1B", "S1C", "S1D"]


def get_aux_files(
    l1_product_path: Path,
    aux_pp1_path: Path,
    aux_cal_path: Path,
    acquisition_time: PreciseDateTime,
    sensor: SensorNames,
) -> tuple[Path, Path]:
    """Retrieve and validate auxiliary files

    Parameters
    ----------
    l1_product_path : Path
        path to product
    aux_pp1_path : Path
        path to AUX_PP1 folder
    aux_cal_path : Path
        path to AUX_CAL folder
    acquisition_time : PreciseDateTime
        acquisition time

    Returns
    -------
    tuple[Path, Path]
        path to AUX_CAL xml file, path to AUX_PP1 xml file
    """
    prod_root = etree.parse(l1_product_path.joinpath("manifest.safe")).getroot()
    ns = {"s1sarl1": "http://www.esa.int/safe/sentinel-1.0/sentinel-1/sar/level-1"}
    prod_ins_config_id = int(prod_root.find(".//s1sarl1:instrumentConfigurationID", ns).text)

    aux_pp1_root = etree.parse(aux_pp1_path.joinpath("manifest.safe")).getroot()
    ns = {"s1auxsar": "http://www.esa.int/safe/sentinel-1.0/sentinel-1/auxiliary/sar"}
    aux_pp1_ins_config_id = int(aux_pp1_root.find(".//s1auxsar:instrumentConfigurationId", ns).text)
    aux_pp1_validity = PreciseDateTime.fromisoformat(aux_pp1_root.find(".//s1auxsar:validity", ns).text)
    aux_pp1_sensor = aux_pp1_path.name.split("_")[0]

    aux_cal_root = etree.parse(aux_cal_path.joinpath("manifest.safe")).getroot()
    aux_cal_ins_config_id = int(aux_cal_root.find(".//s1auxsar:instrumentConfigurationId", ns).text)
    aux_cal_validity = PreciseDateTime.fromisoformat(aux_cal_root.find(".//s1auxsar:validity", ns).text)
    aux_cal_sensor = aux_cal_path.name.split("_")[0]

    if aux_pp1_sensor != sensor:
        raise ValueError("Product ({}) and AUX_PP1 ({}) sensor names differ!".format(sensor, aux_pp1_sensor))

    if aux_cal_sensor != sensor:
        raise ValueError("Product ({}) and AUX_CAL ({}) sensor names differ!".format(sensor, aux_cal_sensor))

    if prod_ins_config_id != aux_pp1_ins_config_id:
        raise ValueError(
            "Product ({}) and AUX_PP1 ({}) instrument config ids differ!".format(
                prod_ins_config_id, aux_pp1_ins_config_id
            )
        )
    if prod_ins_config_id != aux_cal_ins_config_id:
        raise ValueError(
            "Product ({}) and AUX_CAL ({}) instrument config ids differ!".format(
                prod_ins_config_id, aux_cal_ins_config_id
            )
        )
    if acquisition_time < aux_pp1_validity:
        raise ValueError("Product outside of AUX_PP1 time validity")
    if acquisition_time < aux_cal_validity:
        raise ValueError("Product outside of AUX_CAL time validity")

    aux_pp1_xml_path = [p for p in aux_pp1_path.joinpath("data").glob("*xml") if "aux-pp1" in p.name][0]
    aux_cal_xml_path = [p for p in aux_cal_path.joinpath("data").glob("*xml") if "aux-cal" in p.name][0]
    return (aux_cal_xml_path, aux_pp1_xml_path)


def apply_roll_correction(roll: float, mission_id: str, az_time: PreciseDateTime) -> float:
    """Apply a 30 milli-degrees correction to roll for S1D product if product data is before 2026/02/23

    Parameters
    ----------
    roll : float
        roll
    mission_id : str
        mission identifier, e.g. S1D
    az_time : PreciseDateTime
        azimuth time

    Returns
    -------
    float
        corrected roll
    """
    roll_data = PreciseDateTime.from_numeric_datetime(year=2026, month=2, day=23, hours=8, minutes=35)
    if mission_id == "S1D" and az_time < roll_data:
        return roll + 0.03
    else:
        return roll
