# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Radiometric Re-Calibration Main Function
----------------------------------------
"""

from pathlib import Path

import numpy as np
from eo_products.sentinel1.reader import open_product, read_channel_metadata
from perseo_quality.radiometric_analysis.block_wise.core.radiometric_profiles import blocks_partitioning
from sct_sentinel1_reader.protocol_implementation import Sentinel1ChannelManager

from rad_cal import GETASSE_DEM_FOLDER
from rad_cal.core.look_angles import compute_terrain_corrected_look_angles, load_dem_from_sar_times
from rad_cal.corrections.abs_cal import compute_absolute_calibration_correction
from rad_cal.corrections.common import get_aux_files
from rad_cal.corrections.proc_gain import compute_processing_gain_correction, get_aux_pp1_xml_path_from_product


def run(
    l1_product_path: str | Path, aux_pp1_path_new: str | Path, aux_cal_path_new: str | Path, output_path: str | Path
):
    l1_product_path = Path(l1_product_path)
    aux_pp1_path_new = Path(aux_pp1_path_new)
    aux_cal_path_new = Path(aux_cal_path_new)
    output_path = Path(output_path)

    # Define product channels
    prod = open_product(l1_product_path)
    aux_cal_xml_path_new, aux_pp1_xml_path_new = get_aux_files(
        l1_product_path=l1_product_path,
        aux_pp1_path=aux_pp1_path_new,
        aux_cal_path=aux_cal_path_new,
        acquisition_time=prod.acquisition_time,
    )
    aux_pp1_xml_path_original = get_aux_pp1_xml_path_from_product(l1_product_path)
    for ch_id, channel in enumerate(prod.channels_list):
        print(f"Processing channel {channel}")
        metadata_file, raster_file_path, cal_file, noise_path = prod.get_files_from_channel_name(channel)
        metadata = read_channel_metadata(xml_path=metadata_file)
        swath = metadata.general_info.swath
        pol = metadata.general_info.polarization.name

        proc_gain_correction = compute_processing_gain_correction(
            aux_pp1_xml_path_new=aux_pp1_xml_path_new,
            aux_pp1_xml_path_original=aux_pp1_xml_path_original,
            swath=swath,
            polarization=pol,
        )

        print(proc_gain_correction)

        abs_cal_correction = compute_absolute_calibration_correction(
            aux_cal_xml_path_new=aux_cal_xml_path_new, aux_cal_xml_path_original=cal_file
        )
        print(abs_cal_correction)

        channel_manager = Sentinel1ChannelManager(
            channel_metadata_path=metadata_file,
            channel_raster_path=raster_file_path,
            channel_calibration_path=cal_file,
            channel_noise_path=noise_path,
            channel_name=channel,
        )
        az_block_size, blocks_num, blocks_centers_px = blocks_partitioning(
            azimuth_axis=channel_manager.azimuth_axis,
            range_axis=channel_manager.range_axis,
            lines_per_burst=channel_manager.lines_per_burst,
            default_block_size=2000,
        )

        for bc_num, center in enumerate(blocks_centers_px):
            print(f"Processing block {bc_num + 1} of {blocks_num}")

            cropping_size = (
                channel_manager.slant_range_axis.size,  # range
                az_block_size[bc_num],  # azimuth
            )

            # reading block, without converting the data here, applying radiometric conversion in the next steps
            target_area = channel_manager.read_data(
                azimuth_index=center[0],
                range_index=center[1],
                cropping_size=cropping_size,
                output_radiometric_quantity=channel_manager.radiometric_quantity,
            )

            print(target_area.shape)
            azimuth_times = channel_manager.azimuth_axis[
                np.sum(az_block_size[:bc_num]) : np.sum(az_block_size[:bc_num]) + az_block_size[bc_num]
            ]
            burst_area_dem = load_dem_from_sar_times(
                dem=GETASSE_DEM_FOLDER,
                trajectory=channel_manager.trajectory,
                range_times=channel_manager.range_axis,
                azimuth_times=azimuth_times,
                look_direction=channel_manager.looking_side.name.split("_")[0],
            )

            look_angles = compute_terrain_corrected_look_angles(
                dem_values=burst_area_dem.values,
                dem_lat_axis=burst_area_dem.lat.values,
                dem_lon_axis=burst_area_dem.lon.values,
                trajectory=channel_manager.trajectory,
                range_times=channel_manager.range_axis,
                azimuth_times=azimuth_times,
                radians=False,
            )

            print(look_angles.shape)

    # EAP correction ????


if __name__ == "__main__":
    l1_product_path = Path(
        r"C:\Users\marco.spadoni\Downloads\S1C_IW_SLC__1SSV_20260625T083150_20260625T083221_008259_01054C_3F3E.SAFE"
    )
    aux_pp1_path_new = Path(r"C:\Users\marco.spadoni\Downloads\S1D_AUX_PP1_V20260319T000000_G20260603T073733.SAFE")
    aux_cal_path_new = Path(r"C:\Users\marco.spadoni\Downloads\S1D_AUX_CAL_V20260319T000000_G20260603T113322.SAFE")
    run(
        l1_product_path=l1_product_path,
        aux_cal_path_new=aux_cal_path_new,
        aux_pp1_path_new=aux_pp1_path_new,
        output_path="...",
    )
