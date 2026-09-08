# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Radiometric Re-Calibration Main Function
----------------------------------------
"""

import logging
import sys
from pathlib import Path

import numpy as np
from arepytools.io import create_product_folder, write_metadata, write_raster_with_raster_info
from eo_products.sentinel1.reader import (
    open_product,
    read_channel_calibration,
    read_channel_data,
    read_channel_metadata,
    read_channel_noise_vectors,
)

from rad_cal.config import Config
from rad_cal.corrections.abs_cal import compute_absolute_calibration_correction
from rad_cal.corrections.ap_gain import compute_eap_gain_correction
from rad_cal.corrections.common import get_aux_files
from rad_cal.corrections.denoising import apply_denoising_correction
from rad_cal.corrections.proc_gain import compute_processing_gain_correction, get_aux_pp1_xml_path_from_product
from rad_cal.corrections.radiometric_conversion import radiometric_quantity_conversion
from rad_cal.utils import create_pf_metadata

logger = logging.getLogger(__name__)


def run(config: Config):
    l1_product_path = Path(config.l1_product)
    aux_pp1_path_new = Path(config.aux_pp1)
    aux_cal_path_new = Path(config.aux_cal)
    output_path = Path(config.output)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(output_path / "rad_cal.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    if not (config.corrections.eap or config.corrections.processing_gain or config.corrections.absolute_calibration):
        raise ValueError("No corrections selected, aborting...")

    summary = f"""
    Recalibrating {l1_product_path.name}
    Selected output radiometric quantity {config.output_quantity.name}
    Incidence angles source : {"ellipsoid" if config.incidence_angles_dem is None else config.incidence_angles_dem}

    Selected corrections
    --------------------
    - Elevation antenna pattern gain        : {"ON" if config.corrections.eap.enabled else "OFF"}
    - Absolute calibration factor           : {"ON" if config.corrections.absolute_calibration else "OFF"}
    - Processing gain                       : {"ON" if config.corrections.processing_gain else "OFF"}
    - Thermal denoising                     : {"ON" if config.corrections.denoising.enabled else "OFF"}

    Auxiliary files in use
    ----------------------
    {aux_pp1_path_new.name}
    {aux_cal_path_new.name}
    """
    logger.info(summary)
    if config.corrections.eap.enabled:
        logger.info(f"DEM source for EAP correction: {config.corrections.eap.dem}")

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
        logger.info(f"Processing channel {channel}")
        channel_raster_file = prod_folder.get_channel_data(channel=ch_id)
        metadata_file, raster_file_path, cal_file, noise_path = prod.get_files_from_channel_name(channel)
        ext_noise_vector_dir = config.corrections.denoising.external_noise_vector_folder
        if ext_noise_vector_dir is not None:
            noise_path = Path(ext_noise_vector_dir).joinpath(noise_path.name)
            if not noise_path.is_file():
                raise FileNotFoundError(
                    f"{noise_path.name} noise file does not exist in external noise folder {ext_noise_vector_dir}"
                )
            logger.info(f"Using external noise calibration file: {noise_path.name}")

        # Always start from beta naught, data is converted later if needed
        scaling_factor = read_channel_calibration(xml_path=cal_file)
        metadata = read_channel_metadata(xml_path=metadata_file)
        list_azimuth_noise_vectors, list_range_noise_vectors = read_channel_noise_vectors(noise_path)
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
            az_block_size = [az_block_size] * blocks_num

        pf_channel_mtd = create_pf_metadata(
            metadata=metadata,
            channel_raster_file=channel_raster_file,
            swath=swath,
            output_quantity=config.output_quantity,
        )

        for bc_num, center in enumerate(blocks_centers_px):
            logger.info(f"Processing block {bc_num + 1} of {blocks_num}")
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

            if config.corrections.eap.enabled:
                eap_gain_correction = compute_eap_gain_correction(
                    channel_metadata=metadata,
                    swath=swath,
                    polarization=pol,
                    aux_cal_xml_path=aux_cal_xml_path_new,
                    az_block_size=az_block_size,
                    bc_num=bc_num,
                    dem=config.corrections.eap.dem,
                )
            else:
                eap_gain_correction = 1

            if config.corrections.processing_gain:
                proc_gain_correction = compute_processing_gain_correction(
                    aux_pp1_xml_path_new=aux_pp1_xml_path_new,
                    aux_pp1_xml_path_original=aux_pp1_xml_path_original,
                    swath=swath,
                    polarization=pol,
                )
            else:
                proc_gain_correction = 1

            if config.corrections.absolute_calibration:
                abs_cal_correction = compute_absolute_calibration_correction(
                    aux_cal_xml_path_new=aux_cal_xml_path_new, aux_cal_xml_path_original=cal_file
                )
            else:
                abs_cal_correction = 1

            target_area = radiometric_quantity_conversion(
                target_area=target_area,
                channel_metadata=metadata,
                swath=swath,
                az_block_size=az_block_size,
                bc_num=bc_num,
                output_quantity=config.output_quantity,
                dem=config.incidence_angles_dem,
            )

            if config.corrections.denoising.enabled:
                target_area = apply_denoising_correction(
                    target_area=target_area,
                    swath=swath,
                    azimuth_indexes=(target_block[0], target_block[0] + target_block[2]),
                    azimuth_noise_vectors=list_azimuth_noise_vectors,
                    range_noise_vectors=list_range_noise_vectors,
                    is_grd=False,
                    scaling_conversion=scaling_factor,
                )

            radiometric_correction = eap_gain_correction * abs_cal_correction * proc_gain_correction
            target_area_recal = target_area * radiometric_correction

            write_raster_with_raster_info(
                raster_file=channel_raster_file,
                data=target_area_recal,
                raster_info=pf_channel_mtd.get_raster_info(),
                start_point=(az_block_size[bc_num] * bc_num, 0),
            )
        write_metadata(pf_channel_mtd, metadata_file=prod_folder.get_channel_metadata(channel=ch_id))
