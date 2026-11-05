# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for atmospheric attenuation computation"""

from unittest.mock import Mock

import numpy as np
import pytest
import xarray as xr

from s1_rad_cal.corrections.atmospheric_attenuation import compute_atmospheric_attenuation


@pytest.fixture
def weather():
    lat = np.array([45.0, 46.0])
    lon = np.array([8.0, 9.0])

    shape = (2, 2)

    return xr.Dataset(
        data_vars={
            "rho": (("latitude", "longitude"), np.full(shape, 10.0)),
            "P": (("latitude", "longitude"), np.full(shape, 1013.0)),
            "T": (("latitude", "longitude"), np.full(shape, 290.0)),
        },
        coords={
            "latitude": lat,
            "longitude": lon,
        },
    )


@pytest.fixture
def channel_metadata():
    metadata = Mock()

    metadata.orbit = Mock()

    metadata.dataset_info = Mock()
    metadata.dataset_info.fc_hz = 5.405e9
    metadata.dataset_info.side_looking = "RIGHT"

    return metadata


def test_output_shape(
    monkeypatch,
    channel_metadata,
    weather,
):
    azimuth_times = np.arange(5)
    range_times = np.arange(6)

    monkeypatch.setattr("s1_rad_cal.corrections.atmospheric_attenuation.llh2xyz", lambda coordinates: np.zeros((4, 3)))

    monkeypatch.setattr(
        "s1_rad_cal.corrections.atmospheric_attenuation.inverse_geocoding_monostatic",
        lambda **kwargs: (
            np.array([0, 1, 2, 3]),
            np.array([10, 11, 12, 13]),
        ),
    )

    monkeypatch.setattr(
        "s1_rad_cal.corrections.atmospheric_attenuation.compute_incidence_angles",
        lambda **kwargs: np.full(4, 35.0),
    )

    attenuation_mock = Mock()
    attenuation_mock.value = np.arange(4).reshape(2, 2)

    monkeypatch.setattr(
        "s1_rad_cal.corrections.atmospheric_attenuation.gaseous_attenuation_slant_path",
        lambda **kwargs: attenuation_mock,
    )

    monkeypatch.setattr(
        "s1_rad_cal.corrections.atmospheric_attenuation.LinearNDInterpolator",
        lambda *args, **kwargs: lambda az, rg: np.ones_like(az, dtype=float),
    )

    result = compute_atmospheric_attenuation(
        channel_metadata,
        azimuth_times,
        range_times,
        weather,
        mode="exact",
    )

    assert result.shape == (5, 6)
