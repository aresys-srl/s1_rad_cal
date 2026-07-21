# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Common utilities for corrections
--------------------------------
"""

from pathlib import Path

from lxml import etree
from perseo_core.timing.precise_datetime import PreciseDateTime


def get_aux_files(
    l1_product_path: Path, aux_pp1_path: Path, aux_cal_path: Path, acquisition_time: PreciseDateTime
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

    aux_cal_root = etree.parse(aux_cal_path.joinpath("manifest.safe")).getroot()
    aux_cal_ins_config_id = int(aux_cal_root.find(".//s1auxsar:instrumentConfigurationId", ns).text)
    aux_cal_validity = PreciseDateTime.fromisoformat(aux_cal_root.find(".//s1auxsar:validity", ns).text)

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
