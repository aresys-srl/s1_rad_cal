# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Utilities for arepytools metadata compilation
---------------------------------------------
"""

from pathlib import Path

import arepytools.io.metadata as mtd
import arepytools.timing.precisedatetime as att
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
    arepytools_dataset_info.fc_hz = metadata.dataset_info.fc_hz

    return arepytools_dataset_info


def create_pf_metadata(metadata: S1ChannelMetadata, channel_raster_file: Path, swath: str) -> mtd.MetaData:
    """Create product folder metadata DataSetInfo object"""
    pf_raster_info = mtd.RasterInfo(
        lines=metadata.raster_info.lines.length,
        samples=metadata.raster_info.samples.length,
        celltype=metadata.raster_info.data_type,
        filename=channel_raster_file.name,
    )
    pf_raster_info.set_lines_axis(
        lines_start=att.PreciseDateTime.from_sec85(metadata.raster_info.lines.start.sec85),
        lines_start_unit="Utc",
        lines_step=metadata.raster_info.lines.step,
        lines_step_unit="s",
    )
    pf_raster_info.set_samples_axis(
        samples_start=metadata.raster_info.samples.start,
        samples_start_unit="s" if metadata.general_info.product_type.value == "SLC" else "m",
        samples_step=metadata.raster_info.samples.step,
        samples_step_unit="s" if metadata.general_info.product_type.value == "SLC" else "m",
    )

    pf_swath_info = mtd.SwathInfo(
        swath_i=swath,
        polarization_i=metadata.general_info.polarization.value,
        acquisition_prf_i=metadata.swath_info.prf,
    )
    pf_swath_info.acquisition_start_time = att.PreciseDateTime.from_sec85(metadata.general_info.start_time.sec85)
    acq_mode = (
        "TOPSAR" if metadata.dataset_info.acquisition_mode in ["EW", "IW"] else metadata.dataset_info.acquisition_mode
    )
    pf_dataset_info = mtd.DataSetInfo(acquisition_mode_i=acq_mode, image_quantity="BETA")
    pf_dataset_info = _compile_dataset_info(arepytools_dataset_info=pf_dataset_info, metadata=metadata)
    pf_state_vector = mtd.StateVectors(
        position_vector=metadata.state_vectors.positions,
        velocity_vector=metadata.state_vectors.velocities,
        t_ref_utc=metadata.state_vectors.time_axis[0],
        dt_sv_s=metadata.state_vectors.time_axis[1] - metadata.state_vectors.time_axis[0],
    )
    pf_sampling_constant = mtd.SamplingConstants(
        frg_hz_i=metadata.sampling_constants.range_freq_hz,
        brg_hz_i=metadata.sampling_constants.range_bandwidth_freq_hz,
        faz_hz_i=metadata.sampling_constants.azimuth_freq_hz,
        baz_hz_i=metadata.sampling_constants.azimuth_bandwidth_freq_hz,
    )
    pf_burst_info = mtd.BurstInfo()
    if metadata.burst_info.num == 1:
        pf_burst_info.add_burst(
            range_start_time_i=metadata.burst_info.range_start_times,
            azimuth_start_time_i=metadata.burst_info.azimuth_start_times,
            lines_i=metadata.burst_info.lines_per_burst,
        )
    else:
        for burst_id in range(metadata.burst_info.num):
            pf_burst_info.add_burst(
                range_start_time_i=metadata.burst_info.range_start_times[burst_id],
                azimuth_start_time_i=metadata.burst_info.azimuth_start_times[burst_id],
                lines_i=metadata.burst_info.lines_per_burst,
            )

    pf_channel_mtd = create_new_metadata()
    pf_channel_mtd.insert_element(pf_raster_info)
    pf_channel_mtd.insert_element(pf_swath_info)
    pf_channel_mtd.insert_element(pf_dataset_info)
    pf_channel_mtd.insert_element(pf_state_vector)
    pf_channel_mtd.insert_element(pf_sampling_constant)

    return pf_channel_mtd
