# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Processing Gain
---------------
"""

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
from lxml import etree

from rad_cal import AUX_PP1_DATASET

logger = logging.getLogger(__name__)


@lru_cache(maxsize=20)
def compute_processing_gain_correction(
    aux_pp1_xml_path_new: Path, aux_pp1_xml_path_original: Path, swath: str, polarization: str
) -> float:
    """Compute processing gain correction [dB]

    Parameters
    ----------
    aux_pp1_xml_path_new : Path
        path to the AUX_PP1 file to be applied
    aux_pp1_xml_path_original : Path
        path to the original AUX_PP1 file
    swath : str
        swath name
    polarization : str
        polarization

    Returns
    -------
    float
        processing gain correction [dB]
    """

    proc_gain_new = _get_processing_gain_from_aux_pp1(
        xml_path=aux_pp1_xml_path_new, swath=swath, polarization=polarization
    )
    proc_gain_original = _get_processing_gain_from_aux_pp1(
        xml_path=aux_pp1_xml_path_original, swath=swath, polarization=polarization
    )

    return proc_gain_new / proc_gain_original


def _get_processing_gain_from_aux_pp1(xml_path: str | Path, swath: str, polarization: str) -> float:
    """Retrieve processing gain for AUX_PP1 file ini dB

    Parameters
    ----------
    xml_path : str | Path
        path to AUX_PP1 xml path
    swath : str
        swath name
    polarization : str
        polarization

    Returns
    -------
    float
        processing gain [dB]
    """
    root = etree.parse(Path(xml_path)).getroot()
    for item in root.findall(".//slcProcParams/swathParamsList/swathParams"):
        sw = item.find("swath").text
        if sw == swath:
            gains = np.array(item.find("gain").text.split(" "), dtype=float)
            if polarization == "HH":
                return gains[0]
            if polarization == "HV":
                return gains[1]
            if polarization == "VV":
                return gains[2]
            if polarization == "VH":
                return gains[3]


def get_aux_pp1_xml_path_from_product(path_to_product: str | Path) -> Path:
    """Retrieve the product-associated AUX_PP1 xml file path.

    Parameters
    ----------
    path_to_product : str | Path
        Path to product

    Returns
    -------
    Path
        Path to the associated AUX_PP1 xml file

    Raises
    ------
    FileNotFoundError
        more than one xml files were found
    FileNotFoundError
        no xml files were found
    """
    path_to_product = Path(path_to_product)
    root = etree.parse(path_to_product.joinpath("manifest.safe")).getroot()
    ns = {"safe": "http://www.esa.int/safe/sentinel-1.0"}
    aux_pp1_node = root.find('.//safe:resource[@role="AUX_PP1"]', ns)
    if aux_pp1_node is not None:
        filename = Path(aux_pp1_node.attrib["name"]).name
        target_dir = Path(AUX_PP1_DATASET) / filename / "data"
        xml_files = list(target_dir.glob("*.xml"))
        if not xml_files or len(xml_files) > 1:
            raise FileNotFoundError("AUX_PP1 association failed: none or more than one xml files were found!")
        else:
            xml_file = xml_files[0]
            logger.debug("Associated AUX_PP1 file: {}".format(xml_file))
            return Path(xml_file)
    else:
        raise FileNotFoundError("AUX_PP1 association failed!")
