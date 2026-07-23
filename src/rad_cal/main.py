# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Radiometric Re-Calibration Main Function
----------------------------------------
"""

from pathlib import Path

import arepytools.io.metadata as mtd
import numpy as np
from arepytools.io import create_new_metadata, create_product_folder, write_metadata, write_raster_with_raster_info
from eo_products.sentinel1.reader import (
    open_product,
    read_channel_calibration,
    read_channel_data,
    read_channel_metadata,
)

from rad_cal.corrections.abs_cal import compute_absolute_calibration_correction
from rad_cal.corrections.ap_gain import compute_eap_gain_correction
from rad_cal.corrections.common import get_aux_files
from rad_cal.corrections.proc_gain import compute_processing_gain_correction, get_aux_pp1_xml_path_from_product
from rad_cal.utils import compile_dataset_info


def run(
    l1_product_path: str | Path, aux_pp1_path_new: str | Path, aux_cal_path_new: str | Path, output_path: str | Path
):
    l1_product_path = Path(l1_product_path)
    aux_pp1_path_new = Path(aux_pp1_path_new)
    aux_cal_path_new = Path(aux_cal_path_new)
    output_path = Path(output_path)

    prod = open_product(l1_product_path)
    aux_cal_xml_path_new, aux_pp1_xml_path_new = get_aux_files(
        l1_product_path=l1_product_path,
        aux_pp1_path=aux_pp1_path_new,
        aux_cal_path=aux_cal_path_new,
        acquisition_time=prod.acquisition_time,
    )
    aux_pp1_xml_path_original = get_aux_pp1_xml_path_from_product(l1_product_path)
    pf_name = output_path.joinpath("PF")
    prod_folder = create_product_folder(pf_path=pf_name, overwrite_ok=True)
    for ch_id, channel in enumerate(prod.channels_list, start=1):
        print(f"Processing channel {channel}")
        channel_raster_file = prod_folder.get_channel_data(channel=ch_id)
        metadata_file, raster_file_path, cal_file, noise_path = prod.get_files_from_channel_name(channel)
        scaling_factor = read_channel_calibration(xml_path=cal_file)
        metadata = read_channel_metadata(xml_path=metadata_file)
        swath = metadata.general_info.swath
        pol = metadata.general_info.polarization.name

        range_axis = metadata.raster_info.samples.axis
        azimuth_axis = metadata.raster_info.lines.axis

        mid_range_pixel = int(range_axis.size // 2)
        if metadata.burst_info.num > 1:
            az_block_size = [metadata.burst_info.lines_per_burst] * metadata.burst_info.num
            blocks_num = metadata.burst_info.num  # number of bursts
            blocks_centers_px = [
                (int(a + b // 2), mid_range_pixel)
                for a, b in zip(
                    np.concatenate([[0], np.cumsum(az_block_size)[:-1]], dtype=int),
                    az_block_size,
                    strict=True,
                )
            ]
        else:
            az_block_size = 2000
            blocks_num = int(np.floor(azimuth_axis.size / az_block_size))
            blocks_centers_px = np.arange(az_block_size // 2, az_block_size * blocks_num, az_block_size).tolist()
            blocks_centers_px = [(px, mid_range_pixel) for px in blocks_centers_px]

        pf_raster_info = mtd.RasterInfo(
            lines=metadata.raster_info.lines.length,
            samples=metadata.raster_info.samples.length,
            celltype=metadata.raster_info.data_type,
            filename=channel_raster_file.name,
        )
        pf_swath_info = mtd.SwathInfo(swath_i=swath, polarization_i=metadata.general_info.polarization.value)
        pf_dataset_info = mtd.DataSetInfo(
            acquisition_mode_i=metadata.dataset_info.acquisition_mode, image_quantity="BETA"
        )
        pf_dataset_info = compile_dataset_info(arepytools_dataset_info=pf_dataset_info, metadata=metadata)
        pf_dataset_info.description = ""
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

        for bc_num, center in enumerate(blocks_centers_px):
            print(f"Processing block {bc_num + 1} of {blocks_num}")

            cropping_size = (
                range_axis.size,  # range
                az_block_size[bc_num],  # azimuth
            )
            target_block = [
                center[0] - np.floor(cropping_size[1] / 2).astype(int),
                center[1] - np.floor(cropping_size[0] / 2).astype(int),
                cropping_size[1],
                cropping_size[0],
            ]
            target_area = read_channel_data(
                raster_file=raster_file_path, block_to_read=target_block, scaling_conversion=scaling_factor
            )

            eap_gain_correction = compute_eap_gain_correction(
                channel_metadata=metadata,
                swath=swath,
                polarization=pol,
                aux_cal_xml_path=aux_cal_xml_path_new,
                az_block_size=az_block_size,
                bc_num=bc_num,
            )

            proc_gain_correction = compute_processing_gain_correction(
                aux_pp1_xml_path_new=aux_pp1_xml_path_new,
                aux_pp1_xml_path_original=aux_pp1_xml_path_original,
                swath=swath,
                polarization=pol,
            )

            abs_cal_correction = compute_absolute_calibration_correction(
                aux_cal_xml_path_new=aux_cal_xml_path_new, aux_cal_xml_path_original=cal_file
            )

            radiometric_correction = eap_gain_correction * abs_cal_correction * proc_gain_correction
            target_area_recal = target_area * radiometric_correction
            print(
                "Target area mean amplitude [dB] = "
                + f"{np.nanmean(20 * np.log10(np.where(abs(target_area) == 0, np.nan, abs(target_area))))}"
            )
            print(
                "Target area re-calibrated mean amplitude [dB] = "
                + f"{np.nanmean(20 * np.log10(np.where(abs(target_area_recal) == 0, np.nan, abs(target_area_recal))))}"
            )

            pf_burst_info.add_burst(
                range_start_time_i=range_axis[0],
                azimuth_start_time_i=az_block_size * bc_num,
                lines_i=metadata.burst_info.lines_per_burst,
            )
            write_raster_with_raster_info(
                raster_file=channel_raster_file,
                data=target_area_recal,
                raster_info=pf_raster_info,
                start_point=(az_block_size[bc_num] * bc_num, 0),
            )

        pf_channel_mtd.insert_element(pf_burst_info)
        write_metadata(pf_channel_mtd, metadata_file=prod_folder.get_channel_metadata(channel=ch_id))
