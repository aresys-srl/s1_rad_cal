# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for elevation antenna pattern gain correction computation"""

from pathlib import Path
from types import SimpleNamespace

import numpy as np

import rad_cal.corrections.ap_gain as eap_gain
from rad_cal.corrections.ap_gain import (
    _compute_antenna_pattern_gain_from_metadata,
    _get_elevation_antenna_pattern_from_aux_cal,
)


def create_aux_cal(path: Path):
    path.write_text(
        """
<root>
  <calibrationParams>
    <swath>IW1</swath>
    <polarisation>VV</polarisation>
    <elevationAntennaPattern>
      <values>1 2 3 4 5 6</values>
      <elevationAngleIncrement>0.5</elevationAngleIncrement>
    </elevationAntennaPattern>
  </calibrationParams>
</root>
"""
    )


def test_get_elevation_antenna_pattern_from_aux_cal(tmp_path):
    xml = tmp_path / "aux_cal.xml"
    create_aux_cal(xml)

    eap, angles = _get_elevation_antenna_pattern_from_aux_cal(
        xml,
        swath="IW1",
        polarization="VV",
        roll=1.0,
    )

    np.testing.assert_array_equal(
        eap,
        np.array([1 + 2j, 3 + 4j, 5 + 6j]),
    )

    np.testing.assert_allclose(
        angles,
        np.array([-0.5, 0.0, 0.5]) + 1.0,
    )


def test_compute_antenna_pattern_gain_from_metadata():

    metadata = SimpleNamespace(
        antenna_pattern={
            "IW1": SimpleNamespace(
                time_axis=np.array([10, 20]),
                elevation_pattern_array=np.array(
                    [
                        [1, 2, 3],
                        [4, 5, 6],
                    ]
                ),
                elevation_angle_array=np.array(
                    [
                        [0, 1, 2],
                        [0, 1, 2],
                    ]
                ),
            )
        }
    )

    result = _compute_antenna_pattern_gain_from_metadata(
        channel_metadata=metadata,
        swath="IW1",
        az_time=15,
        look_angles_axis=np.array([0.5, 1.5]),
    )

    np.testing.assert_allclose(result, [1.5, 2.5])


def test_compute_eap_gain_correction(monkeypatch):

    # Mock DEM loading
    monkeypatch.setattr(
        eap_gain,
        "load_dem_from_sar_times",
        lambda **kwargs: SimpleNamespace(
            values=np.zeros((2, 2)),
            lat=SimpleNamespace(values=np.array([0, 1])),
            lon=SimpleNamespace(values=np.array([0, 1])),
        ),
    )

    # Mock terrain corrected look angles
    monkeypatch.setattr(
        eap_gain,
        "compute_terrain_corrected_look_angles",
        lambda **kwargs: np.array([0, 1, 2]),
    )

    # Mock look angle computation
    monkeypatch.setattr(
        eap_gain,
        "compute_look_angles",
        lambda **kwargs: np.array([0, 1, 2]),
    )

    # Mock original EAP from metadata
    monkeypatch.setattr(
        eap_gain,
        "_compute_antenna_pattern_gain_from_metadata",
        lambda **kwargs: np.array([2, 2, 2]),
    )

    # Mock roll correction
    monkeypatch.setattr(
        eap_gain,
        "apply_roll_correction",
        lambda **kwargs: 0.0,
    )

    # Mock AUX_CAL reader
    monkeypatch.setattr(
        eap_gain,
        "_get_elevation_antenna_pattern_from_aux_cal",
        lambda **kwargs: (
            np.array([1, 1, 1]),
            np.array([0, 1, 2]),
        ),
    )

    # Minimal fake metadata object
    channel_metadata = SimpleNamespace(
        raster_info=SimpleNamespace(
            lines=SimpleNamespace(axis=np.arange(4)),
            samples=SimpleNamespace(axis=np.arange(3)),
        ),
        dataset_info=SimpleNamespace(
            side_looking="RIGHT",
        ),
        orbit="fake_orbit",
        general_info=SimpleNamespace(
            mission_id="S1A",
        ),
        antenna_pattern={
            "IW1": SimpleNamespace(
                time_axis=np.array([0]),
                roll=np.array([0]),
            )
        },
    )

    result = eap_gain.compute_eap_gain_correction(
        channel_metadata=channel_metadata,
        swath="IW1",
        polarization="VV",
        aux_cal_xml_path="dummy.xml",
        azimuth_times=np.linspace(0, 1, 4),
        range_times=np.linspace(0.0004, 0.0006, 4),
        dem=Path("path/to/dem"),
    )

    expected = np.sqrt(2) * np.ones(3)

    np.testing.assert_allclose(result, expected)
