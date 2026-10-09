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
    target_area: npt.NDArray[np.complex64] | npt.NDArray[np.floating],
    swath: str,
    azimuth_indexes: tuple[int, int],
    range_indexes: tuple[int, int],
    azimuth_noise_vectors: list[S1AzimuthNoiseVector] | None,
    range_noise_vectors: list[S1RangeNoiseVector],
    scaling_conversion: float,
    is_grd: bool,
) -> npt.NDArray[np.complex64]:
    """Apply thermal denoising vectors to ``target_area``

    Parameters
    ----------
    target_area : npt.NDArray[np.complex64] | npt.NDArray[np.floating]
        target raster area to which denoising is applied
    swath : str
        swath name
    azimuth_indexes : tuple[int, int]
        indexes of the first and last azimuth line of the current block
    range_indexes : tuple[int, int]
            indexes of the first and last range samples of the current block
    azimuth_noise_vectors : list[S1AzimuthNoiseVector] | None
        list of S1 azimuth noise vectors
    range_noise_vectors : list[S1RangeNoiseVector]
        list of S1 range noise vectors
    scaling_conversion : float
        radiometric data scaling factor
    is_grd : bool
        boolean to flag GRD product

    Returns
    -------
    npt.NDArray[np.complex64]
        denoised target area
    """
    if is_grd:
        noise_vectors = []

        for idx in range(azimuth_indexes[0], azimuth_indexes[1]):
            noise_vectors.append(
                get_noise_vectors(
                    swath=swath,
                    azimuth_indexes=idx,
                    azimuth_noise_vectors=azimuth_noise_vectors,
                    range_noise_vectors=range_noise_vectors,
                    is_grd=is_grd,
                )
            )
        max_len = max(len(v) for v in noise_vectors)
        noise_array = np.full((len(noise_vectors), max_len), np.nan)
        for idx, noise_vector in enumerate(noise_vectors):
            noise_array[idx, : len(noise_vector)] = noise_vector
        noise_array = noise_array[:, 0 : (range_indexes[1] - range_indexes[0])]
    else:
        noise_array = get_noise_vectors(
            swath=swath,
            azimuth_indexes=azimuth_indexes,
            azimuth_noise_vectors=azimuth_noise_vectors,
            range_noise_vectors=range_noise_vectors,
            is_grd=is_grd,
        )
    noise_array = noise_array * scaling_conversion**2
    power = np.abs(target_area) ** 2

    if is_grd:
        return np.sqrt(np.maximum(power - noise_array, 0.0))

    scale = np.zeros_like(power)
    valid = (power > 0) & np.isfinite(power) & np.isfinite(noise_array)
    scale[valid] = np.sqrt(np.maximum(power[valid] - noise_array[valid], 0.0) / power[valid])
    target_area = target_area * scale
    return target_area
