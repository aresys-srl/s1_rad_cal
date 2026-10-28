# SPDX-FileCopyrightText: Aresys S.r.l. <info@aresys.it>
# SPDX-License-Identifier: MIT

"""Unit tests for radiometric conversion"""

import numpy as np
import pytest
from perseo_quality.core.generic_dataclasses import SARRadiometricQuantity

import s1_rad_cal.corrections.radiometric_conversion as radiometric_conversion


class TestComputeIncidenceAngles:
    def test_without_dem(self, monkeypatch):
        """Incidence angles are computed at the central azimuth time and broadcast."""
        range_times = np.array([1.0, 2.0, 3.0])
        azimuth_times = np.array([10.0, 20.0, 30.0, 40.0])

        expected_angles = np.array([0.1, 0.2, 0.3])

        class FakeAntennaPattern:
            time_axis = np.array([10.0, 20.0, 30.0])
            terrain_height = np.array([100.0, 200.0, 300.0])

        class FakeDatasetInfo:
            side_looking = "right"

        class FakeMetadata:
            orbit = "fake-orbit"
            antenna_pattern = {"IW": FakeAntennaPattern()}
            dataset_info = FakeDatasetInfo()

        calls = {}

        def fake_compute_incidence_angles(
            trajectory,
            azimuth_time,
            range_times,
            look_direction,
            geodetic_altitude,
        ):
            calls["trajectory"] = trajectory
            calls["azimuth_time"] = azimuth_time
            calls["range_times"] = range_times
            calls["look_direction"] = look_direction
            calls["geodetic_altitude"] = geodetic_altitude

            return expected_angles

        monkeypatch.setattr(
            radiometric_conversion,
            "compute_incidence_angles",
            fake_compute_incidence_angles,
        )

        result = radiometric_conversion._compute_incidence_angles(
            channel_metadata=FakeMetadata(),
            swath="IW",
            range_times=range_times,
            azimuth_times=azimuth_times,
            dem=None,
        )

        # Central azimuth time is 30.0 for four samples.
        assert calls["azimuth_time"] == 30.0
        assert calls["trajectory"] == "fake-orbit"
        assert calls["range_times"] is range_times
        assert calls["look_direction"] == "right"

        # 30.0 corresponds to terrain height 300.0.
        assert calls["geodetic_altitude"] == 300.0

        expected = np.broadcast_to(
            expected_angles,
            (len(azimuth_times), len(range_times)),
        )

        np.testing.assert_array_equal(result, expected)

    def test_with_dem(self, monkeypatch):
        """DEM-based incidence angles use the DEM loaded from SAR times."""
        range_times = np.array([1.0, 2.0, 3.0])
        azimuth_times = np.array([10.0, 20.0])

        class FakeDatasetInfo:
            side_looking = "left"

        class FakeMetadata:
            orbit = "fake-orbit"
            dataset_info = FakeDatasetInfo()

        class FakeDem:
            values = np.array([[100.0, 101.0], [102.0, 103.0]])
            lat = type("Axis", (), {"values": np.array([45.0, 46.0])})()
            lon = type("Axis", (), {"values": np.array([8.0, 9.0])})()

        expected = np.array(
            [
                [0.5, 0.6, 0.7],
                [0.8, 0.9, 1.0],
            ]
        )

        load_calls = {}
        incidence_calls = {}

        def fake_load_dem_from_sar_times(
            dem,
            trajectory,
            range_times,
            azimuth_times,
            look_direction,
        ):
            load_calls["dem"] = dem
            load_calls["trajectory"] = trajectory
            load_calls["range_times"] = range_times
            load_calls["azimuth_times"] = azimuth_times
            load_calls["look_direction"] = look_direction

            return FakeDem()

        def fake_compute_terrain_corrected_incidence_angles(
            dem_values,
            dem_lat_axis,
            dem_lon_axis,
            trajectory,
            range_times,
            azimuth_times,
        ):
            incidence_calls["dem_values"] = dem_values
            incidence_calls["dem_lat_axis"] = dem_lat_axis
            incidence_calls["dem_lon_axis"] = dem_lon_axis
            incidence_calls["trajectory"] = trajectory
            incidence_calls["range_times"] = range_times
            incidence_calls["azimuth_times"] = azimuth_times

            return expected

        monkeypatch.setattr(
            radiometric_conversion,
            "load_dem_from_sar_times",
            fake_load_dem_from_sar_times,
        )
        monkeypatch.setattr(
            radiometric_conversion,
            "compute_terrain_corrected_incidence_angles",
            fake_compute_terrain_corrected_incidence_angles,
        )

        dem_path = "/tmp/fake-dem"

        result = radiometric_conversion._compute_incidence_angles(
            channel_metadata=FakeMetadata(),
            swath="IW",
            range_times=range_times,
            azimuth_times=azimuth_times,
            dem=dem_path,
        )

        assert load_calls["dem"] == dem_path
        assert load_calls["trajectory"] == "fake-orbit"
        assert load_calls["range_times"] is range_times
        assert load_calls["azimuth_times"] is azimuth_times
        assert load_calls["look_direction"] == "left"

        np.testing.assert_array_equal(
            incidence_calls["dem_values"],
            FakeDem.values,
        )
        np.testing.assert_array_equal(
            incidence_calls["dem_lat_axis"],
            FakeDem.lat.values,
        )
        np.testing.assert_array_equal(
            incidence_calls["dem_lon_axis"],
            FakeDem.lon.values,
        )

        assert incidence_calls["trajectory"] == "fake-orbit"

        np.testing.assert_array_equal(
            incidence_calls["range_times"],
            range_times,
        )
        np.testing.assert_array_equal(
            incidence_calls["azimuth_times"],
            azimuth_times,
        )

        np.testing.assert_array_equal(result, expected)


