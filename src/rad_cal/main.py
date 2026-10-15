# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Radiometric Re-Calibration Main Function
----------------------------------------
"""

import logging
import sys
from pathlib import Path

from arepytools.io import create_product_folder, write_metadata, write_raster_with_raster_info
from eo_products.sentinel1.reader import (
    open_product,
    read_channel_calibration,
    read_channel_data,
    read_channel_metadata,
    read_channel_noise_vectors,
)
from eo_products.sentinel1.utilities import S1L1ProductType

from rad_cal.config import Config
from rad_cal.corrections.abs_cal import compute_absolute_calibration_correction
from rad_cal.corrections.ap_gain import compute_eap_gain_correction
from rad_cal.corrections.common import get_aux_files
from rad_cal.corrections.denoising import apply_denoising_correction
from rad_cal.corrections.proc_gain import compute_processing_gain_correction, get_aux_pp1_xml_path_from_product
from rad_cal.corrections.radiometric_conversion import radiometric_quantity_conversion
from rad_cal.utils import build_grd_blocks, build_slc_blocks, create_pf_metadata, resolve_noise_path

logger = logging.getLogger(__name__)


def run(
    l1_product_path: str | Path,
    aux_pp1_path: str | Path,
    aux_cal_path: str | Path,
    output_path: str | Path,
    config: Config,
) -> None:
    """Perform radiometric calibration"""
    l1_product_path = Path(l1_product_path)
    aux_pp1_path_new = Path(aux_pp1_path)
    aux_cal_path_new = Path(aux_cal_path)
    output_path = Path(output_path)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(output_path / "rad_cal.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    if not (
        config.corrections.eap
        or config.corrections.processing_gain
        or config.corrections.absolute_calibration
        or config.corrections.denoising.enabled
    ):
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
        sensor=prod.channels_list[0].split("-")[0].upper(),
    )
    aux_pp1_xml_path_original = get_aux_pp1_xml_path_from_product(l1_product_path)
    pf_name = output_path.joinpath("PF")
    prod_folder = create_product_folder(pf_path=pf_name, overwrite_ok=True)
    for ch_id, channel in enumerate(prod.channels_list, start=1):
        logger.info(f"Processing channel {channel}")
        channel_raster_file = prod_folder.get_channel_data(channel=ch_id)
        metadata_file, raster_file_path, cal_file, noise_path = prod.get_files_from_channel_name(channel)
        ext_noise_vector_dir = config.corrections.denoising.external_noise_vector_folder
        noise_path = resolve_noise_path(original_noise_path=noise_path, external_noise_folder=ext_noise_vector_dir)

        # Always start from beta naught, data is converted later if needed
        scaling_factor = read_channel_calibration(xml_path=cal_file)
        metadata = read_channel_metadata(xml_path=metadata_file)
        list_azimuth_noise_vectors, list_range_noise_vectors = read_channel_noise_vectors(noise_path)
        swath = metadata.general_info.swath
        pol = metadata.general_info.polarization.name
        is_grd = metadata.general_info.product_type == S1L1ProductType.GRD

        pf_channel_mtd = create_pf_metadata(
            metadata=metadata,
            channel_raster_file=channel_raster_file,
            swath=swath,
            output_quantity=config.output_quantity,
            is_grd=is_grd,
        )

        blocks = (
            build_grd_blocks(metadata=metadata, metadata_file=metadata_file)
            if is_grd
            else build_slc_blocks(metadata=metadata, swath=swath)
        )

        for block in blocks:
            logger.info(f"Processing block {block.index + 1} of {len(blocks)}")
            target_area = read_channel_data(
                raster_file=raster_file_path,
                block_to_read=block.target_block,
                scaling_conversion=scaling_factor,
            )

            if config.corrections.eap.enabled:
                eap_gain_correction = compute_eap_gain_correction(
                    channel_metadata=metadata,
                    swath=block.swath,
                    polarization=pol,
                    aux_cal_xml_path=aux_cal_xml_path_new,
                    azimuth_times=block.azimuth_axis,
                    range_times=block.range_axis,
                    dem=config.corrections.eap.dem,
                    is_grd=is_grd,
                )
            else:
                eap_gain_correction = 1.0

            if config.corrections.processing_gain:
                proc_gain_correction = compute_processing_gain_correction(
                    aux_pp1_xml_path_new=aux_pp1_xml_path_new,
                    aux_pp1_xml_path_original=aux_pp1_xml_path_original,
                    swath=block.swath,
                    polarization=pol,
                )
            else:
                proc_gain_correction = 1.0

            if config.corrections.absolute_calibration:
                abs_cal_correction = compute_absolute_calibration_correction(
                    aux_cal_xml_path_new=aux_cal_xml_path_new, aux_cal_xml_path_original=cal_file
                )
            else:
                abs_cal_correction = 1.0

            if not is_grd:
                target_area = radiometric_quantity_conversion(
                    target_area=target_area,
                    channel_metadata=metadata,
                    swath=swath,
                    azimuth_times=block.azimuth_axis,
                    range_times=block.range_axis,
                    output_quantity=config.output_quantity,
                    dem=config.incidence_angles_dem,
                )

            if config.corrections.denoising.enabled:
                target_area = apply_denoising_correction(
                    target_area=target_area,
                    swath=swath,
                    azimuth_indexes=(block.first_line, block.first_line + block.n_lines),
                    range_indexes=(block.first_sample, block.first_sample + block.n_samples),
                    azimuth_noise_vectors=list_azimuth_noise_vectors,
                    range_noise_vectors=list_range_noise_vectors,
                    scaling_conversion=scaling_factor,
                    is_grd=is_grd,
                )

            radiometric_correction = eap_gain_correction * abs_cal_correction * proc_gain_correction
            target_area_recal = target_area * radiometric_correction
            write_raster_with_raster_info(
                raster_file=channel_raster_file,
                data=target_area_recal,
                raster_info=pf_channel_mtd.get_raster_info(),
                start_point=(block.first_line, block.first_sample),
            )
        write_metadata(pf_channel_mtd, metadata_file=prod_folder.get_channel_metadata(channel=ch_id))
    logger.info(f"Results saved to {output_path}")
