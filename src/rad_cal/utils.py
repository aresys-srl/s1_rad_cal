# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Utilities for arepytools metadata compilation
---------------------------------------------
"""

from pathlib import Path

import arepytools.io.metadata as mtd
from arepytools.io import create_new_metadata
from eo_products.sentinel1.utilities import S1ChannelMetadata


def _compile_dataset_info(arepytools_dataset_info: mtd.DataSetInfo, metadata: S1ChannelMetadata) -> mtd.DataSetInfo:
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


def create_pf_metadata(metadata: S1ChannelMetadata, channel_raster_file: Path, swath: str) -> mtd.MetaData:
    """Create product folder metadata DataSetInfo object"""
    pf_raster_info = mtd.RasterInfo(
        lines=metadata.raster_info.lines.length,
        samples=metadata.raster_info.samples.length,
        celltype=metadata.raster_info.data_type,
        filename=channel_raster_file.name,
    )
    pf_swath_info = mtd.SwathInfo(swath_i=swath, polarization_i=metadata.general_info.polarization.value)
    pf_dataset_info = mtd.DataSetInfo(acquisition_mode_i=metadata.dataset_info.acquisition_mode, image_quantity="BETA")
    pf_dataset_info = _compile_dataset_info(arepytools_dataset_info=pf_dataset_info, metadata=metadata)
    pf_state_vector = mtd.StateVectors(
        position_vector=metadata.state_vectors.positions,
        velocity_vector=metadata.state_vectors.velocities,
        t_ref_utc=metadata.state_vectors.time_axis[0],
        dt_sv_s=metadata.state_vectors.time_axis[1] - metadata.state_vectors.time_axis[0],
    )
    pf_burst_info = mtd.BurstInfo()
    pf_channel_mtd = create_new_metadata()
    pf_channel_mtd.insert_element(pf_raster_info)
    pf_channel_mtd.insert_element(pf_swath_info)
    pf_channel_mtd.insert_element(pf_dataset_info)
    pf_channel_mtd.insert_element(pf_state_vector)
    pf_channel_mtd.insert_element(pf_burst_info)
    return pf_channel_mtd