class TestRadiometricQuantityConversion:
    @pytest.fixture
    def metadata(self):
        """
        Minimal metadata object.

        The public function only needs raster_info.lines.axis.samples.axis
        to determine the requested block's azimuth/range times.
        """

        class Axis:
            def __init__(self, values):
                self.axis = np.asarray(values)

        class RasterInfo:
            lines = Axis([0.0, 1.0, 2.0, 3.0, 4.0])
            samples = Axis([10.0, 20.0, 30.0])

        class Metadata:
            raster_info = RasterInfo()

        return Metadata()

    def test_beta_nought_returns_input_unchanged(self, metadata):
        """BETA_NOUGHT should not perform any conversion."""
        target_area = np.array(
            [[1.0, 2.0], [3.0, 4.0]],
            dtype=float,
        )

        result = radiometric_conversion.radiometric_quantity_conversion(
            target_area=target_area,
            channel_metadata=metadata,
            swath="IW",
            azimuth_times=np.linspace(0, 1, target_area.shape[0]),
            range_times=np.linspace(0, 1, target_area.shape[1]),
            output_quantity=SARRadiometricQuantity.BETA_NOUGHT,
        )

        # The implementation returns target_area directly.
        assert result is target_area

    def test_sigma_nought_conversion(self, metadata, monkeypatch):
        """SIGMA0 = BETA0 * sqrt(sin(incidence_angle))."""
        target_area = np.array(
            [[2.0, 4.0], [6.0, 8.0]],
            dtype=float,
        )

        incidence_angles = np.array(
            [
                [np.pi / 6, np.pi / 4],
                [np.pi / 3, np.pi / 2],
            ]
        )

        captured = {}

        def fake_compute_incidence_angles(
            channel_metadata,
            swath,
            range_times,
            azimuth_times,
            dem,
        ):
            captured["range_times"] = range_times
            captured["azimuth_times"] = azimuth_times
            captured["dem"] = dem
            return incidence_angles

        monkeypatch.setattr(
            radiometric_conversion,
            "_compute_incidence_angles",
            fake_compute_incidence_angles,
        )

        # Blocks: [2, 2, 1], block 1 starts at line 2 and contains
        # lines 2 and 3.
        result = radiometric_conversion.radiometric_quantity_conversion(
            target_area=target_area,
            channel_metadata=metadata,
            swath="IW",
            azimuth_times=np.array([2.0, 3.0]),
            range_times=np.array([10.0, 20.0, 30.0]),
            output_quantity=SARRadiometricQuantity.SIGMA_NOUGHT,
        )

        expected = target_area * np.sqrt(np.sin(incidence_angles))

        np.testing.assert_allclose(result, expected)

        np.testing.assert_array_equal(
            captured["range_times"],
            np.array([10.0, 20.0, 30.0]),
        )
        np.testing.assert_array_equal(
            captured["azimuth_times"],
            np.array([2.0, 3.0]),
        )
        assert captured["dem"] is None

    def test_gamma_nought_conversion(self, metadata, monkeypatch):
        """GAMMA0 = BETA0 * sqrt(tan(incidence_angle))."""
        target_area = np.array(
            [[2.0, 4.0], [6.0, 8.0]],
            dtype=float,
        )

        incidence_angles = np.array(
            [
                [np.pi / 6, np.pi / 4],
                [np.pi / 3, np.pi / 4],
            ]
        )

        monkeypatch.setattr(
            radiometric_conversion,
            "_compute_incidence_angles",
            lambda **kwargs: incidence_angles,
        )

        result = radiometric_conversion.radiometric_quantity_conversion(
            target_area=target_area,
            channel_metadata=metadata,
            swath="IW",
            azimuth_times=np.linspace(0, 1, target_area.shape[0]),
            range_times=np.linspace(0, 1, target_area.shape[1]),
            output_quantity=SARRadiometricQuantity.GAMMA_NOUGHT,
        )

        expected = target_area * np.sqrt(np.tan(incidence_angles))

        np.testing.assert_allclose(result, expected)

    def test_dem_is_forwarded(self, metadata, monkeypatch):
        """The supplied DEM is forwarded to incidence-angle computation."""
        target_area = np.ones((2, 3), dtype=float)
        incidence_angles = np.full((2, 3), np.pi / 4)

        captured = {}

        def fake_compute_incidence_angles(**kwargs):
            captured.update(kwargs)
            return incidence_angles

        monkeypatch.setattr(
            radiometric_conversion,
            "_compute_incidence_angles",
            fake_compute_incidence_angles,
        )

        dem = "/path/to/dem"

        radiometric_conversion.radiometric_quantity_conversion(
            target_area=target_area,
            channel_metadata=metadata,
            swath="IW",
            azimuth_times=np.linspace(0, 1, target_area.shape[0]),
            range_times=np.linspace(0, 1, target_area.shape[1]),
            output_quantity=SARRadiometricQuantity.SIGMA_NOUGHT,
            dem=dem,
        )

        assert captured["dem"] == dem

    def test_unsupported_quantity_raises(self, metadata, monkeypatch):
        """Unsupported radiometric quantities should raise ValueError."""
        target_area = np.ones((2, 3), dtype=float)

        monkeypatch.setattr(
            radiometric_conversion,
            "_compute_incidence_angles",
            lambda **kwargs: np.full((2, 3), np.pi / 4),
        )

        class FakeQuantity:
            name = "UNSUPPORTED"

        with pytest.raises(ValueError, match="Unsupported output quantity UNSUPPORTED provided"):
            radiometric_conversion.radiometric_quantity_conversion(
                target_area=target_area,
                channel_metadata=metadata,
                swath="IW",
                azimuth_times=np.linspace(0, 1, target_area.shape[0]),
                range_times=np.linspace(0, 1, target_area.shape[1]),
                output_quantity=FakeQuantity(),
            )
