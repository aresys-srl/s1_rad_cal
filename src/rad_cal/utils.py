# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Utilities for arepytools metadata compilation
---------------------------------------------
"""

import arepytools.io.metadata as mtd
from eo_products.sentinel1.utilities import S1ChannelMetadata


def compile_dataset_info(arepytools_dataset_info: mtd.DataSetInfo, metadata: S1ChannelMetadata) -> mtd.DataSetInfo:
    """Generating the output DataSetInfo for the SLC FR Corrected product.

    Parameters
    ----------
    ref_dataset_info : DataSetInfo
        SLC channel dataset info
    metadata: S1ChannelMetadata
        Sentinel-1 channel metadata

    Returns
    -------
    DataSetInfo
        compiled channel dataset info
    """
    arepytools_dataset_info.description = "Radiometric Re-Calibrated Data"
    arepytools_dataset_info.sensor_name = metadata.general_info.mission_id
    arepytools_dataset_info.image_type = metadata.dataset_info.image_type
    arepytools_dataset_info.projection = metadata.dataset_info.projection
    arepytools_dataset_info.acquisition_station = ""
    arepytools_dataset_info.processing_center = ""
    arepytools_dataset_info.processing_software = "rad-cal"
    arepytools_dataset_info.side_looking = metadata.dataset_info.side_looking

    return arepytools_dataset_info
