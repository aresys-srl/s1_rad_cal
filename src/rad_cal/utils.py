# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Utilities for arepytools metadata compilation
---------------------------------------------
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import arepytools.io.metadata as mtd
import arepytools.timing.precisedatetime as att
import numpy as np
from arepytools.io import create_new_metadata
from eo_products.sentinel1.utilities import S1ChannelMetadata
from perseo_core.timing import PreciseDateTime
from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity

logger = logging.getLogger(__name__)

C: int = 299792458  # m/s


@dataclass(frozen=True)
class DataBlock:
    first_line: int
    first_sample: int
    n_lines: int
    n_samples: int
    azimuth_axis: np.ndarray
    range_axis: np.ndarray
    swath: str
    index: int

    @property
    def target_block(self) -> list[int]:
        """Data block specified as a list of 4 integers, in the form:

        0. first line
        1. first sample
        2. total number of lines
        3. total number of samples

        Returns
        -------
        list[int]
            target block
        """
        return [self.first_line, self.first_sample, self.n_lines, self.n_samples]


def resolve_noise_path(original_noise_path: str | Path, external_noise_folder: str | Path | None) -> Path:
    original_noise_path = Path(original_noise_path)
    if external_noise_folder is not None:
        external_noise_folder = Path(external_noise_folder)
        noise_path = external_noise_folder.joinpath(original_noise_path.name)
        if not noise_path.is_file():
            raise FileNotFoundError(
                f"{noise_path.name} noise file does not exist in external noise folder {external_noise_folder}"
            )
        logger.info(f"Using external noise calibration file: {noise_path.name}")
        return noise_path
    return original_noise_path


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


def create_pf_metadata(
    metadata: S1ChannelMetadata,
    channel_raster_file: Path,
    swath: str,
    output_quantity: SARRadiometricQuantity,
    is_grd: bool,
) -> mtd.MetaData:
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

    mode = metadata.dataset_info.acquisition_mode
    if mode in ["EW", "IW"]:
        acq_mode = "TOPSAR"
    elif mode in ["S1", "S2", "S3", "S4", "S5", "S6"]:
        acq_mode = "STRIPMAP"
    elif mode == "WV":
        acq_mode = "WAVE"
    else:
        acq_mode = mode

    pf_dataset_info = mtd.DataSetInfo(acquisition_mode_i=acq_mode, image_quantity=output_quantity.name.split("_")[0])
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
            range_start_time_i=float(metadata.burst_info.range_start_times),
            azimuth_start_time_i=metadata.burst_info.azimuth_start_times,
            lines_i=metadata.burst_info.lines_per_burst,
        )
    else:
        for burst_id in range(metadata.burst_info.num):
            pf_burst_info.add_burst(
                range_start_time_i=float(metadata.burst_info.range_start_times[burst_id]),
                azimuth_start_time_i=metadata.burst_info.azimuth_start_times[burst_id],
                lines_i=metadata.burst_info.lines_per_burst,
            )

    if is_grd:
        ground_to_slant_list = []
        for conversion_function in metadata.coordinate_conversions.ground_to_slant:
            slant_time = conversion_function.function(metadata.raster_info.samples.axis) * 2 / C
            coeffs = np.polyfit(
                metadata.raster_info.samples.axis, slant_time, len(conversion_function.function.coef) - 1
            )
            ground_to_slant_list.append(
                mtd.GroundToSlant(
                    i_ref_az=conversion_function.azimuth_reference_time,
                    i_ref_rg=0.0,
                    i_coefficients=np.flip(coeffs).tolist(),
                )
            )
        ground_to_slant_vector = mtd.GroundToSlantVector(ground_to_slant_list)

        slant_to_ground_list = []
        for az_idx, conversion_function in enumerate(metadata.coordinate_conversions.slant_to_ground):
            slant_time = (
                metadata.coordinate_conversions.ground_to_slant[az_idx].function(metadata.raster_info.samples.axis)
                * 2
                / C
            )
            coeffs = np.polyfit(
                slant_time, metadata.raster_info.samples.axis, len(conversion_function.function.coef) - 1
            )
            slant_to_ground_list.append(
                mtd.SlantToGround(
                    i_ref_az=conversion_function.azimuth_reference_time,
                    i_ref_rg=0.0,
                    i_coefficients=np.flip(coeffs).tolist(),
                )
            )
        slant_to_ground_vector = mtd.SlantToGroundVector(slant_to_ground_list)

    pf_channel_mtd = create_new_metadata()
    pf_channel_mtd.insert_element(pf_raster_info)
    pf_channel_mtd.insert_element(pf_swath_info)
    pf_channel_mtd.insert_element(pf_dataset_info)
    pf_channel_mtd.insert_element(pf_state_vector)
    pf_channel_mtd.insert_element(pf_sampling_constant)
    pf_channel_mtd.insert_element(pf_burst_info)
    if is_grd:
        pf_channel_mtd.insert_element(slant_to_ground_vector)
        pf_channel_mtd.insert_element(ground_to_slant_vector)

    return pf_channel_mtd


