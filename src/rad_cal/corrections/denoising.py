# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""
Denosing
--------
"""

import numpy as np
import numpy.typing as npt
from eo_products.sentinel1.utilities import S1AzimuthNoiseVector, S1RangeNoiseVector, get_noise_vectors


def apply_denoising_correction(
    target_area: npt.NDArray[np.complex64],
    swath: str,
    azimuth_indexes: tuple[int, int],
    azimuth_noise_vectors: list[S1AzimuthNoiseVector] | None,
    range_noise_vectors: list[S1RangeNoiseVector],
    scaling_conversion: float,
    is_grd: bool,
) -> npt.NDArray[np.complex64]:
    noise_vectors = get_noise_vectors(
        swath=swath,
        azimuth_indexes=azimuth_indexes,
        azimuth_noise_vectors=azimuth_noise_vectors,
        range_noise_vectors=range_noise_vectors,
        is_grd=is_grd,
    )

    noise_vectors = noise_vectors * scaling_conversion**2
    power = np.abs(target_area) ** 2

    scale = np.zeros_like(power)
    valid = (power > 0) & np.isfinite(power) & np.isfinite(noise_vectors)

    scale[valid] = np.sqrt(np.maximum(power[valid] - noise_vectors[valid], 0.0) / power[valid])

    target_area = target_area * scale

    return target_area