def parse_swath_bounds(xml_path: str) -> dict[str, list[dict]]:
    """Parse metadata of GRD product and return a dictionary containing the swath bounds list.

    Parameters
    ----------
    xml_path : str
        path to xml metadata file of GRD product

    Returns
    -------
    dict[str, list[dict]]
        swath bounds list dictionary
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    swaths: dict[str, list[dict]] = {}
    for sm in root.iter("swathMerge"):
        swath_name = sm.findtext("swath", "").strip()
        if not swath_name:
            continue
        bounds_list = sm.find("swathBoundsList")
        if bounds_list is None:
            continue
        rectangles = []
        for sb in bounds_list.findall("swathBounds"):
            rectangles.append(
                {
                    "firstAzimuth": int(sb.findtext("firstAzimuthLine", "0")),
                    "lastAzimuth": int(sb.findtext("lastAzimuthLine", "0")),
                    "firstRange": int(sb.findtext("firstRangeSample", "0")),
                    "lastRange": int(sb.findtext("lastRangeSample", "0")),
                    "azimuthTime": PreciseDateTime.from_utc_string(sb.findtext("azimuthTime", "")),
                }
            )
        swaths[swath_name] = rectangles
    return swaths


def build_slc_blocks(metadata: S1ChannelMetadata, swath: str) -> list[DataBlock]:
    """Build a list of SLC `DataBlock`"""
    range_axis = metadata.raster_info.samples.axis
    azimuth_axis = metadata.raster_info.lines.axis
    n_samples = range_axis.size

    if metadata.burst_info.num > 1:
        lpb = metadata.burst_info.lines_per_burst
        sizes = [lpb] * metadata.burst_info.num
    else:
        size = 2000
        sizes = [size] * int(azimuth_axis.size // size)

    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(int)
    return [
        DataBlock(
            first_line=int(s),
            first_sample=0,
            n_lines=n,
            n_samples=n_samples,
            azimuth_axis=azimuth_axis[s : s + n],
            range_axis=range_axis,
            swath=swath,
            index=i,
        )
        for i, (s, n) in enumerate(zip(starts, sizes, strict=True))
    ]


def build_grd_blocks(metadata: S1ChannelMetadata, metadata_file: Path) -> list[DataBlock]:
    """Build a list of GRD `DataBlock`"""
    ground_axis = metadata.raster_info.samples.axis
    azimuth_axis = metadata.raster_info.lines.axis
    blocks, idx = [], 0
    for sw, bounds in parse_swath_bounds(xml_path=metadata_file).items():
        for bound in bounds:
            first_line, last_line = bound["firstAzimuth"], bound["lastAzimuth"]
            first_sample, last_sample = bound["firstRange"], bound["lastRange"]
            slant = metadata.coordinate_conversions.evaluate_ground_to_slant(
                azimuth_time=azimuth_axis[len(azimuth_axis) // 2],
                ground_range=ground_axis[first_sample : last_sample + 1],
            )
            slant = 2 * slant / C
            blocks.append(
                DataBlock(
                    first_line=first_line,
                    first_sample=first_sample,
                    n_lines=last_line - first_line + 1,
                    n_samples=last_sample - first_sample + 1,
                    azimuth_axis=azimuth_axis[first_line : last_line + 1],
                    range_axis=slant,
                    swath=sw,
                    index=idx,
                )
            )
            idx += 1
    return blocks
